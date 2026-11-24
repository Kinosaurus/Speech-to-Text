"""Bounded next-anchor recovery without lowering global match requirements."""
from books_to_life.matching.alignment_matcher import AlignmentSpan, align_words
from books_to_life.matching.boundary_matcher import BoundaryEvidenceMatcher
from books_to_life.matching.checkpoint_matcher import fuzz
from books_to_life.matching.effect_permission import EffectPermission, similar
from books_to_life.matching.phonetic_endpoint import pronunciations
from dataclasses import replace


class TimelyEvidenceMatcher(BoundaryEvidenceMatcher):
    mode = 'experimental contextual alignment with timely anchor recovery'
    expand_default_window = False
    _permission_grace_seconds = 2.0
    _permission_grace_updates = 4
    _prompt_words = {'not', 'never', 'dont', "don't", 'say', 'repeat'}
    _negation_words = {'not', 'never', 'dont', "don't"}

    @staticmethod
    def _default_window_words(book_word_count):
        six_percent_rounded = (6 * book_word_count + 50) // 100
        return max(12, min(60, six_percent_rounded))

    def __init__(self, *args, **kwargs):
        self._pending_effect = None
        self._cue_prefix = None
        self._aside_prefix = None
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

    @property
    def hint_checkpoint_index(self):
        # Reading progress can advance before an unfinished cue's permission resolves.
        return self.current_index - 1 if self._pending_effect is not None else self.current_index

    def process(self, transcript, segments=None):
        self._resumed_cue = False
        self._aside_completed = False
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
        if self.current_index != previous_index:
            self._cue_prefix = None
            self._aside_prefix = None
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
        words = [] if self.explain_matches else None
        allowed, reason = permission.permits(self._buffer, allow_phonetic_endpoint=locally_acquired,
                                             allow_word_boundaries=locally_acquired,
                                             allow_endpoint_fragment=(previous_position > 0
                                                 and not update.skipped_checkpoint_ids and not update.recovering),
                                             allow_article_omissions=(previous_position > 0
                                                 and not update.skipped_checkpoint_ids
                                                 and self.checkpoint_ranges[previous_index][1] <= previous_position + self.window_words
                                                 and update.checkpoint_id == str(self.checkpoints[previous_index]['id'])),
                                             word_evidence=words)
        if not allowed and not update.skipped_checkpoint_ids:
            evidence = self._phonetic_phrase_support(previous_index, previous_position, update.recovering,
                                                     word_evidence=words)
            if evidence:
                allowed = True
                update = replace(update, partial_words=evidence[3])
        if not allowed and self._resumed_cue:
            # Both pieces were verified against this exact anchor in order.
            allowed, reason = permission.permits(permission.anchor, word_evidence=words)
        if allowed:
            if words:
                update = replace(update, cue_word_evidence=tuple(words))
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
        words = [] if self.explain_matches else None
        allowed = False
        if not expired and not prompted and fresh:
            allowed, _ = permission.permits(
                buffer, allow_phonetic_endpoint=True, allow_word_boundaries=True,
                allow_endpoint_fragment=not changed_segment, word_evidence=words,
            )
            if not allowed and not changed_segment:
                threshold = self._threshold(self.current_index - 1, False)
                allowed = permission.phonetic_split_support(buffer, threshold, word_evidence=words) is not None
        if allowed:
            self._pending_effect = None
            self.triggered_checkpoint_ids.add(saved.checkpoint_id)
            return replace(saved, triggered=True, effect_policy=permission.policy,
                           tracked_word_position=self.tracked_word_position, completed=self.completed,
                           partial_words=(), cue_word_evidence=tuple(words or ()))
        if expired or prompted or completed or changed_segment:
            self._close_pending()
            return replace(saved, triggered=False, effect=None, effect_suppressed=True,
                           effect_policy=permission.policy, tracked_word_position=self.tracked_word_position,
                           effect_suppression_reason='one-shot endpoint remained unsupported before its pending window closed',
                           completed=self.completed, partial_words=())
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
        if fresh:
            self._remember_aside_prefix()
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

    def _remember_aside_prefix(self):
        """Keep exact, locally acquired cue words while ASR adds an aside."""
        start, end = self.checkpoint_ranges[self.current_index]
        permission = self._effect_permissions[str(self.current_checkpoint['id'])]
        if (not self._segments or permission.policy != 'one_shot'
                or not 0 < start <= self.tracked_word_position < end):
            self._aside_prefix = None
            return
        segment = self._segments[-1]
        words = segment['text'].split()
        for stop in range(end - 1, max(start + 2, end - 4), -1):
            head = self.words[start:stop]
            if words[-len(head):] != head or len(set(head)) < 3:
                continue
            if (self._prompt_words.intersection(words[-len(head)-3:])
                    or sum(self.words[i:i+len(head)] == head for i in range(len(self.words)-len(head)+1)) != 1):
                return
            prior = self._aside_prefix
            offset = len(words) - len(head)
            if prior is None or (segment['start'], offset, stop) != prior[:3]:
                self._aside_prefix = (segment['start'], offset, stop, segment['end'])
            return

    def _aside_continuation(self, start, end):
        """Return whether an aside is underway and whether its cue has resumed."""
        if self._aside_prefix is None:
            return False, False
        segment_start, offset, stop, observed_at = self._aside_prefix
        if not 0 < self._audio_time - observed_at <= 12:
            return False, False
        owner = next((i for i, segment in enumerate(self._segments)
                      if segment['start'] == segment_start), None)
        if owner is None:
            return False, False
        first = self._segments[owner]['text'].split()
        tail_start = offset + stop - start
        if first[offset:tail_start] != self.words[start:stop]:
            return False, False
        tail = first[tail_start:] + [word for segment in self._segments[owner+1:]
                                     for word in segment['text'].split()]
        suffix = self.words[stop:end]
        if (len(tail) < 2 or similar(suffix[0], tail[0])
                or len(tail) > self.transcript_words):
            return False, False
        if self._prompt_words.intersection(tail):
            return False, False
        # Require the entire missing suffix, including its exact last word.
        # Two exact following book words corroborate the resumed reading.
        # A homophone in the surrounding text can supply the third word.
        context = self.words[end:end+3]
        for i in range(self.minimum_words, len(tail) - len(suffix) - 2):
            after = i + len(suffix)
            heard = tail[after:after+3]
            if tail[i:after] != suffix or len(context) != 3:
                continue
            exact = sum(a == b for a, b in zip(context, heard))
            if exact >= 2 and all(a == b or set(pronunciations(a)).intersection(pronunciations(b))
                                  for a, b in zip(context, heard)):
                return True, True
        return True, False

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
        if recovering and scene == self.current_index and self._article_omission_support():
            recovering = False
        return super()._threshold(scene, recovering)

    def _article_omission_support(self, *, include_partial=False, word_evidence=None):
        if self.tracked_word_position <= 0:
            return None
        _, end = self.checkpoint_ranges[self.current_index]
        if end > self.tracked_word_position + self.window_words:
            return None
        return self._effect_permissions[str(self.current_checkpoint['id'])].article_omission_support(
            self._buffer, include_partial=include_partial, word_evidence=word_evidence,
        )

    def _phonetic_phrase_support(self, index, position, recovering, *, word_evidence=None):
        start, end = self.checkpoint_ranges[index]
        if position <= 0 or end > position + self.window_words:
            return None
        anchor = self.words[start:end]
        if sum(self.words[i:i + len(anchor)] == anchor for i in range(len(self.words) - len(anchor) + 1)) != 1:
            return None
        permission = self._effect_permissions[str(self.checkpoints[index]['id'])]
        evidence = permission.phonetic_phrase_support(
            self._buffer, self._threshold(index, recovering), include_partial=True, word_evidence=word_evidence,
        )
        if evidence and evidence[1] >= min(self.minimum_words, len(anchor)):
            return evidence
        return None

    def _alignment_candidates(self, low, high):
        candidates = self._cue_alignment_candidates(low, high)
        start, end = self.checkpoint_ranges[self.current_index]
        waiting, self._aside_completed = self._aside_continuation(start, end)
        if self._aside_completed and low <= start < end <= high:
            candidates.append(AlignmentSpan(start, end, 100.0, end-start, end-start))
        elif waiting and not self._effect_permissions[str(self.current_checkpoint['id'])].supports_anchor(self._buffer)[0]:
            candidates = [span for span in candidates if self._scene(span.end) != self.current_index]
        # A short match can establish nearby progress. For a large jump,
        # require either more matching words or evidence inside the target cue.
        return [span for span in candidates if self._supports_forward_jump(span)]

    def _supports_forward_jump(self, span):
        scene = self._scene(span.end)
        if (span.matched_words >= 2 * self.minimum_words
                or (scene <= self.current_index + 1
                    and span.start <= self.tracked_word_position + self.window_words)):
            return True
        if scene < self.current_index:
            return False
        _, cue_end = self.checkpoint_ranges[scene]
        return span.start <= cue_end - self.minimum_words

    def _cue_alignment_candidates(self, low, high):
        candidates = super()._alignment_candidates(low, high)
        start, end = self.checkpoint_ranges[self.current_index]
        anchor = self.words[start:end]
        if low <= start < end <= high:
            article_words = [] if self.explain_matches else None
            phonetic_words = [] if self.explain_matches else None
            support = self._article_omission_support(include_partial=True, word_evidence=article_words)
            phonetic = self._phonetic_phrase_support(
                self.current_index, self.tracked_word_position, self._recovering,
                word_evidence=phonetic_words,
            )
            if phonetic:
                candidates.append(AlignmentSpan(
                    start, end, *phonetic[:3], required_confirmations=1 if support else None,
                    partial_words=phonetic[3], word_evidence=tuple(enumerate(phonetic_words or (), start)),
                ))
            elif support:
                matched, total, partial = support
                candidates.append(AlignmentSpan(
                    start, end, 100 * matched / total, matched, total, required_confirmations=1,
                    partial_words=partial, word_evidence=tuple(enumerate(article_words or (), start)),
                ))
        if self._continues_cue() and low <= self._cue_prefix['end'] < end <= high:
            candidates.append(AlignmentSpan(start, end, 100.0, len(anchor), len(anchor)))
        # Reading progress and effect permission share contextual phonetic
        # endpoint evidence. Otherwise a valid endpoint can age out while the
        # spelling-only alignment waits for following sentence words.
        endpoint_words = [] if self.explain_matches else None
        if (self.tracked_word_position > 0 and self.tracked_word_position >= start
                and low <= start < end <= high and len(anchor) >= self.minimum_words
                and sum(self.words[i:i+len(anchor)] == anchor
                        for i in range(len(self.words)-len(anchor)+1)) == 1
                and (partial := self._effect_permissions[str(self.current_checkpoint['id'])]
                    .supports_phonetic_anchor(self._buffer, include_partial=True, word_evidence=endpoint_words))):
            # Give the uncertain endpoint 0.75 word credit. Normal thresholds,
            # ambiguity checks and independent confirmations still apply.
            if endpoint_words:
                endpoint_words[-1] = replace(endpoint_words[-1], credit=partial[0][2])
            candidates.append(AlignmentSpan(start, end, 100*(len(anchor)-.25)/len(anchor),
                                            len(anchor), len(anchor), partial_words=partial,
                                            word_evidence=tuple(enumerate(endpoint_words or (), start))))
        # A complete anchor with different spacing can reach its endpoint without waiting
        # for the next sentence. Only the acquired NEXT region is eligible,
        # and repeated anchors cannot manufacture a unique position.
        split_words = [] if self.explain_matches else None
        if (self.tracked_word_position > 0 and self.tracked_word_position >= start
                and low <= start < end <= high
                and sum(self.words[i:i+len(anchor)] == anchor
                        for i in range(len(self.words)-len(anchor)+1)) == 1):
            permission = self._effect_permissions[str(self.current_checkpoint['id'])]
            score = permission.word_boundary_score(self._buffer, word_evidence=split_words)
            if score is not None:
                # Count book words after grouping and preserve the original ASR tokens.
                candidates.append(AlignmentSpan(start, end, score, len(anchor), len(anchor),
                                                word_evidence=tuple(enumerate(split_words or (), start))))
        if not self._live_prefix(self.current_index) or not self._ending_supported():
            return candidates
        # Only add a next-endpoint candidate. Preserve the original ASR buffer;
        # collapsing adjacent repeats cannot create global progress elsewhere.
        indices = [i for i, word in enumerate(self._buffer) if i == 0 or word != self._buffer[i - 1]]
        words = [self._buffer[i] for i in indices]
        if len(words) == len(self._buffer):
            return candidates
        end = self.checkpoint_ranges[self.current_index][1]
        for length in {len(words), max(self.minimum_words,len(words)//2),
                       self.minimum_words, min(len(words),self.minimum_words+3)}:
            candidates.extend(s for s in align_words(words[-length:],self.words[low:high],low,
                                                     self.minimum_words,self._minimum_coverage, indices[-length:],
                                                     explain=self.explain_matches)
                              if s.end == end)
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

    def _confirm_candidate(self, scene, best):
        target = self.current_index
        start,end = self.checkpoint_ranges[target]
        self._resumed_cue = scene == target and (
            (best.end == end and self._continues_cue()) or self._aside_completed)
        if self._resumed_cue and self._pending_scene != scene:
            prefix_end, evidence_time = (self._aside_prefix[2:] if self._aside_completed
                                         else (self._cue_prefix['end'], self._cue_prefix['audio_end']))
            self._pending_scene = scene
            self.confirmations = 1
            self._evidence_end = prefix_end
            self._evidence_time = evidence_time
        if best.end <= start or best.end > end:
            self._cue_prefix = None
        elif self._segments and best.start <= start and start+3 <= best.end < end:
            segment = self._segments[-1]
            heard = segment['text'].split()
            partial = self.words[start:best.end]
            offset = len(heard) - len(partial)
            if (heard[offset:] == partial and len(set(partial)) >= 3
                    and not self._prompt_words.intersection(heard[max(0, offset-3):offset])):
                self._cue_prefix = dict(end=best.end, segment_start=segment['start'],
                                        audio_end=segment['end'], offset=offset)
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
