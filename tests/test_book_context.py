import contextlib
import io
import json
from pathlib import Path
import runpy
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from alignment_matcher import AlignmentMatcher
from book_context import BookContext, BookHints, ContextState, install_context_updates, parse_context_message
from checkpoint_matcher import CheckpointMatcher


ROOT = Path(__file__).resolve().parents[1]


def sample(name="sample_story.json"):
    story=name.removesuffix('_story.json')
    reader='demo' if story=='sample' else story
    return json.loads((ROOT / f'recordings/library/stories/{story}/readers/{reader}/checkpoints.json').read_text(encoding="utf-8"))


class BookContextTests(unittest.TestCase):
    def test_startup_uses_next_checkpoint_and_two_ahead_not_the_whole_book(self):
        matcher = AlignmentMatcher(sample())
        context = BookContext(matcher)
        for checkpoint in matcher.checkpoints[:3]:
            self.assertIn(checkpoint["checkpoint_text"], context.hints.hotwords)
        self.assertNotIn(matcher.checkpoints[3]["checkpoint_text"], context.hints.hotwords)
        self.assertLessEqual(len(context.hints.initial_prompt.split()), 64)

    def test_mermaid_phrases_are_supplied_automatically(self):
        matcher = AlignmentMatcher(sample("little_mermaid_story.json"))
        context = BookContext(matcher)
        self.assertIn("She had the prettiest legs on earth", context.hints.hotwords)
        self.assertIn("And the little mermaid could not speak", context.hints.hotwords)
        self.assertIn("deep blue eyes", context.hints.initial_prompt)

    def test_tentative_or_unrelated_speech_does_not_move_hints(self):
        matcher = AlignmentMatcher(sample())
        context = BookContext(matcher)
        original = context.hints
        matcher.process(matcher.checkpoints[0]["checkpoint_text"])
        self.assertIsNone(context.refresh())
        matcher.process("Please bring me a glass of water from the kitchen")
        self.assertIsNone(context.refresh())
        self.assertEqual(context.hints, original)

    def test_confirmed_progress_moves_window_and_retains_a_short_lookback(self):
        matcher = AlignmentMatcher(sample(), stability=1)
        context = BookContext(matcher)
        matcher.process(matcher.checkpoints[0]["checkpoint_text"])
        hints = context.refresh()
        self.assertNotIn(matcher.checkpoints[0]["checkpoint_text"], hints.hotwords)
        self.assertIn(matcher.checkpoints[3]["checkpoint_text"], hints.hotwords)
        self.assertTrue(hints.initial_prompt.startswith("a tiny silver seed"))

    def test_final_checkpoint_keeps_context_for_remaining_reading(self):
        matcher = AlignmentMatcher(sample("little_mermaid_story.json"), stability=1)
        context = BookContext(matcher)
        matcher.process(matcher.checkpoints[-1]["checkpoint_text"])
        hints = context.refresh()
        self.assertTrue(matcher.completed)
        self.assertIn("could not speak", hints.hotwords)
        self.assertIn("deep blue eyes", hints.initial_prompt)

    def test_explicit_fields_override_only_their_automatic_counterpart(self):
        matcher = AlignmentMatcher(sample(), stability=1)
        context = BookContext(matcher, initial_prompt="Manual passage")
        self.assertEqual(context.hints.initial_prompt, "Manual passage")
        self.assertIn("Mila", context.hints.hotwords)
        matcher.process(matcher.checkpoints[0]["checkpoint_text"])
        self.assertEqual(context.refresh().initial_prompt, "Manual passage")
        context = BookContext(matcher, initial_prompt="Fixed", hotwords="SpecialName")
        matcher.process(matcher.checkpoints[1]["checkpoint_text"])
        self.assertIsNone(context.refresh())
        self.assertEqual(context.hints, BookHints("Fixed", "SpecialName"))

    def test_phrase_only_manifest_and_very_long_anchors_have_bounded_hints(self):
        manifest = sample()
        del manifest["pages"]
        manifest["checkpoints"][0]["checkpoint_text"] = " ".join(["storyword"] * 2000)
        context = BookContext(CheckpointMatcher(manifest))
        self.assertIsNotNone(context.hints.hotwords)
        self.assertLessEqual(len(context.hints.hotwords), 320)
        self.assertLessEqual(len(context.hints.initial_prompt), 480)

    def test_control_validation_rejects_bad_frames_and_stale_revisions_do_not_revert(self):
        for value in ("[]", "{}", '{"type":"book_context","revision":true}',
                      '{"type":"book_context","revision":1,"hotwords":[]}',
                      json.dumps({"type": "book_context", "revision": 1, "initial_prompt": "x" * 6001})):
            with self.assertRaises(ValueError):
                parse_context_message(value)
        state = ContextState("Start", "First")
        state.queue(2, BookHints("New passage", "New words"))
        state.queue(1, BookHints("Old passage", "Old words"))
        self.assertEqual(state.snapshot(), (BookHints("New passage", "New words"), 2))

    def test_context_is_applied_as_a_pair_on_next_inference_and_is_session_local(self):
        calls = []
        client = SimpleNamespace(initial_prompt="Old passage", hotwords="Old words")
        client.transcribe_audio = lambda audio: calls.append((audio, client.initial_prompt, client.hotwords))
        state = install_context_updates(client)
        other = SimpleNamespace(initial_prompt="Other passage", hotwords="Other words", transcribe_audio=Mock())
        other_state = install_context_updates(other)
        state.queue(1, BookHints("New passage", "New words"))
        self.assertEqual(client.initial_prompt, "Old passage")
        client.transcribe_audio("audio")
        self.assertEqual(calls, [("audio", "New passage", "New words")])
        self.assertEqual(other_state.snapshot()[0], BookHints("Other passage", "Other words"))

    def launch_client(self, options):
        fake = Mock()
        # The mocked audio client never decodes this existing fixture.
        audio = ROOT / "recordings/library/stories/little_mermaid/readers/little_mermaid/passage.txt"
        args = ["run_client.py", "--files", str(audio), *options]
        with patch.object(sys, "argv", args), \
                patch("book_context_client.BookTranscriptionClient", fake), \
                patch("whisper_live.client.TranscriptionClient", fake), \
                patch("audio_runtime.wait_for_server"), contextlib.redirect_stdout(io.StringIO()):
            runpy.run_path(str(ROOT / "run_client.py"), run_name="__main__")
        return fake.call_args.kwargs

    def test_cli_automatic_hints_and_opt_out_reach_client_handshake(self):
        manifest = str(ROOT / "recordings/library/stories/little_mermaid/readers/little_mermaid/checkpoints.json")
        options = self.launch_client(["--checkpoints", manifest])
        self.assertIn("prettiest legs", options["hotwords"])
        self.assertIn("deep blue eyes", options["initial_prompt"])
        options = self.launch_client(["--checkpoints", manifest, "--no_book_context"])
        self.assertIsNone(options["hotwords"])
        self.assertIsNone(options["initial_prompt"])
        options = self.launch_client([])
        self.assertIsNone(options["hotwords"])
        options = self.launch_client(["--checkpoints", manifest, "--no_book_context", "--hotwords", "Manual"])
        self.assertEqual(options["hotwords"], "Manual")


if __name__ == "__main__":
    unittest.main()
