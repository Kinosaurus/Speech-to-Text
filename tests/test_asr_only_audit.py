import json
from pathlib import Path
import tempfile
import unittest
import wave

from benchmarks.asr_only import PROTOCOL, sha256
from benchmarks.verify_asr_only import verify_recorded_failure, verify_trial


class ASROnlyAuditTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.output = Path(directory.name)
        audio = self.output / 'sample.wav'
        with wave.open(str(audio), 'wb') as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(16000)
            wav.writeframes(b'\0\0' * 32)
        reference = self.output / 'reference.txt'
        reference.write_text('hello')
        self.case = {'id': 'sample', 'audio': str(audio), 'audio_sha256': sha256(audio),
                     'reference_path': str(reference), 'reference_sha256': sha256(reference),
                     'reference_kind': 'supplied_passage'}
        self.dataset = {'packet_samples': 16, 'tail_seconds': 0}
        self.result = {'status': 'ok', 'protocol': PROTOCOL, 'profile': 'example', 'case': 'sample',
                       'tracker': False, 'hints': False, 'no_tracker_modules_imported': True,
                       'audio_sha256': sha256(audio), 'packet_samples': 16, 'tail_seconds': 0,
                       'delivery': {'samples_sent': 32}, 'metrics': {'final_text': 'hello', 'spoken_wer': None}}
        self.events = [{'kind': 'audio', 'sample_start': 0, 'sample_count': 16, 'wall_seconds': .001,
                        'feed_lateness_seconds': 0},
                       {'kind': 'audio', 'sample_start': 16, 'sample_count': 16, 'wall_seconds': .002,
                        'feed_lateness_seconds': 0},
                       {'kind': 'end_of_audio', 'samples': 32},
                       {'kind': 'transcript', 'text': 'hello', 'final': True}]

    def run_audit(self):
        (self.output / 'example--sample.json').write_text(json.dumps(self.result))
        (self.output / 'example--sample.events.jsonl').write_text('\n'.join(json.dumps(e) for e in self.events))
        return verify_trial(self.output, 'example', self.case, self.dataset)

    def test_complete_stream_verifies(self):
        self.assertTrue(self.run_audit()['complete_delivery'])

    def test_duplicate_packet_cannot_pass_total_sample_count(self):
        self.events[1]['sample_start'] = 0
        with self.assertRaisesRegex(ValueError, 'skipped, duplicated or reordered'):
            self.run_audit()

    def test_scored_text_must_match_logged_final_snapshot(self):
        self.result['metrics']['final_text'] = 'different text'
        with self.assertRaisesRegex(ValueError, 'differs from raw final snapshot'):
            self.run_audit()

    def test_unverified_passage_cannot_be_presented_as_spoken_accuracy(self):
        self.result['metrics']['spoken_wer'] = 0
        with self.assertRaisesRegex(ValueError, 'verified spoken WER'):
            self.run_audit()

    def test_decoder_discard_is_a_failure_even_if_client_sent_every_sample(self):
        self.events.append({'kind': 'decoder_buffer_trim', 'discarded_unprocessed_seconds': 3})
        with self.assertRaisesRegex(ValueError, 'dropped unprocessed audio'):
            self.run_audit()

    def test_failure_is_retained_separately_from_successful_recognition(self):
        self.result.update(status='failed', error='Decoder buffer discarded uncommitted audio')
        (self.output / 'example--sample.log').write_text('Retained decoder diagnostic')
        with self.assertRaisesRegex(ValueError, 'Trial did not complete'):
            self.run_audit()
        failure = verify_recorded_failure(self.output, 'example', self.case)
        self.assertIn('discarded', failure['error'])

    def test_parent_timeout_is_not_presented_as_a_clean_worker_shutdown(self):
        self.result = {'status': 'failed', 'error': 'Worker exceeded trial timeout; see log.'}
        (self.output / 'example--sample.log').write_text('Decoder warnings retained')
        with self.assertRaisesRegex(ValueError, 'Trial did not complete'):
            self.run_audit()
        failure = verify_recorded_failure(self.output, 'example', self.case)
        self.assertTrue(failure['worker_shutdown_unavailable'])


if __name__ == '__main__':
    unittest.main()
