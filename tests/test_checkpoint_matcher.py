import json
from pathlib import Path
import unittest

from books_to_life.matching.checkpoint_matcher import CheckpointMatcher, normalize_text


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "recordings/library/stories/sample/readers/demo/checkpoints.json"


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
        self.assertEqual(second.checkpoint_position, 1)

    def test_numeric_checkpoint_schema_preserves_effect_payload(self):
        effect = {
            "visual": "grass_and_lamb.gif",
            "visual_delay": 500,
            "sound": "lamb.wav",
            "sound_delay": 1000,
        }
        matcher = CheckpointMatcher({
            "book_id": 1,
            "checkpoints": [{
                "id": 1,
                "book_id": 1,
                "checkpoint_position": 1,
                "checkpoint_text": "mary had a little lamb",
                "effect": effect,
            }],
        })
        self.assertFalse(matcher.process("Mary had a little lamb!").triggered)
        update = matcher.process("Mary had a little lamb!")
        self.assertTrue(update.triggered)
        self.assertEqual(update.effect, effect)
        self.assertEqual(update.checkpoint_position, 1)
        self.assertTrue(update.completed)
        self.assertFalse(matcher.process("Mary had a little lamb!").triggered)

    def test_positions_control_order_without_reordering_input(self):
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        manifest["checkpoints"].reverse()
        matcher = CheckpointMatcher(manifest, stability=1)
        positions = []
        for checkpoint in sorted(manifest["checkpoints"], key=lambda item: item["checkpoint_position"]):
            update = matcher.process(checkpoint["checkpoint_text"])
            self.assertTrue(update.triggered)
            positions.append(update.checkpoint_position)
        self.assertEqual(positions, [1, 2, 3, 4])
        self.assertEqual(manifest["checkpoints"][0]["checkpoint_position"], 4)

    def test_rejects_invalid_checkpoint_records(self):
        cases = [
            ("checkpoint_position", 0),
            ("checkpoint_position", True),
            ("checkpoint_position", "1"),
            ("checkpoint_text", "   "),
            ("checkpoint_text", 123),
            ("book_id", "another-book"),
            ("effect", "soft_chime"),
        ]
        for field, value in cases:
            with self.subTest(field=field, value=value):
                manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
                manifest["checkpoints"][0][field] = value
                with self.assertRaises(ValueError):
                    CheckpointMatcher(manifest)

    def test_rejects_duplicate_positions_and_ids(self):
        for field in ("id", "checkpoint_position"):
            with self.subTest(field=field):
                manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
                manifest["checkpoints"][1][field] = manifest["checkpoints"][0][field]
                with self.assertRaises(ValueError):
                    CheckpointMatcher(manifest)

    def test_rejects_invalid_effect_delays(self):
        for field in ("visual_delay", "sound_delay"):
            for value in (-1, 0.5, "500", True, None):
                with self.subTest(field=field, value=value):
                    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
                    manifest["checkpoints"][0]["effect"][field] = value
                    with self.assertRaises(ValueError):
                        CheckpointMatcher(manifest)

    def test_accepts_null_assets_and_omitted_delays(self):
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        manifest["checkpoints"][0]["effect"] = {"visual": None, "sound": None}
        matcher = CheckpointMatcher(manifest, stability=1)
        update = matcher.process(manifest["checkpoints"][0]["checkpoint_text"])
        self.assertTrue(update.triggered)
        self.assertEqual(update.effect, {"visual": None, "sound": None})

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
