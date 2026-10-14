"""GPU-only Parakeet Unified server with live phrase hints (Linux/WSL)."""
import argparse
import json
import math
import os
from pathlib import Path
import threading

import numpy as np
from websockets.sync.server import serve
from websockets.exceptions import ConnectionClosed

from book_context import CONTEXT_PROTOCOL_VERSION, parse_context_message
from nemo_parakeet import NemoParakeetSession, hint_phrases, load_model


def handle_connection(socket, factory, lock, max_seconds=3600):
    uid = None
    session = None
    acquired = False
    def send(**data):
        socket.send(json.dumps({'uid': uid, **data}))
    try:
        options = json.loads(socket.recv(timeout=30))
        uid = options['uid']
        if options.get('model') != 'parakeet-nemo':
            raise ValueError('Use --model parakeet-nemo with this server.')
        if options.get('language') not in (None, 'en') or options.get('task') == 'translate' or options.get('enable_translation'):
            raise ValueError('English transcription only.')
        hint_phrases(options.get('hotwords'))
        acquired = lock.acquire(blocking=False)
        if not acquired:
            raise ValueError('Another reading session is active.')
        session = factory()
        session.set_hints(options.get('hotwords'))
        send(message='SERVER_READY', backend='parakeet-nemo')
        send(type='book_context_capabilities', version=CONTEXT_PROTOCOL_VERSION, hint_mode='phrases')
        revision = 0
        samples = 0
        def transcript(text, final=False):
            send(segments=[{'start': 0, 'end': samples / 16000, 'text': text, 'completed': final}])
        for packet in socket:
            if isinstance(packet, str):
                try:
                    new_revision, hints = parse_context_message(packet)
                    if new_revision <= revision:
                        raise ValueError('Hint revisions must increase within this session.')
                    session.set_hints(hints.hotwords)
                    revision = new_revision
                    send(type='book_context_ack', revision=revision)
                    print(f'[BOOK_CONTEXT] Applied revision {revision}: {hint_phrases(hints.hotwords)}', flush=True)
                except (ValueError, TypeError) as error:
                    send(status='WARNING', message=str(error))
                continue
            if packet == b'END_OF_AUDIO':
                transcript(session.finish(), final=True)
                send(message='STREAM_DONE')
                return
            if not isinstance(packet, bytes) or len(packet) % 4:
                raise ValueError('Expected mono float32 audio at 16 kHz.')
            audio = np.frombuffer(packet, dtype='<f4').copy()
            if not np.isfinite(audio).all():
                raise ValueError('Audio must contain finite samples.')
            samples += len(audio)
            if samples > max_seconds * 16000:
                raise ValueError('Session duration limit exceeded.')
            for text in session.feed(audio):
                transcript(text)
    except ConnectionClosed:
        pass
    except Exception as error:
        import traceback
        traceback.print_exc()
        try:
            send(status='ERROR', message=str(error))
        except ConnectionClosed:
            pass
    finally:
        try:
            if session is not None:
                session.close()
        finally:
            if acquired:
                lock.release()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model-path', type=Path, required=True)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=9097)
    parser.add_argument('--chunk-ms', type=int, default=560)
    parser.add_argument('--right-ms', type=int, default=560)
    parser.add_argument('--boost', type=float, default=1.0)
    parser.add_argument('--max-seconds', type=int, default=3600)
    args = parser.parse_args()
    if not args.model_path.is_file():
        parser.error('Download the original Parakeet Unified .nemo checkpoint first.')
    if any(x <= 0 or x % 80 or x > 1040 for x in (args.chunk_ms, args.right_ms)):
        parser.error('Chunk/right context must be multiples of 80 ms between 80 and 1040.')
    if not math.isfinite(args.boost) or not 0 <= args.boost <= 5 or args.max_seconds < 1:
        parser.error('Boost must be between 0 and 5; session limit must be positive.')
    os.environ.setdefault('PYTORCH_CUDA_ALLOC_CONF', 'expandable_segments:True')
    model = load_model(args.model_path, args.chunk_ms, args.right_ms)
    import torch
    print(f'[ASR] Parakeet Unified CUDA {torch.cuda.get_device_name()}, bfloat16; phrase boosting={args.boost}', flush=True)
    print(f'[ASR] Buffered streaming: 5600 ms left, {args.chunk_ms} ms chunk, {args.right_ms} ms right.', flush=True)
    lock = threading.Lock()
    factory = lambda: NemoParakeetSession(model, args.chunk_ms, args.right_ms, args.boost)
    with serve(lambda ws: handle_connection(ws, factory, lock, args.max_seconds),
               args.host, args.port, max_size=65536) as server:
        print(f'[READY] ws://{args.host}:{args.port}', flush=True)
        server.serve_forever()


if __name__ == '__main__':
    main()
