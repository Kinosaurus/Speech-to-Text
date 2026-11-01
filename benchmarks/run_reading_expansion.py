"""Run the frozen additional-reader test without changing recognition settings."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / 'recordings/library'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--jobs', type=Path, default=ROOT / 'output/mps-expansion-2026-11-02/jobs.json')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to(ROOT / 'output'):
        parser.error('Raw corpus results must stay in ignored output/.')
    output.mkdir(parents=True, exist_ok=False)
    jobs = json.loads(args.jobs.read_text(encoding='utf-8'))
    manifests = {}
    for row in jobs['recordings']:
        path = LIB / row['path'] / 'checkpoints.json'
        assert hashlib.sha256(path.read_bytes()).hexdigest() == row['manifest_sha256']
        manifest = json.loads(path.read_text(encoding='utf-8'))
        key = tuple(p['text'] for p in manifest['pages'])
        if key not in manifests:
            manifests[key] = str(path)
    controls = {f'passage-{i}': path for i, path in enumerate(manifests.values(), 1)}
    control_jobs = [dict(id=name, condition='off-book',
        audio=f'recordings/library/stories/{name}/readers/{name}/audio.wav',
        manifests=controls, expected={key: {} for key in controls})
        for name in ('dog', 'dragon', 'nickel', 'recording_2')]
    (output / 'controls-jobs.json').write_text(json.dumps(control_jobs, indent=2) + '\n')
    sources = list((ROOT / 'books_to_life').rglob('*.py')) + [ROOT / 'benchmarks' / name for name in
        ('prepare_mps_expansion.py', 'run_reading_expansion.py', 'run_mps_streaming.py',
         'run_boundary_comparison.py', 'live_tracker_probe.py', 'observer_manifests.py')]
    hashes = {}
    for path in sources:
        name = path.relative_to(ROOT).as_posix()
        content = path.read_bytes()
        hashes[name] = hashlib.sha256(content).hexdigest()
        snapshot = output / 'source-snapshot' / name
        snapshot.parent.mkdir(parents=True, exist_ok=True)
        snapshot.write_bytes(content)
    protocol = dict(configuration=dict(model='parakeet-nemo', matching_mode='split', hints=False,
        chunk_ms=560, right_ms=560, left_ms=5600, sample_rate=16000, audio_packet_samples=4096,
        threshold=82, stability=2, min_coverage=0.8, repetitions=1),
        source_sha256=hashes, selection=jobs['selection'],
        jobs_sha256=hashlib.sha256(args.jobs.read_bytes()).hexdigest(),
        controls=dict(audio_recordings=4, unique_passage_manifests=len(controls)),
        warmup='No separate inference warmup; first clip includes first-inference effects.')
    (output / 'protocol.json').write_text(json.dumps(protocol, indent=2) + '\n')
    deadline = time.monotonic() + 240
    while True:
        try:
            with socket.create_connection(('127.0.0.1', 9097), timeout=1):
                break
        except OSError:
            if time.monotonic() > deadline:
                raise TimeoutError('Start the documented NeMo server on port 9097.')
            time.sleep(1)
    commands = [
        ['benchmarks/run_mps_streaming.py', '--jobs', str(args.jobs), '--results', str(output / 'live')],
        ['benchmarks/run_boundary_comparison.py', '--jobs', str(output / 'controls-jobs.json'),
         '--output', str(output / 'controls')]]
    for command in commands:
        subprocess.run([sys.executable, '-X', 'utf8', '-u', *command], cwd=ROOT,
                       env=dict(os.environ, PYTHONUTF8='1'), check=True)
    for name, digest in hashes.items():
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != digest:
            raise RuntimeError(f'Source changed during the test: {name}')
    print('All streams completed; source snapshot unchanged.', flush=True)


if __name__ == '__main__':
    main()
