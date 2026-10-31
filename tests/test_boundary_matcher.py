import copy
import unittest

from books_to_life.matching.boundary_matcher import BoundaryEvidenceMatcher
from books_to_life.matching.split_matcher import SplitEvidenceMatcher


def config():
    return {'book_id': 'boundary-test', 'threshold': 82, 'stability': 2,
            'min_coverage': .8,
            'pages': [{'page': 1, 'text': 'alpha bravo cedar delta eagle forest'}],
            'checkpoints': [{'id': 'ending', 'book_id': 'boundary-test',
                             'checkpoint_position': 1,
                             'checkpoint_text': 'alpha bravo cedar delta eagle forest',
                             'effect': {'effect_id': 'ending'}}]}


def feed(matcher, text, end):
    return matcher.process(text, [{'start': 0, 'end': end, 'text': text,
                                   'completed': False}])


class BoundaryTests(unittest.TestCase):
    def test_final_word_uses_prefix_without_following_words(self):
        old, fixed = SplitEvidenceMatcher(config()), BoundaryEvidenceMatcher(config())
        for matcher in (old, fixed):
            self.assertFalse(feed(matcher, 'alpha bravo cedar delta eagle', 5).triggered)
        text = 'alpha bravo cedar delta eagle forest'
        self.assertFalse(feed(old, text, 6).triggered)
        self.assertTrue(feed(fixed, text, 6).triggered)
        self.assertFalse(feed(fixed, text, 7).triggered)

    def test_partial_abandoned_or_wrong_ending_never_triggers(self):
        for ending in ('please bring some water', 'alpha bravo cedar delta eagle flower'):
            m = BoundaryEvidenceMatcher(config())
            feed(m, 'alpha bravo cedar delta eagle', 5)
            self.assertFalse(feed(m, ending, 6).triggered)

    def test_duplicates_same_audio_and_expiry_cannot_supply_credit(self):
        for end in (5, 30):
            m = BoundaryEvidenceMatcher(config())
            feed(m, 'alpha bravo cedar delta eagle', 5)
            self.assertFalse(feed(m, 'alpha bravo cedar delta eagle forest', end).triggered)
        m = BoundaryEvidenceMatcher(config())
        for end in range(1, 5):
            self.assertFalse(feed(m, 'alpha bravo cedar delta eagle forest', end).triggered)

    def test_prompt_does_not_supply_boundary_credit(self):
        for prefix in ('do not', 'please repeat', 'can you say'):
            m = BoundaryEvidenceMatcher(config())
            feed(m, prefix + ' alpha bravo cedar delta eagle', 5)
            self.assertFalse(feed(m, prefix + ' alpha bravo cedar delta eagle forest', 6).triggered)

    def test_no_credit_for_jumping_over_an_unread_checkpoint(self):
        cfg = copy.deepcopy(config())
        cfg['pages'][0]['text'] += ' garden harbor island jungle kettle lemon'
        cfg['checkpoints'].append(dict(id='later', book_id='boundary-test',
                                      checkpoint_position=2,
                                      checkpoint_text='garden harbor island jungle kettle lemon',
                                      effect={'effect_id':'later'}))
        m = BoundaryEvidenceMatcher(cfg)
        feed(m, 'garden harbor island jungle kettle', 5)
        self.assertFalse(feed(m, 'garden harbor island jungle kettle lemon', 6).triggered)

    def test_checkpoint_requiring_three_votes_is_not_reduced_to_two(self):
        cfg=config()
        cfg['stability']=3
        m=BoundaryEvidenceMatcher(cfg)
        feed(m, 'alpha bravo cedar delta eagle', 5)
        self.assertFalse(feed(m, 'alpha bravo cedar delta eagle forest', 6).triggered)

    def test_ambiguity_clears_prefix_credit(self):
        m=BoundaryEvidenceMatcher(config())
        feed(m, 'alpha bravo cedar delta eagle', 5)
        m._reject_candidate(ambiguous=True)
        self.assertFalse(feed(m, 'alpha bravo cedar delta eagle forest', 6).triggered)


if __name__ == '__main__':
    unittest.main()
