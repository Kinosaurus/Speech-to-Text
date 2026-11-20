"""Loopback-only sweep server: one resident model, explicit acknowledged per-session boost."""
import argparse
from hashlib import sha256
import json
import math
from pathlib import Path
import threading

from books_to_life.cli.run_nemo_server import handle_connection
from books_to_life.runtime.nemo_parakeet import NemoParakeetSession, hint_phrases, load_model


def validate_boost(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 5:
        raise ValueError('Benchmark boost must be finite and between 0 and 5.')
    return float(value)


class HandshakeSocket:
    def __init__(self, socket, options, session):
        self.socket, self.options, self.session = socket, options, session

    def recv(self, timeout=None):
        return json.dumps(self.options)

    def __iter__(self):
        return iter(self.socket)

    def send(self, value):
        data = json.loads(value)
        if data.get('message') == 'SERVER_READY':
            # Assert actual applied session state before acknowledging client input.
            if self.session.phrases != hint_phrases(self.options.get('hotwords')):
                raise ValueError('Actual phrase state does not match requested full text.')
            data.update(benchmark_boost=self.session.boost,
                        applied_hotwords_sha256=sha256((self.options.get('hotwords') or '').encode()).hexdigest(),
                        phrase_count=len(self.session.phrases))
        self.socket.send(json.dumps(data))


def main():
    from websockets.sync.server import serve
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model-path', type=Path, required=True)
    parser.add_argument('--port', type=int, default=9098)
    args = parser.parse_args()
    model = load_model(args.model_path, 560, 560)
    lock = threading.Lock()

    def connection(socket):
        session = None
        options = {}
        try:
            options = json.loads(socket.recv(timeout=30))
            boost = validate_boost(options.pop('benchmark_boost', None))
            session = NemoParakeetSession(model, 560, 560, boost)
            handle_connection(HandshakeSocket(socket, options, session), lambda: session, lock)
        except Exception as error:
            if session is not None:
                session.close()
            try:
                socket.send(json.dumps({'uid': options.get('uid'), 'status': 'ERROR', 'message': str(error)}))
            except Exception:
                pass

    with serve(connection, '127.0.0.1', args.port, max_size=65536) as server:
        print(f'[READY] sweep server ws://127.0.0.1:{args.port}; boosts 0..5; fixed 560/560 ms', flush=True)
        server.serve_forever()


if __name__ == '__main__':
    main()
