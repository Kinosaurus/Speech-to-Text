"""Freeze the current runtime and evaluate new MPS speakers without tuning."""
import argparse
from collections import Counter
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import wave

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from benchmarks import run_mps_heldout as heldout
from benchmarks.run_pending_regression import replay
from benchmarks.summarize_mps_heldout import listening_review
from books_to_life.matching.timely_matcher import TimelyEvidenceMatcher

read, write, digest = heldout.read, heldout.write, heldout.digest
DATE = '2026-11-06'
SEED = 2026110601
DEST = ROOT / ('output/mps-frozen-streaming-' + DATE)
REFERENCE = ROOT / 'output/internal-phonetic-regression-2026-11-03'


def prepare(output):
    reference = read(REFERENCE / 'protocol.json')
    for name, checksum in reference['source_sha256'].items():
        if name.startswith('books_to_life/'):
            assert digest(ROOT / name) == checksum, name
    original_exclusions = heldout.exclusions

    def exclusions():
        used, evidence = original_exclusions()
        pattern = r'\b([345][a-z]\d+[a-z])_EN-OL-RC-\d+_[12]\b'
        # Also include recording-library provenance and raw artifact names.
        for path in (ROOT / 'recordings').rglob('*.json'):
            found = set(re.findall(pattern, path.read_text(encoding='utf-8')))
            if found:
                used.update(found)
                evidence[path.relative_to(ROOT).as_posix()] = sorted(found)
        for folder in ('output', 'recordings'):
            found = set()
            for path in (ROOT / folder).rglob('*'):
                found.update(re.findall(pattern, path.name))
            if found:
                used.update(found)
                evidence[folder + '/(artifact filenames)'] = sorted(found)
        return used, evidence

    heldout.SEED = SEED
    heldout.exclusions = exclusions
    heldout.prepare(output, heldout.DEFAULT_METADATA, REFERENCE / 'source-snapshot')
    protocol = read(output / 'protocol.json')
    # Freeze evaluation helpers/tests as well as the full runtime. No production
    # source is edited. This paired replay baseline is this same frozen version.
    for path in sorted(set((ROOT / 'benchmarks').glob('*.py')) | set((ROOT / 'tests').glob('*.py'))):
        name = path.relative_to(ROOT).as_posix()
        target = output / 'source-snapshot' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
        protocol['source_sha256'][name] = digest(path)
    protocol.update(date=DATE, scope=__doc__, reference_runtime=REFERENCE.relative_to(ROOT).as_posix(),
        runtime_identical_to_latest_completed_regression=True,
        comparison_baseline='Same frozen matcher on saved fresh callbacks; consistency check, not a before/after repair.',
        selected_sha256=digest(output / 'selected.json'), jobs_sha256=digest(output / 'jobs.json'),
        semantic_failure_policy='Keep every selected sample and outcome. Do not stop, replace samples, or tune on semantic misses.',
        report_path='benchmarks/results/mps-frozen-streaming-' + DATE + '.json')
    write(output / 'protocol.json', protocol)
    write(output / 'freeze-record.json', dict(protocol_sha256=digest(output / 'protocol.json'),
        selected_sha256=protocol['selected_sha256'], jobs_sha256=protocol['jobs_sha256'],
        frozen_before_audio_download_and_recognition=True))
    verify(output, model=True)
    print('FROZEN current runtime; 24 recordings, 12 new speakers; no audio downloaded yet.', flush=True)


def verify(output, model=False, audio=False):
    p = heldout.check_frozen(output, model_hash=model)
    assert digest(output / 'protocol.json') == read(output / 'freeze-record.json')['protocol_sha256']
    assert digest(output / 'selected.json') == p['selected_sha256']
    assert digest(output / 'jobs.json') == p['jobs_sha256']
    for name, sha in p['source_sha256'].items():
        assert digest(output / 'source-snapshot' / name) == sha, name
    if (output / 'downloaded-jobs.json').exists():
        jobs = read(output / 'downloaded-jobs.json')
        assert [j['id'] for j in jobs] == p['ordered_recordings']
        assert [dict((k, j[k]) for k in original) for original, j in zip(read(output / 'jobs.json'), jobs)] == read(output / 'jobs.json')
        if audio:
            for j in jobs:
                assert digest(Path(j['audio'])) == j['audio_sha256'], j['id']
    return p


def run(output):
    verify(output, model=True, audio=True)
    jobs = read(output / 'downloaded-jobs.json')
    (output / 'streams').mkdir(exist_ok=False)
    rows = []
    for index, job in enumerate(jobs, 1):
        verify(output)
        assert digest(Path(job['audio'])) == job['audio_sha256']
        stem = output / 'streams' / job['id']
        cmd = [sys.executable, '-X', 'utf8', '-u', 'benchmarks/live_tracker_probe.py',
            '--model', 'parakeet-nemo', '--server', '127.0.0.1', '--port', '9097',
            '--matching_mode', 'split', '--no_book_context', '--files', job['audio'],
            '--mute_audio_playback', '--checkpoints', job['manifest'],
            '--transcript_file', str(stem.with_suffix('.srt'))]
        env = dict(os.environ, PYTHONUTF8='1')
        env.pop('TRACKER_COMPARE_MANIFESTS', None)
        print('START', index, '/24', job['id'], flush=True)
        with stem.with_suffix('.log').open('x', encoding='utf-8') as log:
            subprocess.run(cmd, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT,
                timeout=math.ceil(job['audio_seconds'] * 1.5) + 180, check=True)
        verify(output)
        result = heldout.audit_and_score(output, job, TimelyEvidenceMatcher)
        assert result['before'] == result['after']
        events = [json.loads(s) for s in stem.with_suffix('.events.jsonl').read_text(encoding='utf-8').splitlines()]
        packets = [e for e in events if e['kind'] == 'audio']
        callbacks = [e for e in events if e['kind'] == 'segments']
        assert not any(e['kind'] == 'book_context_sent' for e in events)
        assert any(e['wall'] < packets[-1]['wall'] and not e['segments'][-1]['completed'] for e in callbacks)
        assert replay(TimelyEvidenceMatcher, read(Path(job['manifest'])), events) == result['after']
        result['final_asr'] = ' '.join(s['text'] for s in callbacks[-1]['segments'])
        result['packet_send_seconds'] = packets[-1]['wall'] - packets[0]['wall']
        result['pacing_ratio'] = result['packet_send_seconds'] / job['audio_seconds']
        assert result['packet_send_seconds'] >= job['audio_seconds'] - 1.0
        result['no_hints_sent'] = True
        rows.append(result)
        write(output / 'results.json', dict(recordings=rows))
        print('DONE', index, '/24', job['id'], result['after'], flush=True)
    verify(output, model=True, audio=True)
    write(output / 'completed.json', dict(streams=24, speakers=12, configured_checkpoints=72,
        source_unchanged=True, model_unchanged=True, manifests_unchanged=True,
        all_selected_trials_retained=True, one_trial_per_recording=True,
        all_delivery_eof_app_replay_and_pacing_audits_pass=True))
    print('COMPLETE 24 fresh streams. Semantic misses retained; no runtime tuning.', flush=True)


def summarize(output):
    p = verify(output, model=True, audio=True)
    assert read(output / 'completed.json')['streams'] == 24
    rows = read(output / 'results.json')['recordings']
    jobs = read(output / 'downloaded-jobs.json')
    assert len(rows) == 24 and len({r['speaker'] for r in rows}) == 12
    assert {r['speaker'] for r in rows}.isdisjoint(p['excluded_speakers'])
    assert len({r['audio_sha256'] for r in rows}) == 24
    assert [r['recording'] for r in rows] == p['ordered_recordings']
    canonical = {r['audioID']: r for r in read(heldout.DEFAULT_METADATA)}
    assert all(canonical[r['audioID']] == r for r in read(output / 'selected.json'))
    points = [(r, cp) for r in rows for cp in r['checkpoints']]
    correct = [(r, cp) for r, cp in points if cp['provider_evidence'].get('words')
        and cp['provider_evidence']['substitutions'] == 0 and cp['provider_evidence']['deletions'] == 0]
    deleted = [(r, cp) for r, cp in points if cp['provider_endpoint_deleted'] or cp['provider_required_word_deleted']]
    compact = []
    for row in rows:
        record = {k: v for k, v in row.items() if k not in ('checkpoints', 'phonetic_calls', 'final_asr')}
        record['checkpoints'] = [{k: v for k, v in cp.items() if k != 'provider_evidence'} | {
            'provider_annotation_status': cp['provider_evidence']['status'],
            'provider_counts': {k: cp['provider_evidence'].get(k) for k in ('correct', 'substitutions', 'deletions')}}
            for cp in row['checkpoints']]
        compact.append(record)
    # Existing unrelated ASR is replay evidence, explicitly separate from the
    # 24 new audio streams. Full runtime is frozen for both.
    unrelated = []
    representatives = {}
    for job in jobs:
        cfg = read(Path(job['manifest']))
        representatives.setdefault(tuple(page['text'] for page in cfg['pages']), cfg)
    for name in ('dog', 'dragon', 'nickel', 'recording_2'):
        path = ROOT / 'output/listening-review-2026-11-02/regression/phonetic-controls' / (name + '.events.jsonl')
        events = [json.loads(s) for s in path.read_text(encoding='utf-8').splitlines()]
        for n, cfg in enumerate(representatives.values(), 1):
            unrelated.append(dict(source=name, passage=n, outcomes=replay(TimelyEvidenceMatcher, cfg, events)))
    report = dict(date=DATE, scope=__doc__, selection={k: p[k] for k in (
        'seed', 'provider_revision', 'metadata_sha256', 'speakers', 'excluded_speakers', 'strata', 'ordered_recordings', 'selection_rule')},
        configuration=p['configuration'], model=p['model'], lexicon=p['lexicon'],
        execution=dict(fresh_reading_streams=24, speakers=12, passage_texts=len(representatives),
            configured=72, audio_seconds=sum(r['audio_seconds'] for r in rows),
            runs_per_recording=1, speaker_overlap=0, all_selected_trials_retained=True,
            all_delivery_eof_app_replay_and_pacing_audits_pass=True),
        integrity=dict(no_asr_or_matcher_tuning=True, no_hint_tuning=True,
            runtime_model_lexicon_manifests_audio_unchanged=True,
            runtime_identical_to_latest_completed_regression=True,
            protocol_sha256=digest(output / 'protocol.json'), source_sha256=p['source_sha256']),
        totals={state: sum(len(r['after'][state]) for r in rows) for state in ('emitted', 'suppressed', 'skipped', 'unreached')},
        provider_annotation_review=dict(provider_correct_anchors=len(correct), emitted_provider_correct=sum(cp['emitted'] for r, cp in correct),
            nonemitting_provider_correct=[dict(recording=r['recording'], checkpoint=cp['id']) for r, cp in correct if not cp['emitted']],
            provider_deleted_endpoints_or_essential_words=len(deleted),
            emissions_on_provider_deleted_endpoints_or_essential_words=[dict(recording=r['recording'], checkpoint=cp['id']) for r, cp in deleted if cp['emitted']]),
        unrelated_controls=dict(kind='Saved callbacks, not fresh audio trials', sources=4, comparisons=len(unrelated),
            emitted=sum(len(r['outcomes']['emitted']) for r in unrelated), results=unrelated),
        limitations=['New speakers on six familiar MPS passages, not unseen books or Southeast Asian readers.',
            'Provider word labels are review evidence, not independent human listening acceptance or timing gold.',
            'No microphone/room or human-verified word-end-to-effect latency claim.'],
        recordings=compact, local_artifacts=output.relative_to(ROOT).as_posix())
    report['listening_review_rows'] = listening_review(output, report,
        title='Frozen MPS new-speaker review — ' + DATE,
        introduction='Listen before opening the automated evidence. These are untouched new speakers evaluated with a frozen runtime.')
    write(ROOT / p['report_path'], report)
    write(output / 'summary.json', report)
    print(json.dumps({k: report[k] for k in ('execution', 'totals', 'provider_annotation_review', 'unrelated_controls', 'listening_review_rows')}, indent=2), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', choices=('prepare', 'download', 'run', 'summarize', 'verify'), required=True)
    parser.add_argument('--output', type=Path, default=DEST)
    args = parser.parse_args()
    dest = args.output.resolve()
    if not dest.is_relative_to(ROOT / 'output'):
        parser.error('Raw artifacts must remain in output/.')
    if args.stage == 'download':
        verify(dest)
        heldout.download(dest)
    elif args.stage == 'verify':
        verify(dest, model=True, audio=True)
        print('FROZEN hashes verified.', flush=True)
    else:
        globals()[args.stage](dest)
