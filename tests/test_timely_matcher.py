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


class ContextualEndingConfirmationTests(unittest.TestCase):
    def test_authored_cue_reuses_context_only_with_new_audio_and_exact_final_word(self):
        manifest = (Path(__file__).resolve().parents[1] / "recordings/library/stories/little_mermaid"
                    / "readers/little_mermaid/checkpoints.json")
        for ending, endpoint_time, expected in [
                ("speak", 28, True), ("sneak", 28, False), ("speak", 27.4, False)]:
            with self.subTest(ending=ending, endpoint_time=endpoint_time):
                matcher = TimelyEvidenceMatcher.from_file(manifest, stability=2)
                intro = "The next thing she knew the little mermaid woke up she had the prettiest life"
                feed(matcher, intro, 9.7)
                intro += " on earth"
                feed(matcher, intro, 10.1)
                context = (intro + " and in front of her stood the handsome prince who are you asked "
                           "the prince where do you come from")
                feed(matcher, context, 25.2)
                feed(matcher, context + " the little mer", 26.8)
                prefix = context + " the little merry could not"
                self.assertFalse(feed(matcher, prefix, 27.4).triggered)
                update = feed(matcher, prefix + " " + ending, endpoint_time)
                self.assertEqual(update.triggered, expected)
                if expected:
                    self.assertEqual(update.confirmations, 2)
                    self.assertEqual(update.checkpoint_id, "mermaid_cannot_speak")


class VerifiedCueConfirmationTests(unittest.TestCase):
    def test_mermaid_waits_for_confirmation_and_revalidates_the_saved_words(self):
        manifest = (Path(__file__).resolve().parents[1] / "recordings/library/stories/little_mermaid"
                    / "readers/little_mermaid/checkpoints.json")
        opening = ("the next thing she knew the little mermaid woke up she had the prettiest "
                   "lines on earth and in front of her stood the handsome prince who are you "
                   "asked the prince where do you come from")
        prefix = opening + " i'm the little mermaid she could not "
        for ending, end_time, expected in [
                ("speak", 32.48, True), ("sleep", 32.48, False), ("speak", 38.0, False)]:
            with self.subTest(ending=ending, end_time=end_time):
                matcher = TimelyEvidenceMatcher.from_file(manifest, stability=2)
                for text, time in [
                        (opening.split(" lines on earth")[0], 8.4),
                        (opening.split(" in front")[0], 10.08),
                        (opening.split(" of her")[0], 12.32),
                        (opening, 24.08),
                        (opening + " the little mermaid", 26.32),
                        (opening + " i'm the little mermaid", 28.0)]:
                    feed(matcher, text, time)
                first = feed(matcher, prefix + "speak she could not", 30.24)
                self.assertEqual(first.confirmations, 1)
                self.assertFalse(first.triggered)
                later = prefix + ending + " she could only look at the prince with her"
                update = feed(matcher, later, end_time)
                self.assertEqual(update.checkpoint_id, "mermaid_cannot_speak")
                self.assertEqual(update.confirmations, 2)
                self.assertEqual(update.triggered, expected)
                self.assertFalse(feed(matcher, later + " deep blue eyes", end_time + 2).triggered)


class CumulativeInterruptionTests(unittest.TestCase):
    def test_authored_cue_requires_book_continuation_after_an_aside(self):
        manifest_path = (Path(__file__).resolve().parents[1] / "recordings/library/stories/little_mermaid"
                         / "readers/little_mermaid/checkpoints.json")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for checkpoint in manifest["checkpoints"]:
            checkpoint["effect_policy"] = "one_shot"
        opening = ("the next thing she knew the little mermaid woke up she had the prettiest legs on earth "
                   "and in front of her stood the handsome prince who are you asked the prince where do you come from")
        prefix = opening + " and the little mermaid"
        aside = " spoken_noise you spoken_noise where you are spoken_noise "
        for first, second, revised, expected in [
                ("could not speak she could", "only", False, True),
                ("not speak she could", "only", False, True),
                ("speak louder so i can hear you", "from the hall", False, False),
                ("not sneak she could", "only look", False, False),
                ("not speak she could", "only", True, False),
        ]:
            with self.subTest(resume=first, revised=revised):
                matcher = TimelyEvidenceMatcher(manifest, stability=2)
                feed(matcher, opening.split(" earth")[0], 9)
                self.assertTrue(feed(matcher, opening.split(" and in front")[0], 10).triggered)
                feed(matcher, opening.rsplit(" from", 1)[0], 23)
                feed(matcher, opening, 24)
                feed(matcher, prefix, 25)
                heard = prefix + aside + first
                self.assertFalse(feed(matcher, prefix + aside.rstrip(), 31).triggered)
                if first != "could not speak she could":
                    self.assertFalse(feed(matcher, prefix + aside + first.split()[0], 33).triggered)
                self.assertFalse(feed(matcher, heard, 34).triggered)
                self.assertFalse(feed(matcher, heard, 34.1).triggered)
                if revised:
                    heard = heard.replace("the little mermaid spoken", "the little maiden spoken")
                later = heard + " " + second
                update = feed(matcher, later, 35)
                self.assertEqual(update.triggered, expected)
                if expected:
                    self.assertEqual(update.checkpoint_id, "mermaid_cannot_speak")
                    self.assertEqual(update.confirmations, 2)
                self.assertFalse(feed(matcher, later + " at the prince", 36).triggered)


if __name__=='__main__':unittest.main()
