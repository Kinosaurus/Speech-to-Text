import gc
import importlib.metadata
import json
import os
from pathlib import Path, PureWindowsPath
import sys
import time
import wave

os.environ.setdefault('OMP_NUM_THREADS', '2')
os.environ.setdefault('MKL_NUM_THREADS', '2')
OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
sys.path[:0] = [str(OUT / 'support')]
from benchmarks.asr_only import enforce_no_tracker, atomic_json
enforce_no_tracker()
import numpy as np
import torch
from nemo.utils import logging
import nemo_parakeet
import nemotron_streaming


def local(path):
    win = PureWindowsPath(path)
    return Path('/mnt', win.drive[0].lower(), *win.parts[1:])


def main():
    data = json.loads((OUT / 'dataset.json').read_text())
    torch.set_num_threads(2)
    logging.set_verbosity(logging.ERROR)
    for family in ('nemotron', 'parakeet'):
        print('LOAD', family, flush=True)
        if family == 'nemotron':
            path = ROOT / 'tmp/nemotron-asr-comparison/model-cache/nemotron-nemo/nemotron-speech-streaming-en-0.6b.nemo'
            model = nemotron_streaming.load_model(path, chunk_ms=160, enable_hints=True)
        else:
            path = ROOT / 'model-cache/parakeet-nemo/parakeet-unified-en-0.6b.nemo'
            model = nemo_parakeet.load_model(path, 560, 560)
        for index, case in enumerate(data['cases'], 1):
            with wave.open(str(local(case['audio']))) as wav:
                pcm = np.frombuffer(wav.readframes(wav.getnframes()), dtype='<i2').astype(np.float32) / 32768
            assert len(pcm) == case['samples']
            pcm = np.concatenate((pcm, np.zeros(round(data['tail_seconds'] * 16000), dtype=np.float32)))
            for ms in ((160, 320) if family == 'nemotron' else (560,)):
                profile = f'nemotron-{ms}-fixed-hints' if family == 'nemotron' else 'parakeet-fixed-hints'
                target = OUT / f'{profile}--{case["id"]}.json'
                if target.exists():
                    continue
                if family == 'nemotron':
                    model.encoder.set_default_att_context_size([70, ms // 80 - 1])
                    session = nemotron_streaming.NemotronSession(model, phrases=case['fixed_hints'], boost=1.0)
                else:
                    session = nemo_parakeet.NemoParakeetSession(model, 560, 560, 1.0)
                    session.set_hints(', '.join(case['fixed_hints']))
                events = []
                clock = compute = 0.0
                started = time.perf_counter()
                try:
                    with torch.inference_mode(), torch.autocast('cuda', dtype=torch.bfloat16):
                        for offset in range(0, len(pcm), data['packet_samples']):
                            part = pcm[offset:offset + data['packet_samples']]
                            audio_end = (offset + len(part)) / 16000
                            before = time.perf_counter()
                            updates = session.feed(part)
                            torch.cuda.synchronize()
                            elapsed = time.perf_counter() - before
                            compute += elapsed
                            clock = max(clock, audio_end) + elapsed
                            for text in updates:
                                events.append(dict(kind='transcript', text=text, final=False,
                                                   audio_end=audio_end, wall_seconds=clock))
                        before = time.perf_counter()
                        text = session.finish()
                        torch.cuda.synchronize()
                        elapsed = time.perf_counter() - before
                        clock += elapsed
                        compute += elapsed
                        events.append(dict(kind='transcript', text=text, final=True,
                                           audio_end=len(pcm) / 16000, wall_seconds=clock))
                finally:
                    session.close()
                assert text.strip()
                no_tracker = not any(name.startswith(('books_to_life.matching', 'books_to_life.context')) for name in sys.modules)
                assert no_tracker
                atomic_json(target, dict(profile=profile, case=case['id'], status='ok', final_text=text,
                                         audio_sha256=case['audio_sha256'], samples_delivered=len(pcm),
                                         no_tracker_modules_imported=no_tracker, hint_policy='fixed_before_audio',
                                         compute_seconds=compute, events=events,
                                         timing='simulated paced packet clock, synchronous processing included',
                                         nemo_version=importlib.metadata.version('nemo-toolkit')))
                print(index, '/', len(data['cases']), profile, case['id'],
                      f'{time.perf_counter() - started:.1f}s', flush=True)
        del model
        gc.collect()
        torch.cuda.empty_cache()


if __name__ == '__main__':
    main()
