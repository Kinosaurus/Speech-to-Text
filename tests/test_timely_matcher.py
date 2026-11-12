import json
from pathlib import Path
import unittest

from books_to_life.matching.boundary_matcher import BoundaryEvidenceMatcher
from books_to_life.matching.timely_matcher import TimelyEvidenceMatcher


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

    def test_wrong_ending_and_negations_do_not_get_repeat_credit(self):
        for prefix,ending in [('', 'doors'),('do not ', 'steps'),('never repeat ', 'steps')]:
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


class SkyGardenInterruptionTests(unittest.TestCase):
    def replay(self, turns, stability=1, cumulative=False):
        manifest_path = (
            Path(__file__).resolve().parents[1]
            / "recordings/library/stories/sample/readers/demo/checkpoints.json"
        )
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        matcher = TimelyEvidenceMatcher(manifest, stability=stability)
        segments = []
        updates = []
        for start, end, text in turns:
            segments.append(dict(start=start, end=end, text=text, completed=True))
            transcript = " ".join(segment["text"] for segment in segments)
            snapshot = ([dict(start=0, end=end, text=transcript, completed=False)]
                        if cumulative else segments)
            updates.append(matcher.process(transcript, snapshot))
        return updates

    def test_child_finishes_after_parent_question(self):
        updates = self.replay([
            (0.0, 1.4, "Mila found a tiny silver"),
            (2.0, 4.5, "Take your time, what does that word say?"),
            (5.0, 6.6, "seed beside the old gate"),
            (7.0, 8.6, "seed beside the old gate"),
        ])
        self.assertEqual([update.tracked_word_position for update in updates[:3]], [5, 5, 10])
        self.assertEqual([update.triggered for update in updates], [False, False, True, False])
        self.assertEqual(updates[2].checkpoint_id, "seed_found")

    def test_parent_can_finish_after_long_pause_at_either_stability(self):
        for stability in (1, 2):
            with self.subTest(stability=stability):
                updates = self.replay([
                    (0.0, 1.4, "Mila found a tiny silver"),
                    (90.0, 91.6, "seed beside the old gate"),
                    (92.0, 93.6, "seed beside the old gate"),
                ], stability=stability)
                self.assertEqual([update.triggered for update in updates], [False, True, False])
                self.assertEqual(updates[1].checkpoint_id, "seed_found")

    def test_cumulative_parakeet_snapshot_preserves_interrupted_cue(self):
        updates = self.replay([
            (0.0, 1.4, "Mila found a tiny silver"),
            (2.0, 4.5, "Take your time, what does that word say?"),
            (90.0, 91.6, "seed beside the old gate"),
            (92.0, 93.6, "seed beside the old gate"),
        ], stability=2, cumulative=True)
        self.assertEqual([update.triggered for update in updates], [False, False, True, False])
        self.assertEqual(updates[2].checkpoint_id, "seed_found")

    def test_stray_endpoint_after_conversation_does_not_finish_cue(self):
        updates = self.replay([
            (0.0, 1.4, "Mila found a tiny silver"),
            (2.0, 4.5, "Take your time, what does that word say?"),
            (90.0, 90.5, "gate"),
        ])
        self.assertFalse(any(update.triggered for update in updates))


if __name__=='__main__':unittest.main()
