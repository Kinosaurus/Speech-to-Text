import copy
import json
from pathlib import Path
import unittest

from alignment_matcher import AlignmentMatcher
from checkpoint_matcher import normalize_text


ROOT = Path(__file__).resolve().parents[1]


def sample():
    return json.loads((ROOT / "examples/sample_story.json").read_text(encoding="utf-8"))


def segment(text, end=1, completed=False, start=0):
    return [{"start": start, "end": end, "text": text, "completed": completed}]


class AlignmentMatcherTests(unittest.TestCase):
    def test_original_demo_errors_still_trigger_all_scenes(self):
        manifest = sample()
        matcher = AlignmentMatcher(manifest)
        events = [update.checkpoint_id for text in manifest["demo_transcripts"]
                  if (update := matcher.process(text)).triggered]
        self.assertEqual(events, [cp["id"] for cp in manifest["checkpoints"]])

    def test_following_sentence_recovers_a_completely_missed_anchor(self):
        matcher = AlignmentMatcher(sample())
        first = "She carried it carefully into the quiet garden"
        self.assertFalse(matcher.process(first).triggered)
        update = matcher.process(first + " and pressed it into the warm soil")
        self.assertTrue(update.triggered)
        self.assertEqual(update.checkpoint_id, "seed_found")
        self.assertEqual(update.page, 1)
        self.assertGreater(update.tracked_word_position, matcher.checkpoint_ranges[0][1])

    def test_one_continuous_snapshot_selects_latest_ambience_without_catchup_burst(self):
        manifest = sample()
        matcher = AlignmentMatcher(manifest)
        text = " ".join(page["text"] for page in manifest["pages"][:2])
        first = matcher.process(text, segment(text))
        self.assertFalse(first.triggered)
        update = matcher.process(text, segment(text, completed=True))
        self.assertTrue(update.triggered)
        self.assertEqual(update.checkpoint_id, "grass_grows")
        self.assertEqual(update.skipped_checkpoint_ids, ("seed_found",))
        self.assertEqual(update.effect, manifest["checkpoints"][1]["effect"])
        self.assertEqual(matcher.triggered_checkpoint_ids, {"grass_grows"})

    def test_growing_continuous_transcript_passes_every_checkpoint(self):
        manifest = sample()
        matcher = AlignmentMatcher(manifest)
        words = normalize_text(" ".join(page["text"] for page in manifest["pages"])).split()
        events = []
        positions = []
        for length in range(1, len(words) + 1):
            update = matcher.process(" ".join(words[:length]))
            positions.append(update.tracked_word_position)
            if update.triggered:
                events.append(update.checkpoint_id)
        self.assertEqual(events, [cp["id"] for cp in manifest["checkpoints"]])
        self.assertEqual(positions, sorted(positions))

    def test_small_text_chunks_are_retained_until_they_form_a_passage(self):
        matcher = AlignmentMatcher(sample(), stability=1)
        chunks = ["Mila found", "a tiny silver", "seed beside the old gate"]
        updates = [matcher.process(text) for text in chunks]
        self.assertFalse(updates[0].triggered)
        self.assertFalse(updates[1].triggered)
        self.assertTrue(updates[2].triggered)

    def test_duplicate_text_does_not_manufacture_confirmation(self):
        matcher = AlignmentMatcher(sample())
        text = sample()["checkpoints"][0]["checkpoint_text"]
        first = matcher.process(text)
        for _ in range(5):
            update = matcher.process(text)
            self.assertTrue(update.duplicate)
            self.assertFalse(update.triggered)
            self.assertEqual(update.confirmations, first.confirmations)

    def test_duplicate_segment_and_rolling_response_do_not_confirm(self):
        matcher = AlignmentMatcher(sample())
        text = sample()["checkpoints"][0]["checkpoint_text"]
        earlier = {"start": 0, "end": 1, "text": "hello", "completed": True}
        latest = {"start": 1, "end": 3, "text": text, "completed": False}
        first = matcher.process(text, [earlier, latest])
        duplicate = matcher.process(text, [latest])
        self.assertTrue(duplicate.duplicate)
        self.assertEqual(duplicate.confirmations, first.confirmations)
        final = matcher.process(text, [{**latest, "completed": True}])
        self.assertTrue(final.triggered)

    def test_partial_revision_replaces_text_instead_of_appending_it(self):
        matcher = AlignmentMatcher(sample())
        wrong = "Mila found a tiny silver seat beside the old gate"
        right = "Mila found a tiny silver seed beside the old gate"
        matcher.process(wrong, segment(wrong))
        update = matcher.process(right, segment(right, end=2))
        self.assertTrue(update.triggered)
        self.assertEqual(matcher._buffer, normalize_text(right).split())

    def test_expiring_old_segments_outside_buffer_is_not_new_evidence(self):
        matcher = AlignmentMatcher(sample())
        text = sample()["checkpoints"][0]["checkpoint_text"]
        history = [{"start": i, "end": i + 1, "text": "unrelated conversation about assorted objects",
                    "completed": True} for i in range(9)]
        latest = {"start": 9, "end": 10, "text": text, "completed": False}
        first = matcher.process(text, history + [latest])
        for length in (8, 7, 6, 5):
            update = matcher.process(text, history[-length:] + [latest])
            self.assertTrue(update.duplicate)
            self.assertFalse(update.triggered)
            self.assertEqual(update.confirmations, first.confirmations)
        update = matcher.process(text, [{**latest, "completed": True}])
        self.assertTrue(update.triggered)

    def test_fewer_words_substitutions_and_extra_words_are_tolerated(self):
        matcher = AlignmentMatcher(sample(), stability=1)
        update = matcher.process("Mila found a silver seat beside the old gate she carried it carefully")
        self.assertTrue(update.triggered)
        self.assertEqual(update.checkpoint_id, "seed_found")

    def test_lost_tracking_expands_past_three_missed_checkpoints(self):
        manifest = sample()
        manifest["alignment"].update(window_words=12, recovery_after=1)
        matcher = AlignmentMatcher(manifest)
        text = manifest["pages"][3]["text"]
        events = []
        for end in range(1, 10):
            update = matcher.process(text, segment(text, end=end))
            if update.triggered:
                events.append(update)
                break
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].checkpoint_id, "flower_opens")
        self.assertTrue(events[0].recovering)
        self.assertEqual(events[0].skipped_checkpoint_ids,
                         ("seed_found", "grass_grows", "clouds_arrive"))
        self.assertTrue(matcher.completed)

    def test_repeated_phrase_waits_for_distinctive_surrounding_text(self):
        anchor = "The stars shone brightly above us"
        manifest = {
            "book_id": 1,
            "pages": [
                {"page": 1, "text": anchor + ". Ancient oak branches sheltered the sleeping animals."},
                {"page": 2, "text": anchor + ". Silver waves splashed against the empty lighthouse."},
            ],
            "checkpoints": [
                {"id": page, "book_id": 1, "checkpoint_position": page, "page": page,
                 "checkpoint_text": anchor, "effect": {"effect_id": f"scene_{page}"}}
                for page in (1, 2)
            ],
        }
        matcher = AlignmentMatcher(manifest, stability=1)
        update = matcher.process(anchor)
        self.assertTrue(update.ambiguous)
        self.assertFalse(update.triggered)
        update = matcher.process("Silver waves splashed against the empty lighthouse")
        self.assertTrue(update.triggered)
        self.assertEqual(update.checkpoint_id, "2")
        self.assertEqual(update.skipped_checkpoint_ids, ("1",))

    def test_unrelated_speech_and_silence_do_not_advance(self):
        matcher = AlignmentMatcher(sample(), stability=1)
        for text in ("", "hello", "bring me a sandwich before lunch please",
                     "have you seen my computer charger today", "",
                     "the television remote has disappeared again"):
            self.assertFalse(matcher.process(text).triggered)
            self.assertEqual(matcher.tracked_word_position, 0)
        self.assertEqual(matcher.current_index, 0)

    def test_old_scene_never_replays_or_moves_progress_backwards(self):
        manifest = sample()
        matcher = AlignmentMatcher(manifest, stability=1)
        matcher.process(manifest["pages"][0]["text"])
        update = matcher.process(manifest["pages"][1]["text"])
        position = update.tracked_word_position
        for end in (1, 2, 3):
            update = matcher.process(manifest["pages"][0]["text"],
                                     segment(manifest["pages"][0]["text"], end=end))
            self.assertFalse(update.triggered)
            self.assertEqual(matcher.tracked_word_position, position)

    def test_requires_full_passage_data_and_valid_checkpoint_locations(self):
        cases = []
        manifest = sample()
        del manifest["pages"]
        cases.append(manifest)
        manifest = sample()
        manifest["checkpoints"][0]["checkpoint_text"] = "phrase not present anywhere in this book"
        cases.append(manifest)
        manifest = sample()
        manifest["checkpoints"][0].update(word_start=0, word_end=1)
        cases.append(manifest)
        manifest = sample()
        manifest["pages"].append(copy.deepcopy(manifest["pages"][0]))
        cases.append(manifest)
        for value in cases:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    AlignmentMatcher(value)

    def test_explicit_global_word_ranges_and_out_of_order_pages(self):
        manifest = sample()
        first = manifest["checkpoints"][0]
        first.update(word_start=0, word_end=10)
        manifest["pages"].reverse()
        matcher = AlignmentMatcher(manifest, stability=1)
        self.assertTrue(matcher.process(first["checkpoint_text"]).triggered)

    def test_invalid_segment_times_fail_with_actionable_error(self):
        matcher = AlignmentMatcher(sample())
        for value in (-1, float("nan"), float("inf")):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    matcher.process("hello", segment("hello", end=value))


if __name__ == "__main__":
    unittest.main()
