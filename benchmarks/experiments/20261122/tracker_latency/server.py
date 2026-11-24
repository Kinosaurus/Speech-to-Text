"""Local paced-replay transport using the previously evaluated Nemotron adapter."""
import hashlib
import json
import os
from pathlib import Path
import sys
import threading
import time

os.environ.setdefault('OMP_NUM_THREADS', '2')
os.environ.setdefault('MKL_NUM_THREADS', '2')
OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
sys.path.insert(0, str(ROOT / 'output/asr-slide26-20261122/support'))
import numpy as np
import torch
from websockets.sync.server import serve
import nemotron_streaming
from nemo_parakeet import hint_phrases


def main():
    torch.set_num_threads(2)
    path = ROOT / 'tmp/nemotron-asr-comparison/model-cache/nemotron-nemo/nemotron-speech-streaming-en-0.6b.nemo'
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    model = nemotron_streaming.load_model(path, chunk_ms=160, enable_hints=True)
    lock = threading.Lock()

    def connection(ws):
        uid = None
        session = None
        acquired = False
        def send(**data):
            ws.send(json.dumps(dict(uid=uid, **data)))
        try:
            options = json.loads(ws.recv(timeout=30))
            uid = options['uid']
            ms = options['chunk_ms']
            assert options['model'] == 'nemotron' and ms in (160, 320)
            acquired = lock.acquire(blocking=False)
            if not acquired:
                raise RuntimeError('Another test session is active')
            context = [70, ms // 80 - 1]
            model.encoder.set_default_att_context_size(context)
            phrases = hint_phrases(options.get('hotwords'))
            session = nemotron_streaming.NemotronSession(model, phrases=phrases, boost=1.0)
            send(message='SERVER_READY', backend='nemotron', chunk_ms=ms,
                 att_context=context, boost=1.0, model_sha256=digest,
                 applied_hotwords_sha256=hashlib.sha256((options.get('hotwords') or '').encode()).hexdigest())
            samples = 0
            compute = 0.0
            def transcript(text, final=False):
                send(segments=[dict(start=0, end=samples / 16000, text=text, completed=final)],
                     benchmark_server_timing=dict(decode_seconds=compute, audio_samples=samples,
                                                  processed_frames=session.processed_frames))
            with torch.inference_mode(), torch.autocast('cuda', dtype=torch.bfloat16):
                for packet in ws:
                    before = time.perf_counter()
                    if packet == b'END_OF_AUDIO':
                        text = session.finish()
                        torch.cuda.synchronize()
                        compute += time.perf_counter() - before
                        transcript(text, final=True)
                        send(message='STREAM_DONE')
                        return
                    if not isinstance(packet, bytes) or len(packet) % 4:
                        raise ValueError('Expected 16kHz float32 audio')
                    audio = np.frombuffer(packet, dtype='<f4').copy()
                    assert np.isfinite(audio).all()
                    samples += len(audio)
                    updates = session.feed(audio)
                    torch.cuda.synchronize()
                    compute += time.perf_counter() - before
                    for text in updates:
                        transcript(text)
        except Exception as error:
            import traceback
            traceback.print_exc()
            try:
                send(status='ERROR', message=repr(error))
            except Exception:
                pass
        finally:
            if session is not None:
                session.close()
            if acquired:
                lock.release()

    with serve(connection, '127.0.0.1', 9100, max_size=65536) as server:
        print('[READY] Nemotron tracker test ws://127.0.0.1:9100', flush=True)
        server.serve_forever()


if __name__ == '__main__':
    main()
