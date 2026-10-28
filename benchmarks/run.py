"""Benchmark five ASR models sequentially without building images or touching the app."""
import argparse
import csv
import hashlib
import json
import math
import subprocess
import sys
import uuid
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from benchmarks.metrics import edit_alignment

PROFILES = {
    'whisper-medium-raw': ('whisper', 'medium.en', False, 160, False, None),
    'whisper-medium-hints': ('whisper', 'medium.en', True, 160, False, None),
    'whisper-small-raw': ('whisper', 'small.en', False, 160, False, None),
    'whisper-small-hints': ('whisper', 'small.en', True, 160, False, None),
    'whisper-base-raw': ('whisper', 'base.en', False, 160, False, None),
    'whisper-base-hints': ('whisper', 'base.en', True, 160, False, None),
    'parakeet-320ms': ('cpp', 'parakeet', False, 160, False, None),
    'parakeet-1120ms': ('cpp', 'parakeet', False, 560, False, None),
    'parakeet-2080ms': ('cpp', 'parakeet', False, 1040, False, None),
    'moonshine-cpp-gpu': ('cpp', 'moonshine', False, 160, False, None),
    'moonshine-official-cpu-raw': ('moonshine', 'moonshine-medium', False, 160, False, None),
    'moonshine-official-cpu-hints': ('moonshine', 'moonshine-medium', True, 160, False, None),
    'moonshine-official-cpu-single-raw': ('moonshine', 'moonshine-medium', False, 160, True, None),
    'moonshine-official-cpu-single-hints': ('moonshine', 'moonshine-medium', True, 160, True, None),
    'moonshine-cpp-gpu-500ms': ('cpp', 'moonshine', False, 160, False, 500),
}


def matching_result(path, profile, args):
    if not path.exists():
        return False
    result = json.loads(path.read_text(encoding='utf-8'))
    backend, model, hints, chunk, single_thread, decode_ms = profile
    expected = {'backend': backend, 'model': model, 'hints': hints, 'chunk_ms': chunk,
                'benchmark_mode': 'streaming-only-v1', 'stream_repetitions': 1,
                'audio_sha256': hashlib.sha256(args.audio.read_bytes()).hexdigest(),
                'manifest_sha256': hashlib.sha256(args.manifest.read_bytes()).hexdigest()}
    return (all(result.get(key) == value for key, value in expected.items())
            and result.get('ort_single_thread', False) == single_thread
            and result.get('moonshine_decode_ms') == decode_ms)


def load_manual_timing(audio_path, manifest_path, output):
    """Load listening marks and optional skipped-anchor provenance, never ASR estimates."""
    path = output / 'manual-checkpoint-times.json'
    if not path.exists():
        return {}, set(), {}
    times = json.loads(path.read_text(encoding='utf-8'))
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    valid_ids = {str(cp['id']) for cp in manifest['checkpoints']}
    with wave.open(str(audio_path), 'rb') as recording:
        duration = recording.getnframes() / recording.getframerate()
    if not isinstance(times, dict) or any(
        key not in valid_ids or type(end) not in (int, float)
        or not math.isfinite(end) or not 0 <= end <= duration
        for key, end in times.items()
    ):
        raise ValueError('Manual checkpoint times require known IDs and finite seconds within the audio.')
    metadata_path = output / 'manual-checkpoint-annotations.json'
    metadata = json.loads(metadata_path.read_text(encoding='utf-8')) if metadata_path.exists() else {}
    if not isinstance(metadata, dict):
        raise ValueError('Manual annotation metadata must be an object.')
    for key, source in [('audio_sha256', audio_path), ('manifest_sha256', manifest_path)]:
        if key in metadata and metadata[key] != hashlib.sha256(source.read_bytes()).hexdigest():
            raise ValueError('Manual annotations have mismatched input: ' + key)
    skipped = metadata.get('skipped_checkpoint_ids', [])
    if (not isinstance(skipped, list) or any(not isinstance(cp, str) or cp not in valid_ids for cp in skipped)
            or set(skipped) & set(times)):
        raise ValueError('Skipped checkpoints must have known IDs and cannot also have spoken endpoint times.')
    return times, set(skipped), metadata


def summarize(args):
    manifest = json.loads(args.manifest.read_text(encoding='utf-8'))
    reference = ' '.join(p['text'] for p in sorted(manifest['pages'], key=lambda p: p['page']))
    anchor_times, skipped_anchors, annotation_metadata = load_manual_timing(args.audio, args.manifest, args.output)
    anchor_sources = {key: 'manual' for key in anchor_times}
    # No whole-file inference, including automatic timing-reference passes.
    timing_kind = 'unavailable; no manually timed anchor endings supplied'
    if anchor_times:
        timing_kind = 'manually supplied checkpoint endpoints'
        if annotation_metadata.get('resolution'):
            timing_kind += '; ' + annotation_metadata['resolution']
    rows, results = [], {}
    for name, profile in PROFILES.items():
        path = args.output / (name + '.json')
        if not matching_result(path, profile, args):
            continue
        result = json.loads(path.read_text())
        # Score stored transcripts with one common normalizer, including resumed runs.
        result['stream']['reference_score'] = edit_alignment(reference, result['stream']['text'])[0]
        rows.append({'profile': name, 'device': 'CPU' if profile[0] == 'moonshine' else 'RTX 4060 GPU',
                     'stream_reference_wer_pct': round(result['stream']['reference_score']['wer'] * 100, 2),
                     'checkpoints_triggered': len(result['stream']['triggered_ids']),
                     'checkpoints_total': len(manifest['checkpoints']),
                     'sampled_peak_process_rss_mib': round(result['sampled_peak_process_rss_bytes'] / 2**20, 1)
                         if result['sampled_peak_process_rss_bytes'] else None,
                     'gpu_memory_after_stream_mib': result['gpu_memory_after_stream_mib'],
                     'max_feed_lateness_seconds': round(result['stream']['max_feed_lateness_seconds'], 3),
                     'stream_wall_seconds': round(result['stream']['wall_seconds'], 3),
                     'invalid_updates': result['stream']['invalid_update_count']})
        result['checkpoint_delays'] = []
        for event in result['stream']['events']:
            if event['triggered']:
                end = anchor_times.get(event['checkpoint_id'])
                result['checkpoint_delays'].append({
                    'id': event['checkpoint_id'], 'trigger_wall_seconds': event['wall_seconds'],
                    'reference_anchor_end_seconds': end,
                    'delay_seconds': event['wall_seconds'] - end if end is not None else None,
                    'reference_timing_kind': timing_kind,
                    'reference_model': anchor_sources.get(event['checkpoint_id']),
                    'estimated_early_trigger': event['wall_seconds'] < end - 0.25 if end is not None else None,
                    'anchor_reported_skipped': event['checkpoint_id'] in skipped_anchors,
                })
        rows[-1]['early_triggers'] = sum(e['estimated_early_trigger'] is True for e in result['checkpoint_delays']) if anchor_times else None
        rows[-1]['activations_on_skipped_anchors'] = len(set(result['stream']['triggered_ids']) & skipped_anchors) if annotation_metadata else None
        rows[-1]['manually_timed_anchors_triggered'] = len(set(result['stream']['triggered_ids']) & set(anchor_times)) if anchor_times else None
        rows[-1]['manually_timed_anchors_total'] = len(anchor_times) if anchor_times else None
        results[name] = result
    payload = {'scope': 'one child recording; five model identities with separately labelled deployment profiles',
               'benchmark_mode': 'streaming-only-v1', 'warmup': 'none; models load before the stream timer starts',
               'audio': str(args.audio), 'manifest': str(args.manifest),
               'normalization': 'lowercase words; punctuation ignored; common English contractions expanded',
               'reference_status': 'supplied passage; audible misreads/repetitions not independently annotated',
               'anchor_times': anchor_times, 'anchor_time_source': timing_kind, 'anchor_reference_models': anchor_sources,
               'manually_reported_skipped_anchors': sorted(skipped_anchors),
               'manual_annotation_metadata': annotation_metadata,
               'latency_scope': 'arrival of the confirming ASR update; matcher computation, microphone, '
                                'network and physical effect playback excluded',
               'stream_repetitions': 1,
               'false_trigger_evaluation': 'not established: requires separate off-book/negative audio and review of scene catch-up policy',
               'rows': rows, 'profiles': results}
    (args.output / 'results.json').write_text(json.dumps(payload, indent=2), encoding='utf-8')
    if rows:
        with (args.output / 'results.csv').open('w', newline='', encoding='utf-8') as output:
            writer = csv.DictWriter(output, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    with wave.open(str(args.audio), 'rb') as recording:
        duration = recording.getnframes() / recording.getframerate()
    lines = ['# Child-reading streaming ASR benchmark', '',
             f'{args.audio.name}, {duration:.1f}-second recording. Lower word error rate (WER) is better.', '',
             'Streaming only. No whole-file recognition, whole-recording warmup or automatic timing-reference pass.', '',
             '| Profile | Streaming WER | Effects emitted | Maximum feed lag | Total stream time | Invalid ASR updates | Early effects |',
             '|---|---:|---:|---:|---:|---:|---:|']
    for row in rows:
        early = row['early_triggers'] if row['early_triggers'] is not None else 'not measured'
        lines.append(f"| {row['profile']} | {row['stream_reference_wer_pct']}% | "
                     f"{row['checkpoints_triggered']}/{row['checkpoints_total']} | {row['max_feed_lateness_seconds']} s | "
                     f"{row['stream_wall_seconds']} s | {row['invalid_updates']} | {early} |")
    lines += ['', '## How to interpret this', '',
              '- WER compares the output to the supplied passage. Unannotated child misreads/repetitions can affect it.',
              '- Models load before timing starts. Each receives the recording once, with no recognition warmup.',
              '- Streaming replays the original audio at real speed. Each profile has one streaming trial.',
              '- Whisper uses the existing WhisperLive backend, VAD and live BookContext; only the socket is replaced with an in-process capture.',
              '- C++ profiles use the exact RTX 4060 Vulkan device, F16 weights, and two CPU threads.',
              '- Official Moonshine uses quantized assets and CPU, so its timings compare a deployment option, not GPU kernel efficiency.',
              '- Official Moonshine single-thread profiles set MOONSHINE_ORT_SINGLE_THREAD=1; default-thread measurements are retained.',
              '- Moonshine C++ 500ms limits decoding frequency while still receiving 64 ms audio packets; its native default is also retained.',
              '- Model and CPU/GPU/runtime choices differ; this is a practical setup comparison.',
              '- All profiles use the same unchanged AlignmentMatcher and checkpoints.',
              '- Delay timestamps mark the arrival of the ASR update used to confirm a checkpoint, before matcher computation.',
              '- GPU memory is a whole-device snapshot after streaming, not an allocator peak or process-exclusive measurement.',
              '- Memory RSS is sampled every 50 ms and includes each runtime\'s imports and model.',
              '- Invalid timestamp updates are retained for ASR scoring and reported, but cannot advance the unchanged matcher.',
              '- Maximum feed lag measures whether audio delivery falls behind real time. It is not checkpoint response delay.',
              '- Total stream time includes 1.5 s trailing silence and Whisper\'s additional 2 s settling wait.',
              '- No negative/off-book recordings were included; false-trigger rates are not established.', '',
              '## Checkpoint response times', '',
              f'Endpoint timing source: **{timing_kind}**.', '',
              'Delay and early-trigger checks require manually supplied anchor-end times. Missing times remain unavailable.',
              'Effects emitted is a raw count, not a count of correctly timed detections.', '',
              'Early-effect counts include only manually timed anchors. Missing timing marks are not assumed on time.',
              'An activation on a skipped anchor may reflect scene catch-up; it is not a direct detection of that phrase.', '',
              '| Profile | Checkpoint | Confirming ASR update arrived | Delay relative to supplied mark |',
              '|---|---|---:|---:|']
    for name, result in results.items():
        for event in result['checkpoint_delays']:
            delay = (f"{event['delay_seconds']:+.1f} s" if event['delay_seconds'] is not None else
                     'phrase reported skipped; no delay defined' if event['anchor_reported_skipped'] else 'not available')
            lines.append(f"| {name} | {event['id']} | {event['trigger_wall_seconds']:.3f} s | {delay} |")
    if skipped_anchors:
        lines += ['', '## Activations on skipped checkpoint phrases', '',
                  'Reported skipped: ' + ', '.join(sorted(skipped_anchors)) + '.', '',
                  '| Profile | Activations on skipped phrases |', '|---|---:|']
        for row in rows:
            lines.append(f"| {row['profile']} | {row['activations_on_skipped_anchors']} |")
    lines += ['', 'Review every transcript in results.json. Add manual-checkpoint-times.json with checkpoint IDs mapped to',
              'the listening-marked end time of each anchor in the WAV, then rerun run.py --summarize-only to update delays.', '']
    if rows:
        best_score = min(row['stream_reference_wer_pct'] for row in rows)
        best_profiles = ', '.join(row['profile'] for row in rows if row['stream_reference_wer_pct'] == best_score)
        lines += ['## Findings for this recording', '',
                  f'Lowest measured streaming WER: **{best_score}%**, shared by {best_profiles}.', '',
                  'This is one recording, with one streaming replay per profile. It does not establish a universal model ranking.',
                  'Hints provide the expected passage to the decoder and can also cause future text to appear prematurely.',
                  'Read suspected early effects alongside word scores; a good final transcript can hide an earlier wrong trigger.', '']
    (args.output / 'report.md').write_text('\n'.join(lines), encoding='utf-8')
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--audio', type=Path, default=Path('recordings/little_mermaid.wav'))
    parser.add_argument('--manifest', type=Path, default=Path('examples/little_mermaid_story.json'))
    parser.add_argument('--cache', type=Path, default=Path('model-cache/asr-benchmark'))
    parser.add_argument('--output', type=Path, default=Path('output/benchmarks/little-mermaid-streaming'))
    parser.add_argument('--profiles', nargs='+', choices=list(PROFILES), default=list(PROFILES))
    parser.add_argument('--profile-timeout', type=int, default=240,
                        help='Maximum seconds per profile, including loading and real-paced replay.')
    parser.add_argument('--resume', action='store_true')
    parser.add_argument('--summarize-only', action='store_true')
    args = parser.parse_args()
    if args.profile_timeout <= 0:
        parser.error('--profile-timeout must be positive.')
    root = Path(__file__).resolve().parents[1]
    for key in ('audio', 'manifest', 'cache', 'output'):
        setattr(args, key, getattr(args, key).resolve())
    args.output.mkdir(parents=True, exist_ok=True)
    if not args.summarize_only:
        for name in args.profiles:
            profile = PROFILES[name]
            backend, model, hints, chunk, single_thread, decode_ms = profile
            result_path = args.output / (name + '.json')
            if args.resume and matching_result(result_path, profile, args):
                print('Reusing matching completed profile:', name, flush=True)
                continue
            if backend == 'whisper':
                if not args.audio.is_relative_to(root) or not args.manifest.is_relative_to(root):
                    parser.error('Docker audio and manifest must be inside the repository.')
                container_name = 'stt-asr-benchmark-' + uuid.uuid4().hex[:12]
                command = ['docker', 'run', '--rm', '--name', container_name, '--gpus', 'all', '--entrypoint', 'python',
                           '-e', 'HF_HUB_OFFLINE=1', '-e', 'OMP_NUM_THREADS=2', '-e', 'OPENBLAS_NUM_THREADS=1',
                           '-v', f'{root}:/workspace:ro', '-v', f'{args.output}:/results',
                           '-v', 'speech-to-text_gpu-model-cache:/root/.cache:ro', '-w', '/workspace',
                           'books-to-life-asr-gpu:local', '-u', 'benchmarks/worker.py',
                           '--audio', '/workspace/' + args.audio.relative_to(root).as_posix(),
                           '--manifest', '/workspace/' + args.manifest.relative_to(root).as_posix(),
                           '--output', '/results/' + result_path.name]
            else:
                command = [sys.executable, '-u', str(root / 'benchmarks/worker.py'),
                           '--audio', str(args.audio), '--manifest', str(args.manifest),
                           '--cache', str(args.cache), '--output', str(result_path)]
            command += ['--backend', backend, '--model', model, '--chunk-ms', str(chunk)]
            if hints:
                command += ['--hints']
            if single_thread:
                command += ['--ort-single-thread']
            if decode_ms is not None:
                command += ['--moonshine-decode-ms', str(decode_ms)]
            print('Running:', name, flush=True)
            with (args.output / (name + '.log')).open('w', encoding='utf-8') as log:
                try:
                    completed = subprocess.run(command, cwd=root, stdout=log, stderr=subprocess.STDOUT,
                                               timeout=args.profile_timeout)
                except subprocess.TimeoutExpired:
                    if backend == 'whisper':
                        subprocess.run(['docker', 'stop', '--time', '10', container_name],
                                       stdout=log, stderr=subprocess.STDOUT, timeout=30)
                    raise
            if completed.returncode:
                raise RuntimeError(f'{name} failed; inspect {name}.log. No other profile was started.')
            result = json.loads(result_path.read_text())
            print(f"Completed {name}: streaming WER {result['stream']['reference_score']['wer']:.1%}; "
                  f"effects {len(result['stream']['triggered_ids'])}/"
                  f"{len(json.loads(args.manifest.read_text())['checkpoints'])}", flush=True)
    rows = summarize(args)
    print('Profiles summarized:', len(rows), flush=True)
    print('Report:', args.output / 'report.md', flush=True)


if __name__ == '__main__':
    main()
