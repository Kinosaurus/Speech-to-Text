from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import unittest
import wave

from benchmarks.asr_only import sha256
from benchmarks.asr_reference import approval_status, compare_delivery_runs, comparison, digest, estimated_comparison, unambiguous_matches, validate, word_arrivals
from benchmarks.asr_reference_review import ReviewProject


def fixture_annotation():
    return {'schema': 'asr-reference-review-v1', 'case': 'demo', 'audio': 'fixture.wav',
            'audio_sha256': 'fixture', 'duration_seconds': 2, 'scope': 'all spoken words',
            'draft_source': 'synthetic unit test', 'draft_model_sha256': 'fixture',
            'review': {}, 'words': [{'id': 'w1', 'text': 'silver', 'start': .1, 'end': .5,
                                     'text_reviewed': False, 'timing_reviewed': False},
                                    {'id': 'w2', 'text': 'seed', 'start': .6, 'end': 1,
                                     'text_reviewed': False, 'timing_reviewed': False}]}


def approve_fixture(annotation):
    for row in annotation['words']:
        row.update(text_reviewed=True, timing_reviewed=True)
    annotation['review'].update(all_speech_checked=True, timing_uncertainty_seconds=.1)
    for timing, key in [(False, 'text_approval'), (True, 'timing_approval')]:
        annotation['review'][key] = {'reviewer': 'SYNTHETIC UNIT TEST ONLY',
                                    'at': datetime.now(timezone.utc).isoformat(), 'digest': digest(annotation, timing)}
    return annotation


class ReferenceScoringTests(unittest.TestCase):
    def test_automatic_status_label_does_not_certify_draft(self):
        a = fixture_annotation()
        a['status'] = 'verified'
        self.assertEqual(approval_status(a), {'text_verified': False, 'timing_verified': False})

    def test_content_and_timing_edits_invalidate_different_approvals(self):
        original = approve_fixture(fixture_annotation())
        self.assertTrue(approval_status(original)['timing_verified'])
        timing = deepcopy(original)
        timing['words'][0]['end'] = .55
        self.assertEqual(approval_status(timing), {'text_verified': True, 'timing_verified': False})
        text = deepcopy(original)
        text['words'][0]['text'] = 'gold'
        self.assertEqual(approval_status(text), {'text_verified': False, 'timing_verified': False})

    def test_no_accuracy_approval_with_unreviewed_or_unclear_words(self):
        a = approve_fixture(fixture_annotation())
        a['words'][0]['text_reviewed'] = False
        self.assertFalse(approval_status(a)['text_verified'])
        a = approve_fixture(fixture_annotation())
        a['words'][0]['text'] = '[unclear]'
        approve_fixture(a)
        self.assertFalse(approval_status(a)['text_verified'])

    def test_invalid_word_times_cannot_be_saved(self):
        for value in [float('nan'), float('inf'), -1, 10]:
            a = fixture_annotation()
            a['words'][0]['start'] = value
            with self.assertRaises(ValueError):
                validate(a)

    def test_repeated_words_are_ambiguous_instead_of_guessed(self):
        self.assertEqual(unambiguous_matches(['a', 'a'], ['a']), {})
        self.assertEqual(unambiguous_matches(['a', 'cat', 'a', 'dog'], ['a', 'dog']), {3: 1})

    def test_soundalikes_receive_no_asr_accuracy_credit(self):
        self.assertEqual(unambiguous_matches(['silver', 'seed'], ['silver', 'seat']), {0: 0})

    def test_stable_latency_distinguishes_revised_away_first_hit(self):
        a = fixture_annotation()
        a['words'] = a['words'][1:]
        a['words'][0]['start'] = .1
        events = [{'kind': 'transcript', 'text': text, 'wall_seconds': t, 'delivered_audio_seconds': t}
                  for text, t in [('seed', .8), ('seat', 1.1), ('seed', 1.5)]]
        result = word_arrivals(events, a)[0]
        self.assertAlmostEqual(result['first_delay_seconds'], -.2)
        self.assertAlmostEqual(result['stable_delay_seconds'], .5)

    def test_undelivered_future_words_cannot_get_early_timing_credit(self):
        a = fixture_annotation()
        result = word_arrivals([{'kind': 'transcript', 'text': 'silver seed', 'wall_seconds': .3,
                                'delivered_audio_seconds': .3}], a)
        self.assertIsNone(result[1]['first_delay_seconds'])


class ReferenceProjectTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.run = self.root / 'run'
        self.run.mkdir()
        audio = self.root / 'fixture.wav'
        with wave.open(str(audio), 'wb') as wav:
            wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(16000)
            wav.writeframes(b'\0\0' * 32000)
        self.annotation = fixture_annotation()
        self.annotation.update(audio=str(audio), audio_sha256=sha256(audio))
        (self.root / 'project.json').write_text(json.dumps({'run': str(self.run), 'cases': ['demo']}))
        (self.root / 'demo.annotation.json').write_text(json.dumps(self.annotation))
        (self.run / 'run.json').write_text(json.dumps({'profiles': ['A', 'B']}))
        (self.run / 'dataset.json').write_text(json.dumps({'cases': [{'id': 'demo'}]}))
        for profile, text in [('A', 'silver seed'), ('B', 'silver seat')]:
            (self.run / f'{profile}--demo.json').write_text(json.dumps({'status': 'ok', 'metrics': {'final_text': text}}))
            (self.run / f'{profile}--demo.events.jsonl').write_text(json.dumps(
                {'kind': 'transcript', 'text': text, 'wall_seconds': 1.5, 'delivered_audio_seconds': 2}))
        self.project = ReviewProject(self.root)

    def body(self, action='draft'):
        payload = self.project.payload('demo')
        return {'revision': payload['revision'], 'words': payload['annotation']['words'],
                'action': action, 'reviewer': 'SYNTHETIC UNIT TEST ONLY',
                'all_speech_checked': True, 'timing_uncertainty_seconds': .1}

    def test_table_keeps_actual_scores_blank_until_review(self):
        for row in self.project.table()['rows']:
            self.assertIsNone(row['verified_wer_percent'])
            self.assertIsNone(row['stable_word_delay_median_seconds'])

    def test_save_refuses_automatic_approval_and_stale_revision(self):
        with self.assertRaisesRegex(ValueError, 'Review every word'):
            self.project.save('demo', self.body('approve_text'))
        body = self.body()
        body['words'][0]['text'] = 'tiny'
        self.project.save('demo', body)
        with self.assertRaisesRegex(ValueError, 'changed in another window'):
            self.project.save('demo', body)
        self.assertTrue(list(self.root.glob('demo.before-*.json')))

    def test_reviewed_text_then_boundaries_populates_wer_and_timing_separately(self):
        body = self.body('approve_text')
        for row in body['words']:
            row.update(text_reviewed=True, timing_reviewed=True)
        result = self.project.save('demo', body)
        self.assertEqual(result['verification'], {'text_verified': True, 'timing_verified': False})
        table = self.project.table()
        self.assertEqual([r['verified_wer_percent'] for r in table['rows']], [0, 50])
        self.assertTrue(all(r['stable_word_delay_median_seconds'] is None for r in table['rows']))
        self.project.save('demo', self.body('approve_timing'))
        table = self.project.table()
        self.assertEqual([r['timed_correct_words'] for r in table['rows']], [2, 1])
        self.assertEqual([r['common_correct_word_count'] for r in table['rows']], [1, 1])
        self.assertEqual([r['common_correct_word_delay_median_seconds'] for r in table['rows']], [1, 1])
        self.assertEqual([r['full_corpus_verified_wer_percent'] for r in table['rows']], [0, 50])

    def test_changed_audio_cannot_be_approved(self):
        with open(self.annotation['audio'], 'ab') as file:
            file.write(b'changed')
        with self.assertRaisesRegex(ValueError, 'Recording changed'):
            self.project.save('demo', self.body())

    def test_estimates_do_not_create_or_bypass_real_reference_approval(self):
        original = (self.root / 'demo.annotation.json').read_bytes()
        estimated = self.project.estimated_table()
        self.assertTrue(estimated['estimated'])
        self.assertFalse(estimated['human_verified'])
        self.assertEqual([r['estimated_wer_percent'] for r in estimated['rows']], [0, 50])
        self.assertTrue(all('verified_wer_percent' not in r for r in estimated['rows']))
        self.assertEqual((self.root / 'demo.annotation.json').read_bytes(), original)
        self.assertTrue(all(r['verified_wer_percent'] is None for r in self.project.table()['rows']))
        self.assertTrue(all(r['stable_word_delay_median_seconds'] is None for r in self.project.table()['rows']))
        self.assertIn('ESTIMATED', (self.root / 'estimated-comparison.md').read_text())

    def test_zero_duration_draft_words_are_excluded_from_estimated_latency_only(self):
        a = deepcopy(self.annotation)
        a['words'][0]['end'] = a['words'][0]['start']
        result = estimated_comparison(self.run, {'demo': a})
        row = result['rows'][0]
        self.assertEqual(row['estimated_wer_percent'], 0)
        self.assertEqual(row['eligible_reference_words'], 1)
        self.assertEqual(row['reference_words_with_unusable_timing'], 1)
        self.assertEqual(row['timed_correct_words'], 1)
        self.assertIsNone(result['word_ledgers']['A']['demo'][0]['stable_delay_seconds'])

    def test_incomplete_trials_do_not_become_estimated_full_recording_scores(self):
        (self.run / 'B--demo.json').write_text(json.dumps({'status': 'failed', 'error': 'trial timeout'}))
        result = estimated_comparison(self.run, {'demo': self.annotation})
        self.assertEqual(result['shared_recordings'], [])
        self.assertTrue(all(row['estimated_wer_percent'] is None for row in result['rows']))
        self.assertIsNone(result['rows'][1]['full_corpus_estimated_wer_percent'])
        self.assertNotIn('score', result['case_scores']['B']['demo'])

    def test_queued_comparison_retains_same_file_scores_when_a_backend_fails(self):
        annotations = {'demo': self.annotation}
        baseline = estimated_comparison(self.run, annotations)
        (self.run / 'run.json').write_text(json.dumps({'profiles': ['A', 'B'], 'delivery': 'queued'}))
        (self.run / 'B--demo.json').write_text(json.dumps({'status': 'failed', 'error': 'trial timeout'}))
        queued = estimated_comparison(self.run, annotations)
        queued['run'] = 'queued'
        self.assertEqual(queued['comparison_profiles'], ['A'])
        self.assertEqual([row['estimated_wer_percent'] for row in queued['rows']], [0, None])
        paired = compare_delivery_runs(baseline, queued)
        self.assertEqual(paired['common_words'], 2)
        self.assertEqual(paired['profile_count'], 1)
        self.assertIsNone(paired['rows'][1]['after_median_seconds'])


if __name__ == '__main__':
    unittest.main()
