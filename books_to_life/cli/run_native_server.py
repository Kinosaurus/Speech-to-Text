"""Local Parakeet/Moonshine WebSocket server for run_client.py audio streams."""
import argparse
import json
import os
from pathlib import Path
import sys
import threading

import numpy as np
from websockets.sync.server import serve
from websockets.exceptions import ConnectionClosed

MODELS = {
    'parakeet': 'parakeet-unified-en-0.6b-F16.gguf',
    'moonshine': 'moonshine-streaming-medium-F16.gguf',
}


def handle_stream(socket, model, api, args, lock):
    uid = None
    acquired = False
    try:
        options = json.loads(socket.recv(timeout=30))
        uid = options['uid']
        def send(**value):
            socket.send(json.dumps({'uid': uid, **value}))
        if options.get('model') != args.model:
            raise ValueError(f'This server requires --model {args.model}.')
        if options.get('language') not in (None, 'en') or options.get('task') == 'translate' or options.get('enable_translation'):
            raise ValueError('This server supports English transcription only.')
        if options.get('initial_prompt') or options.get('hotwords'):
            raise ValueError('This runtime has no book hints; use --no_book_context and omit explicit hints.')
        acquired = lock.acquire(blocking=False)
        if not acquired:
            raise ValueError('Another recording is active. Try again when it finishes.')
        with model.session(n_threads=args.threads) as session:
            family = (api.ParakeetBufferedStreamOptions(left_ms=5600, chunk_ms=args.chunk_ms,
                                                       right_ms=args.chunk_ms)
                      if args.model == 'parakeet' else None)
            with session.stream(language='en', family=family) as stream:
                samples = 0
                def snapshot(final=False):
                    text = stream.text().full
                    # These are stream bounds, not word-aligned timestamps.
                    send(segments=[{'start': 0, 'end': samples / 16000,
                                    'text': text, 'completed': final}])
                send(message='SERVER_READY', backend=args.model)
                for packet in socket:
                    if packet == b'END_OF_AUDIO':
                        stream.finalize()
                        snapshot(final=True)
                        send(message='STREAM_DONE')
                        return
                    if not isinstance(packet, bytes) or len(packet) % 4:
                        raise ValueError('Expected 16 kHz mono float32 audio packets.')
                    audio = np.frombuffer(packet, dtype='<f4').copy()
                    if not np.isfinite(audio).all():
                        raise ValueError('Audio contains non-finite samples.')
                    samples += len(audio)
                    if samples > args.max_seconds * 16000:
                        raise ValueError('Recording exceeded the server session limit.')
                    update = stream.feed(audio)
                    if update.result_changed:
                        snapshot()
    except ConnectionClosed:
        pass
    except Exception as error:
        print(f'[ERROR] {error}', flush=True)
        try:
            socket.send(json.dumps({'uid': uid, 'status': 'ERROR', 'message': str(error)}))
        except ConnectionClosed:
            pass
    finally:
        if acquired:
            lock.release()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', choices=MODELS, required=True)
    parser.add_argument('--cache', type=Path, default=Path('model-cache/asr-benchmark'))
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=9091)
    parser.add_argument('--device', choices=('vulkan', 'cpu'), default='vulkan')
    parser.add_argument('--threads', type=int, default=2)
    parser.add_argument('--chunk-ms', type=int, default=160,
                        help='Parakeet chunk and right-context durations (total buffer is twice this).')
    parser.add_argument('--max-seconds', type=int, default=3600)
    args = parser.parse_args()
    if min(args.threads, args.chunk_ms, args.max_seconds) < 1:
        parser.error('Thread count, chunk duration and session limit must be positive.')
    cache = args.cache.resolve()
    native = cache / 'transcribe-native-windows-x86_64-cpu-vulkan'
    if not (native / 'transcribe.dll').is_file() or not (cache / MODELS[args.model]).is_file():
        parser.error('Models/runtime missing. Run .\\.venv\\Scripts\\python.exe benchmarks\\prepare.py first.')
    os.environ['TRANSCRIBE_LIBRARY'] = str(native / 'transcribe.dll')
    dll_directory = os.add_dll_directory(str(native))
    sys.path.insert(0, str(cache / 'api'))
    import transcribe_cpp as api
    devices = [device for device in api.backends() if device.kind == args.device]
    if not devices:
        parser.error(f'No {args.device} device available; try --device cpu.')
    lock = threading.Lock()
    with api.Model(cache / MODELS[args.model], device=devices[0]) as model:
        print(f'[ASR] {args.model}, {model.device}; no phrase hints; native streaming defaults', flush=True)
        with serve(lambda socket: handle_stream(socket, model, api, args, lock),
                   args.host, args.port, max_size=1024 * 1024) as server:
            print(f'[READY] ws://{args.host}:{args.port}', flush=True)
            server.serve_forever()
    dll_directory.close()


if __name__ == '__main__':
    main()
