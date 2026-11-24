"""Carry recent, ordered anchor-prefix evidence into its reached endpoint.

The unchanged SplitEvidenceMatcher remains available for paired benchmarks.
Only an accepted candidate ending at the next checkpoint can use this credit;
silence, stale text and a timer cannot trigger a scene.
"""
from books_to_life.matching.split_matcher import SplitEvidenceMatcher


class BoundaryEvidenceMatcher(SplitEvidenceMatcher):
    mode = 'experimental contextual alignment with boundary evidence carry'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._boundary_prefix = None

    def _reject_candidate(self, ambiguous):
        super()._reject_candidate(ambiguous)
        if ambiguous:
            self._boundary_prefix = None

    def _confirm_candidate(self, scene, best):
        prefix = self._boundary_prefix
        target = self.current_index
        start, end = self.checkpoint_ranges[target]
        text = tuple(self._buffer)
        # Do not turn a quoted instruction/negated ending into extra support.
        prompt = set(text[-16:]) & {'not', 'never', 'dont', "don't", 'say', 'repeat'}
        fresh = (prefix is not None and self._fresh_updates > prefix['update']
                 and self._fresh_updates - prefix['update'] <= 12
                 and (not self._segments or 0 < self._audio_time-prefix['time'] <= 12)
                 and text != prefix['text'])
        if (fresh and not prompt and scene == target == prefix['scene']
                and best.end == end and best.start <= prefix['end']-2
                and text[-1] == self.words[end-1]
                and self._pending_scene != scene):
            # One prior independent prefix supports THIS anchor, not the old
            # ambience scene. The accepted endpoint below supplies the next vote.
            self._pending_scene = scene
            self.confirmations = 1
            self._evidence_end = prefix['end']
            self._evidence_time = prefix['time']
            self._evidence_update = prefix['update']
            self._evidence_text = prefix['text']
            self._evidence_completed = False
        count = super()._confirm_candidate(scene, best)
        # Require actual anchor words near the end, not unrelated earlier book
        # progress. Keep one vote, independent of how many callbacks repeat it.
        anchor_prefix = self.words[start:best.end]
        if (not prompt and end-2 <= best.end < end and best.end-start >= 3
                and best.start <= best.end-3
                and len(set(anchor_prefix) & set(text[-16:])) >= 3):
            self._boundary_prefix = dict(scene=target, end=best.end,
                                         time=self._audio_time, update=self._fresh_updates,
                                         text=text)
        elif prefix is not None and (scene >= target or
                self._audio_time-prefix['time'] > 12 or
                self._fresh_updates-prefix['update'] > 12):
            self._boundary_prefix = None
        return count
