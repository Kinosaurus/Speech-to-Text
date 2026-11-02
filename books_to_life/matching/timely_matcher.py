"""Bounded next-anchor recovery without lowering global match requirements."""
from books_to_life.matching.alignment_matcher import AlignmentSpan, align_words
from books_to_life.matching.boundary_matcher import BoundaryEvidenceMatcher
from books_to_life.matching.checkpoint_matcher import fuzz
from books_to_life.matching.effect_permission import EffectPermission, similar
from dataclasses import replace


class TimelyEvidenceMatcher(BoundaryEvidenceMatcher):
    mode = 'experimental contextual alignment with timely anchor recovery'
    _permission_grace_seconds = 2.0
    _permission_grace_updates = 4
    _prompt_words = {'not', 'never', 'dont', "don't", 'say', 'repeat'}

    def __init__(self, *args, **kwargs):
        self._pending_effect = None
        super().__init__(*args, **kwargs)
        self._effect_permissions = {
            str(cp['id']): EffectPermission(cp, self.default_min_coverage, self.words[max(0, start-3):start])
            for cp, (start, end) in zip(self.checkpoints, self.checkpoint_ranges)}
        self.suppressed_checkpoint_ids = set()

    @property
    def completed(self):
        return super().completed and self._pending_effect is None

    @property
    def current_checkpoint(self):
        # Reading can finish while its last one-shot decision is still pending.
        return self.checkpoints[self.current_index] if self.current_index < len(self.checkpoints) else None

    def process(self, transcript, segments=None):
        previous_index = self.current_index
        previous_position = self.tracked_word_position
        if previous_index >= len(self.checkpoints) and self._pending_effect is not None:
            # Ingest fresh final-word revisions even after reading reaches EOF.
            # Bypass the next-anchor helper, which requires an unread checkpoint.
            fresh = super()._ingest(transcript, segments)
            update = replace(self._pending_effect['update'], triggered=False, effect=None,
                             completed=False, duplicate=not fresh, skipped_checkpoint_ids=())
        else:
            update = super().process(transcript, segments)
        extra_suppressed = ()
        if self._pending_effect is not None:
            pending = self._pending_effect
            if update.triggered:
                # A later checkpoint takes priority. Never replay an old effect
                # after that new scene, and do not lose the new scene's event.
                extra_suppressed = (self._close_pending(),)
            else:
                return self._resolve_pending(update)
        if not update.triggered:
            return update
        permission = self._effect_permissions[update.checkpoint_id]
        # Extra permission routes belong to the acquired NEXT checkpoint;
        # a cold-start match or a jump to a later scene cannot use this aid.
        locally_acquired = (previous_position > 0
                            and update.checkpoint_id == str(self.checkpoints[previous_index]['id'])
                            and previous_position >= self.checkpoint_ranges[previous_index][0])
        allowed, reason = permission.permits(self._buffer, allow_phonetic_endpoint=locally_acquired,
                                             allow_word_boundaries=locally_acquired)
        if allowed:
            return replace(update, effect_policy=permission.policy, completed=self.completed,
                           additional_suppressed_checkpoint_ids=extra_suppressed)
        # Reading progress advances independently of this effect decision.
        self.triggered_checkpoint_ids.discard(update.checkpoint_id)
        if self._can_defer(permission, locally_acquired, update):
            self._pending_effect = dict(update=update, time=self._audio_time,
                fresh_update=self._fresh_updates, text=tuple(self._buffer),
                end=self.checkpoint_ranges[self.current_index-1][1],
                segment_start=self._segments[-1]['start'] if self._segments else None)
            return replace(update, triggered=False, effect=None, completed=False,
                           effect_policy=permission.policy, effect_pending_checkpoint_id=update.checkpoint_id,
                           additional_suppressed_checkpoint_ids=extra_suppressed)
        self.suppressed_checkpoint_ids.add(update.checkpoint_id)
        return replace(update, triggered=False, effect=None, effect_suppressed=True,
                       effect_suppression_reason=reason, effect_policy=permission.policy,
                       completed=self.completed, additional_suppressed_checkpoint_ids=extra_suppressed)

    def _can_defer(self, permission, acquired, update):
        if (not acquired or update.ambiguous or update.recovering or update.skipped_checkpoint_ids
                or (self._segments and self._segments[-1]['completed'])
                or set(self._buffer[-16:]) & self._prompt_words
                or any(similar(permission.anchor[-1], word) for word in self._buffer[-4:])):
            return False
        # An exact, recent prefix and at most one unfinished/restarted token
        # distinguish an unfolding endpoint from a reader who has moved on.
        prefix = permission.anchor[:-1]
        if len(prefix) < 2 or len(set(prefix)) < 2:
            return False
        end = self.checkpoint_ranges[self.current_index-1][1]
        at_tail = (self._buffer[-len(prefix):] == prefix
                   or self._buffer[-len(prefix)-1:-1] == prefix)
        return self.tracked_word_position <= end+1 and at_tail

    def _close_pending(self):
        ident = self._pending_effect['update'].checkpoint_id
        self.suppressed_checkpoint_ids.add(ident)
        self._pending_effect = None
        return ident

    def _resolve_pending(self, update):
        pending = self._pending_effect
        saved = pending['update']
        permission = self._effect_permissions[saved.checkpoint_id]
        expired = (self._audio_time-pending['time'] > self._permission_grace_seconds
                   or self._fresh_updates-pending['fresh_update'] > self._permission_grace_updates
                   or self.tracked_word_position > pending['end']+3 or update.ambiguous or update.recovering)
        buffer = self._buffer
        completed = bool(self._segments and self._segments[-1]['completed'])
        changed_segment = False
        if pending['segment_start'] is not None and self._segments:
            changed_segment = self._segments[-1]['start'] > pending['segment_start']
            if changed_segment:
                # A new utterance cannot borrow the old prefix to fill an
                # omitted word. A revised completion of the old one still can.
                prior = [s for s in self._segments if s['start'] <= pending['segment_start']]
                buffer = ' '.join(s['text'] for s in prior).split()[-self.transcript_words:]
        prompted = bool(set(self._buffer[-16:]) & self._prompt_words)
        fresh = (not update.duplicate and self._fresh_updates > pending['fresh_update']
                 and tuple(buffer) != pending['text']
                 and (not self._segments or self._audio_time > pending['time'] or completed))
        if not expired and not prompted and fresh and permission.permits(
                buffer, allow_phonetic_endpoint=True, allow_word_boundaries=True)[0]:
            self._pending_effect = None
            self.triggered_checkpoint_ids.add(saved.checkpoint_id)
            return replace(saved, triggered=True, effect_policy=permission.policy,
                           tracked_word_position=self.tracked_word_position, completed=self.completed)
        if expired or prompted or completed or changed_segment:
            self._close_pending()
            return replace(saved, triggered=False, effect=None, effect_suppressed=True,
                           effect_policy=permission.policy, tracked_word_position=self.tracked_word_position,
                           effect_suppression_reason='one-shot endpoint remained unsupported before its pending window closed',
                           completed=self.completed)
        return replace(update, completed=False, effect_pending_checkpoint_id=saved.checkpoint_id)

    def _select_candidate(self, candidates):
        best = super()._select_candidate(candidates)
        if best is None:
            return None
        checkpoint = self.checkpoints[self.current_index]
        start, end = self.checkpoint_ranges[self.current_index]
        # Only resolve a near tie one word before the acquired NEXT endpoint.
        # Never reward a global jump, distant checkpoint, or unsupported anchor.
        if best.end != end-1 or self.tracked_word_position < start:
            return best
        supported, _ = self._effect_permissions[str(checkpoint['id'])].supports_anchor(self._buffer)
        if not supported:
            return best
        alternatives = [span for span in candidates if span.end == end
                        and span.start <= best.end and best.start < span.end
                        and best.score-span.score <= .5]
        return max(alternatives, key=lambda span: (span.score, span.matched_words)) if alternatives else best

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
        start = self.checkpoint_ranges[self.current_index][0]
        acquired = self.tracked_word_position > 0 and self.tracked_word_position >= start
        return bool(self._buffer and (fuzz.ratio(self._buffer[-1], self.words[end-1]) >= 75
                    or (acquired and self._effect_permissions[str(self.current_checkpoint['id'])]
                        .supports_phonetic_anchor(self._buffer))))

    def _threshold(self, scene, recovering):
        # A recent prefix of THIS next anchor is local acquisition, not a
        # book-wide recovery guess. Restore the configured threshold only for
        # a fresh, recognizably similar ending; unrelated scenes keep 92.
        if self._live_prefix(scene) and self._ending_supported():
            recovering = False
        return super()._threshold(scene, recovering)

    def _alignment_candidates(self, low, high):
        candidates = super()._alignment_candidates(low, high)
        start, end = self.checkpoint_ranges[self.current_index]
        anchor = self.words[start:end]
        # Reading progress and effect permission share contextual phonetic
        # endpoint evidence. Otherwise a valid endpoint can age out while the
        # spelling-only alignment waits for following sentence words.
        if (self.tracked_word_position > 0 and self.tracked_word_position >= start
                and low <= start < end <= high and len(anchor) >= self.minimum_words
                and sum(self.words[i:i+len(anchor)] == anchor
                        for i in range(len(self.words)-len(anchor)+1)) == 1
                and self._effect_permissions[str(self.current_checkpoint['id'])]
                    .supports_phonetic_anchor(self._buffer)):
            # Give the uncertain endpoint 0.75 word credit. Normal thresholds,
            # ambiguity checks and independent confirmations still apply.
            candidates.append(AlignmentSpan(start, end, 100*(len(anchor)-.25)/len(anchor),
                                            len(anchor), len(anchor)))
        # A complete exact anchor can reach its split endpoint without waiting
        # for the next sentence. Only the acquired NEXT region is eligible,
        # and repeated anchors cannot manufacture a unique position.
        if (self.tracked_word_position > 0 and self.tracked_word_position >= start
                and low <= start < end <= high
                and sum(self.words[i:i+len(anchor)] == anchor
                        for i in range(len(self.words)-len(anchor)+1)) == 1
                and self._effect_permissions[str(self.checkpoints[self.current_index]['id'])].supports_split_anchor(self._buffer)):
            # Scores/counts use authored-word units after exact segmentation;
            # ASR tokens and normal independent-confirmation rules stay intact.
            candidates.append(AlignmentSpan(start, end, 100.0, len(anchor), len(anchor)))
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
        elif (end-start <= 6 and start+2 <= best.end < end
                and self.tracked_word_position >= start
                and not (set(self._buffer[-16:]) & {'not','never','dont',"don't",'say','repeat'})):
            # A short, function-word-heavy anchor may first arrive as only
            # "a bit". Count its PREVIOUS callback only with an acquired local
            # position and a unique exact five-word run including book context
            # (e.g. "it gets is a bit"). The reached endpoint must still supply
            # a different, newer callback; same-audio revisions cannot confirm.
            context = self.words[best.end-5:best.end]
            if (len(context) == 5 and best.end-5 < start and len(set(context)) >= 4
                    and self._buffer[-5:] == context
                    and sum(self.words[i:i+5] == context for i in range(len(self.words)-4)) == 1):
                self._boundary_prefix = dict(scene=target,end=best.end,time=self._audio_time,
                                             update=self._fresh_updates,text=tuple(self._buffer))
        return count
