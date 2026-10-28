import unittest

from boundary_matcher import BoundaryEvidenceMatcher
from timely_matcher import TimelyEvidenceMatcher


def config():
    text='grandma has a big house with lots of steps'
    return dict(book_id='timely',threshold=82,stability=2,min_coverage=.8,
                pages=[dict(page=1,text=text)],checkpoints=[dict(id='steps',book_id='timely',
                checkpoint_position=1,checkpoint_text=text,effect={'effect_id':'steps'})])


def feed(m,text,t):
    return m.process(text,[dict(start=0,end=t,text=text,completed=False)])


class TimelyTests(unittest.TestCase):
    def test_repetition_with_supported_near_spelling_ending(self):
        old,new=BoundaryEvidenceMatcher(config()),TimelyEvidenceMatcher(config())
        for m in (old,new):feed(m,'grandma has a big house with',1)
        text='grandma has a big house with with a lot of stops'
        self.assertFalse(feed(old,text,2).triggered)
        self.assertTrue(feed(new,text,2).triggered)

    def test_scoped_recovery_threshold_uses_recent_prefix(self):
        m=TimelyEvidenceMatcher(config())
        feed(m,'grandma has a big house with lots of',1)
        for t in (2,3,4):feed(m,'unrelated speech about going outside',t)
        self.assertTrue(feed(m,'grandma has a big house with with a lot of steps',5).triggered)

    def test_no_prefix_stale_prefix_or_same_audio_cannot_supply_credit(self):
        text='grandma has a big house with with a lot of stops'
        self.assertFalse(feed(TimelyEvidenceMatcher(config()),text,2).triggered)
        for t in (1,30):
            m=TimelyEvidenceMatcher(config())
            feed(m,'grandma has a big house with',1)
            self.assertFalse(feed(m,text,t).triggered)

    def test_wrong_ending_and_prompts_do_not_get_repeat_credit(self):
        for prefix,ending in [('', 'doors'),('do not ', 'steps'),('please repeat ', 'steps')]:
            m=TimelyEvidenceMatcher(config())
            feed(m,prefix+'grandma has a big house with',1)
            self.assertFalse(feed(m,prefix+'grandma has a big house with with a lot of '+ending,2).triggered)

    def test_unrecognised_ending_is_not_guessed_from_prefix(self):
        cfg=config();cfg['pages'][0]['text']='I like to help her'
        cfg['checkpoints'][0]['checkpoint_text']='I like to help her'
        m=TimelyEvidenceMatcher(cfg)
        feed(m,'I like to',1)
        self.assertFalse(feed(m,'I like to hope for',2).triggered)

    def test_exact_prefix_before_filler_counts_only_on_next_audio(self):
        m=TimelyEvidenceMatcher(config())
        self.assertFalse(feed(m,'has a big house with a lot',1).triggered)
        self.assertFalse(feed(m,'has a big house with a lot of steps',1).triggered)
        m=TimelyEvidenceMatcher(config())
        feed(m,'has a big house with a lot',1)
        self.assertTrue(feed(m,'has a big house with a lot of steps',2).triggered)


if __name__=='__main__':unittest.main()
