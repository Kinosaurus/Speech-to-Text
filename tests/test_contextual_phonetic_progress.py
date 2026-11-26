import unittest

from books_to_life.matching.effect_permission import EffectPermission
from books_to_life.matching.timely_matcher import TimelyEvidenceMatcher


def manifest(anchor, **settings):
    text = 'we walked along a quiet path then ' + anchor
    checkpoint = dict(id='last', book_id='features', checkpoint_position=1,
                      checkpoint_text=anchor, effect={}, **settings)
    return dict(book_id='features', threshold=82, stability=2, min_coverage=.8,
                pages=[dict(page=1, text=text)], checkpoints=[checkpoint])


def callback(matcher, text, time, completed=False):
    return matcher.process(text, [dict(start=0, end=time, text=text, completed=completed)])


class ContextualPhoneticProgressTests(unittest.TestCase):
    def test_grouped_sound_match_and_fuzzy_spelling_can_confirm_the_next_cue(self):
        anchor = 'the children quietly showed great patience'
        heard = 'the children quietly show great pay seance'
        tracker = TimelyEvidenceMatcher(manifest(anchor))
        tracker.explain_matches = True
        opening = 'we walked along a quiet path'

        callback(tracker, opening, 1)
        prefix = opening + ' then the children quietly showed great'
        self.assertFalse(callback(tracker, prefix, 2).triggered)
        transcript = opening + ' then ' + heard
        update = callback(tracker, transcript, 3)
        if not update.triggered:
            update = callback(tracker, transcript, 4, completed=True)
        self.assertTrue(update.triggered)
        self.assertEqual(update.checkpoint_id, 'last')
        self.assertAlmostEqual(update.score, 92.5)
        self.assertEqual(tracker._buffer[-2:], ['pay', 'seance'])
        last_word = update.cue_word_evidence[-1]
        self.assertEqual((last_word.expected, last_word.heard, last_word.kind, last_word.credit),
                         ('patience', 'pay seance', 'sound', .75))
        self.assertFalse(callback(tracker, transcript, 5, completed=True).triggered)

    def test_grouped_sound_match_keeps_exact_context_and_required_word_guards(self):
        anchor = 'the children quietly showed great patience'
        heard = 'the children quietly show great pay seance'.split()
        optional = EffectPermission(dict(checkpoint_text=anchor), .8, [])
        self.assertEqual(optional.phonetic_split_support(heard, 82), (92.5, 6, 6))
        self.assertIsNone(optional.phonetic_split_support(heard, 93))
        for word in ('patience', 'showed'):
            required = EffectPermission(dict(checkpoint_text=anchor, required_words=[word]), .8, [])
            self.assertIsNone(required.phonetic_split_support(heard, 82))
        for text in ('the child quietly show great pay seance',
                     'the children quietly show great pay attention',
                     'never the children quietly show great pay seance'):
            with self.subTest(text=text):
                self.assertIsNone(optional.phonetic_split_support(text.split(), 82))

    def test_sound_alikes_get_partial_credit_at_any_position(self):
        for anchor, heard in (
            ('curled leaves drifted across the empty garden', 'coat leaves drifted across the empty garden'),
            ('the little fern curled beside the garden gate', 'the little fern coat beside the garden gate'),
            ('beside the garden gate the little fern curled', 'beside the garden gate the little fern coat'),
        ):
            with self.subTest(anchor=anchor):
                matcher = TimelyEvidenceMatcher(manifest(anchor, stability=1, threshold=92))
                callback(matcher, 'we walked along a quiet path', 1)
                update = callback(matcher, 'we walked along a quiet path then ' + heard, 2)
                self.assertTrue(update.triggered)
                permission = EffectPermission(dict(checkpoint_text=anchor), .8, [])
                score, _, _ = permission.phonetic_phrase_support(heard.split(), 92)
                self.assertGreater(score, 92)
                self.assertLess(score, 100)
                self.assertIn('coat', matcher._buffer)

    def test_sound_alike_phrase_needs_ordered_context_and_authored_required_words(self):
        anchor = 'the little fern curled beside the garden gate'
        permission = EffectPermission(dict(checkpoint_text=anchor), .8, [])
        required = EffectPermission(dict(checkpoint_text=anchor, required_words=['curled']), .8, [])
        heard = 'the little fern coat beside the garden gate'.split()
        self.assertIsNotNone(permission.phonetic_phrase_support(heard, 82))
        self.assertIsNone(required.phonetic_phrase_support(heard, 82))
        for text in ('repeat the little fern coat beside the garden gate',
                     'the little coat garden fern beside the gate', 'coat beside gate'):
            self.assertIsNone(permission.phonetic_phrase_support(text.split(), 82))

    def test_dress_trap_overlap_and_final_devoicing_get_contextual_credit(self):
        anchor = 'the sleepy cat pads on my bed and purrs'
        heard = 'the sleepy cat pets of my bed and purse'
        matcher = TimelyEvidenceMatcher(manifest(anchor, stability=1))
        matcher.explain_matches = True
        callback(matcher, 'we walked along a quiet path', 1)
        update = callback(matcher, 'we walked along a quiet path then ' + heard, 2)
        self.assertTrue(update.triggered)
        self.assertEqual(matcher._buffer[-6], 'pets')
        self.assertIn(('pads', 'pets', 'sound', .75),
                      [(word.expected, word.heard, word.kind, word.credit)
                       for word in update.cue_word_evidence])

        permission = EffectPermission(dict(checkpoint_text=anchor), .8, [])
        required = EffectPermission(dict(checkpoint_text=anchor, required_words=['pads']), .8, [])
        self.assertIsNone(required.phonetic_phrase_support(heard.split(), 82))
        for text in ('repeat ' + heard, heard.removesuffix(' purse'), heard.replace('pets', 'pots')):
            with self.subTest(text=text):
                self.assertIsNone(permission.phonetic_phrase_support(text.split(), 82))

    def test_prior_progress_and_fresh_endpoint_reach_final_anchor_without_following_words(self):
        for anchor, heard in [('we found the little sheep', 'chip'),
                              ('she carried the winter coat', 'goat'),
                              ('he switched on the fan', 'van'),
                              ('we spotted a playful seal', 'zeal')]:
            with self.subTest(anchor=anchor):
                matcher = TimelyEvidenceMatcher(manifest(anchor))
                prefix = ' '.join(matcher.words[:-1])
                callback(matcher, 'we walked along a quiet path', 1)
                callback(matcher, prefix, 2)
                update = callback(matcher, prefix + ' ' + heard, 3)
                self.assertTrue(update.triggered)
                self.assertEqual(update.checkpoint_id, 'last')
                self.assertEqual(matcher._buffer[-1], heard)
                self.assertTrue(matcher.completed)
                self.assertFalse(callback(matcher, prefix + ' ' + heard, 4, True).triggered)

    def test_same_audio_revision_or_duplicate_cannot_add_an_independent_vote(self):
        for newer_time in (1, 2):
            matcher = TimelyEvidenceMatcher(manifest('she carried the winter coat'))
            matcher.tracked_word_position = matcher.checkpoint_ranges[0][0]
            prefix = ' '.join(matcher.words[:-1])
            callback(matcher, prefix, 1)
            first = callback(matcher, prefix + ' goat', newer_time)
            self.assertEqual(first.triggered, newer_time == 2)
            self.assertFalse(callback(matcher, prefix + ' goat', newer_time).triggered)

    def test_permission_keeps_required_word_prefix_prompt_and_recency_guards(self):
        anchor = 'she carried the winter coat'
        normal = EffectPermission(dict(checkpoint_text=anchor), .8, [])
        required = EffectPermission(dict(checkpoint_text=anchor, required_words=['coat']), .8, [])
        self.assertTrue(normal.supports_phonetic_anchor('she carried the winter goat'.split()))
        self.assertFalse(required.supports_phonetic_anchor('she carried the winter goat'.split()))
        for text in ('she carried the winter', 'she carried winter goat',
                     'repeat she carried the winter goat',
                     'she carried the winter goat and then we went home',
                     'she carried the winter cone'):
            with self.subTest(text=text):
                self.assertFalse(normal.supports_phonetic_anchor(text.split()))

    def test_cold_start_and_repeated_anchor_cannot_generate_phonetic_progress(self):
        for repeated in (False, True):
            cfg = manifest('he switched on the fan')
            cfg['checkpoints'][0].update(word_start=7, word_end=12)
            if repeated:
                cfg['pages'][0]['text'] += ' then he switched on the fan'
            matcher = TimelyEvidenceMatcher(cfg)
            matcher.tracked_word_position = 7 if repeated else 0
            matcher._buffer = 'he switched on the van'.split()
            candidates = matcher._alignment_candidates(0, len(matcher.words))
            self.assertFalse(any(s.start == 7 and s.end == 12 and s.score >= 82 for s in candidates))

    def test_omitted_endpoint_stays_off_when_reading_continues(self):
        matcher = TimelyEvidenceMatcher(manifest('she carried the winter coat'))
        prefix = ' '.join(matcher.words[:-1])
        for time, text in enumerate(['we walked along a quiet path', prefix,
                                     prefix + ' then we went home'], 1):
            self.assertFalse(callback(matcher, text, time, time == 3).triggered)


if __name__ == '__main__':
    unittest.main()
