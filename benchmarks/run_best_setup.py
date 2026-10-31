"""Repeat the nine local passage trials and four unrelated-speech controls.

Start the documented NeMo server first. Raw transcripts and corpus data stay in
ignored output/. The generated summary contains hashes and aggregate measurements.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import statistics
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / 'recordings/library'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')


def source_hashes():
    paths = sorted((ROOT / 'books_to_life').rglob('*.py'))
    paths += [ROOT / 'benchmarks' / name for name in
              ('live_tracker_probe.py', 'run_mps_streaming.py',
               'run_boundary_comparison.py', 'run_best_setup.py')]
    return {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in paths}


def summarize(output):
    protocol = read(output / 'protocol.json')
    current_sources = source_hashes()
    changed = sorted(name for name in current_sources.keys() | protocol['source_sha256'].keys()
                     if current_sources.get(name) != protocol['source_sha256'].get(name))
    # Allow this coordinator's report reader to be repaired after a completed
    # trial, while keeping the actual inference/client/probe sources immutable.
    if any(name != 'benchmarks/run_best_setup.py' for name in changed):
        raise RuntimeError('Inference or audit harness source changed during the evaluation.')
    estimates = {}
    for folder in ('live-2026-10-29-verified', 'published-passages-live-2026-10-30'):
        for point in read(LIB / 'evaluation' / folder / 'estimated_delays.json')['checkpoints']:
            estimates[point['audio_id'], point['id']] = point['estimated_end_seconds']
    summary = dict(configuration=protocol['configuration'], source_sha256=protocol['source_sha256'],
                   summary_source_sha256=current_sources,
                   summary_only_source_changes=changed,
                   timing='Previously frozen acoustic estimates mapped onto fresh packet clocks; not manually verified.',
                   repetitions=1, recordings=[], controls={})
    for group in ('mps', 'published'):
        for row in read(output / group / 'comparison.json')['recordings']:
            stem = output / group / row['audio_id']
            events = [json.loads(line) for line in stem.with_suffix('.events.jsonl').read_text(encoding='utf-8').splitlines()]
            packets = [e for e in events if e['kind'] == 'audio']
            origin = packets[0]['wall']
            current = row['observers']['timely']
            # Older Windows child processes wrote cp1252 even though the parent
            # opened the destination as UTF-8. Trigger IDs are ASCII; replacement
            # decoding preserves those lines without rewriting the raw evidence.
            app = re.findall(r'^\[TRIGGER\] (\S+):', stem.with_suffix('.log').read_text(encoding='utf-8', errors='replace'), flags=re.M)
            if app != current['triggered']:
                raise RuntimeError(f'Application/observer mismatch: {row["audio_id"]}')
            delays = []
            for event in current['events']:
                endpoint = estimates[row['audio_id'], event['checkpoint']]
                sample = endpoint * row['sample_rate']
                packet = next(p for p in packets if p['sample_start'] + p['sample_count'] >= sample)
                wall = packet['wall'] + (sample - packet['sample_start']) / row['sample_rate']
                delays.append(dict(checkpoint=event['checkpoint'],
                                   estimated_delay_seconds=origin + event['arrival_seconds'] - wall))
            summary['recordings'].append(dict(
                group=group, audio_id=row['audio_id'], audio_sha256=row['audio_sha256'],
                manifest_sha256=row['manifest_sha256'], audio_seconds=row['audio_seconds'],
                expected=len(row['expected_checkpoint_ids']), triggered=len(current['triggered']),
                missing=current['missing'], duplicates=current['duplicate_triggers'],
                unexpected=current['unexpected'], first_asr_seconds=row['first_asr_seconds'],
                all_samples_delivered=row['samples_sent'] == round(row['audio_seconds'] * row['sample_rate']),
                stream_done=row['stream_done'], partial_before_eof=row['partial_before_eof'],
                application_observer_agree=True, delays=delays,
                observer_counts={mode: len(value['triggered']) for mode, value in row['observers'].items()}))
    controls = read(output / 'controls/results.json')
    summary['controls'] = dict(recordings=len(controls),
        book_comparisons=sum(len(row['manifests']) for row in controls),
        current_tracker_triggers=sum(t['mode'] == 'timely' for row in controls for t in row['triggers']),
        all_observer_triggers=sum(len(row['triggers']) for row in controls),
        all_samples_delivered=all(row['samples_sent'] == round(row['audio_seconds'] * 16000) for row in controls),
        all_final_completed_and_normal_close=all(row['final_completed_and_normal_close'] for row in controls))
    rows = summary['recordings']
    delays = [d['estimated_delay_seconds'] for row in rows for d in row['delays']]
    summary['aggregate'] = dict(recordings=len(rows), expected=sum(r['expected'] for r in rows),
        triggered=sum(r['triggered'] for r in rows), median_estimated_delay_seconds=statistics.median(delays),
        min_estimated_delay_seconds=min(delays), max_estimated_delay_seconds=max(delays),
        more_than_one_second_early=sum(d < -1 for d in delays),
        duplicate_recordings=sum(r['duplicates'] for r in rows),
        unexpected_ids=sum(len(r['unexpected']) for r in rows),
        median_first_asr_seconds=statistics.median(r['first_asr_seconds'] for r in rows),
        delivery_and_completion_pass=all(r['all_samples_delivered'] and r['stream_done'] and
            r['partial_before_eof'] and r['application_observer_agree'] for r in rows))
    write(output / 'summary.json', summary)
    print(json.dumps(summary['aggregate'], indent=2), flush=True)
    print(json.dumps(summary['controls'], indent=2), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--summarize-only', action='store_true')
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to(ROOT / 'output'):
        parser.error('Keep raw results inside the ignored output/ folder.')
    if args.summarize_only:
        summarize(output)
        return
    output.mkdir(parents=True, exist_ok=True)
    if (output / 'protocol.json').exists():
        parser.error('Use a new output folder; prior runs are preserved.')
    mps = read(LIB / 'acquisition/mps/import_report.json')
    published = read(ROOT / 'output/published-passages-2026-10-30/jobs.json')
    books = {r['audio_id']: str(LIB / r['path'] / 'checkpoints.json')
             for r in mps['recordings'] + published['recordings']}
    jobs = [dict(id=name, audio=f'recordings/library/stories/{name}/readers/{name}/audio.wav',
                 condition='off-book', manifests=books, expected={book: {} for book in books})
            for name in ('dog', 'dragon', 'nickel', 'recording_2')]
    write(output / 'controls-jobs.json', jobs)
    write(output / 'protocol.json', dict(configuration=dict(
        model='Parakeet Unified NeMo 0.6B', device='RTX 3070 Ti CUDA bfloat16 / WSL Ubuntu-24.04',
        chunk_ms=560, right_ms=560, left_ms=5600, boost=1.0, hints=False,
        matching_mode='split (TimelyEvidenceMatcher)', threshold=82, stability=2,
        minimum_coverage=0.8, audio_packet_samples=4096, sample_rate=16000,
        warmup='No separate recognition warmup; first recording includes first-inference effects.'),
        source_sha256=source_hashes(), jobs=jobs))
    deadline = time.monotonic() + 240
    while True:
        try:
            with socket.create_connection(('127.0.0.1', 9097), timeout=1):
                break
        except OSError:
            if time.monotonic() > deadline:
                raise TimeoutError('Start the NeMo server on port 9097 first.')
            time.sleep(1)
    commands = [
        ['benchmarks/run_mps_streaming.py', '--results', str(output / 'mps')],
        ['benchmarks/run_mps_streaming.py', '--results', str(output / 'published'),
         '--jobs', 'output/published-passages-2026-10-30/jobs.json'],
        ['benchmarks/run_boundary_comparison.py', '--output', str(output / 'controls'),
         '--jobs', str(output / 'controls-jobs.json')]]
    for command in commands:
        subprocess.run([sys.executable, '-X', 'utf8', '-u', *command], cwd=ROOT, check=True,
                       env=dict(os.environ, PYTHONUTF8='1'))
    summarize(output)


if __name__ == '__main__':
    main()
