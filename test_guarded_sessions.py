import unittest
from pathlib import Path

from guarded_sessions import GuardedSessions


class GuardedSessionTests(unittest.TestCase):
    def setUp(self):
        self.sessions = GuardedSessions(Path(__file__).parent / "public" / "books")
        self.attempt = self.sessions.start("little-mermaid")["attempt"]

    def update(self, text, seconds, completed=False):
        return self.sessions.update(self.attempt, text, seconds, completed)

    def test_display_requires_guarded_cue_permission(self):
        opening = ("the next thing she knew the little mermaid woke up she had "
                   "the prettiest legs on earth and in front of her stood the handsome prince "
                   "who are you asked the prince where do you come from")
        self.assertIsNone(self.update(opening.split(" earth")[0], 9)["trigger"])
        first = self.update(opening.split(" and in front")[0], 10)
        self.assertEqual(first["trigger"], "mermaid_has_legs")
        self.update(opening.rsplit(" from", 1)[0], 23)
        self.update(opening, 24)
        prefix = opening + " and the little mermaid"
        self.update(prefix, 25)
        resumed = prefix + " take your time you can keep reading when you are ready not speak she could"
        self.assertIsNone(self.update(resumed, 34)["trigger"])
        second = self.update(resumed + " only", 35)
        self.assertEqual(second["trigger"], "mermaid_cannot_speak")
        self.assertEqual([cp["status"] for cp in second["checkpoints"]], ["triggered", "triggered"])
        self.assertIsNone(self.update(resumed + " only look", 36)["trigger"])

    def test_attempts_start_fresh_and_reject_late_updates_after_close(self):
        self.sessions.close(self.attempt)
        with self.assertRaises(KeyError):
            self.update("speak", 20)
        fresh = self.sessions.start("little-mermaid")
        self.assertNotEqual(fresh["attempt"], self.attempt)
        self.assertEqual([cp["status"] for cp in fresh["checkpoints"]], ["pending", "pending"])

    def test_conversation_cannot_trigger_a_cue(self):
        first = self.update("take your time", 1)
        second = self.update("take your time you can keep reading when you are ready", 3, True)
        self.assertIsNone(first["trigger"])
        self.assertIsNone(second["trigger"])
        self.assertEqual([cp["status"] for cp in second["checkpoints"]], ["pending", "pending"])

    def test_tracking_can_reach_the_cue_without_speak(self):
        opening = ("the next thing she knew the little mermaid woke up she had "
                   "the prettiest legs on earth and in front of her stood the handsome prince "
                   "who are you asked the prince where do you come from")
        self.update(opening.split(" earth")[0], 9)
        self.update(opening.split(" and in front")[0], 10)
        self.update(opening.rsplit(" from", 1)[0], 23)
        self.update(opening, 24)
        for time, tail in enumerate(("she could only look", "she could only look at the",
                                    "she could only look at the prince with her"), 25):
            result = self.update(opening + " and the little mermaid " + tail, time)
            self.assertIsNone(result["trigger"])
        self.assertEqual(result["checkpoints"][1]["status"], "withheld")

    def test_tea_handoff_requires_a_confirmed_final_word(self):
        prefix = "yes yes yes yes said the mouse i will make us a pot of"
        for final, should_fire in [
            (prefix + " tea", True),
            (prefix + " tea is ready", False),
            (prefix + " house toad", False),
            (prefix.replace("make us", "make you") + " tea", False),
        ]:
            with self.subTest(final=final):
                attempt = self.sessions.start("tea")["attempt"]
                def feed(text, seconds, complete=False):
                    return self.sessions.update(attempt, text, seconds, complete)
                for i in range(8, len(prefix.split()) + 1):
                    feed(" ".join(prefix.split()[:i]), i + 4)
                for i, tail in enumerate((" pot", " of", " of house", " of house toad"), 20):
                    self.assertIsNone(feed(prefix + tail, i)["trigger"])
                partial = feed(prefix + " tea", 35)
                self.assertIsNone(partial["trigger"])
                self.assertTrue(partial["awaiting_handoff_final"])
                if not should_fire:
                    self.assertFalse(feed(final, 36)["awaiting_handoff_final"])
                self.assertEqual(feed(final, 40, True)["trigger"],
                                 "make_a_pot_of_tea" if should_fire else None)
                self.assertIsNone(feed(final, 41, True)["trigger"])

    def test_tea_handoff_confirms_during_continuing_reading(self):
        prefix = "yes yes yes yes said the mouse i will make us a pot of"
        for revisions in [(" tea", " tea she"), (" tea", " of house tea", " tea she"), (" tea she",)]:
            with self.subTest(revisions=revisions):
                attempt = self.sessions.start("tea")["attempt"]
                for i in range(8, len(prefix.split()) + 1):
                    self.sessions.update(attempt, " ".join(prefix.split()[:i]), i + 4, False)
                aside = (" pot", " of", " of house", " of house toad")
                for i, tail in enumerate(aside + revisions, 20):
                    result = self.sessions.update(attempt, prefix + tail, i, False)
                    self.assertIsNone(result["trigger"])
                result = self.sessions.update(attempt, prefix + " tea she put", 27, False)
                self.assertEqual(result["trigger"], "make_a_pot_of_tea")
                stove = prefix + " tea she put the teapot on the stove"
                cues = [self.sessions.update(attempt, text, second, False)["trigger"]
                        for second, text in enumerate((stove, stove + " she", stove + " she set"), 28)]
                self.assertEqual([cue for cue in cues if cue], ["teapot_on_stove"])

    def test_stray_tea_after_aside_cannot_fire_on_its_first_callback(self):
        prefix = "yes yes yes yes said the mouse i will make us a pot of"
        attempt = self.sessions.start("tea")["attempt"]
        for i in range(8, len(prefix.split()) + 1):
            self.sessions.update(attempt, " ".join(prefix.split()[:i]), i + 4, False)
        for time, suffix in [(20, " of"), (21, " of house"), (28, " tea"),
                             (30, " tea of"), (31, " tea hung")]:
            result = self.sessions.update(attempt, prefix + suffix, time, False)
            self.assertIsNone(result["trigger"])
        self.assertIsNone(self.sessions.update(attempt, prefix + " tea hung", 57, True)["trigger"])


if __name__ == "__main__":
    unittest.main()
