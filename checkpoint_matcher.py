"""Forward-only fuzzy matching for story checkpoints."""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
from pathlib import Path
import re
from typing import Any
import unicodedata

try:
    from rapidfuzz import fuzz

    MATCHING_ENGINE = "rapidfuzz"
except ImportError:  # Allows the sample demo to run before dependencies are installed.
    from difflib import SequenceMatcher

    MATCHING_ENGINE = "difflib fallback"

    class _FallbackFuzz:
        @staticmethod
        def ratio(left: str, right: str) -> float:
            return SequenceMatcher(None, left, right).ratio() * 100.0

    fuzz = _FallbackFuzz()


def normalize_text(text: str) -> str:
    """Normalize ASR and book text before comparing them."""
    text = unicodedata.normalize("NFKC", text).lower()
    text = re.sub(r"[^\w\s']", " ", text, flags=re.UNICODE)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def best_window_score(transcript: str, anchor: str, min_coverage: float) -> float:
    """Return the best ordered word-window similarity score from 0 to 100."""
    transcript_words = normalize_text(transcript).split()
    anchor_words = normalize_text(anchor).split()
    if not transcript_words or not anchor_words:
        return 0.0

    minimum_words = max(3, math.ceil(len(anchor_words) * min_coverage))
    if len(transcript_words) < minimum_words:
        return 0.0

    # Only recent text is relevant. This also prevents an earlier checkpoint
    # from dominating a long rolling transcript.
    transcript_words = transcript_words[-max(80, len(anchor_words) * 3) :]
    shortest = minimum_words
    longest = min(len(transcript_words), len(anchor_words) + 2)
    expected = " ".join(anchor_words)
    best_score = 0.0

    for window_size in range(shortest, longest + 1):
        for start in range(0, len(transcript_words) - window_size + 1):
            candidate = " ".join(transcript_words[start : start + window_size])
            best_score = max(best_score, float(fuzz.ratio(expected, candidate)))

    return best_score


@dataclass(frozen=True)
class MatchUpdate:
    checkpoint_id: str | None
    score: float
    confirmations: int
    confirmations_required: int
    triggered: bool
    completed: bool
    effect: dict[str, Any] | None = None
    checkpoint_position: int | None = None


class CheckpointMatcher:
    """Match only the next checkpoint and trigger every checkpoint once."""

    mode = "fuzzy checkpoint matching"

    def __init__(
        self,
        manifest: dict[str, Any],
        threshold: float | None = None,
        stability: int | None = None,
    ) -> None:
        checkpoints = manifest.get("checkpoints")
        if not isinstance(checkpoints, list) or not checkpoints:
            raise ValueError("Manifest must contain a non-empty 'checkpoints' list.")

        self.book_id = str(manifest.get("book_id", "unknown-book"))
        self.title = str(manifest.get("title", self.book_id))
        self.default_threshold = float(
            threshold if threshold is not None else manifest.get("threshold", 82.0)
        )
        self.default_stability = int(
            stability if stability is not None else manifest.get("stability", 2)
        )
        self.default_min_coverage = float(manifest.get("min_coverage", 0.8))

        if not 0.0 <= self.default_threshold <= 100.0:
            raise ValueError("Checkpoint threshold must be between 0 and 100.")
        if self.default_stability < 1:
            raise ValueError("Checkpoint stability must be at least 1.")
        if not 0.0 < self.default_min_coverage <= 1.0:
            raise ValueError("Minimum coverage must be greater than 0 and at most 1.")

        positions = set()
        checkpoint_ids = set()
        for checkpoint in checkpoints:
            if not isinstance(checkpoint, dict):
                raise ValueError("Every checkpoint must be an object.")
            checkpoint_id = checkpoint.get("id")
            text = checkpoint.get("checkpoint_text")
            if (
                isinstance(checkpoint_id, bool)
                or not isinstance(checkpoint_id, (str, int))
                or not str(checkpoint_id).strip()
                or not isinstance(text, str)
                or not normalize_text(text)
            ):
                raise ValueError(
                    "Every checkpoint requires an 'id' and non-empty 'checkpoint_text'."
                )
            if str(checkpoint_id) in checkpoint_ids:
                raise ValueError("Checkpoint IDs must be unique within a book.")
            checkpoint_ids.add(str(checkpoint_id))

            if "book_id" not in checkpoint or str(checkpoint["book_id"]) != self.book_id:
                raise ValueError("Every checkpoint's 'book_id' must match the manifest.")
            position = checkpoint.get("checkpoint_position")
            if type(position) is not int or position < 1:
                raise ValueError("Checkpoint positions must be positive integers.")
            if position in positions:
                raise ValueError("Checkpoint positions must be unique within a book.")
            positions.add(position)

            effect = checkpoint.get("effect")
            if not isinstance(effect, dict):
                raise ValueError("Every checkpoint requires an 'effect' object.")
            for asset in ("visual", "sound"):
                if effect.get(asset) is not None and not isinstance(effect[asset], str):
                    raise ValueError(f"Effect '{asset}' must be a string or null.")
            for delay in ("visual_delay", "sound_delay"):
                value = effect.get(delay, 0)
                if type(value) is not int or value < 0:
                    raise ValueError(f"Effect '{delay}' must be a non-negative integer in milliseconds.")

        self.checkpoints = sorted(checkpoints, key=lambda item: item["checkpoint_position"])

        self.current_index = 0
        self.confirmations = 0

    @classmethod
    def from_file(
        cls,
        path: str | Path,
        threshold: float | None = None,
        stability: int | None = None,
    ) -> "CheckpointMatcher":
        manifest_path = Path(path)
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except FileNotFoundError as error:
            raise ValueError(f"Checkpoint file not found: {manifest_path}") from error
        except json.JSONDecodeError as error:
            raise ValueError(
                f"Invalid JSON in checkpoint file {manifest_path}: {error}"
            ) from error
        return cls(manifest, threshold=threshold, stability=stability)

    @property
    def completed(self) -> bool:
        return self.current_index >= len(self.checkpoints)

    @property
    def current_checkpoint(self) -> dict[str, Any] | None:
        if self.completed:
            return None
        return self.checkpoints[self.current_index]

    def process(self, transcript: str) -> MatchUpdate:
        if self.completed:
            return MatchUpdate(None, 0.0, 0, 0, False, True)

        checkpoint = self.checkpoints[self.current_index]
        threshold = float(checkpoint.get("threshold", self.default_threshold))
        stability = int(checkpoint.get("stability", self.default_stability))
        min_coverage = float(
            checkpoint.get("min_coverage", self.default_min_coverage)
        )
        score = best_window_score(transcript, checkpoint["checkpoint_text"], min_coverage)

        if score >= threshold:
            self.confirmations += 1
        else:
            self.confirmations = 0

        triggered = self.confirmations >= stability
        effect = None
        checkpoint_id = str(checkpoint["id"])
        confirmations = self.confirmations

        if triggered:
            effect = checkpoint.get("effect", {})
            self.current_index += 1
            self.confirmations = 0

        return MatchUpdate(
            checkpoint_id=checkpoint_id,
            score=score,
            confirmations=confirmations,
            confirmations_required=stability,
            triggered=triggered,
            completed=self.completed,
            effect=effect,
            checkpoint_position=checkpoint["checkpoint_position"],
        )
