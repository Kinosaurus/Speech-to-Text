import json
from pathlib import Path
import unittest

from checkpoint_matcher import CheckpointMatcher, normalize_text


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "examples" / "sample_story.json"


class CheckpointMatcherTests(unittest.TestCase):
    def setUp(self):
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        self.matcher = CheckpointMatcher(manifest)

    def test_normalizes_case_and_punctuation(self):
        self.assertEqual(normalize_text("Hello,  SKY!"), "hello sky")

    def test_short_partial_does_not_confirm(self):
        update = self.matcher.process("Mila found a tiny")
        self.assertEqual(update.score, 0.0)
        self.assertEqual(update.confirmations, 0)
        self.assertFalse(update.triggered)

    def test_requires_two_confirmations(self):
        text = "Mila found a tiny silver seed beside the old gate"
        first = self.matcher.process(text)
        second = self.matcher.process(text)
        self.assertFalse(first.triggered)
        self.assertTrue(second.triggered)
        self.assertEqual(second.checkpoint_id, "seed_found")

    def test_does_not_skip_to_later_checkpoint(self):
        later_text = "White clouds drifted slowly above the warm golden hill"
        first = self.matcher.process(later_text)
        second = self.matcher.process(later_text)
        self.assertFalse(first.triggered)
        self.assertFalse(second.triggered)
        self.assertEqual(self.matcher.current_checkpoint["id"], "seed_found")

    def test_all_demo_checkpoints_trigger_in_order(self):
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        triggered = []
        for transcript in manifest["demo_transcripts"]:
            update = self.matcher.process(transcript)
            if update.triggered:
                triggered.append(update.checkpoint_id)

        self.assertEqual(
            triggered,
            ["seed_found", "grass_grows", "clouds_arrive", "flower_opens"],
        )
        self.assertTrue(self.matcher.completed)


if __name__ == "__main__":
    unittest.main()
