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


if __name__ == "__main__":
    unittest.main()
