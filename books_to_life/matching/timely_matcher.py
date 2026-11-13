"""Bounded next-anchor recovery without lowering global match requirements."""
from books_to_life.matching.alignment_matcher import AlignmentSpan, align_words
from books_to_life.matching.boundary_matcher import BoundaryEvidenceMatcher
from books_to_life.matching.checkpoint_matcher import fuzz
from books_to_life.matching.effect_permission import EffectPermission, NEGATION_WORDS, similar
from books_to_life.matching.phonetic_endpoint import phonetic_endpoint_match
from dataclasses import replace
from collections import Counter


class TimelyEvidenceMatcher(BoundaryEvidenceMatcher):
    mode = 'experimental contextual alignment with timely anchor recovery'
    _permission_grace_seconds = 2.0
    _permission_grace_updates = 4
    _verified_cue_grace_seconds = 6.0
    _negation_words = NEGATION_WORDS
    _prompt_words = {'not', 'never', 'dont', "don't", 'say', 'repeat'}

    def __init__(self, *args, hold_cumulative_endpoint=False, **kwargs):
        self._hold_cumulative_endpoint = hold_cumulative_endpoint
        self._aside_prefix = None
        self._pending_effect = None
        self._verified_cue = None
        self._cue_prefix = None
        self._previous_segment = None
        super().__init__(*args, **kwargs)
        self._effect_permissions = {
            str(cp['id']): EffectPermission(cp, self.default_min_coverage, self.words[max(0, start-3):start])
            for cp, (start, end) in zip(self.checkpoints, self.checkpoint_ranges)}
        # Full checkpoint text/ranges are validated by the base matcher and
        # remain book context. An authored cue supplies this effect's boundary.
        self.tracking_checkpoint_ranges = tuple(self.checkpoint_ranges)
        self.checkpoint_ranges = [
            (start + self._effect_permissions[str(cp['id'])].cue_offset,
             start + self._effect_permissions[str(cp['id'])].cue_offset
                 + len(self._effect_permissions[str(cp['id'])].anchor))
            for cp, (start, end) in zip(self.checkpoints, self.tracking_checkpoint_ranges)]
        self._checkpoint_ends = [end for start, end in self.checkpoint_ranges]
        self._bounded_candidates = set()
        self._bounded_selection = False
        self._accepted_context_words = 0
        self._bounded_context_counts = {}
        self.suppressed_checkpoint_ids = set()
        self._confirmation_prefix = None
        self._interrupted_prefix = None
        self._interruption_context = None
        self._interruption_scenes = set()
        self._exact_prefixes = {}
        prefix_counts = {}
        # A prefix is evidence, not an accepted alignment or effect. Require
        # nearly the normal minimum length, the existing distinct-word guard,
        # and the existing final-three-word neighbourhood. Completed candidates
        # still pass the unchanged score, coverage and stability requirements.
        for scene, (start, end) in enumerate(self.checkpoint_ranges):
            for stop in range(max(start+self.minimum_words-1, end-3), end):
                phrase = tuple(self.words[start:stop])
                if len(set(phrase)) < 3 or len(phrase) > self.transcript_words:
                    continue
                if len(phrase) not in prefix_counts:
                    prefix_counts[len(phrase)] = Counter(tuple(self.words[i:i+len(phrase)])
                        for i in range(len(self.words)-len(phrase)+1))
                if prefix_counts[len(phrase)][phrase] == 1:
                    self._exact_prefixes.setdefault(len(phrase), {})[phrase] = (scene, stop)

    @property
    def completed(self):
        return super().completed and self._pending_effect is None

    @property
    def current_checkpoint(self):
        # Reading can finish while its last one-shot decision is still pending.
        return self.checkpoints[self.current_index] if self.current_index < len(self.checkpoints) else None

    def process(self, transcript, segments=None):
        self._bounded_selection = False
        self._accepted_context_words = 0
        self._interruption_context = None
        self._interruption_scenes = set()
        self._resumed_cue = False
        previous_index = self.current_index
        previous_position = self.tracked_word_position
        previous_prefix = self._cue_prefix
        previous_segment = self._segments[-1] if self._segments else None
        self._previous_segment = previous_segment
        if previous_index >= len(self.checkpoints) and self._pending_effect is not None:
            # Ingest fresh final-word revisions even after reading reaches EOF.
            # Bypass the next-anchor helper, which requires an unread checkpoint.
            fresh = super()._ingest(transcript, segments)
            update = replace(self._pending_effect['update'], triggered=False, effect=None,
                             completed=False, duplicate=not fresh, skipped_checkpoint_ids=())
        else:
            update = super().process(transcript, segments)
        verified_cue = self._update_verified_cue(update, previous_index) if segments else False
        if not segments:
            self._verified_cue = None
        if self.current_index != previous_index:
            self._cue_prefix = None
            self._aside_prefix = None
        extra_suppressed = ()
        if self._pending_effect is not None:
            if update.triggered:
                # A later checkpoint takes priority. Never replay an old effect
                # after that new scene, and do not lose the new scene's event.
                extra_suppressed = (self._close_pending(),)
            else:
                return self._resolve_pending(update, previous_segment)
        if not update.triggered:
            return update
        permission = self._effect_permissions[update.checkpoint_id]
        # Extra permission routes belong to the acquired NEXT checkpoint;
        # a cold-start match or a jump to a later scene cannot use this aid.
        locally_acquired = self._bounded_selection or (previous_position > 0
                            and update.checkpoint_id == str(self.checkpoints[previous_index]['id'])
                            and previous_position >= self.checkpoint_ranges[previous_index][0])
        allowed, reason = permission.permits(self._buffer, allow_phonetic_endpoint=locally_acquired,
                                             allow_word_boundaries=locally_acquired,
                                             allow_phonetic_internal=(locally_acquired
                                                 and (len(permission.anchor) >= self.minimum_words
                                                      or self._bounded_selection)),
                                             allow_context_suffix=(permission.has_explicit_cue
                                                 and previous_position > 0
                                                 and update.checkpoint_id == str(self.checkpoints[previous_index]['id'])
                                                 and self.checkpoint_ranges[previous_index][0]-self.backtrack_words <= previous_position
                                                 and update.alignment_start is not None
                                                 and update.alignment_start <= self.checkpoint_ranges[previous_index][1]-3
                                                 and self._accepted_context_words >= self.minimum_words))
        if not allowed and verified_cue:
            allowed = True
        if not allowed and locally_acquired:
            allowed = self._interrupted_permission(update.checkpoint_id)
        if not allowed and self._resumed_cue:
            # Both pieces were verified against this exact anchor in order.
            allowed, reason = permission.permits(permission.anchor)
        if allowed:
            return replace(update, effect_policy=permission.policy, completed=self.completed,
                           additional_suppressed_checkpoint_ids=extra_suppressed)
        # Reading progress advances independently of this effect decision.
        self.triggered_checkpoint_ids.discard(update.checkpoint_id)
        if self._can_defer(permission, locally_acquired, update):
            end = self.checkpoint_ranges[previous_index][1]
            prefix_words = tuple(permission.anchor[:-1])
            resume_prefix = None
            if (previous_prefix is not None and previous_prefix['end'] == previous_position == end-1
                    and self.tracked_word_position == end and len(prefix_words) >= self.minimum_words
                    and self._exact_prefixes.get(len(prefix_words), {}).get(prefix_words)
                    == (previous_index, end-1) and self.words.count(permission.anchor[-1]) == 1):
                resume_prefix = previous_prefix
            self._pending_effect = dict(update=update, time=self._audio_time,
                fresh_update=self._fresh_updates, text=tuple(self._buffer),
                end=end, segment_start=self._segments[-1]['start'] if self._segments else None,
                resume_prefix=resume_prefix)
            return replace(update, triggered=False, effect=None, completed=False,
                           effect_policy=permission.policy, effect_pending_checkpoint_id=update.checkpoint_id,
                           additional_suppressed_checkpoint_ids=extra_suppressed)
        self.suppressed_checkpoint_ids.add(update.checkpoint_id)
        return replace(update, triggered=False, effect=None, effect_suppressed=True,
                       effect_suppression_reason=reason, effect_policy=permission.policy,
                       completed=self.completed, additional_suppressed_checkpoint_ids=extra_suppressed)

    def _update_verified_cue(self, update, previous_index):
        """Carry effect permission while ordinary alignment confirms the next cue."""
        saved = self._verified_cue
        self._verified_cue = None
        if (previous_index >= len(self.checkpoints) or update.ambiguous
                or (update.triggered and update.skipped_checkpoint_ids)):
            return False
        cue_id = str(self.checkpoints[previous_index]['id'])
        if update.checkpoint_id != cue_id:
            return False

        if saved is not None and saved['index'] == previous_index:
            owner = next((segment for segment in self._segments
                          if segment['start'] == saved['segment_start']), None)
            if (owner is not None and owner['end'] >= saved['segment_end']
                    and self._audio_time - saved['time'] <= self._verified_cue_grace_seconds
                    and self._fresh_updates - saved['update'] <= self._permission_grace_updates):
                start = saved['offset']
                heard = owner['text'].split()[start:start + len(saved['words'])]
                if heard == saved['words']:
                    if update.triggered:
                        return True
                    if self._pending_scene == previous_index:
                        self._verified_cue = saved

        if (update.triggered or update.duplicate or self._pending_scene != previous_index
                or self._evidence_update != self._fresh_updates or update.alignment_end is None):
            return False
        _, cue_end = self.checkpoint_ranges[previous_index]
        if update.alignment_start > cue_end - 2 or update.alignment_end < cue_end:
            return False
        permission = self._effect_permissions[cue_id]
        if permission.policy != 'one_shot':
            return False

        # Keep the observed cue neighbourhood in its source segment. A later
        # revision must still contain those same words at that offset.
        segment = self._segments[-1]
        heard = segment['text'].split()
        width = min(self.transcript_words, max(12, len(permission.anchor) + 8))
        for end in range(len(heard), max(0, len(heard) - 4), -1):
            start = max(0, len(heard) - width)
            words = heard[start:end]
            if heard[end - 1] == permission.anchor[-1] and permission.permits(words)[0]:
                self._verified_cue = dict(index=previous_index, segment_start=segment['start'],
                                          segment_end=segment['end'], offset=start, words=words,
                                          time=self._audio_time, update=self._fresh_updates)
                break
        return False

    def _can_defer(self, permission, acquired, update):
        if (not acquired or update.ambiguous or update.recovering or update.skipped_checkpoint_ids
                or (self._segments and self._segments[-1]['completed'])
                or set(self._buffer[-16:]) & self._negation_words
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

    def _resolve_pending(self, update, previous_segment):
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
        negated = bool(set(self._buffer[-16:]) & self._negation_words)
        fresh = (not update.duplicate and self._fresh_updates > pending['fresh_update']
                 and tuple(buffer) != pending['text']
                 and (not self._segments or self._audio_time > pending['time'] or completed))
        waiting, resumed = self._pending_interruption(update, permission, previous_segment)
        holding, confirmed = self._cumulative_pending_endpoint(update, permission, previous_segment)
        if holding:
            return replace(update, completed=False, effect_pending_checkpoint_id=saved.checkpoint_id)
        aside_seen = pending.get('cumulative_aside', False)
        if confirmed or (not aside_seen and not negated and fresh and (resumed or (not expired and permission.permits(
                buffer, allow_phonetic_endpoint=True, allow_word_boundaries=True)[0]))):
            self._pending_effect = None
            self.triggered_checkpoint_ids.add(saved.checkpoint_id)
            return replace(saved, triggered=True, effect_policy=permission.policy,
                           tracked_word_position=self.tracked_word_position, completed=self.completed)
        if aside_seen or negated or ((expired or completed or changed_segment) and not waiting):
            self._close_pending()
            return replace(saved, triggered=False, effect=None, effect_suppressed=True,
                           effect_policy=permission.policy, tracked_word_position=self.tracked_word_position,
                           effect_suppression_reason='one-shot endpoint remained unsupported before its pending window closed',
                           completed=self.completed)
        return replace(update, completed=False, effect_pending_checkpoint_id=saved.checkpoint_id)

    def _cumulative_pending_endpoint(self, update, permission, previous_segment):
        """Keep the exact prefix through a revised cumulative aside."""
        if not self._hold_cumulative_endpoint or not self._segments:
            return False, False
        pending = self._pending_effect
        prefix = pending['resume_prefix']
        segment = self._segments[-1]
        if (prefix is None or segment['start'] != prefix['segment_start']
                or self.tracked_word_position > pending['end'] + 3 or update.ambiguous):
            return False, False
        head = permission.anchor[:-1]
        words = segment['text'].split()
        offset = prefix['offset']
        if words[offset:offset + len(head)] != head:
            return False, False
        tail = words[offset + len(head):]
        endpoint = permission.anchor[-1]
        if self._negation_words.intersection(tail):
            return False, False
        # Keep the ordinary short grace for a simple spelling revision.
        # Once there is an aside, a single provisional endpoint is insufficient.
        if not pending.get('cumulative_aside') and len(tail) < 2:
            return False, False
        exact_ending = tail in ([endpoint], [head[-1], endpoint])
        if exact_ending:
            # Ignore one repeated prefix word, preserving the observed endpoint.
            exact_ending = permission.permits(head + [tail[-1]])[0]
        if not segment['completed']:
            next_start = (self.checkpoint_ranges[self.current_index][0]
                          if self.current_index < len(self.checkpoints) else len(self.words))
            continuations = [self.words[i:i+2] for i in (pending['end'], next_start)
                             if i + 2 <= len(self.words)]
            ending = tail[1:] if tail[:1] == [head[-1]] else tail
            starts_next_line = (len(ending) == 2 and ending[0] == endpoint
                                and any(ending[1:] == words[:1] for words in continuations))
            prior_endpoint = pending.get('cumulative_endpoint')
            if prior_endpoint is not None and 0 < self._audio_time - prior_endpoint <= 12:
                # A newer callback confirms the ending with two exact words
                # from the next line or next cue.
                if ending[:1] == [endpoint]:
                    if ending[1:3] in continuations and permission.permits(head + ending[:1])[0]:
                        return False, True
                    if starts_next_line:
                        return True, False
            if self._audio_time - prefix['audio_end'] > 25:
                return False, False
            pending['cumulative_aside'] = True
            if exact_ending or (starts_next_line and permission.permits(head + ending[:1])[0]):
                pending['cumulative_endpoint'] = self._audio_time
            else:
                pending.pop('cumulative_endpoint', None)
            return True, False
        confirmed = (exact_ending and 'cumulative_endpoint' in pending
                        and self._audio_time - pending['cumulative_endpoint'] <= 30
                        and previous_segment is not None
                        and previous_segment['start'] == segment['start']
                        and not previous_segment['completed']
                        and previous_segment['text'] == segment['text'])
        return False, bool(confirmed)

    def _pending_interruption(self, update, permission, previous_segment):
        """Check for a separate aside after a verified near-complete cue."""
        pending = self._pending_effect
        prefix = pending['resume_prefix']
        if (prefix is None or not self._segments or update.ambiguous
                or self.tracked_word_position != pending['end']):
            return False, False
        owner_index = next((i for i, segment in enumerate(self._segments)
                            if segment['start'] == prefix['segment_start']), None)
        if owner_index is None or owner_index == len(self._segments)-1:
            return False, False
        owner = self._segments[owner_index]
        head = owner['text'].split()[prefix['offset']:]
        if not owner['completed'] or head != permission.anchor[:-1]:
            return False, False
        following = self._segments[owner_index+1:]
        heard = [word for segment in following for word in segment['text'].split()]
        if len(head) + len(heard) > self.transcript_words:
            return False, False
        endpoint = permission.anchor[-1]
        if endpoint not in heard:
            # A single incomplete token stays subject to the short revision
            # window. More speech in a separate segment can be an aside.
            return len(heard) >= 2, False
        segment = following[-1]
        resumed = (
            previous_segment is not None
            and previous_segment['completed']
            and owner['start'] < previous_segment['start'] < segment['start']
            and previous_segment['end'] <= segment['start'] < segment['end']
            and len(heard) >= 3 and heard.count(endpoint) == 1
            and segment['text'] == endpoint
            and permission.permits(head + [endpoint])[0]
        )
        return False, resumed

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
        previous_source = self._prefix_source()
        prior_vote = (self._pending_scene, self.confirmations, self._evidence_end,
                      self._evidence_time, self._evidence_completed)
        fresh = super()._ingest(transcript, segments)
        if fresh and self._hold_cumulative_endpoint:
            self._retain_vote_until_cumulative_final(prior_vote)
        if fresh:
            self._acquire_confirmation_prefix(previous_source)
            self._acquire_interrupted_prefix()
        if fresh and self._cue_prefix is not None:
            prefix = self._cue_prefix
            start, _ = self.checkpoint_ranges[self.current_index]
            for segment in self._segments:
                if segment['start'] == prefix['segment_start']:
                    offset = prefix['offset']
                    length = prefix['end'] - start
                    if segment['text'].split()[offset:offset+length] != self.words[start:prefix['end']]:
                        self._cue_prefix = None
                    break
        if fresh and self._hold_cumulative_endpoint:
            self._observe_cumulative_aside()
        if not fresh or self._ending_supported():
            return fresh
        start,end = self.checkpoint_ranges[self.current_index]
        tail = self._buffer[-12:]
        if set(tail) & self._negation_words:
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

    def _observe_cumulative_aside(self):
        if not self._segments or self.current_index >= len(self.checkpoints):
            return
        start, end = self.checkpoint_ranges[self.current_index]
        segment = self._segments[-1]
        words = segment['text'].split()
        prefix = self._cue_prefix
        if (self._aside_prefix is None and prefix is not None and prefix['end'] == end-1
                and start <= self.tracked_word_position < end
                and segment['start'] == prefix['segment_start']
                and 0 < self._audio_time - prefix['audio_end'] <= 25):
            head = self.words[start:end-1]
            offset = prefix['offset']
            tail = words[offset + len(head):]
            if words[offset:offset + len(head)] == head and len(tail) >= 2 and self.words[end-1] not in tail:
                self._aside_prefix = dict(prefix, scene=self.current_index, endpoint_at=None)

    def _has_confirmed_aside_ending(self, start, end):
        prefix = self._aside_prefix
        segment = self._segments[-1]
        head = self.words[start:end-1]
        words = segment['text'].split()
        offset = prefix['offset']
        tail = words[offset + len(head):]
        if (segment['start'] != prefix['segment_start']
                or words[offset:offset + len(head)] != head
                or self._negation_words.intersection(tail)):
            prefix['endpoint_at'] = None
            return False
        if tail[:1] == head[-1:]:
            tail = tail[1:]
        endpoint = self.words[end-1:end]
        if tail[:1] != endpoint:
            prefix['endpoint_at'] = None
            return False
        prior = prefix['endpoint_at']
        next_start = self.checkpoint_ranges[self.current_index+1][0] if self.current_index+1 < len(self.checkpoints) else end
        book_context = [self.words[i:i+2] for i in (end, next_start) if i+2 <= len(self.words)]
        starts_next_line = len(tail) == 2 and any(tail[1:] == words[:1] for words in book_context)
        if ((tail == endpoint or starts_next_line) and not segment['completed']
                and (starts_next_line or 0 < self._audio_time-prefix['audio_end'] <= 25)):
            if prior is None:
                prefix['endpoint_at'] = self._audio_time
            return False
        return (prior is not None and 0 < self._audio_time-prior <= (30 if segment['completed'] else 12)
                and (tail[1:3] in book_context or (segment['completed'] and tail == endpoint)))

    def _retain_vote_until_cumulative_final(self, prior_vote):
        """Allow a final callback to confirm the same exact pre-final cue."""
        scene, votes, end, time, completed = prior_vote
        prefix = self._cue_prefix
        previous = self._previous_segment
        if (scene != self.current_index or votes != 1 or completed
                or prefix is None or previous is None or not self._segments):
            return
        segment = self._segments[-1]
        start, cue_end = self.checkpoint_ranges[scene]
        heard = segment['text'].split()
        if (segment['completed'] and not previous['completed']
                and segment['start'] == previous['start'] == prefix['segment_start']
                and segment['text'] == previous['text'] and previous['end'] == time
                and 0 <= self._audio_time-time <= 30
                and end == cue_end and prefix['end'] == cue_end-1
                and 0 < time-prefix['audio_end'] <= 25
                and heard[prefix['offset']:] == self.words[start:cue_end]):
            self._pending_scene = scene
            self.confirmations = votes
            self._evidence_end = end
            self._evidence_time = time
            self._evidence_completed = completed

    @property
    def awaiting_handoff_final(self):
        """Expose a verified provisional ending to the recognizer's VAD."""
        if not self._hold_cumulative_endpoint or not self._segments:
            return False
        if self._pending_effect is not None:
            return 'cumulative_endpoint' in self._pending_effect
        prefix = self._cue_prefix
        scene = self.current_index
        if (prefix is None or scene != self._pending_scene or self.confirmations != 1
                or scene >= len(self.checkpoints)):
            return False
        start, end = self.checkpoint_ranges[scene]
        segment = self._segments[-1]
        return (not segment['completed'] and segment['start'] == prefix['segment_start']
                and self._evidence_end == end and self._evidence_time == self._audio_time
                and prefix['end'] == end-1
                and 4 <= self._audio_time-prefix['audio_end'] <= 25
                and segment['text'].split()[prefix['offset']:] == self.words[start:end])

    def _acquire_interrupted_prefix(self):
        """Retain observed words of the acquired next anchor across an aside."""
        prior = self._interrupted_prefix
        if prior is not None:
            owner = next((s for s in self._segments if s['start'] == prior['segment_start']), None)
            invalid_owner = (owner is not None and
                tuple(owner['text'].split()[:len(prior['head'])]) != prior['head'])
            if owner is not None and owner['completed']:
                prior['committed'] = True
                continuation = owner['text'].split()[len(prior['head']):]
                start,end = self.checkpoint_ranges[prior['scene']]
                expected = self.words[start+len(prior['words'])]
                if len(continuation) >= self.minimum_words and not similar(expected,continuation[0]):
                    prior['interrupted'] = True
            if (prior['scene'] != self.current_index or invalid_owner
                    or self._audio_time-prior['time'] > 12
                    or prior['reading_updates'] > 12
                    or set(self._buffer[-16:]) & self._negation_words
                    or (owner is None and not prior['committed'])):
                self._interrupted_prefix = None
        if not self._segments or self.current_index >= len(self.checkpoints):
            return
        start,end = self.checkpoint_ranges[self.current_index]
        if not start < self.tracked_word_position < end:
            return  # This aid cannot acquire a cold checkpoint or jump ahead.
        segment = self._segments[-1];text = segment['text'].split()
        if set(text[-16:]) & self._negation_words:
            return
        anchor = self.words[start:end]
        for length in range(len(anchor)-1,1,-1):
            phrase = anchor[:length]
            if (len(set(phrase)) >= 2 and text[-length:] == phrase
                    and sum(self.words[i:i+length] == phrase
                            for i in range(len(self.words)-length+1)) == 1):
                old = self._interrupted_prefix
                head = tuple(text)
                if old is None or old['head'] != head or old['segment_start'] != segment['start']:
                    self._interrupted_prefix = dict(scene=self.current_index, words=phrase,
                        head=head, segment_start=segment['start'], committed=segment['completed'],
                        time=self._audio_time, update=self._fresh_updates,
                        reading_updates=0, last_reading_update=self._fresh_updates, interrupted=False)
                break

    def _interrupted_candidates(self, low, high):
        prefix = self._interrupted_prefix
        if prefix is None or prefix['scene'] != self.current_index:
            return []
        if not (prefix['committed'] and prefix['interrupted']
                and self._segments[-1]['start'] > prefix['segment_start']):
            return []
        start,end = self.checkpoint_ranges[self.current_index]
        if not low <= start < end <= high:
            return []
        anchor = self.words[start:end];permission = self._effect_permissions[str(self.current_checkpoint['id'])]
        tail = self._segments[-1]['text'].split()[-self.transcript_words:]
        choices = []; candidates = []
        for i,word in enumerate(tail):
            # Resume where the observed prefix stopped. Off-book words never
            # become reading evidence, and no missing book word is supplied.
            if not similar(anchor[len(prefix['words'])], word):
                continue
            # Match the same final-four-token endpoint neighbourhood used by
            # ordinary permission; following callback words are not part of
            # this anchor's alignment score.
            for extra in range(min(4,len(tail)-i)):
                spoken = prefix['words']+tail[i:len(tail)-extra]
                if len(spoken) > self.transcript_words:
                    continue
                allowed = permission.permits(spoken,
                        allow_phonetic_endpoint=True, allow_word_boundaries=True)[0]
                spans = [s for s in align_words(spoken,self.words[low:high],low,
                            self.minimum_words,self._minimum_coverage)
                         if start+len(prefix['words']) < s.end <= end
                         and s.start <= start+len(prefix['words'])-2
                         and (s.end < end or allowed)]
                candidates.extend(spans)
                full = [s for s in spans if s.end == end]
                if full:
                    choices.append((max(s.score for s in full),spoken))
        if choices:
            _,spoken = max(choices,key=lambda c:c[0])
            self._interruption_context = dict(id=str(self.current_checkpoint['id']), words=spoken)
        if candidates and prefix['last_reading_update'] != self._fresh_updates:
            # An off-book aside does not consume reading confirmations. The
            # audio-time bound still expires independently of recognition.
            prefix['reading_updates'] += 1
            prefix['last_reading_update'] = self._fresh_updates
            if prefix['reading_updates'] > 12:
                self._interrupted_prefix = None
                self._interruption_context = None
                return []
        self._interruption_scenes = {self._scene(s.end) for s in candidates}
        return candidates

    def _interrupted_permission(self, ident):
        context = self._interruption_context
        return bool(context and context['id'] == ident
                    and self._effect_permissions[ident].permits(context['words'],
                        allow_phonetic_endpoint=True,allow_word_boundaries=True)[0])

    def _cumulative_interruption_candidates(self, low, high):
        """Rejoin a verified cue across an aside in one cumulative segment."""
        prefix = self._cue_prefix
        if prefix is None or not self._segments or self._interruption_context is not None:
            return []
        start, end = self.checkpoint_ranges[self.current_index]
        segment = self._segments[-1]
        if (segment['start'] != prefix['segment_start']
                or not 0 < self._audio_time - prefix['audio_end'] <= 12
                or not low <= start < prefix['end'] <= self.tracked_word_position < end <= high):
            return []
        ident = str(self.current_checkpoint['id'])
        permission = self._effect_permissions[ident]
        endpoint = self.words[end-1]
        if not (permission.policy == 'one_shot' and permission.has_explicit_cue
                and endpoint in permission.required):
            return []
        head = self.words[start:prefix['end']]
        heard = segment['text'].split()
        context = prefix['context']
        context_start = prefix['offset'] - len(context)
        if heard[context_start:prefix['offset']] != context:
            return []
        appended = heard[prefix['offset'] + len(head):]
        suffix = self.words[prefix['end']:end]
        endings = [suffix]
        if len(suffix) >= 3 and suffix[0] not in permission.required:
            endings.append(suffix[1:])
        # An isolated endpoint after a break could be conversation. Require
        # the contiguous book continuation, including words after the cue.
        stop = min(end+4, high)
        if self.current_index+1 < len(self.checkpoint_ranges):
            stop = min(stop, self.checkpoint_ranges[self.current_index+1][0])
        for after in range(2, stop-end+1):
            following = self.words[end:end+after]
            for ending in endings:
                resume = ending + following
                aside = appended[:-len(resume)]
                if (appended[-len(resume):] != resume or len(aside) < self.minimum_words
                        or self._negation_words.intersection(aside)
                        or not permission.permits(head + ending)[0]):
                    continue
                run = context + head
                if sum(self.words[i:i+len(run)] == run for i in range(len(self.words)-len(run)+1)) != 1:
                    return []
                # Align observed words only. If the first resumed word was
                # dropped, the usual alignment score and cue coverage apply.
                finish = end+after
                candidates = [span for span in align_words(head+resume, self.words[start:finish], start,
                                                          self.minimum_words, self._minimum_coverage)
                              if span.start == start and span.end == finish
                              and span.score >= self._threshold(self.current_index, False)]
                if candidates:
                    self._interruption_context = dict(id=ident, words=head+ending, cumulative=True)
                    self._interruption_scenes.add(self.current_index)
                    return candidates
        return []

    def _prefix_source(self):
        if self._segments:
            segment = self._segments[-1]
            return segment['start'], tuple(segment['text'].split()[-self.transcript_words:])
        return None, tuple(self._buffer)

    def _exact_anchor_at_tail(self, scene):
        start, end = self.checkpoint_ranges[scene]
        anchor = tuple(self.words[start:end]);_, text = self._prefix_source()
        return any(text[len(text)-extra-len(anchor):len(text)-extra] == anchor
                   for extra in range(min(4, len(text)-len(anchor)+1)))

    def _acquire_confirmation_prefix(self, previous_source):
        # Retained earlier segments are useful to normal alignment, but cannot
        # impersonate newly spoken prefix words in this additional evidence path.
        segment_start, text = self._prefix_source()
        prior = self._confirmation_prefix
        if (set(text[-16:]) & self._negation_words or
                (prior is not None and (prior['scene'] < self.current_index
                 or self._audio_time-prior['time'] > 12
                 or self._fresh_updates-prior['update'] > 12
                 or segment_start != prior['segment_start']))):
            self._confirmation_prefix = None
        if set(text[-16:]) & self._negation_words:
            return
        matches = {}
        for length, prefixes in self._exact_prefixes.items():
            for extra in (0, 1):
                stop = len(text)-extra
                if stop < length:
                    continue
                found = prefixes.get(text[stop-length:stop])
                if found is None:
                    continue
                scene, book_end = found
                if scene < self.current_index or self._exact_anchor_at_tail(scene):
                    continue
                if extra and not (self.words[book_end].startswith(text[-1])
                                  and self.words[book_end] != text[-1]):
                    continue
                if scene not in matches or book_end > matches[scene]:
                    matches[scene] = book_end
        if len(matches) > 1:
            self._confirmation_prefix = None
            return
        prior = self._confirmation_prefix
        if prior is not None and prior['scene'] not in matches and not self._exact_anchor_at_tail(prior['scene']):
            # A contradictory revision or unrelated continuation abandons the
            # prefix. It cannot later be resurrected by a standalone endpoint.
            self._confirmation_prefix = None
        if (segment_start, text) != previous_source and matches:
            scene, book_end = next(iter(matches.items()))
            self._confirmation_prefix = dict(scene=scene, end=book_end, text=text,
                buffer=tuple(self._buffer), time=self._audio_time,
                update=self._fresh_updates, segment_start=segment_start)

    def _reject_candidate(self, ambiguous):
        super()._reject_candidate(ambiguous)
        if ambiguous:
            self._confirmation_prefix = None
            self._interrupted_prefix = None

    def _confirm_from_prefix(self, scene, best):
        prefix = self._confirmation_prefix
        if prefix is None or scene != prefix['scene'] or scene < self.current_index:
            return False
        start, end = self.checkpoint_ranges[scene]
        segment_start, text = self._prefix_source()
        if not (0 < self._fresh_updates-prefix['update'] <= 12
                and 0 < self._audio_time-prefix['time'] <= 12
                and text != prefix['text']
                and segment_start == prefix['segment_start']
                and not (set(text[-16:]) & self._negation_words)
                and best.end >= end and best.start <= prefix['end']-2
                and self._exact_anchor_at_tail(scene)):
            return False
        self._confirmation_prefix = None
        if self._pending_scene == scene and self.confirmations > 0:
            return False  # That scene already has a vote; never count it twice.
        self._pending_scene = scene
        self.confirmations = 1
        self._evidence_end = prefix['end']
        self._evidence_time = prefix['time']
        self._evidence_update = prefix['update']
        self._evidence_text = prefix['buffer']
        self._evidence_completed = False
        return True

    def _live_prefix(self, scene):
        prefix = self._boundary_prefix
        return (prefix is not None and scene == self.current_index == prefix['scene']
                and 0 < self._fresh_updates-prefix['update'] <= 12
                and (not self._segments or 0 < self._audio_time-prefix['time'] <= 12)
                and tuple(self._buffer) != prefix['text']
                and not (set(self._buffer[-16:]) & self._negation_words))

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
        if ((self._live_prefix(scene) and self._ending_supported())
                or scene in self._interruption_scenes):
            recovering = False
        return super()._threshold(scene, recovering)

    def _alignment_candidates(self, low, high):
        candidates = super()._alignment_candidates(low, high)
        bounded = self._bounded_acquisition_candidates(low, high)
        self._bounded_candidates = {(s.start, s.end, s.score) for s in bounded}
        candidates.extend(bounded)
        candidates.extend(self._interrupted_candidates(low,high))
        candidates.extend(self._cumulative_interruption_candidates(low, high))
        start, end = self.checkpoint_ranges[self.current_index]
        anchor = self.words[start:end]
        if self._continues_cue() and low <= self._cue_prefix['end'] < end <= high:
            candidates.append(AlignmentSpan(start, end, 100.0, len(anchor), len(anchor)))
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

    def _bounded_acquisition_candidates(self, low, high):
        """One observed internal sound variant in unique, nearby book context.

        This can acquire only the next unread cue. It supplies real-word spans
        to the normal score/ambiguity/confirmation path; no progress is assigned
        here. Missing words, required-word variants and compound uncertainty
        cannot be filled by this route.
        """
        start, end = self.checkpoint_ranges[self.current_index]
        if (self.tracked_word_position <= 0 or self.tracked_word_position < start-self.backtrack_words
                or self.tracked_word_position > end+3 or not low <= start < end <= high):
            return []
        _, source = self._prefix_source()
        query = list(source)[-self.transcript_words:]
        if len(query) < self.minimum_words or set(query[-16:]) & self._negation_words:
            return []
        permission = self._effect_permissions[str(self.current_checkpoint['id'])]
        stop = min(len(self.words), end+3)
        if self.current_index+1 < len(self.checkpoint_ranges):
            stop = min(stop, self.checkpoint_ranges[self.current_index+1][0])
        candidates = []
        for begin in range(max(low, start-self.minimum_words+1), start+1):
            for finish in range(max(end, begin+self.minimum_words), stop+1):
                reference = self.words[begin:finish]
                if len(reference) > self.transcript_words or len(set(reference)) < 3:
                    continue
                length = len(reference)
                if length not in self._bounded_context_counts:
                    self._bounded_context_counts[length] = Counter(
                        tuple(self.words[i:i+length]) for i in range(len(self.words)-length+1))
                if self._bounded_context_counts[length][tuple(reference)] != 1:
                    continue
                for query_end in range(len(query), max(0, len(query)-4), -1):
                    if query_end < length:
                        continue
                    observed = query[query_end-length:query_end]
                    # Exact cue and context endpoints keep the uncertainty
                    # internal, as in the existing permission support rule.
                    if observed[-1] != reference[-1] or observed[end-begin-1] != self.words[end-1]:
                        continue
                    unsupported = []
                    credit = 0.0
                    for i, (expected, heard) in enumerate(zip(reference, observed)):
                        ratio = fuzz.ratio(expected, heard)/100
                        required = expected in permission.required
                        if (required and not similar(expected, heard, 85)) or (not required and ratio < .75):
                            unsupported.append(i)
                        else:
                            credit += ratio
                    if len(unsupported) != 1:
                        continue
                    i = unsupported[0]
                    if (not start < begin+i < end-1 or reference[i] in permission.required
                            or observed[i-1] != reference[i-1] or observed[i+1] != reference[i+1]
                            or len({reference[j] for j in range(length) if j != i}) < 3
                            or not phonetic_endpoint_match(reference[i], observed[i])):
                        continue
                    # The existing uncertain-endpoint candidate uses .75 word
                    # credit. Reuse it for one observed internal token; numeric
                    # thresholds, coverage and independent votes stay unchanged.
                    candidates.append(AlignmentSpan(begin, finish, 100*(credit+.75)/length,
                                                    length, length))
        return candidates

    def _continues_cue(self):
        prefix = self._cue_prefix
        if prefix is None or not self._segments:
            return False
        _, end = self.checkpoint_ranges[self.current_index]
        suffix = self.words[prefix['end']:end]
        if len(set(suffix)) < 2:
            return False
        segment = self._segments[-1]
        heard = segment['text'].split()
        if segment['start'] > prefix['segment_start']:
            return segment['start'] >= prefix['audio_end'] and heard[:len(suffix)] == suffix
        if segment['start'] != prefix['segment_start'] or segment['end'] <= prefix['audio_end']:
            return False
        # Cumulative snapshots retain the verified prefix in the same segment.
        # Only words appended after that prefix can supply the continuation.
        start, _ = self.checkpoint_ranges[self.current_index]
        appended = heard[prefix['offset'] + prefix['end'] - start:]
        before_suffix = appended[max(0, len(appended)-len(suffix)-3):-len(suffix)]
        return (appended[-len(suffix):] == suffix
                and not self._negation_words.intersection(before_suffix))

    def _confirm_contextual_ending(self, scene, best, start, end):
        """Carry one accepted vote across the boundary of an authored cue."""
        if (scene != self.current_index or best.end != end or best.start >= start
                or self.tracked_word_position != end-1 or self._evidence_end != end-1
                or self._pending_scene != self._scene(end-1) or self.confirmations == 0
                or best.matched_words < self.minimum_words or not self._segments):
            return
        checkpoint = self.current_checkpoint
        permission = self._effect_permissions[str(checkpoint['id'])]
        endpoint = self.words[end-1]
        previous = self._previous_segment
        segment = self._segments[-1]
        if (checkpoint.get('stability', self.default_stability) == 2
                and permission.has_explicit_cue and endpoint in permission.required
                and previous is not None and previous['end'] == self._evidence_time
                and segment['start'] == previous['start'] and segment['end'] > previous['end']
                and previous['text'].split()[-2:] == self.words[end-3:end-1]
                and segment['text'] == previous['text'] + ' ' + endpoint
                and permission.supports_context_suffix(self._buffer)):
            self._pending_scene = scene
            self.confirmations = 1

    def _confirm_candidate(self, scene, best):
        self._accepted_context_words = best.matched_words
        start, end = self.checkpoint_ranges[self.current_index]
        # A stronger ordinary alignment may win while the SAME cue has a
        # qualifying bounded context span. Keep that observed support only if
        # the accepted alignment still overlaps the cue, and the context span
        # passes the unchanged threshold independently.
        self._bounded_selection = (scene == self.current_index and best.start <= end-2
            and best.end >= end and any(self._scene(stop) == scene and score >=
                self._threshold(scene, self._misses >= self.recovery_after)
                for begin, stop, score in self._bounded_candidates))
        self._confirm_contextual_ending(scene, best, start, end)
        self._confirm_from_prefix(scene, best)
        target = self.current_index
        start,end = self.checkpoint_ranges[target]
        self._resumed_cue = scene == target and best.end == end and self._continues_cue()
        if self._resumed_cue and self._pending_scene != scene:
            self._pending_scene = scene
            self.confirmations = 1
            self._evidence_end = self._cue_prefix['end']
            self._evidence_time = self._cue_prefix['audio_end']
        continuing = (self._interruption_context and self._interruption_context.get('cumulative')
                      and scene == target)
        if best.end <= start or (best.end > end and not continuing):
            self._cue_prefix = None
        elif self._segments and best.start <= start and start+3 <= best.end < end:
            segment = self._segments[-1]
            heard = segment['text'].split()
            partial = self.words[start:best.end]
            offset = len(heard) - len(partial)
            if (heard[offset:] == partial and len(set(partial)) >= 3
                    and not self._prompt_words.intersection(heard[max(0, offset-3):offset])):
                context = []
                for word in self.words[max(best.start, start-4):start][::-1]:
                    i = offset - len(context) - 1
                    if i < 0 or heard[i] != word:
                        break
                    context.insert(0, word)
                self._cue_prefix = dict(end=best.end, segment_start=segment['start'],
                                        audio_end=segment['end'], offset=offset, context=context)
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
                and not (set(self._buffer[-16:]) & self._negation_words)):
            self._boundary_prefix = dict(scene=target,end=best.end,time=self._audio_time,
                                         update=self._fresh_updates,text=tuple(self._buffer))
        elif (end-start <= 6 and start+2 <= best.end < end
                and self.tracked_word_position >= start
                and not (set(self._buffer[-16:]) & self._negation_words)):
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
        if (scene == target and self._aside_prefix is not None and self._segments
                and self._effect_permissions[str(self.current_checkpoint['id'])].permits(self._buffer)[0]
                and not self._has_confirmed_aside_ending(start, end)):
            # Preserve ordinary alignment votes, while withholding a cue
            # whose first exact endpoint might still expand into conversation.
            return 1
        return count
