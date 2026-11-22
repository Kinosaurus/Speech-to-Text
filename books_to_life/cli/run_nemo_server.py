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

from books_to_life.context.book_context import CONTEXT_PROTOCOL_VERSION, parse_context_message
from books_to_life.runtime.nemo_parakeet import NemoParakeetSession, hint_phrases, load_model
from books_to_life.runtime.nemo_defaults import CHUNK_MS, RIGHT_MS, NEMO_MODELS


def warm_model(model,chunk_ms,right_ms,boost):
    """Initialize CUDA inference before readiness, without microphone input."""
    session=NemoParakeetSession(model,chunk_ms,right_ms,boost)
    try:
        session.set_hints(None)
        session.feed(np.zeros(32000,dtype=np.float32))
        session.finish()
    finally:
        session.close()


def handle_connection(socket, factory, lock, max_seconds=3600, backend='parakeet-nemo'):
    uid = None
    session = None
    acquired = False
    def send(**data):
        socket.send(json.dumps({'uid': uid, **data}))
    try:
        options = json.loads(socket.recv(timeout=30))
        uid = options['uid']
        if options.get('model') != backend:
            raise ValueError(f'Use --model {backend} with this server.')
        if options.get('language') not in (None, 'en') or options.get('task') == 'translate' or options.get('enable_translation'):
            raise ValueError('English transcription only.')
        hint_phrases(options.get('hotwords'))
        acquired = lock.acquire(blocking=False)
        if not acquired:
            raise ValueError('Another reading session is active.')
        session = factory()
        session.set_hints(options.get('hotwords'))
        configuration=getattr(session,'configuration',{})
        send(message='SERVER_READY', backend=backend,
             **(configuration if isinstance(configuration,dict) else {}))
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
    parser.add_argument('--backend', choices=NEMO_MODELS, default='parakeet-nemo')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=9097)
    parser.add_argument('--chunk-ms', type=int, default=CHUNK_MS)
    parser.add_argument('--right-ms', type=int, default=RIGHT_MS)
    parser.add_argument('--boost', type=float, default=1.0)
    parser.add_argument('--max-seconds', type=int, default=3600)
    args = parser.parse_args()
    if not args.model_path.is_file():
        parser.error('Download the selected backend’s .nemo checkpoint first.')
    if args.backend == 'nemotron' and args.chunk_ms not in (80, 160, 560, 1120):
        parser.error('Nemotron supports trained chunk sizes 80, 160, 560 or 1120 ms.')
    if args.backend == 'parakeet-nemo' and any(x <= 0 or x % 80 or x > 1040 for x in (args.chunk_ms, args.right_ms)):
        parser.error('Chunk/right context must be multiples of 80 ms between 80 and 1040.')
    if not math.isfinite(args.boost) or not 0 <= args.boost <= 5 or args.max_seconds < 1:
        parser.error('Boost must be between 0 and 5; session limit must be positive.')
    os.environ.setdefault('PYTORCH_CUDA_ALLOC_CONF', 'expandable_segments:True')
    import torch
    torch.set_num_threads(2)
    if args.backend == 'nemotron':
        from books_to_life.runtime.nemotron import load_model as load_nemotron, NemotronSession
        model = load_nemotron(args.model_path, chunk_ms=args.chunk_ms)
        factory = lambda: NemotronSession(model, chunk_ms=args.chunk_ms, boost=args.boost)
        print(f'[ASR] Nemotron CUDA, bfloat16; {args.chunk_ms} ms chunks; phrase boosting={args.boost}', flush=True)
    else:
        model = load_model(args.model_path, args.chunk_ms, args.right_ms)
        factory = lambda: NemoParakeetSession(model, args.chunk_ms, args.right_ms, args.boost)
        print(f'[ASR] Parakeet Unified CUDA {torch.cuda.get_device_name()}, bfloat16; phrase boosting={args.boost}', flush=True)
        print(f'[ASR] Buffered streaming: 5600 ms left, {args.chunk_ms} ms chunk, {args.right_ms} ms right.', flush=True)
    lock = threading.Lock()
    print('[ASR] Warming CUDA with two seconds of synthetic silence before readiness.',flush=True)
    if args.backend == 'nemotron':
        session = factory()
        try:
            session.feed(np.zeros(32000, dtype=np.float32))
            session.finish()
        finally:
            session.close()
    else:
        warm_model(model,args.chunk_ms,args.right_ms,args.boost)
    with serve(lambda ws: handle_connection(ws, factory, lock, args.max_seconds, backend=args.backend),
               args.host, args.port, max_size=65536) as server:
        print(f'[READY] ws://{args.host}:{args.port}', flush=True)
        server.serve_forever()


if __name__ == '__main__':
    main()
