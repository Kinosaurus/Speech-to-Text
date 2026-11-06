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

    def test_permission_keeps_required_word_prefix_negation_and_recency_guards(self):
        anchor = 'she carried the winter coat'
        normal = EffectPermission(dict(checkpoint_text=anchor), .8, [])
        required = EffectPermission(dict(checkpoint_text=anchor, required_words=['coat']), .8, [])
        self.assertTrue(normal.supports_phonetic_anchor('she carried the winter goat'.split()))
        self.assertTrue(normal.supports_phonetic_anchor('repeat she carried the winter goat'.split()))
        self.assertFalse(required.supports_phonetic_anchor('she carried the winter goat'.split()))
        for text in ('she carried the winter', 'she carried winter goat',
                     'never repeat she carried the winter goat',
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
