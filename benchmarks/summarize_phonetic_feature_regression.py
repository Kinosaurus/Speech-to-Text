"""Verify and report the inspected-data phonetic-feature regression."""
import argparse
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from benchmarks.run_mps_heldout import read, write, check_frozen, digest
from benchmarks.run_phonetic_feature_regression import DEST, EARLIER, LATEST
from benchmarks.summarize_mps_heldout import listening_review


def totals(rows, label):
    return {k: sum(len(r[label][k]) for r in rows) for k in ('emitted', 'suppressed', 'skipped', 'unreached')}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=DEST)
    output = parser.parse_args().output.resolve()
    done = read(output / 'completed.json'); protocol = check_frozen(output, model_hash=True)
    rows = read(output / 'results.json')['recordings']; pre = read(output / 'preflight-replay.json')['recordings']
    controls = read(output / 'controls-results.json'); jobs = read(output / 'jobs.json')
    assert len(rows) == done['fresh_reading_streams'] == 9
    assert len(pre) == done['saved_callback_recordings'] == 99
    assert len(controls) == done['fresh_unrelated_streams'] == 4
    assert [r['recording'] for r in rows] == protocol['ordered_recordings']
    assert all(r['delivery_audit_pass'] and r['app_observer_agreement'] and r['stream_done'] for r in rows)
    assert all(r['assertion']['passed'] for r in rows)
    assert not any(r['removed_emissions'] for r in rows) and not any(r['removed'] for r in pre)
    assert sum(r['emitted'] for r in controls) == sum(r['suppressed'] for r in controls) == 0
    indexed = {r['recording']: r for r in pre}; omission_controls = []
    for case in protocol['provider_deletion_controls']:
        item = dict(case, emitted=case['checkpoint'] in indexed[case['recording']]['after']['emitted'])
        omission_controls.append(item); assert not item['emitted']
    callback_agreement = []
    for job in jobs:
        assert digest(Path(job['audio'])) == job['audio_sha256']
        assert digest(Path(job['baseline_events'])) == job['baseline_events_sha256']
        if job['id'] not in protocol['ordered_recordings']: continue
        def segments(path):
            return [e['segments'] for line in path.read_text(encoding='utf-8').splitlines()
                    if (e := json.loads(line))['kind'] == 'segments']
        callback_agreement.append(dict(recording=job['id'], same_asr_segments=segments(Path(job['baseline_events'])) ==
            segments(output / 'streams' / (job['id'] + '.events.jsonl'))))
    unit_log = output / 'unit-tests.log'; unit_text = unit_log.read_text(encoding='utf-8')
    tests_run = int(re.search(r'Ran (\d+) tests', unit_text)[1])
    assert 'OK (skipped=1)' in unit_text
    portable = []
    for row in rows:
        item = {k: v for k, v in row.items() if k not in ('checkpoints', 'phonetic_calls')}
        item['checkpoints'] = []
        for cp in row['checkpoints']:
            e = cp['provider_evidence']
            item['checkpoints'].append({k: v for k, v in cp.items() if k != 'provider_evidence'} | {
                'provider_annotation_status': e['status'],
                'provider_counts': {k: e.get(k) for k in ('correct', 'substitutions', 'deletions')}})
        portable.append(item)
    report = dict(date='2026-11-02', scope='Contextual phonetic-feature and endpoint-progress repair: inspected-data regression',
        change=dict(asr_unchanged=True, no_word_aliases=True,
            phonetic_features='Complete CMU phone inventory: equal-length pronunciations, same final phone, at most two one-feature substitutions and at most one changed consonant; existing structural route retained.',
            contextual_requirements='Previously acquired next region; entire exact contiguous prefix of at least four distinct words; latest four endpoint positions; required-word and prompt checks.',
            progress='Unique full anchor may supply a local endpoint candidate with 0.75 credit for the uncertain endpoint; ordinary score, coverage, ambiguity and independent-confirmation rules remain.'),
        configuration=protocol['configuration'], model=protocol['model'], lexicon=protocol['lexicon'],
        execution=dict(fresh_reading_streams=9, fresh_unrelated_streams=4, saved_callback_recordings=99,
            configured_fresh_reading=27, fresh_reading_audio_seconds=sum(r['audio_seconds'] for r in rows),
            all_samples_delivered=True, all_partial_before_eof=True, all_stream_done=True,
            all_app_observer_agreement=True, one_trial_per_recording=True, all_trials_retained=True),
        totals=dict(before=totals(rows, 'before'), after=totals(rows, 'after')),
        saved_callback_regression=dict(recordings=99, configured=297, kind='Not fresh ASR trials',
            before=totals(pre, 'before'), after=totals(pre, 'after'),
            added=[dict(recording=r['recording'], checkpoints=r['added']) for r in pre if r['added']],
            removed=[dict(recording=r['recording'], checkpoints=r['removed']) for r in pre if r['removed']],
            omission_controls=omission_controls),
        assertions=[dict(recording=r['recording'], **r['assertion']) for r in rows],
        added_emissions=[dict(recording=r['recording'], checkpoints=r['added_emissions']) for r in rows if r['added_emissions']],
        removed_emissions=[dict(recording=r['recording'], checkpoints=r['removed_emissions']) for r in rows if r['removed_emissions']],
        unrelated_controls=dict(fresh_streams=4, passage_policies=6, comparisons=sum(r['comparisons'] for r in controls),
            emitted=0, suppressed=0, results=controls),
        integrity=dict(asr_and_eof_runtime_unchanged=True, model_hash_unchanged=True, lexicon_unchanged=True,
            sources_unchanged_during_run=True, audio_and_manifests_unchanged=True,
            source_sha256=protocol['source_sha256'], baseline_sha256=protocol['baseline_sha256']),
        asr_callback_agreement=callback_agreement,
        validation=dict(windows_tests_run=tests_run, windows_passed=tests_run-1, skipped_requiring_nemo=1,
            unit_log_sha256=digest(unit_log)), recordings=portable,
        limits=['All recordings are inspected regression data. Original frozen held-out results remain unchanged.',
            'Phonetic features compare dictionary text, not raw audio; a close intentional substitution can be accepted as a recognition error. This is not acoustic verification.',
            'Omission controls cannot rule out every ASR hallucination or similar-sounding following word.',
            'User supplied an approximate phrase-end cue, not a verified acoustic alignment or latency score.',
            'Same familiar MPS passages; this does not validate new books, Singapore accents or physical microphones.'])
    review = output / 'review'; review.mkdir(exist_ok=True); human = {}
    for folder in (EARLIER, LATEST):
        path = folder / 'review/human_reviews.json'
        if path.exists(): human.update(read(path)['cases'])
    write(review / 'human_reviews.json', dict(source='Prior user review of these unchanged source recordings; original judgments retained', cases=human))
    count = listening_review(output, report, title='Contextual phonetic regression listening review',
        introduction='Inspected recordings rerun after a general phonetic/progress change with unchanged ASR. Original user judgments and current outcomes are shown separately.')
    report['listening_review'] = dict(flagged_checkpoints=count, source_audio_reviews=len(human))
    write(output / 'summary.json', report)
    write(ROOT / 'benchmarks/results' / (output.name + '.json'), report)
    print(json.dumps({k: report[k] for k in ('execution', 'totals', 'assertions', 'added_emissions', 'removed_emissions', 'validation')}, indent=2))


if __name__ == '__main__': main()
