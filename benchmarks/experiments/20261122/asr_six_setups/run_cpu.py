import argparse
import json
from pathlib import Path
from types import SimpleNamespace
import sys
import time
import wave

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
sys.path.insert(0, str(OUT / 'support'))
from benchmarks.asr_only import ASRRecorder, atomic_json, enforce_no_tracker
enforce_no_tracker()
from benchmarks.asr_only_worker import whisper, moonshine
import numpy as np


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--profile', choices=['whisper-tiny-cpu', 'moonshine-cpu'], required=True)
    args = parser.parse_args()
    args.cache = ROOT / 'model-cache/asr-benchmark'
    data = json.loads((OUT / 'dataset.json').read_text(encoding='utf-8'))
    backend = whisper if args.profile.startswith('whisper') else moonshine
    for index, case in enumerate(data['cases'], 1):
        target = OUT / f'{args.profile}--{case["id"]}.json'
        if target.exists():
            if json.loads(target.read_text(encoding='utf-8'))['status'] != 'ok':
                raise RuntimeError('Retain failed run before retry')
            continue
        with wave.open(case['audio']) as wav:
            pcm = np.frombuffer(wav.readframes(wav.getnframes()), dtype='<i2').astype(np.float32) / 32768
        recorder = ASRRecorder(target.with_suffix('.events.jsonl'), delivery='queued')
        print('START', index, '/', len(data['cases']), args.profile, case['id'], flush=True)
        result = dict(profile=args.profile, case=case['id'], audio_sha256=case['audio_sha256'])
        started = time.perf_counter()
        try:
            result['runtime'] = backend(args, pcm, recorder, data)
            assert recorder.sent_samples == len(pcm) + round(data['tail_seconds'] * 16000)
            assert recorder.last_text and recorder.last_text.strip()
            result.update(status='ok', final_text=recorder.last_text, samples_delivered=recorder.sent_samples,
                          no_tracker_modules_imported=not any(n.startswith(('books_to_life.matching', 'books_to_life.context')) for n in sys.modules))
        except Exception as error:
            result.update(status='failed', error=repr(error))
        finally:
            recorder.close()
            atomic_json(target, result)
        print(result['status'], args.profile, case['id'], round(time.perf_counter()-started, 1), result.get('error', ''), flush=True)
        if result['status'] != 'ok':
            raise RuntimeError(result['error'])


if __name__ == '__main__':
    main()
