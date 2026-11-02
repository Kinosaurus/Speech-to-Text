"""Inspected-data regression for contextual phonetic endpoint progress."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from benchmarks.run_mps_heldout import read, write, digest, check_frozen, old_tracker, audit_and_score, source_files
from benchmarks.run_pending_regression import TARGETS as EARLIER_TARGETS, replay
from benchmarks.run_split_word_regression import controls

DEST = ROOT / 'output/phonetic-feature-regression-2026-11-02'
EARLIER = ROOT / 'output/pending-regression-2026-11-02'
LATEST = ROOT / 'output/mps-heldout-pending-2026-11-02'
TARGETS = {'3a4h_EN-OL-RC-234_1': ('hundred_sheep', True, 'User accepted the spoken endpoint'),
           **EARLIER_TARGETS}


def prepare(output):
    assert not (output / 'protocol.json').exists()
    jobs = {j['id']: dict(j) for j in read(EARLIER / 'jobs.json')}
    expected = {r['recording']: r['after'] for r in read(EARLIER / 'preflight-replay.json')['recordings']}
    for source in read(LATEST / 'downloaded-jobs.json'):
        ident = source['id']; assert ident not in jobs
        events = LATEST / 'streams' / (ident + '.events.jsonl')
        jobs[ident] = dict(source, baseline_events=str(events), baseline_events_sha256=digest(events), group=LATEST.name)
    expected.update({r['recording']: r['after'] for r in read(LATEST / 'results.json')['recordings']})
    assert len(jobs) == len(expected) == 99
    selected = {r['audioID']: r for folder in (EARLIER, LATEST) for r in read(folder / 'selected.json')}
    for ident, job in jobs.items():
        assert digest(Path(job['audio'])) == job['audio_sha256']
        target = output / 'inputs' / ident / 'checkpoints.json'; target.parent.mkdir(parents=True)
        target.write_bytes(Path(job['manifest']).read_bytes()); job['manifest'] = str(target)
        assert digest(target) == job['manifest_sha256']
        # The copied prior jobs may contain earlier assertions; redefine this sweep explicitly.
        for field in ('asserted_checkpoint', 'expected_emission', 'assertion_basis'):
            job.pop(field, None)
        if ident in TARGETS:
            cp, emit, basis = TARGETS[ident]
            job.update(asserted_checkpoint=cp, expected_emission=emit, assertion_basis=basis)
    write(output / 'jobs.json', list(jobs.values()))
    write(output / 'downloaded-jobs.json', [jobs[ident] for ident in TARGETS])
    write(output / 'selected.json', list(selected.values()))
    write(output / 'original-live-ledgers.json', expected)
    baseline = {p.name: digest(p) for p in (output / 'baseline-snapshot').iterdir()}
    latest_sources = read(LATEST / 'protocol.json')['source_sha256']
    for name, sha in baseline.items():
        assert sha == latest_sources['books_to_life/matching/' + name]
    hashes = {}
    files = set(source_files()) | {Path(__file__).resolve(), ROOT / 'tests/test_contextual_phonetic_progress.py',
                                  ROOT / 'tests/test_phonetic_endpoint.py'}
    for path in sorted(files):
        name = path.relative_to(ROOT).as_posix(); data = path.read_bytes()
        target = output / 'source-snapshot' / name; target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data); hashes[name] = hashlib.sha256(data).hexdigest()
        if name.startswith('books_to_life/runtime/') or name == 'books_to_life/cli/run_nemo_server.py':
            assert hashes[name] == latest_sources[name]
    previous = read(LATEST / 'protocol.json')
    deleted = list(read(EARLIER / 'protocol.json')['provider_deletion_controls'])
    deleted.extend(dict(recording=r['recording'], checkpoint=cp['id'])
                   for r in read(LATEST / 'results.json')['recordings'] for cp in r['checkpoints']
                   if cp['provider_endpoint_deleted'] or cp['provider_required_word_deleted'])
    write(output / 'protocol.json', dict(date='2026-11-02', kind='Inspected-data phonetic-feature regression',
        configuration=previous['configuration'], model=previous['model'], lexicon=previous['lexicon'],
        source_sha256=hashes, baseline_sha256=baseline, provider_deletion_controls=deleted,
        replay_recordings=list(jobs), ordered_recordings=list(TARGETS), saved_callback_recordings=99,
        fresh_reading_streams=9, fresh_unrelated_streams=4, asr_unchanged=True,
        audio_and_manifests_unmodified=True,
        plan='Replay all 99 saved reading timelines against the frozen previous matcher; one fresh stream for each of nine reviewed/omission cases plus four unrelated controls. No changes after freezing. These samples are inspected and are not held out.'))
    check_frozen(output, model_hash=True)
    print('FROZEN 99 callback replays, 9 fresh readings and 4 fresh unrelated streams.', flush=True)


def preflight(output):
    check_frozen(output); Old = old_tracker(output); expected = read(output / 'original-live-ledgers.json'); rows = []
    from books_to_life.matching.timely_matcher import TimelyEvidenceMatcher
    for job in read(output / 'jobs.json'):
        assert digest(Path(job['baseline_events'])) == job['baseline_events_sha256']
        events = [json.loads(s) for s in Path(job['baseline_events']).read_text(encoding='utf-8').splitlines()]
        manifest = read(Path(job['manifest']))
        before = replay(Old, manifest, events); assert before == expected[job['id']], job['id']
        after = replay(TimelyEvidenceMatcher, manifest, events)
        row = dict(recording=job['id'], before=before, after=after,
                   added=sorted(set(after['emitted']) - set(before['emitted'])),
                   removed=sorted(set(before['emitted']) - set(after['emitted'])))
        rows.append(row)
        if 'asserted_checkpoint' in job:
            assert (job['asserted_checkpoint'] in after['emitted']) == job['expected_emission'], job['id']
    indexed = {r['recording']: r for r in rows}
    for case in read(output / 'protocol.json')['provider_deletion_controls']:
        assert case['checkpoint'] not in indexed[case['recording']]['after']['emitted'], case
    write(output / 'preflight-replay.json', dict(kind='Saved streaming callbacks; not fresh ASR trials', recordings=rows))
    print('PREFLIGHT', len(rows), 'timelines; all nine assertions and deletion controls pass.', flush=True)
    print('ADDED', [(r['recording'], r['added']) for r in rows if r['added']], flush=True)
    print('REMOVED', [(r['recording'], r['removed']) for r in rows if r['removed']], flush=True)


def run(output):
    check_frozen(output, model_hash=True)
    assert len(read(output / 'preflight-replay.json')['recordings']) == 99
    jobs = read(output / 'downloaded-jobs.json'); Old = old_tracker(output); results = []
    assert [j['id'] for j in jobs] == read(output / 'protocol.json')['ordered_recordings']
    (output / 'streams').mkdir(exist_ok=False)
    for index, job in enumerate(jobs, 1):
        check_frozen(output); assert digest(Path(job['audio'])) == job['audio_sha256']
        stem = output / 'streams' / job['id']; print('START', index, '/', len(jobs), job['id'], flush=True)
        command = [sys.executable, '-X', 'utf8', '-u', 'benchmarks/live_tracker_probe.py',
            '--model', 'parakeet-nemo', '--server', '127.0.0.1', '--port', '9097',
            '--matching_mode', 'split', '--no_book_context', '--files', job['audio'], '--mute_audio_playback',
            '--checkpoints', job['manifest'], '--transcript_file', str(stem.with_suffix('.srt'))]
        env = dict(os.environ, PYTHONUTF8='1'); env.pop('TRACKER_COMPARE_MANIFESTS', None)
        with stem.with_suffix('.log').open('w', encoding='utf-8') as log:
            subprocess.run(command, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT,
                           timeout=math.ceil(job['audio_seconds']*1.5)+180, check=True)
        check_frozen(output); row = audit_and_score(output, job, Old)
        actual = job['asserted_checkpoint'] in row['after']['emitted']
        row['assertion'] = dict(checkpoint=job['asserted_checkpoint'], expected_emission=job['expected_emission'],
            actual_emission=actual, passed=actual == job['expected_emission'], basis=job['assertion_basis'])
        results.append(row); write(output / 'results.json', dict(recordings=results))
        print('DONE', index, 'before/after', len(row['before']['emitted']), len(row['after']['emitted']),
              'added', row['added_emissions'], 'removed', row['removed_emissions'], flush=True)
        assert row['assertion']['passed'], row['assertion']
    controls(output); check_frozen(output, model_hash=True)
    write(output / 'completed.json', dict(fresh_reading_streams=9, fresh_unrelated_streams=4,
        saved_callback_recordings=99, sources_unchanged_during_run=True, asr_unchanged=True,
        model_hash_unchanged=True, all_trials_retained=True, audio_and_manifests_unchanged=True))
    print('COMPLETE 13 fresh streams and 99 saved-callback regressions.', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', choices=('prepare', 'preflight', 'run'), required=True)
    parser.add_argument('--output', type=Path, default=DEST)
    args = parser.parse_args(); output = args.output.resolve()
    if not output.is_relative_to(ROOT / 'output'):
        parser.error('Raw data must remain under ignored output/.')
    {'prepare': prepare, 'preflight': preflight, 'run': run}[args.stage](output)
