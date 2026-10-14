import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
import wave

from benchmarks.metrics import edit_alignment, estimated_anchor_times, latest_text
from benchmarks.common import Recorder
from benchmarks.stream_timing import timed_words
from benchmarks.checkpoint_latency import unique_endpoint
from benchmarks.run import load_manual_timing, summarize


class BenchmarkMetricsTests(unittest.TestCase):
    def test_edit_counts_and_normalization(self):
        score, _ = edit_alignment('The child reads a story.', 'the child read story today')
        self.assertEqual(score['substitutions'] + score['deletions'] + score['insertions'], 3)
        self.assertEqual(score['reference_words'], 5)
        self.assertEqual(edit_alignment('Hello, WORLD!', 'hello world')[0]['wer'], 0)

    def test_revised_snapshot_does_not_append_old_words(self):
        first = [{'text': 'she had the prettiest life'}]
        revised = [{'text': 'she had the prettiest legs'}]
        self.assertEqual(latest_text(first), 'she had the prettiest life')
        self.assertEqual(latest_text(revised), 'she had the prettiest legs')

    def test_contraction_format_is_not_a_recognition_error(self):
        score, _ = edit_alignment('She could not speak. It is quiet.', "She couldn’t speak. It's quiet.")
        self.assertEqual(score['wer'], 0)

    def test_missing_anchor_endpoint_is_not_fabricated(self):
        checkpoints = [{'id': 'one', 'word_end': 3}]
        self.assertEqual(estimated_anchor_times('the mermaid speaks',
                         [{'word': 'the', 'end': 1}, {'word': 'mermaid', 'end': 2}], checkpoints), {})

    def test_duplicate_update_cannot_add_confirmation(self):
        manifest = json.loads((Path(__file__).parents[1] / 'examples/little_mermaid_story.json').read_text())
        recorder = Recorder(manifest)
        recorder.begin()
        snapshot = [{'start': 0, 'end': 5, 'text': 'She had the prettiest legs on earth', 'completed': False}]
        recorder.receive(latest_text(snapshot), snapshot, 5)
        recorder.receive(latest_text(snapshot), snapshot, 5)
        self.assertEqual(len(recorder.events), 1)
        self.assertFalse(recorder.matcher.triggered_checkpoint_ids)

    def test_invalid_asr_timestamps_are_reported_without_advancing(self):
        manifest = json.loads((Path(__file__).parents[1] / 'examples/little_mermaid_story.json').read_text())
        recorder = Recorder(manifest)
        recorder.begin()
        text = 'She had the prettiest legs on earth'
        recorder.receive(text, [{'start': 5, 'end': 4, 'text': text}], 5)
        self.assertEqual(len(recorder.invalid_updates), 1)
        self.assertEqual(recorder.events, [])
        self.assertFalse(recorder.matcher.triggered_checkpoint_ids)
        self.assertEqual(recorder.summary(text)['reference_score']['wer'], 0)
        recorder.receive(text, [{'start': 0, 'end': 6, 'text': text}], 6)
        self.assertEqual(len(recorder.events), 1)
        self.assertEqual(recorder.summary(text)['invalid_update_count'], 1)

    def test_streaming_subword_times_join_into_words(self):
        text, words = timed_words([
            {'text': ' F', 'start': 0.96, 'end': 1.04},
            {'text': 'at', 'start': 1.04, 'end': 1.12},
            {'text': ' c', 'start': 1.60, 'end': 1.68},
            {'text': 'at.', 'start': 1.84, 'end': 1.92},
        ])
        self.assertEqual(text, ' Fat cat.')
        self.assertEqual(words, [
            {'word': 'Fat', 'start': 0.96, 'end': 1.12},
            {'word': 'cat', 'start': 1.60, 'end': 1.92},
        ])

    def test_streaming_word_times_reject_missing_or_reversed_times(self):
        for start, end in [(-1, -1), (5, 4)]:
            with self.subTest(start=start, end=end), self.assertRaises(ValueError):
                timed_words([{'text': ' tea', 'start': start, 'end': end}])

    def test_estimated_endpoint_requires_one_matching_occurrence(self):
        timed = [{'word': word, 'start': i, 'end': i + 0.5}
                 for i, word in enumerate('on the stove'.split())]
        self.assertEqual(unique_endpoint(timed, 'on the stove')['endpoint_seconds'], 2.5)
        self.assertIsNone(unique_endpoint(timed, 'a pot of tea'))
        self.assertIsNone(unique_endpoint(timed + timed, 'on the stove'))
        with self.assertRaises(ValueError):
            unique_endpoint(timed, '')

    def make_manual_timing_fixture(self, root):
        audio = root / 'recording.wav'
        with wave.open(str(audio), 'wb') as recording:
            recording.setparams((1, 2, 16000, 16000, 'NONE', 'not compressed'))
            recording.writeframes(b'\0\0' * 16000)
        manifest = root / 'manifest.json'
        manifest.write_text(json.dumps({'pages': [{'page': 1, 'text': 'first checkpoint second checkpoint'}],
                                        'checkpoints': [{'id': 'first'}, {'id': 'second'}]}))
        (root / 'manual-checkpoint-times.json').write_text(json.dumps({'second': 0.5}))
        metadata = {'audio_sha256': hashlib.sha256(audio.read_bytes()).hexdigest(),
                    'manifest_sha256': hashlib.sha256(manifest.read_bytes()).hexdigest(),
                    'skipped_checkpoint_ids': ['first'], 'resolution': 'whole-second marks'}
        (root / 'manual-checkpoint-annotations.json').write_text(json.dumps(metadata))
        return SimpleNamespace(audio=audio, manifest=manifest, output=root), metadata

    def test_partial_manual_timing_keeps_skipped_activation_separate(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1] / 'output') as directory:
            args, metadata = self.make_manual_timing_fixture(Path(directory))
            result = {'backend': 'whisper', 'model': 'small.en', 'hints': True, 'chunk_ms': 160,
                      'benchmark_mode': 'streaming-only-v1', 'stream_repetitions': 1,
                      'audio_sha256': metadata['audio_sha256'], 'manifest_sha256': metadata['manifest_sha256'],
                      'sampled_peak_process_rss_bytes': None, 'gpu_memory_after_stream_mib': 100,
                      'stream': {'text': 'second checkpoint', 'triggered_ids': ['first', 'second'],
                                 'skipped_ids': [], 'max_feed_lateness_seconds': 0, 'wall_seconds': 2.5,
                                 'invalid_update_count': 0, 'events': [
                                     {'checkpoint_id': 'first', 'triggered': True, 'wall_seconds': 0.2},
                                     {'checkpoint_id': 'second', 'triggered': True, 'wall_seconds': 0.8},
                                 ]}}
            (args.output / 'whisper-small-hints.json').write_text(json.dumps(result))
            rows = summarize(args)
            self.assertEqual(rows[0]['early_triggers'], 0)
            self.assertEqual(rows[0]['activations_on_skipped_anchors'], 1)
            self.assertEqual(rows[0]['manually_timed_anchors_triggered'], 1)
            saved = json.loads((args.output / 'results.json').read_text())
            events = saved['profiles']['whisper-small-hints']['checkpoint_delays']
            self.assertIsNone(events[0]['delay_seconds'])
            self.assertTrue(events[0]['anchor_reported_skipped'])
            self.assertAlmostEqual(events[1]['delay_seconds'], 0.3)

    def test_manual_annotations_reject_wrong_audio_and_contradictory_skips(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1] / 'output') as directory:
            args, metadata = self.make_manual_timing_fixture(Path(directory))
            annotation_file = args.output / 'manual-checkpoint-annotations.json'
            annotation_file.write_text(json.dumps({**metadata, 'audio_sha256': 'different recording'}))
            with self.assertRaisesRegex(ValueError, 'mismatched input'):
                load_manual_timing(args.audio, args.manifest, args.output)
            annotation_file.write_text(json.dumps({**metadata, 'skipped_checkpoint_ids': ['second']}))
            with self.assertRaisesRegex(ValueError, 'cannot also have spoken endpoint'):
                load_manual_timing(args.audio, args.manifest, args.output)


if __name__ == '__main__':
    unittest.main()
