import unittest

from books_to_life.matching.timely_matcher import TimelyEvidenceMatcher
from books_to_life.matching.effect_permission import EffectPermission
from books_to_life.matching.alignment_matcher import AlignmentSpan


def manifest(text, anchors, **settings):
    return dict(book_id='effects', threshold=82, stability=1, min_coverage=.8,
        pages=[dict(page=1, text=text)], checkpoints=[dict(id=str(i), book_id='effects',
            checkpoint_position=i, checkpoint_text=anchor, effect={'effect_id': str(i)}, **settings)
            for i, anchor in enumerate(anchors, 1)])


class EffectPermissionTests(unittest.TestCase):
    def test_omitted_endpoint_advances_progress_without_emitting_effect(self):
        cfg = manifest('they help it to escape from its enemies a bird flies away',
                       ['they help it to escape from its enemies'])
        matcher = TimelyEvidenceMatcher(cfg)
        update = matcher.process('they help it to escape from its a bird flies away')
        self.assertFalse(update.triggered)
        self.assertTrue(update.effect_suppressed)
        self.assertIsNone(update.effect)
        self.assertTrue(matcher.completed)
        self.assertEqual(matcher.triggered_checkpoint_ids, set())
        self.assertEqual(matcher.suppressed_checkpoint_ids, {'1'})
        self.assertFalse(matcher.process(cfg['pages'][0]['text']).triggered)

    def test_required_action_word_cannot_be_replaced_by_date_context(self):
        cp = dict(checkpoint_text='bears hibernate from October to April', required_words=['hibernate'])
        permission = EffectPermission(cp, .8, [])
        self.assertFalse(permission.permits('bears from october to april'.split())[0])
        self.assertTrue(permission.permits('bears hibernate from october to april'.split())[0])

    def test_suppressed_scene_does_not_stall_next_effect(self):
        cfg = manifest('the bear sleeps in a warm cave then the little bird flies into the blue sky',
            ['the bear sleeps in a warm cave', 'the little bird flies into the blue sky'])
        matcher = TimelyEvidenceMatcher(cfg)
        first = matcher.process('the bear sleeps in a warm then the little bird flies')
        self.assertTrue(first.effect_suppressed)
        self.assertEqual(matcher.current_index, 1)
        second = matcher.process('then the little bird flies into the blue sky')
        self.assertTrue(second.triggered)
        self.assertEqual(second.checkpoint_id, '2')
        self.assertEqual(matcher.triggered_checkpoint_ids, {'2'})
        self.assertEqual(matcher.suppressed_checkpoint_ids, {'1'})

    def test_genuine_skip_emits_supported_later_effect_without_replaying_skipped_one(self):
        first = 'the small frog jumped into the pond'
        second = 'the little bird landed on the old fence'
        matcher = TimelyEvidenceMatcher(manifest(first+' then '+second, [first, second]))
        update = matcher.process(second)
        self.assertTrue(update.triggered)
        self.assertEqual(update.checkpoint_id, '2')
        self.assertEqual(update.skipped_checkpoint_ids, ('1',))
        self.assertEqual(matcher.triggered_checkpoint_ids, {'2'})
        self.assertEqual(matcher.suppressed_checkpoint_ids, set())

    def test_ambience_can_explicitly_catch_up(self):
        cfg = manifest('they help it to escape from its enemies a bird flies away',
                       ['they help it to escape from its enemies'], effect_policy='ambience')
        update = TimelyEvidenceMatcher(cfg).process('they help it to escape from its a bird flies away')
        self.assertTrue(update.triggered)
        self.assertEqual(update.effect_policy, 'ambience')

    def test_inflections_and_minor_spelling_variants_are_retained(self):
        for anchor, spoken in [('make very fine patterns', 'make very fine pattern'),
                               ('a bit of the wing', 'a bit of wings'),
                               ('put the teapot on the stove', 'put the key pot on the stove'),
                               ('with lots of steps', 'with lots of stops')]:
            self.assertTrue(EffectPermission(dict(checkpoint_text=anchor), .8, []).permits(spoken.split())[0])

    def test_old_endpoint_and_negated_instruction_cannot_grant_permission(self):
        permission = EffectPermission(dict(checkpoint_text='the small frog jumped into the pond'), .8, [])
        for spoken in ['do not say the small frog jumped into the pond',
                       'never repeat the small frog jumped into the pond',
                       "don't say the small frog jumped into the pond",
                       'the small frog jumped into the pond and then we talked about another animal']:
            self.assertFalse(permission.permits(spoken.split())[0])

    def test_positive_coaching_uses_the_same_content_checks_as_reading(self):
        permission = EffectPermission(dict(checkpoint_text='the small frog jumped into the pond',
                                           required_words=['jumped']), .8, [])
        for prefix in ('can you say', 'please repeat', 'she said', 'he asked'):
            self.assertTrue(permission.permits((prefix+' the small frog jumped into the pond').split())[0])
            self.assertFalse(permission.permits((prefix+' the small frog jumped into the').split())[0])
            self.assertFalse(permission.permits((prefix+' the small frog into the pond').split())[0])

    def test_phonetic_endpoint_requires_acquisition_and_entire_exact_prefix(self):
        permission = EffectPermission(dict(checkpoint_text='covered with very small scales'), .8, [])
        spoken = 'they are covered with very small cells it is'.split()
        self.assertFalse(permission.permits(spoken)[0])
        self.assertTrue(permission.permits(spoken, allow_phonetic_endpoint=True)[0])
        for text in ['covered with small cells', 'covered with really small cells',
                     'not covered with very small cells', 'covered with very small birds',
                     'covered with very small coils',
                     'covered with very small cells and we moved far away']:
            with self.subTest(text=text):
                self.assertFalse(permission.permits(text.split(), allow_phonetic_endpoint=True)[0])

    def test_phonetic_endpoint_cannot_replace_required_words_or_missing_endpoints(self):
        cases = [
            (dict(checkpoint_text='covered with very small scales', required_words=['scales']),
             'covered with very small cells'),
            (dict(checkpoint_text='bears hibernate from October to April', required_words=['hibernate']),
             'bears from october to april'),
            (dict(checkpoint_text='they help it to escape from its enemies'),
             'they help it to escape from its a bird flies away'),
            (dict(checkpoint_text='covered with very small scales'), 'covered with very small'),
        ]
        for checkpoint, text in cases:
            with self.subTest(text=text):
                self.assertFalse(EffectPermission(checkpoint, .8, []).permits(
                    text.split(), allow_phonetic_endpoint=True)[0])

    def test_phonetic_endpoint_rejects_short_and_repetitive_anchor_context(self):
        for anchor, text in [('very small scales', 'very small cells'),
                             ('very very very small scales', 'very very very small cells')]:
            with self.subTest(anchor=anchor):
                self.assertFalse(EffectPermission(dict(checkpoint_text=anchor), .8, []).permits(
                    text.split(), allow_phonetic_endpoint=True)[0])

    def test_acquired_checkpoint_accepts_variant_without_rewriting_transcript(self):
        prefix = ('we admire the brilliant colours of their wings '
                  'then we see that they are covered with very small')
        text = prefix + ' scales it is these scales which have colour'
        cfg = manifest(text, ['the brilliant colours of their wings', 'covered with very small scales'])
        matcher = TimelyEvidenceMatcher(cfg)
        self.assertTrue(matcher.process('we admire the brilliant colours of their wings').triggered)
        self.assertFalse(matcher.process(prefix).triggered)
        heard = prefix + ' cells it is'
        update = matcher.process(heard)
        self.assertTrue(update.triggered)
        self.assertEqual(update.checkpoint_id, '2')
        self.assertIn('cells', matcher._buffer)
        self.assertNotIn('scales', matcher._buffer)
        self.assertFalse(matcher.process(heard + ' these cells which have colour').triggered)

        cold = TimelyEvidenceMatcher(cfg)
        update = cold.process(heard)
        self.assertFalse(update.triggered)
        self.assertTrue(update.effect_suppressed)

    def test_phonetic_endpoint_applies_to_unrelated_words_without_metadata(self):
        for anchor, heard in [
            ('the painted surface felt rough', 'the painted surface felt ruff'),
            ('the arrow went straight through', 'the arrow went straight threw'),
            ('children waited in the queue', 'children waited in the cue'),
            ('she watched the final scene', 'she watched the final seen'),
            ('the workers checked its weight', 'the workers checked its wait'),
        ]:
            with self.subTest(anchor=anchor):
                permission = EffectPermission(dict(checkpoint_text=anchor), .8, [])
                self.assertFalse(permission.permits(heard.split())[0])
                self.assertTrue(permission.permits(heard.split(), allow_phonetic_endpoint=True)[0])

    def test_invalid_policy_and_required_words_fail_at_manifest_load(self):
        for settings in [dict(effect_policy='unknown'), dict(required_words='hibernate'),
                         dict(required_words=['not in the anchor'])]:
            with self.assertRaises(ValueError):
                TimelyEvidenceMatcher(manifest('the frog jumped into the pond',
                    ['the frog jumped into the pond'], **settings))

    def test_near_tied_acquired_endpoint_wins_without_promoting_unrelated_text(self):
        text = 'we walk past the gate all that she gets is a bit of the wing'
        matcher = TimelyEvidenceMatcher(manifest(text, ['a bit of the wing']))
        start, end = matcher.checkpoint_ranges[0]
        matcher.tracked_word_position = start
        matcher._buffer = 'all that she gets is a bit of wings'.split()
        short = AlignmentSpan(start-4, end-1, 93.75, 8, 9)
        reached = AlignmentSpan(start-4, end, 93.60, 8, 9)
        self.assertEqual(matcher._select_candidate([short, reached]), reached)
        matcher._buffer = 'unrelated speech with no endpoint'.split()
        self.assertEqual(matcher._select_candidate([short, reached]), short)
        matcher._buffer = 'all that she gets is a bit of wings'.split()
        matcher.tracked_word_position = 0
        self.assertEqual(matcher._select_candidate([short, reached]), short)
        matcher.tracked_word_position = start
        lower = AlignmentSpan(start-4, end, 92.9, 8, 9)
        self.assertEqual(matcher._select_candidate([short, lower]), short)

    def test_short_anchor_uses_unique_prior_book_context_on_new_audio_only(self):
        text = 'we walk past the gate all that she gets is a bit of the wing'
        cfg = manifest(text, ['a bit of the wing'])
        cfg['stability'] = 2
        for next_time, should_fire in [(2, True), (1, False), (30, False)]:
            matcher = TimelyEvidenceMatcher(cfg)
            matcher.tracked_word_position = matcher.checkpoint_ranges[0][0]
            prefix = 'we walk past the gate all that she gets is a bit'
            matcher.process(prefix, [dict(start=0, end=1, text=prefix, completed=False)])
            full = prefix + ' of wings'
            update = matcher.process(full, [dict(start=0, end=next_time, text=full, completed=False)])
            self.assertEqual(update.triggered, should_fire)

    def test_short_generic_prefix_without_acquired_position_has_no_extra_vote(self):
        text = 'we walk past the gate all that she gets is a bit of the wing'
        cfg = manifest(text, ['a bit of the wing']); cfg['stability'] = 2
        matcher = TimelyEvidenceMatcher(cfg)
        prefix = 'all that she gets is a bit'
        matcher.process(prefix, [dict(start=0, end=1, text=prefix, completed=False)])
        full = prefix + ' of wings'
        self.assertFalse(matcher.process(full, [dict(start=0, end=2, text=full, completed=False)]).triggered)

    def test_repeated_book_context_cannot_supply_short_anchor_credit(self):
        text = 'she gets is a bit then we walk past the gate all that she gets is a bit of the wing'
        matcher = TimelyEvidenceMatcher(manifest(text, ['a bit of the wing']))
        start, end = matcher.checkpoint_ranges[0]
        matcher.tracked_word_position = start
        matcher._buffer = 'all that she gets is a bit'.split()
        matcher._confirm_candidate(-1, AlignmentSpan(start-5, start+2, 100, 7, 7))
        self.assertIsNone(matcher._boundary_prefix)

    def test_short_anchor_confirmation_after_real_forward_progress(self):
        text = ('we walked along a quiet path and saw an old sign '
                'the note said all that she gets is a bit of the wing')
        cfg = manifest(text, ['we walked along a quiet path', 'a bit of the wing'])
        cfg['stability'] = 2
        matcher = TimelyEvidenceMatcher(cfg)
        prefix = 'we walked along a quiet path and saw an old sign the note said all that she gets is'
        snapshots = ['we walked along a quiet', 'we walked along a quiet path',
                     prefix, prefix+' a', prefix+' a bit', prefix+' a bit of wings']
        effects = []
        for time, spoken in enumerate(snapshots, 1):
            update = matcher.process(spoken, [dict(start=0, end=time, text=spoken, completed=False)])
            if update.triggered:
                effects.append((update.checkpoint_id, time))
        self.assertEqual(effects, [('1', 2), ('2', 6)])


if __name__ == '__main__':
    unittest.main()
