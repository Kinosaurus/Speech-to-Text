"""Track streamed transcript words against nearby book passages.

This aligns ASR text, not raw audio. Local dynamic programming supports missing,
extra and substituted words; checkpoint ranges select persistent ambience scenes.
"""

from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass
from functools import lru_cache
import math
from typing import Any

from books_to_life.matching.checkpoint_matcher import CheckpointMatcher, MatchUpdate, fuzz, normalize_text


@lru_cache(maxsize=8192)
def _word_similarity(left: str, right: str) -> float:
    return float(fuzz.ratio(left, right)) / 100.0


@dataclass(frozen=True)
class AlignmentSpan:
    start: int
    end: int  # Exclusive, in the normalized book token stream.
    score: float
    matched_words: int
    query_words: int


@dataclass(frozen=True)
class AlignmentUpdate(MatchUpdate):
    tracked_word_position: int = 0
    page: int | None = None
    alignment_start: int | None = None
    alignment_end: int | None = None
    skipped_checkpoint_ids: tuple[str, ...] = ()
    recovering: bool = False
    ambiguous: bool = False
    duplicate: bool = False


def align_words(
    spoken: list[str], reference: list[str], offset: int,
    minimum_words: int, min_coverage: float,
) -> list[AlignmentSpan]:
    """Smith-Waterman word alignment, anchored to the latest spoken word.

    Matching words earn up to 2 points; a substitution costs 1 and a gap costs 2.
    Free local starts allow reacquisition after a skipped passage. Requiring the
    final query row prevents an old phrase elsewhere in the buffer winning alone.
    """
    n, m = len(spoken), len(reference)
    if n < minimum_words or not m:
        return []
    scores = [[0.0] * (m + 1) for _ in range(n + 1)]
    parents = [bytearray(m + 1) for _ in range(n + 1)]
    for i, word in enumerate(spoken, 1):
        row, previous = scores[i], scores[i - 1]
        for j, target in enumerate(reference, 1):
            similarity = 1.0 if word == target else _word_similarity(word, target)
            reward = 2.0 * similarity if similarity >= 0.75 else -1.0
            diagonal = previous[j - 1] + reward
            insertion, deletion = previous[j] - 2.0, row[j - 1] - 2.0
            best = max(0.0, diagonal, insertion, deletion)
            row[j] = best
            if best > 0:
                parents[i][j] = 1 if best == diagonal else (2 if best == insertion else 3)

    # Trace promising endpoints rather than tracing every matrix cell.
    endpoints = sorted(range(1, m + 1), key=lambda j: scores[n][j], reverse=True)
    spans = []
    for end in endpoints[:24]:
        if scores[n][end] < minimum_words:
            continue
        i, j, matches, credit = n, end, 0, 0.0
        last_match = -1
        distinct = set()
        while i and j and scores[i][j] > 0:
            direction = parents[i][j]
            if direction == 1:
                similarity = (1.0 if spoken[i - 1] == reference[j - 1]
                              else _word_similarity(spoken[i - 1], reference[j - 1]))
                if similarity >= 0.75:
                    matches += 1
                    credit += similarity
                    distinct.add(spoken[i - 1])
                    last_match = max(last_match, i - 1)
                i -= 1
                j -= 1
            elif direction == 2:
                i -= 1
            else:
                j -= 1
        query_length, target_length = n - i, end - j
        if (matches < minimum_words or matches < math.ceil(query_length * min_coverage)
                or len(distinct) < 3 or last_match < n - 2):
            continue
        score = 100.0 * credit / max(query_length, target_length)
        spans.append(AlignmentSpan(offset + j, offset + end, score, matches, query_length))
    return spans


class AlignmentMatcher(CheckpointMatcher):
    """Forward scene progress using full passages, with bounded recovery searches."""

    mode = "word-sequence alignment"

    def __init__(self, manifest: dict[str, Any], threshold=None, stability=None):
        super().__init__(manifest, threshold=threshold, stability=stability)
        self.words: list[str] = []
        self.page_ranges: dict[int, tuple[int, int]] = {}
        pages = manifest.get("pages")
        if not isinstance(pages, list) or not pages:
            raise ValueError("Alignment requires a non-empty 'pages' list with 'page' and 'text'.")
        for page in pages:
            if (not isinstance(page, dict) or type(page.get("page")) is not int
                    or page["page"] < 1 or not isinstance(page.get("text"), str)
                    or not normalize_text(page["text"])):
                raise ValueError("Every page needs a positive integer 'page' and non-empty 'text'.")
        for page in sorted(pages, key=lambda item: item["page"]):
            number = page["page"]
            if number in self.page_ranges:
                raise ValueError("Page numbers must be unique.")
            start = len(self.words)
            self.words.extend(normalize_text(page["text"]).split())
            self.page_ranges[number] = (start, len(self.words))

        self.checkpoint_ranges = []
        previous_end = 0
        for checkpoint in self.checkpoints:
            anchor = normalize_text(checkpoint["checkpoint_text"]).split()
            page_number = checkpoint.get("page")
            if page_number is not None and (type(page_number) is not int
                                            or page_number not in self.page_ranges):
                raise ValueError("Checkpoint 'page' must refer to a page in the book.")
            low, high = self.page_ranges.get(page_number, (0, len(self.words)))
            if "word_start" in checkpoint or "word_end" in checkpoint:
                start, end = checkpoint.get("word_start"), checkpoint.get("word_end")
                if (type(start) is not int or type(end) is not int
                        or not low <= start < end <= high
                        or self.words[start:end] != anchor):
                    raise ValueError("Checkpoint word range must contain its exact normalized text.")
            else:
                occurrences = [i for i in range(low, high - len(anchor) + 1)
                               if self.words[i:i + len(anchor)] == anchor]
                if len(occurrences) != 1:
                    raise ValueError(
                        f"Checkpoint '{checkpoint['id']}' needs one occurrence in its page/text; "
                        "provide explicit 'word_start' and 'word_end' for repeated phrases."
                    )
                start, end = occurrences[0], occurrences[0] + len(anchor)
            if start < previous_end:
                raise ValueError("Checkpoint word ranges must follow checkpoint_position without overlap.")
            self.checkpoint_ranges.append((start, end))
            previous_end = end
        self._checkpoint_ends = [end for _, end in self.checkpoint_ranges]
        self._minimum_coverage = min(
            [self.default_min_coverage]
            + [float(item.get("min_coverage", self.default_min_coverage)) for item in self.checkpoints]
        )

        settings = manifest.get("alignment", {})
        if not isinstance(settings, dict):
            raise ValueError("'alignment' must be an object.")
        self.window_words = self._positive_setting(settings, "window_words", 120)
        self.transcript_words = self._positive_setting(settings, "transcript_words", 32)
        self.minimum_words = self._positive_setting(settings, "minimum_words", 5)
        self.backtrack_words = self._positive_setting(settings, "backtrack_words", 32)
        self.recovery_after = self._positive_setting(settings, "recovery_after", 3)
        if self.minimum_words > self.transcript_words:
            raise ValueError("minimum_words cannot exceed transcript_words.")
        if self.minimum_words < 3:
            raise ValueError("minimum_words must be at least 3.")
        self.ambiguity_margin = float(settings.get("ambiguity_margin", 4))
        self.recovery_threshold = float(settings.get("recovery_threshold", 92))
        if not 0 <= self.ambiguity_margin <= 100 or not 0 <= self.recovery_threshold <= 100:
            raise ValueError("Alignment margins and thresholds must be between 0 and 100.")
        # Validate overrides now rather than allowing malformed data in callbacks.
        for checkpoint in self.checkpoints:
            if not 0 <= float(checkpoint.get("threshold", self.default_threshold)) <= 100:
                raise ValueError("Checkpoint threshold must be between 0 and 100.")
            value = checkpoint.get("stability", self.default_stability)
            if type(value) is not int or value < 1:
                raise ValueError("Checkpoint stability must be a positive integer.")
            if not 0 < float(checkpoint.get("min_coverage", self.default_min_coverage)) <= 1:
                raise ValueError("Checkpoint coverage must be greater than 0 and at most 1.")

        self.tracked_word_position = 0
        self.triggered_checkpoint_ids: set[str] = set()
        self.skipped_checkpoint_ids: set[str] = set()
        self._misses = 0
        self._pending_scene: int | None = None
        self._last_text: list[str] = []
        self._buffer: list[str] = []
        self._segments: list[dict[str, Any]] = []
        self._previous_response: dict[float, dict[str, Any]] = {}
        self._last_signature = None

    @staticmethod
    def _positive_setting(settings, key, default):
        value = settings.get(key, default)
        if type(value) is not int or value < 1:
            raise ValueError(f"Alignment '{key}' must be a positive integer.")
        return value

    def _ingest(self, transcript, segments):
        """Replace revised ASR segments; merge text-only snapshots/chunks for demos."""
        incoming = normalize_text(transcript).split()
        if segments:
            valid = []
            for segment in segments:
                try:
                    start, end = float(segment["start"]), float(segment["end"])
                    text = normalize_text(segment["text"])
                except (KeyError, TypeError, ValueError):
                    raise ValueError("Transcript segments require start, end and text.")
                if not math.isfinite(start) or not math.isfinite(end) or start < 0 or end < start:
                    raise ValueError("Transcript segment times must be finite and ordered.")
                valid.append({"start": start, "end": end, "text": text,
                              "completed": bool(segment.get("completed", False))})
            valid.sort(key=lambda segment: segment["start"])
            signature = tuple((s["start"], s["end"], s["text"], s["completed"]) for s in valid)
            known = self._previous_response
            # Removing old segments from a rolling response is not new evidence.
            if signature == self._last_signature or all(known.get(s["start"]) == s for s in valid):
                return False
            self._last_signature = signature
            self._previous_response = {s["start"]: s for s in valid}
            # A response's partial segment may replace/split old partial segments.
            first = valid[0]["start"]
            prefix = [s for s in self._segments if s["end"] <= first and s["start"] < first]
            self._segments = prefix + valid
            total = 0
            keep = []
            for segment in reversed(self._segments):
                keep.append(segment)
                total += len(segment["text"].split())
                if total >= self.transcript_words:
                    break
            self._segments = list(reversed(keep))
            self._buffer = " ".join(s["text"] for s in self._segments).split()[-self.transcript_words:]
            return bool(self._buffer)
        signature = tuple(incoming)
        if not incoming or signature == self._last_signature:
            return False
        self._last_signature = signature
        previous = self._last_text
        # Growing/shrinking hypotheses and revisions of the same sentence.
        common = 0
        for left, right in zip(previous, incoming):
            if left != right:
                break
            common += 1
        if previous and (common == min(len(previous), len(incoming)) or common >= 2):
            remove = min(len(previous), len(self._buffer))
            self._buffer = self._buffer[:-remove] + incoming
        else:
            overlap = 0
            for length in range(min(len(self._buffer), len(incoming)), 1, -1):
                if self._buffer[-length:] == incoming[:length]:
                    overlap = length
                    break
            self._buffer.extend(incoming[overlap:])
        self._last_text = incoming
        self._buffer = self._buffer[-self.transcript_words:]
        return True

    def _scene(self, end):
        return bisect_right(self._checkpoint_ends, end) - 1

    def _threshold(self, scene, recovering):
        checkpoint = self.checkpoints[scene] if scene >= 0 else {}
        value = float(checkpoint.get("threshold", self.default_threshold))
        return max(value, self.recovery_threshold) if recovering else value

    def _reject_candidate(self, ambiguous):
        self.confirmations = 0
        self._pending_scene = None

    def _confirm_candidate(self, scene, best):
        self.confirmations = self.confirmations + 1 if scene == self._pending_scene else 1
        self._pending_scene = scene
        return self.confirmations

    def _alignment_candidates(self, low, high):
        candidates = []
        lengths = {len(self._buffer), max(self.minimum_words, len(self._buffer) // 2),
                   self.minimum_words, min(len(self._buffer), self.minimum_words + 3)}
        for length in sorted(lengths, reverse=True):
            candidates.extend(align_words(self._buffer[-length:], self.words[low:high], low,
                                          self.minimum_words, self._minimum_coverage))
        return candidates

    def process(self, transcript: str, segments=None) -> AlignmentUpdate:
        if self.completed:
            return AlignmentUpdate(None, 0, 0, 0, False, True,
                                   tracked_word_position=self.tracked_word_position)
        checkpoint = self.current_checkpoint
        required = checkpoint.get("stability", self.default_stability)
        base = dict(checkpoint_id=str(checkpoint["id"]), checkpoint_position=checkpoint["checkpoint_position"],
                    score=0.0, confirmations=0, confirmations_required=required,
                    triggered=False, completed=False, tracked_word_position=self.tracked_word_position)
        if not self._ingest(transcript, segments):
            return AlignmentUpdate(**{**base, "confirmations": self.confirmations}, duplicate=True,
                                   recovering=self._misses >= self.recovery_after)
        low = max(0, self.tracked_word_position - self.backtrack_words)
        # Every recovery_after failed fresh updates doubles the forward search.
        level = min(self._misses // self.recovery_after, len(self.words).bit_length())
        high = min(len(self.words), self.tracked_word_position + self.window_words * (2 ** level))
        recovering = level > 0
        candidates = self._alignment_candidates(low, high)
        candidates = [span for span in candidates
                      if span.score >= self._threshold(self._scene(span.end), recovering)
                      and span.matched_words >= math.ceil(span.query_words * float(
                          (self.checkpoints[self._scene(span.end)] if self._scene(span.end) >= 0 else {})
                          .get("min_coverage", self.default_min_coverage)))]
        # Check per-checkpoint coverage as well as the default guard.
        best_by_end = {}
        for span in candidates:
            previous = best_by_end.get(span.end)
            if previous is None or (span.score, span.matched_words) > (previous.score, previous.matched_words):
                best_by_end[span.end] = span
        candidates = sorted(best_by_end.values(), key=lambda span: (span.score, span.matched_words), reverse=True)
        best = candidates[0] if candidates else None
        ambiguous = bool(best and any(
            self._scene(other.end) != self._scene(best.end)
            and (other.end <= best.start or best.end <= other.start)
            and best.score - other.score < self.ambiguity_margin for other in candidates[1:]
        ))
        if best is None or ambiguous:
            if len(self._buffer) >= self.minimum_words:
                self._misses += 1
            self._reject_candidate(ambiguous)
            return AlignmentUpdate(**base, recovering=recovering, ambiguous=ambiguous)

        scene = self._scene(best.end)
        selected = self.checkpoints[scene] if scene >= 0 else checkpoint
        required = selected.get("stability", self.default_stability)
        confirmations = self._confirm_candidate(scene, best)
        skipped = ()
        effect = None
        triggered = False
        if confirmations >= required:
            self._misses = 0
            self.tracked_word_position = max(self.tracked_word_position, best.end)
            if scene >= self.current_index:
                skipped = tuple(str(item["id"]) for item in self.checkpoints[self.current_index:scene])
                self.skipped_checkpoint_ids.update(skipped)
                effect = selected["effect"]
                triggered = True
                self.triggered_checkpoint_ids.add(str(selected["id"]))
                self.current_index = scene + 1
                self.confirmations = 0
                self._pending_scene = None
        page = next(number for number, (start, end) in self.page_ranges.items()
                    if start < best.end <= end)
        return AlignmentUpdate(
            checkpoint_id=str(selected["id"]), checkpoint_position=selected["checkpoint_position"],
            score=best.score, confirmations=confirmations, confirmations_required=required,
            triggered=triggered, completed=self.completed, effect=effect,
            tracked_word_position=self.tracked_word_position, page=page,
            alignment_start=best.start, alignment_end=best.end,
            skipped_checkpoint_ids=skipped, recovering=recovering,
        )
