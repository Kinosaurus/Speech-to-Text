"""Repeat both reading batches with explicit effect semantics and source audit."""
import argparse
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from books_to_life.matching.checkpoint_matcher import normalize_text
from books_to_life.matching.timely_matcher import TimelyEvidenceMatcher
LIB = ROOT / 'recordings/library'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def prepare(output):
    policy = read(ROOT / 'benchmarks/pilot_effect_policy.json')
    groups = [
        ('original', read(LIB / 'acquisition/mps/import_report.json')['recordings'],
         ROOT / 'output/best-setup-2026-10-31-verified/mps'),
        ('original', read(ROOT / 'output/published-passages-2026-10-30/jobs.json')['recordings'],
         ROOT / 'output/best-setup-2026-10-31-verified/published'),
        ('expansion', read(ROOT / 'output/mps-expansion-2026-11-02/jobs.json')['recordings'],
         ROOT / 'output/mps-expansion-2026-11-02/evaluation/live')]
    jobs = []
    for group, recordings, baseline in groups:
        for row in recordings:
            ident = row['audio_id']
            folder = LIB / row['path']
            frozen = baseline / (ident + '.checkpoints.json')
            manifest = read(frozen)
            for cp in manifest['checkpoints']:
                cp['effect_policy'] = policy['default_effect_policy']
                for rule in policy['rules']:
                    if normalize_text(cp['checkpoint_text']) == normalize_text(rule['checkpoint_text']):
                        cp['required_words'] = rule['required_words']
            inputs = output / 'inputs' / ident
            inputs.mkdir(parents=True)
            write(inputs / 'checkpoints.json', manifest)
            jobs.append(dict(id=ident, group=group, audio=str(folder / 'audio.wav'),
                manifest=str(inputs / 'checkpoints.json'), baseline=str(baseline),
                audio_sha256=hashlib.sha256((folder / 'audio.wav').read_bytes()).hexdigest(),
                original_manifest_sha256=hashlib.sha256(frozen.read_bytes()).hexdigest(),
                manifest_sha256=hashlib.sha256((inputs / 'checkpoints.json').read_bytes()).hexdigest()))
    write(output / 'jobs.json', jobs)
    write(output / 'effect_policy.json', policy)
    return jobs


def replay(output, jobs):
    results = []
    for job in jobs:
        events = [json.loads(s) for s in (Path(job['baseline']) / (job['id'] + '.events.jsonl')).read_text(encoding='utf-8').splitlines()]
        matcher = TimelyEvidenceMatcher(read(Path(job['manifest'])))
        origin = next(e['wall'] for e in events if e['kind'] == 'audio')
        changes = []
        for event in events:
            if event['kind'] != 'segments':
                continue
            segments = event['segments']
            update = matcher.process(' '.join(s['text'] for s in segments), segments)
            if update.triggered or update.effect_suppressed:
                changes.append(dict(wall_seconds=event['wall'] - origin, **asdict(update)))
        results.append(dict(id=job['id'], group=job['group'], updates=changes,
            triggered=sorted(matcher.triggered_checkpoint_ids), suppressed=sorted(matcher.suppressed_checkpoint_ids)))
        print('REPLAY', job['id'], 'emitted', len(matcher.triggered_checkpoint_ids),
              'suppressed', sorted(matcher.suppressed_checkpoint_ids), flush=True)
    write(output / 'diagnostic-replay.json', dict(kind='saved-callback diagnostic replay, not fresh ASR', results=results))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--prepare-only', action='store_true')
    parser.add_argument('--use-prepared', action='store_true')
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to(ROOT / 'output'):
        parser.error('Raw results must stay under ignored output/.')
    if args.use_prepared:
        jobs = read(output / 'jobs.json')
    else:
        output.mkdir(parents=True, exist_ok=False)
        jobs = prepare(output)
    replay(output, jobs)
    if args.prepare_only:
        return
    if (output / 'protocol.json').exists():
        parser.error('Prior live protocol exists; use a new destination.')
    sources = list((ROOT / 'books_to_life').rglob('*.py')) + [ROOT / 'benchmarks' / name for name in
        ('run_guarded_pilot.py', 'live_tracker_probe.py', 'pilot_effect_policy.json')]
    hashes = {}
    for path in sources:
        name = path.relative_to(ROOT).as_posix()
        content = path.read_bytes()
        hashes[name] = hashlib.sha256(content).hexdigest()
        dest = output / 'source-snapshot' / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(content)
    write(output / 'protocol.json', dict(source_sha256=hashes,
        configuration=dict(model='parakeet-nemo', matching_mode='split', hints=False,
            chunk_ms=560, right_ms=560, left_ms=5600, threshold=82, stability=2, min_coverage=.8),
        effect_policy=read(output / 'effect_policy.json'), runs_per_recording=1,
        warmup='No separate inference warmup; first stream includes first-inference effects.'))
    deadline = time.monotonic() + 240
    while True:
        try:
            with socket.create_connection(('127.0.0.1', 9097), timeout=1):
                break
        except OSError:
            if time.monotonic() > deadline:
                raise TimeoutError('Start the documented NeMo server on port 9097.')
            time.sleep(1)
    unique = {}
    for job in jobs:
        key = tuple(p['text'] for p in read(Path(job['manifest']))['pages'])
        unique.setdefault(key, job['manifest'])
    controls = {f'passage-{i}': path for i, path in enumerate(unique.values(), 1)}
    jobs += [dict(id=name + '-control', group='controls',
        audio=str(LIB / f'stories/{name}/readers/{name}/audio.wav'), manifests=controls)
        for name in ('dog', 'dragon', 'nickel', 'recording_2')]
    for job in jobs:
        folder = output / job['group']
        folder.mkdir(exist_ok=True)
        stem = folder / job['id']
        args = ['--model', 'parakeet-nemo', '--port', '9097', '--server', '127.0.0.1',
            '--matching_mode', 'split', '--no_book_context', '--files', job['audio'],
            '--mute_audio_playback', '--transcript_file', str(stem.with_suffix('.srt'))]
        env = dict(os.environ, PYTHONUTF8='1')
        if 'manifest' in job:
            args += ['--checkpoints', job['manifest']]
        else:
            env['TRACKER_COMPARE_MANIFESTS'] = json.dumps(job['manifests'])
        if stem.with_suffix('.events.jsonl').exists():
            raise FileExistsError('Refusing to overwrite completed or partial stream evidence.')
        print('START', job['group'], job['id'], flush=True)
        with stem.with_suffix('.log').open('w', encoding='utf-8') as log:
            subprocess.run([sys.executable, '-X', 'utf8', '-u', 'benchmarks/live_tracker_probe.py', *args],
                cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT, timeout=420, check=True)
        print('DONE', job['id'], flush=True)
    for name, digest in hashes.items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest, name
    write(output / 'completed.json', dict(reading_streams=21, control_streams=4,
        control_manifest_comparisons=4*len(controls), source_unchanged=True))
    print('All 25 fresh streams completed; source snapshot unchanged.', flush=True)


if __name__ == '__main__':
    main()
