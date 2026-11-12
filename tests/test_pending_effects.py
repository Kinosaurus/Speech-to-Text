import unittest

from books_to_life.matching.timely_matcher import TimelyEvidenceMatcher


INTRO = 'we walked along the quiet lane past the old wooden gate'
PREFIX = INTRO+' then we looked for the small'


def config(ending='puppies', later=False):
    anchor='we looked for the small '+ending
    text=INTRO+' then '+anchor
    anchors=[INTRO,anchor]
    if later:
        text+=' and the bright birds flew above the tall trees'
        anchors.append('the bright birds flew above the tall trees')
    return dict(book_id='pending',threshold=82,stability=1,min_coverage=.8,
        pages=[dict(page=1,text=text)],checkpoints=[dict(id=str(i),book_id='pending',
            checkpoint_position=i,checkpoint_text=words,effect={'effect_id':str(i)})
            for i,words in enumerate(anchors,1)])


def step(matcher,text,time,completed=False):
    return matcher.process(text,[dict(start=0,end=time,text=text,completed=completed)])


class PendingEffectTests(unittest.TestCase):
    def pending(self,ending='puppies',partial='puppy',later=False):
        matcher=TimelyEvidenceMatcher(config(ending,later))
        self.assertTrue(step(matcher,INTRO,1).triggered)
        step(matcher,PREFIX,2)
        update=step(matcher,PREFIX+' '+partial,3)
        self.assertFalse(update.triggered)
        self.assertEqual(update.effect_pending_checkpoint_id,'2')
        self.assertNotIn('2',matcher.suppressed_checkpoint_ids)
        self.assertNotIn('2',matcher.triggered_checkpoint_ids)
        return matcher

    def test_restart_recovery_is_general_and_keeps_raw_asr_tokens(self):
        for partial,ending in [('puppy','puppies'),('pony','ponies'),('leaf','leaves'),('knife','knives')]:
            with self.subTest(ending=ending):
                matcher=self.pending(ending,partial)
                full=PREFIX+' '+partial+' '+ending
                update=step(matcher,full,3.5)
                self.assertTrue(update.triggered)
                self.assertEqual(update.checkpoint_id,'2')
                self.assertEqual(matcher._buffer[-2:],[partial,ending])
                self.assertEqual(matcher.suppressed_checkpoint_ids,set())
                self.assertFalse(step(matcher,full,4).triggered)

    def test_omission_and_expiry_never_guess_the_endpoint(self):
        matcher=self.pending()
        update=step(matcher,PREFIX+' puppy',6)
        self.assertFalse(update.triggered)
        self.assertTrue(update.effect_suppressed)
        self.assertEqual(matcher.suppressed_checkpoint_ids,{'2'})
        self.assertTrue(matcher.completed)
        self.assertFalse(step(matcher,PREFIX+' puppies',7).triggered)

    def test_same_audio_revision_and_duplicates_do_not_resolve_pending(self):
        matcher=self.pending()
        partial=PREFIX+' puppy'
        fresh_updates=matcher._fresh_updates
        for _ in range(8):
            self.assertFalse(step(matcher,partial,3).triggered)
        self.assertEqual(matcher._fresh_updates,fresh_updates)
        full=partial+' puppies'
        self.assertFalse(step(matcher,full,3).triggered)
        self.assertTrue(step(matcher,full,3.5).triggered)

    def test_final_completion_can_resolve_a_partial_at_same_audio_time(self):
        matcher=self.pending()
        self.assertFalse(matcher.completed)
        self.assertIsNone(matcher.current_checkpoint)
        update=step(matcher,PREFIX+' puppy puppies',3,completed=True)
        self.assertTrue(update.triggered)
        self.assertTrue(update.completed)
        self.assertTrue(matcher.completed)

    def test_final_completion_without_endpoint_suppresses_once(self):
        matcher=self.pending()
        update=step(matcher,PREFIX+' puppy',3,completed=True)
        self.assertFalse(update.triggered)
        self.assertTrue(update.effect_suppressed)
        self.assertFalse(step(matcher,PREFIX+' puppy puppies',4,completed=True).triggered)

    def test_later_effect_is_not_stalled_or_replaced_by_pending_effect(self):
        matcher=self.pending(later=True)
        later=PREFIX+' puppy and the bright birds flew above the tall trees'
        update=step(matcher,later,4)
        self.assertTrue(update.triggered)
        self.assertEqual(update.checkpoint_id,'3')
        self.assertEqual(update.additional_suppressed_checkpoint_ids,('2',))
        self.assertEqual(matcher.suppressed_checkpoint_ids,{'2'})
        self.assertEqual(matcher.triggered_checkpoint_ids,{'1','3'})

    def test_negated_instruction_closes_pending_without_emitting(self):
        matcher=self.pending()
        update=step(matcher,PREFIX+' puppy never repeat puppies',3.5)
        self.assertFalse(update.triggered)
        self.assertTrue(update.effect_suppressed)

    def test_parent_can_complete_pending_phrase_without_replaying_effect(self):
        matcher=self.pending()
        reading=PREFIX+' puppy please repeat we looked for the small puppies'
        self.assertTrue(step(matcher,reading,3.5).triggered)
        self.assertFalse(step(matcher,reading+' we looked for the small puppies',4).triggered)

    def test_new_utterance_cannot_borrow_an_old_incomplete_prefix(self):
        matcher=self.pending()
        text='puppies'
        update=matcher.process(text,[dict(start=3,end=3.5,text=text,completed=False)])
        self.assertFalse(update.triggered)
        self.assertTrue(update.effect_suppressed)

    def interrupted(self):
        matcher = TimelyEvidenceMatcher(config())
        self.assertTrue(step(matcher, INTRO, 1).triggered)
        self.assertFalse(step(matcher, PREFIX, 2, completed=True).triggered)
        prefix = dict(start=0, end=2, text=PREFIX, completed=True)
        aside = dict(start=3, end=4, text='well', completed=False)
        update = matcher.process(PREFIX + ' well', [prefix, aside])
        self.assertEqual(update.effect_pending_checkpoint_id, '2')
        aside = dict(aside, end=5, text='well the bag is outside', completed=True)
        update = matcher.process(PREFIX + ' ' + aside['text'], [prefix, aside])
        self.assertEqual(update.effect_pending_checkpoint_id, '2')
        return matcher, prefix, aside

    def test_interrupted_pending_cue_accepts_isolated_exact_endpoint_once(self):
        matcher, prefix, aside = self.interrupted()
        finish = dict(start=22, end=23, text='puppies', completed=False)
        segments = [prefix, aside, finish]
        update = matcher.process(PREFIX + ' ' + aside['text'] + ' puppies', segments)
        self.assertTrue(update.triggered)
        self.assertEqual(update.checkpoint_id, '2')
        self.assertFalse(matcher.process(PREFIX + ' ' + aside['text'] + ' puppies', segments).triggered)

    def test_interrupted_pending_cue_rejects_endpoint_inside_conversation(self):
        matcher, prefix, aside = self.interrupted()
        talk = dict(start=22, end=23, text='the puppies are outside', completed=True)
        update = matcher.process(PREFIX + ' ' + aside['text'] + ' ' + talk['text'],
                                 [prefix, aside, talk])
        self.assertFalse(update.triggered)
        self.assertTrue(update.effect_suppressed)

    def test_missing_required_word_is_not_deferred_by_an_existing_endpoint(self):
        cfg=config('garden')
        cp=cfg['checkpoints'][1];cp['required_words']=['small']
        matcher=TimelyEvidenceMatcher(cfg)
        step(matcher,INTRO,1)
        update=step(matcher,INTRO+' then we looked for the garden',2)
        self.assertFalse(update.triggered)
        self.assertIsNone(update.effect_pending_checkpoint_id)
        self.assertTrue(update.effect_suppressed)

    def test_cold_unacquired_match_does_not_receive_pending_grace(self):
        matcher=TimelyEvidenceMatcher(config())
        update=step(matcher,PREFIX+' puppy',3)
        self.assertFalse(update.triggered)
        self.assertIsNone(update.effect_pending_checkpoint_id)
        self.assertTrue(update.effect_suppressed)

    def test_text_only_pending_has_a_bounded_fresh_update_budget(self):
        matcher=TimelyEvidenceMatcher(config())
        matcher.process(INTRO)
        matcher.process(PREFIX)
        update=matcher.process(PREFIX+' puppy')
        self.assertEqual(update.effect_pending_checkpoint_id,'2')
        for i in range(5):
            update=matcher.process(PREFIX+' puppy'+str(i))
            self.assertFalse(update.triggered)
        self.assertTrue(update.effect_suppressed)
        self.assertTrue(matcher.completed)


if __name__=='__main__':unittest.main()
