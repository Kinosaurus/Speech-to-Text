"""Experimental local split-token candidates; no recording-specific aliases."""
import re
from alignment_matcher import AlignmentSpan
from checkpoint_matcher import fuzz
from evidence_matcher import EvidenceAlignmentMatcher


def split_similarity(left, right, target):
    joined = left + right
    if len(target) < 5 or len(joined) < 5:
        return 0.0
    if joined == target:
        return .9
    # Conservative spelling/sound proxy: identical consonant ending, at most
    # one different initial consonant. This is not a pronunciation model.
    a = re.sub('[aeiouy]', '', joined)
    b = re.sub('[aeiouy]', '', target)
    if len(a) >= 3 and len(a) == len(b) and a[1:] == b[1:] and fuzz.ratio(joined, target) >= 50:
        return .7
    return 0.0


class SplitEvidenceMatcher(EvidenceAlignmentMatcher):
    mode = 'experimental contextual split-word alignment'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._split_candidates = set()
        self._last_split = None
        self._split_clock = -1

    def _alignment_candidates(self, low, high):
        candidates = super()._alignment_candidates(low, high)
        self._split_candidates = set()
        # Only assist an already acquired reader near the NEXT scene boundary.
        if not self.triggered_checkpoint_ids or self.completed:
            return candidates
        context = set(self._buffer[-16:])
        if context & {'not', 'never', 'no', 'dont', 'say', 'repeat', 'said', 'asked'}:
            return candidates
        start, end = self.checkpoint_ranges[self.current_index]
        if end - self.tracked_word_position > 40:
            return candidates
        # At least two exact words either side of ONE split compound. The
        # candidate must end at the current utterance tail; no stale matches.
        for stop in range(max(start + 5, end - 1), end + 1):
            for begin in range(start, stop - 4):
                ref = self.words[begin:stop]
                spoken = self._buffer[-(len(ref) + 1):]
                if len(spoken) != len(ref) + 1:
                    continue
                for i in range(2, len(ref) - 2):
                    if spoken[:i] != ref[:i] or spoken[i+2:] != ref[i+1:]:
                        continue
                    credit = split_similarity(spoken[i], spoken[i+1], ref[i])
                    if not credit or len(set(ref[:i]+ref[i+1:])) < 3:
                        continue
                    span = AlignmentSpan(begin, stop, 100*(len(ref)-1+credit)/len(ref),len(ref),len(ref))
                    candidates.append(span)
                    self._split_candidates.add(span)
        return candidates

    def _confirm_candidate(self, scene, best):
        previous = self._last_split
        transfer = (best in self._split_candidates and previous is not None
                    and previous.start == best.start and best.end > previous.end
                    and self._fresh_updates - self._split_clock <= 3
                    and self._audio_time - self._split_time <= 6
                    and (not self._segments or self._audio_time > self._split_time))
        if transfer and scene != self._pending_scene:
            # Supporting prefix ended just before this boundary. Carry that
            # evidence across the boundary, without requiring a following word.
            self._pending_scene = scene
            self.confirmations = 1
        count = super()._confirm_candidate(scene, best)
        if best in self._split_candidates:
            self._last_split = best
            self._split_clock = self._fresh_updates
            self._split_time = self._audio_time
        else:
            self._last_split = None
        return count

    def _reject_candidate(self, ambiguous):
        super()._reject_candidate(ambiguous)
        if ambiguous:
            self._last_split = None
