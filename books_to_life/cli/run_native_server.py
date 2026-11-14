"""Local Parakeet/Moonshine WebSocket server for run_client.py audio streams."""
import argparse
from contextlib import nullcontext
import json
import os
from pathlib import Path
import platform
import sys
import threading

import numpy as np
from websockets.sync.server import serve
from websockets.exceptions import ConnectionClosed

MODELS = {
    'parakeet': 'parakeet-unified-en-0.6b-F16.gguf',
    'moonshine': 'moonshine-streaming-medium-F16.gguf',
}
LINUX_PARAKEET_MODEL = 'parakeet-unified-en-0.6b-Q8_0.gguf'

RUNTIMES = {
    ('Windows', 'amd64'): ('windows-x86_64', 'transcribe.dll'),
    ('Windows', 'x86_64'): ('windows-x86_64', 'transcribe.dll'),
    ('Linux', 'aarch64'): ('linux-aarch64', 'libtranscribe.so'),
    ('Linux', 'arm64'): ('linux-aarch64', 'libtranscribe.so'),
    ('Linux', 'x86_64'): ('linux-x86_64', 'libtranscribe.so'),
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
    parser.add_argument('--device', choices=('vulkan', 'cpu'),
                        default='cpu' if platform.system() == 'Linux' else 'vulkan')
    parser.add_argument('--model-path', type=Path, help='Use a specific GGUF model from disk.')
    parser.add_argument('--threads', type=int, default=2)
    parser.add_argument('--chunk-ms', type=int, default=160,
                        help='Parakeet chunk and right-context durations (total buffer is twice this).')
    parser.add_argument('--max-seconds', type=int, default=3600)
    args = parser.parse_args()
    if min(args.threads, args.chunk_ms, args.max_seconds) < 1:
        parser.error('Thread count, chunk duration and session limit must be positive.')
    cache = args.cache.resolve()
    host = (platform.system(), platform.machine().lower())
    if host not in RUNTIMES:
        parser.error(f'No native runtime configured for {host[0]} {host[1]}.')
    runtime, library_name = RUNTIMES[host]
    library = cache / f'transcribe-native-{runtime}-cpu-vulkan' / library_name
    model_path = args.model_path.resolve() if args.model_path else cache / MODELS[args.model]
    if args.model_path is None and host[0] == 'Linux' and args.model == 'parakeet':
        model_path = cache / LINUX_PARAKEET_MODEL
    if not library.is_file() or not (cache / 'api' / 'transcribe_cpp').is_dir():
        parser.error(f'Native library or Python bindings missing in {cache}. Run python -m benchmarks.prepare'
                     + (' --pi-parakeet' if host[0] == 'Linux' else '') + ' for the target platform.')
    if not model_path.is_file():
        parser.error(f'GGUF model missing: {model_path}')
    os.environ['TRANSCRIBE_LIBRARY'] = str(library)
    sys.path.insert(0, str(cache / 'api'))
    dll_directory = os.add_dll_directory(str(library.parent)) if host[0] == 'Windows' else nullcontext()
    with dll_directory:
        try:
            import transcribe_cpp as api
            devices = [device for device in api.backends() if device.kind == args.device]
        except (ImportError, OSError, RuntimeError) as error:
            parser.exit(1, f'Cannot load native runtime {library}: {error}\n')
        if not devices:
            parser.error(f'No {args.device} backend is available in {library}.')
        lock = threading.Lock()
        with api.Model(model_path, device=devices[0]) as model:
            print(f'[ASR] {args.model}, {model.device}; {args.threads} threads, '
                  f'{args.chunk_ms} ms chunk/right context; no phrase hints', flush=True)
            with serve(lambda socket: handle_stream(socket, model, api, args, lock),
                       args.host, args.port, max_size=1024 * 1024) as server:
                print(f'[READY] ws://{args.host}:{args.port}', flush=True)
                server.serve_forever()


if __name__ == '__main__':
    main()
