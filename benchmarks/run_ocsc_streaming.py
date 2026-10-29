"""Stream a local, provenance-recorded OCSC subset through paired observers.

Source media/manifests remain in ignored output/ocsc. This runs real paced
audio; it does not replay saved transcripts or alter tracker thresholds.
"""
import hashlib
import argparse
import json
import subprocess
import sys
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from recording_library import resolve_recording_path
BASE = ROOT / 'output/ocsc'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--subset', type=Path, default=ROOT / 'recordings/library/evaluation/ocsc_subsets/standard.json')
    parser.add_argument('--results', type=Path, default=BASE / 'results')
    args = parser.parse_args()
    args.results.mkdir(parents=True, exist_ok=True)
    subset = json.loads(args.subset.read_text())
    results = []
    for job in subset['jobs']:
        stem = args.results / job['id']
        audio = resolve_recording_path(job['clip'])
        manifest = job.get('manifest', subset.get('manifest'))
        if not manifest:
            raise ValueError(f"No checkpoint manifest for {job['id']}")
        assert hashlib.sha256(audio.read_bytes()).hexdigest() == job['clip_sha256']
        command = [sys.executable, '-u', str(ROOT / 'benchmarks/live_tracker_probe.py'),
                   '--model', 'parakeet-nemo', '--server', '127.0.0.1', '--port', '9097',
                   '--matching_mode', 'split', '--files', str(audio),
                   '--mute_audio_playback', '--no_book_context', '--checkpoints',
                   str(resolve_recording_path(manifest)), '--transcript_file', str(stem.with_suffix('.srt'))]
        print('START', job['id'], flush=True)
        with stem.with_suffix('.log').open('w', encoding='utf-8') as log:
            process = subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
                                     timeout=job.get('duration_seconds', 420)+180)
        if process.returncode:
            raise RuntimeError(f"Client failed for {job['id']}; inspect {stem}.log")
        events = [json.loads(line) for line in stem.with_suffix('.events.jsonl').read_text().splitlines()]
        packets = [e for e in events if e['kind'] == 'audio']
        segments = [e for e in events if e['kind'] == 'segments']
        with wave.open(str(audio)) as wav:
            frames, rate = wav.getnframes(), wav.getframerate()
        assert sum(e['sample_count'] for e in packets) == frames
        assert segments and any(e['kind'] == 'end_of_audio' for e in events)
        origin = packets[0]['wall']
        row = dict(id=job['id'], audio_seconds=frames/rate, samples_sent=frames,
                   delivery_seconds=packets[-1]['wall']-origin+packets[-1]['sample_count']/rate,
                   first_asr_seconds=segments[0]['wall']-origin,
                   partial_before_eof=segments[0]['wall'] < packets[-1]['wall'],
                   packet_sizes=sorted({e['sample_count'] for e in packets}),
                   expected=job['expected'], unread=job['unread'], exit_code=process.returncode,
                   triggers=[dict(mode=e['mode'], scene=e['scene'],
                                  arrival_seconds=e['wall']-origin,
                                  audio_end=e['audio_end'], skipped=e['skipped'])
                             for e in events if e['kind'] == 'tracker' and e['triggered']])
        results.append(row)
        (args.results / 'comparison.json').write_text(json.dumps(results, indent=2))
        print('DONE', json.dumps(row), flush=True)


if __name__ == '__main__':
    main()
