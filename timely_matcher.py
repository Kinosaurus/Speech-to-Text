"""Bounded next-anchor recovery without lowering global match requirements."""
from alignment_matcher import align_words
from boundary_matcher import BoundaryEvidenceMatcher
from checkpoint_matcher import fuzz


class TimelyEvidenceMatcher(BoundaryEvidenceMatcher):
    mode = 'experimental contextual alignment with timely anchor recovery'

    def _ingest(self, transcript, segments):
        fresh = super()._ingest(transcript, segments)
        if not fresh or self._ending_supported():
            return fresh
        start,end = self.checkpoint_ranges[self.current_index]
        tail = self._buffer[-12:]
        if set(tail) & {'not','never','dont',"don't",'say','repeat'}:
            return fresh
        # ASR may append fillers/repetitions in the same update as a clean
        # prefix. Recognize a unique exact five-word book run followed by at
        # most two tokens. Save it for a FUTURE callback, never count it twice
        # as prefix and ending from one hypothesis.
        for stop in range(end-1,max(start+4,end-4),-1):
            phrase = self.words[stop-5:stop]
            if stop-5 < start or len(set(phrase)) < 3:
                continue
            if sum(self.words[i:i+5] == phrase for i in range(len(self.words)-4)) != 1:
                continue
            if any(tail[-(5+extra):-extra] == phrase for extra in (1,2)):
                self._boundary_prefix = dict(scene=self.current_index,end=stop,time=self._audio_time,
                                             update=self._fresh_updates,text=tuple(self._buffer))
                break
        return fresh

    def _live_prefix(self, scene):
        prefix = self._boundary_prefix
        return (prefix is not None and scene == self.current_index == prefix['scene']
                and 0 < self._fresh_updates-prefix['update'] <= 12
                and (not self._segments or 0 < self._audio_time-prefix['time'] <= 12)
                and tuple(self._buffer) != prefix['text']
                and not (set(self._buffer[-16:]) & {'not','never','dont',"don't",'say','repeat'}))

    def _ending_supported(self):
        end = self.checkpoint_ranges[self.current_index][1]
        return bool(self._buffer and fuzz.ratio(self._buffer[-1], self.words[end-1]) >= 75)

    def _threshold(self, scene, recovering):
        # A recent prefix of THIS next anchor is local acquisition, not a
        # book-wide recovery guess. Restore the configured threshold only for
        # a fresh, recognizably similar ending; unrelated scenes keep 92.
        if self._live_prefix(scene) and self._ending_supported():
            recovering = False
        return super()._threshold(scene, recovering)

    def _alignment_candidates(self, low, high):
        candidates = super()._alignment_candidates(low, high)
        if not self._live_prefix(self.current_index) or not self._ending_supported():
            return candidates
        # Only add a next-endpoint candidate. Preserve the original ASR buffer;
        # collapsing adjacent repeats cannot create global progress elsewhere.
        words = [w for i,w in enumerate(self._buffer)
                 if i == 0 or w != self._buffer[i-1]]
        if len(words) == len(self._buffer):
            return candidates
        end = self.checkpoint_ranges[self.current_index][1]
        for length in {len(words), max(self.minimum_words,len(words)//2),
                       self.minimum_words, min(len(words),self.minimum_words+3)}:
            candidates.extend(s for s in align_words(words[-length:],self.words[low:high],low,
                                                     self.minimum_words,self._minimum_coverage)
                              if s.end == end)
        return candidates

    def _confirm_candidate(self, scene, best):
        target = self.current_index
        start,end = self.checkpoint_ranges[target]
        live = self._live_prefix(scene)
        prefix = self._boundary_prefix
        if (live and scene == target and best.end == end and self._ending_supported()
                and best.start <= prefix['end']-2 and self._pending_scene != scene):
            self._pending_scene = scene
            self.confirmations = 1
            self._evidence_end = prefix['end']
            self._evidence_time = prefix['time']
            self._evidence_update = prefix['update']
            self._evidence_text = prefix['text']
            self._evidence_completed = False
        count = super()._confirm_candidate(scene,best)
        # Keep one extra prefix word of context for an ending like "lots of
        # steps". It still needs three distinct anchor words and an accepted
        # alignment; all time, ambiguity and independence bounds stay intact.
        if (end-3 <= best.end < end and best.end-start >= 3
                and best.start <= best.end-3
                and len(set(self.words[start:best.end]) & set(self._buffer[-16:])) >= 3
                and not (set(self._buffer[-16:]) & {'not','never','dont',"don't",'say','repeat'})):
            self._boundary_prefix = dict(scene=target,end=best.end,time=self._audio_time,
                                         update=self._fresh_updates,text=tuple(self._buffer))
        return count
