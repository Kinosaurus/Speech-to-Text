import unittest

from books_to_life.matching.word_boundaries import exact_boundary_match
from books_to_life.matching.effect_permission import EffectPermission
from books_to_life.matching.timely_matcher import TimelyEvidenceMatcher


class WordBoundaryTests(unittest.TestCase):
    def test_split_points_are_general(self):
        # Exercise every split position, not a hand-authored alias per word.
        for word in ('notebook', 'snowman', 'playground', 'sunflower', 'riverside'):
            for index in range(1, len(word)):
                pieces = [word[:index], word[index:]]
                with self.subTest(word=word, index=index):
                    self.assertTrue(exact_boundary_match([word], pieces))

    def test_all_content_is_required_and_tokens_cannot_be_reused(self):
        for ref, heard in [(['notebook', 'book'], ['note', 'book']),
                           (['snowman'], ['snow']), (['snowman'], ['snow', 'men']),
                           (['snowman'], ['snow', 'old', 'man']),
                           (['hibernate'], ['hi', 'nate']),
                           (['not', 'ice'], ['notice']),
                           (['a', 'b', 'c'], ['abc']), (['abcd'], ['a', 'b', 'c', 'd'])]:
            with self.subTest(ref=ref, heard=heard):
                self.assertFalse(exact_boundary_match(ref, heard))

    def test_internal_and_final_boundaries_preserve_recency_and_negation(self):
        for anchor, heard in [
            ('we opened the red notebook', 'we opened the red note book'),
            ('she put the teapot on the stove', 'she put the tea pot on the stove'),
            ('we watched the snowman outside', 'we watched the snow man outside'),
        ]:
            permission = EffectPermission(dict(checkpoint_text=anchor), 1, [])
            with self.subTest(anchor=anchor):
                self.assertTrue(permission.permits(heard.split(), allow_word_boundaries=True)[0])
                self.assertTrue(permission.permits(('please repeat '+heard).split(), allow_word_boundaries=True)[0])
                self.assertFalse(permission.permits(('never repeat '+heard).split(), allow_word_boundaries=True)[0])
                self.assertFalse(permission.permits((heard+' and then we walked away').split(), allow_word_boundaries=True)[0])

    def test_required_words_may_split_but_cannot_disappear(self):
        cp = dict(checkpoint_text='bears hibernate from october to april', required_words=['hibernate'])
        permission = EffectPermission(cp, .8, [])
        self.assertTrue(permission.permits('bears hi bernate from october to april'.split(), allow_word_boundaries=True)[0])
        self.assertFalse(permission.permits('bears from october to april'.split(), allow_word_boundaries=True)[0])
        endpoint = EffectPermission(dict(checkpoint_text='they help it to escape from its enemies'), .8, [])
        self.assertFalse(endpoint.permits('they help it to escape from its a bird flies away'.split(), allow_word_boundaries=True)[0])
        negation = EffectPermission(dict(checkpoint_text='we will not ice the cake', required_words=['not']), .8, [])
        self.assertFalse(negation.permits('we will notice the cake'.split(), allow_word_boundaries=True)[0])

    def test_acquired_progress_accepts_split_endpoint_without_asr_rewriting(self):
        text = 'he had a hundred sheep one day he took the sheep to the riverside there was grass'
        cfg = dict(book_id='boundaries', threshold=82, stability=1, min_coverage=.8,
            pages=[dict(page=1, text=text)], checkpoints=[
                dict(id='first', book_id='boundaries', checkpoint_position=1, checkpoint_text='he had a hundred sheep', effect={}),
                dict(id='second', book_id='boundaries', checkpoint_position=2, checkpoint_text='he took the sheep to the riverside', effect={})])
        matcher = TimelyEvidenceMatcher(cfg)
        self.assertTrue(matcher.process('he had a hundred sheep').triggered)
        prefix = 'he had a hundred sheep one day he took the sheep to the'
        self.assertFalse(matcher.process(prefix).triggered)
        heard = prefix+' river side there'
        update = matcher.process(heard)
        self.assertTrue(update.triggered)
        self.assertEqual(update.checkpoint_id, 'second')
        self.assertEqual(matcher._buffer[-3:], ['river', 'side', 'there'])
        self.assertFalse(matcher.process(heard+' was grass').triggered)
        cold = TimelyEvidenceMatcher(cfg)
        update = cold.process(heard)
        self.assertFalse(update.triggered)
        self.assertTrue(update.effect_suppressed)

    def test_split_final_word_needs_no_following_book_words(self):
        text = 'he had a hundred sheep one day he took the sheep to the riverside'
        cfg = dict(book_id='end', threshold=82, stability=2, min_coverage=.8,
            pages=[dict(page=1, text=text)], checkpoints=[
                dict(id='first', book_id='end', checkpoint_position=1, checkpoint_text='he had a hundred sheep', effect={}),
                dict(id='last', book_id='end', checkpoint_position=2, checkpoint_text='he took the sheep to the riverside', effect={})])
        matcher = TimelyEvidenceMatcher(cfg)
        prefix = 'he had a hundred sheep one day he took the sheep to the'
        snapshots = ['he had a hundred', 'he had a hundred sheep',
                     'he had a hundred sheep one',
                     'he had a hundred sheep one day he took the sheep', prefix, prefix+' river side']
        effects = []
        for time, spoken in enumerate(snapshots, 1):
            update = matcher.process(spoken, [dict(start=0, end=time, text=spoken, completed=False)])
            if update.triggered: effects.append(update.checkpoint_id)
            if time < len(snapshots): self.assertNotIn('last', effects)
        spoken = snapshots[-1]
        duplicate = matcher.process(spoken, [dict(start=0, end=6, text=spoken, completed=False)])
        self.assertFalse(duplicate.triggered)
        update = matcher.process(spoken, [dict(start=0, end=7, text=spoken, completed=True)])
        if update.triggered: effects.append(update.checkpoint_id)
        self.assertEqual(effects, ['first', 'last'])
        self.assertTrue(matcher.completed)

    def test_split_candidate_requires_acquisition_and_unique_book_anchor(self):
        phrase = 'we opened the red notebook'
        for text, acquired, expected in [(phrase, False, False),
                                         (phrase, True, True),
                                         (phrase+' then '+phrase, True, False)]:
            cfg = dict(book_id='unique', pages=[dict(page=1, text=text)], checkpoints=[
                dict(id='one', book_id='unique', checkpoint_position=1, checkpoint_text=phrase,
                     word_start=0, word_end=5, effect={})])
            matcher = TimelyEvidenceMatcher(cfg)
            matcher.tracked_word_position = 4 if acquired else 0
            matcher._buffer = 'we opened the red note book'.split()
            spans = matcher._alignment_candidates(0, len(matcher.words))
            exact = [s for s in spans if s.start==0 and s.end==5 and s.score==100]
            self.assertEqual(bool(exact), expected)


if __name__ == '__main__':
    unittest.main()
