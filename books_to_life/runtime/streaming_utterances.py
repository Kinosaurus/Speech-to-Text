"""End decoder utterances at digital silence without changing the audio clock.

Only exact zero PCM is silence here. No amplitude/VAD threshold is introduced:
noise and soft speech pass through unchanged. A full encoder right-context of
zero samples closes an utterance; later speech starts a fresh decoder. The
model's existing finish operation supplies its normal encoder context only.
"""
import numpy as np


class SilenceBoundedSession:
    def __init__(self, factory, right_context_samples):
        if right_context_samples <= 0:
            raise ValueError('Right context must be positive.')
        self.factory = factory
        self.silence_samples = right_context_samples
        self.core = factory()
        self.position = 0
        self.start = 0
        self.zeros = 0
        self.committed = []
        self.hotwords = None
        self.finalized = False
        self.final_segments = None

    def set_hints(self, hotwords):
        self.hotwords = hotwords
        if self.core is not None:
            self.core.set_hints(hotwords)

    def _segments(self, text=None, completed=False):
        result = [dict(s) for s in self.committed]
        if text is not None:
            result.append(dict(start=self.start/16000, end=self.position/16000,
                               text=text, completed=completed))
        return result

    def _feed_core(self, audio, updates):
        self.position += len(audio)
        for text in self.core.feed(audio):
            updates.append(self._segments(text))

    def _commit(self, updates):
        text = self.core.finish()
        self.core.close()
        self.core = None
        if text.strip():
            self.committed.append(dict(start=self.start/16000, end=self.position/16000,
                                       text=text, completed=True))
            updates.append(self._segments())

    def feed(self, audio):
        if self.finalized:
            raise ValueError('Audio stream has already ended.')
        updates = []
        # Group runs, not packets. Results cannot depend on network packet size.
        nonzero = audio != 0
        boundaries = np.flatnonzero(nonzero[1:] != nonzero[:-1])+1
        for part in np.split(audio, boundaries):
            if not len(part):
                continue
            if part[0] != 0:
                if self.core is None:
                    self.core = self.factory()
                    self.core.set_hints(self.hotwords)
                    self.start = self.position
                self.zeros = 0
                self._feed_core(part, updates)
            elif self.core is None:
                self.position += len(part)
            else:
                count = min(len(part), self.silence_samples-self.zeros)
                self._feed_core(part[:count], updates)
                self.zeros += count
                if self.zeros == self.silence_samples:
                    self._commit(updates)
                self.position += len(part)-count
        return updates

    def finish(self):
        if not self.finalized:
            updates = []
            if self.core is not None:
                self._commit(updates)
            self.final_segments = self._segments()
            if not self.final_segments:
                self.final_segments = [dict(start=0, end=self.position/16000,
                                            text='', completed=True)]
            else:
                # Retain the original stream duration, including trailing quiet.
                self.final_segments[-1]['end'] = self.position/16000
            self.finalized = True
        return [dict(s) for s in self.final_segments]

    def close(self):
        if self.core is not None:
            self.core.close()
            self.core = None
