"""Experimental alignment with bounded, independent evidence accumulation.

Uses the baseline's candidates, coverage, ambiguity and scene selection. A held
candidate may use the normal score threshold for further support in the SAME
scene. It cannot make an otherwise unsupported scene trigger on a timer.
"""
from alignment_matcher import AlignmentMatcher


class EvidenceAlignmentMatcher(AlignmentMatcher):
    mode = "word-sequence alignment with evidence accumulation (experimental)"

    def __init__(self, manifest, threshold=None, stability=None):
        super().__init__(manifest, threshold, stability)
        self._evidence_end = -1
        self._evidence_time = -1.0
        self._audio_time = 0.0
        self._fresh_updates = 0
        self._evidence_update = 0
        self._evidence_text = ()
        self._evidence_completed = False

    def _clear_evidence(self):
        self.confirmations = 0
        self._pending_scene = None
        self._evidence_end = -1

    def _ingest(self, transcript, segments):
        fresh = super()._ingest(transcript, segments)
        if fresh:
            self._fresh_updates += 1
            if segments:
                self._audio_time = max(self._audio_time, max(float(s['end']) for s in segments))
            if (self._audio_time - self._evidence_time > 12
                    or self._fresh_updates - self._evidence_update > 12):
                self._clear_evidence()
        return fresh

    def _threshold(self, scene, recovering):
        # Retain a strong acquisition through noisy revisions, but never lower
        # coverage or permit a different scene to use this exception.
        held = self._pending_scene == scene and self.confirmations > 0
        return super()._threshold(scene, recovering and not held)

    def _reject_candidate(self, ambiguous):
        if ambiguous:
            self._clear_evidence()
        # Unmatched updates do not count as support. Bounded expiry in _ingest.

    def _confirm_candidate(self, scene, best):
        if scene != self._pending_scene or self.confirmations == 0:
            self._clear_evidence()
            self._pending_scene = scene
        # Progress is one source of support, not a requirement. A strong
        # same-position match may also survive changed text over newer audio,
        # or a transition to a completed utterance. Identical callbacks and
        # timestamp-only changes never add confirmation.
        text = tuple(self._buffer)
        completed = bool(self._segments and self._segments[-1]["completed"])
        first = self.confirmations == 0
        newer_audio = not self._segments or self._audio_time > self._evidence_time
        progress = best.end > self._evidence_end and newer_audio
        strong = best.score >= max(92, self._threshold(scene, False))
        stable_position = best.end >= self._evidence_end
        revised = text != self._evidence_text and newer_audio
        finalized = completed and not self._evidence_completed
        stable = strong and stable_position and (revised or finalized)
        if first or progress or stable:
            self.confirmations += 1
            self._evidence_end = best.end
            self._evidence_time = self._audio_time
            self._evidence_update = self._fresh_updates
            self._evidence_text = text
            self._evidence_completed = completed
        return self.confirmations
