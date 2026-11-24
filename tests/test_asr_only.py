import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from benchmarks.asr_only import ASRRecorder, phrase_present, report, score_updates


class ASROnlyTests(unittest.TestCase):
    @unittest.skipUnless(importlib.util.find_spec('numpy'), 'numpy required')
    def test_queued_capture_finishes_while_recognition_is_blocked(self):
        import numpy as np
        from benchmarks.verify_asr_only import verify_queue

        pcm = np.arange(3000, dtype=np.float32)
        with tempfile.TemporaryDirectory() as directory:
            recorder = ASRRecorder(Path(directory) / 'events.jsonl', delivery='queued')
            try:
                chunks = recorder.chunks(pcm, packet_samples=1000, tail_seconds=0)
                first = next(chunks)
                # The consumer takes no more data until the producer completes.
                recorder.capture_thread.join(timeout=2)
                self.assertFalse(recorder.capture_thread.is_alive())
                self.assertEqual(recorder.sent_samples, 1000)
                self.assertEqual(recorder.events[-1]['kind'], 'end_of_capture')
                recorder.receive('one packet')
                self.assertEqual(recorder.events[-1]['delivered_audio_seconds'], 1000 / 16000)
                np.testing.assert_array_equal(np.concatenate([first, *chunks]), pcm)
                audit = verify_queue(recorder.events, len(pcm), complete=True)
                self.assertGreaterEqual(audit['max_queued_audio_seconds'], 2000 / 16000)
                self.assertGreater(audit['max_queue_wait_seconds'], 0)
            finally:
                recorder.close()

    def test_exact_phrase_scoring_has_no_forgiveness_or_checkpoint_confirmation(self):
        self.assertTrue(phrase_present('Found a tiny silver seed.', 'silver seed'))
        self.assertFalse(phrase_present('Found a tiny silver seat.', 'silver seed'))
        self.assertFalse(phrase_present('Found a tiny silverseed.', 'silver seed'))
        self.assertFalse(phrase_present('Found a tiny seed.', 'tiny silver seed'))

    def test_transient_correct_words_are_separate_from_persistent_words(self):
        case = {'reference': 'a silver seed', 'reference_kind': 'supplied_passage',
                'timing_marks': [{'id': 'example', 'phrase': 'silver seed', 'end_seconds': 2}]}
        events = [{'kind': 'transcript', 'text': text, 'wall_seconds': when}
                  for text, when in [('a silver seed', 2.2), ('a silver seat', 2.5), ('a silver seed', 3.1)]]
        metrics = score_updates(events, case)
        self.assertAlmostEqual(metrics['timing_marks'][0]['first_delay_seconds'], .2)
        self.assertAlmostEqual(metrics['timing_marks'][0]['persistent_delay_seconds'], 1.1)
        self.assertEqual(metrics['non_append_revisions'], 2)
        self.assertIsNone(metrics['spoken_wer'])
        self.assertEqual(metrics['passage_wer'], 0)

    def test_final_wrong_hypothesis_does_not_erase_first_or_claim_persistence(self):
        case = {'reference': 'silver seed', 'reference_kind': 'verified_spoken',
                'timing_marks': [{'id': 'example', 'phrase': 'silver seed', 'end_seconds': 2}]}
        events = [{'kind': 'transcript', 'text': text, 'wall_seconds': when}
                  for text, when in [('silver seed', 1.8), ('silver seat', 3)]]
        result = score_updates(events, case)
        self.assertAlmostEqual(result['timing_marks'][0]['first_delay_seconds'], -.2)
        self.assertIsNone(result['timing_marks'][0]['persistent_delay_seconds'])
        self.assertEqual(result['spoken_wer'], .5)
        self.assertIsNone(result['passage_wer'])

    def test_missing_words_have_no_fabricated_latency(self):
        case = {'reference': 'silver seed', 'reference_kind': 'supplied_passage',
                'timing_marks': [{'id': 'example', 'phrase': 'silver seed', 'end_seconds': 2}]}
        result = score_updates([], case)
        self.assertIsNone(result['first_text_seconds_from_audio_start'])
        self.assertIsNone(result['timing_marks'][0]['first_delay_seconds'])
        self.assertEqual(result['reference_score']['deletions'], 2)

    @unittest.skipUnless(importlib.util.find_spec('numpy'), 'numpy required')
    def test_pacing_delivers_all_samples_and_tail_even_when_feed_is_late(self):
        import numpy as np
        import time
        with tempfile.TemporaryDirectory() as directory:
            recorder = ASRRecorder(Path(directory) / 'events.jsonl')
            chunks = []
            try:
                for chunk in recorder.chunks(np.ones(20, dtype=np.float32), packet_samples=16, tail_seconds=.001):
                    chunks.append(chunk.copy())
                    time.sleep(.003)
            finally:
                recorder.close()
            delivered = np.concatenate(chunks)
            np.testing.assert_array_equal(delivered, np.r_[np.ones(20), np.zeros(16)])
            self.assertEqual(recorder.events[-1]['kind'], 'end_of_audio')
            self.assertGreater(recorder.events[-2]['feed_lateness_seconds'], 0)
            self.assertGreaterEqual(recorder.events[0]['wall_seconds'], 16 / 16000)

    def test_guard_refuses_tracker_imports_in_fresh_process(self):
        result = subprocess.run([sys.executable, '-c',
                                 'from benchmarks.asr_only import enforce_no_tracker; '
                                 'enforce_no_tracker(); import books_to_life.matching.alignment_matcher'],
                                capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('forbids tracker/context imports', result.stderr)

    def test_failed_trials_are_visible_and_not_scored_as_success(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / 'example--tea.json').write_text(json.dumps({'status': 'failed', 'error': 'No CUDA'}))
            rows = report(path, {'cases': [{'id': 'tea', 'timing_marks': []}, {'id': 'cat'}]}, ['example'])
            self.assertEqual(rows[0]['completed'], 0)
            self.assertEqual(len(rows[0]['failures']), 2)
            self.assertIsNone(rows[0]['passage_wer_percent'])
            self.assertIn('No CUDA', (path / 'report.md').read_text())


if __name__ == '__main__':
    unittest.main()
