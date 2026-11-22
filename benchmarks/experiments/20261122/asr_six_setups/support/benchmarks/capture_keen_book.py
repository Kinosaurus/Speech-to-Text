"""Run the installed KeenASR browser SDK on local WAVs in a muted headless browser."""

import argparse
from contextlib import closing
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import subprocess
import tempfile
from threading import Thread
import time
from urllib.request import urlopen

import websocket

from benchmarks.asr_only import atomic_json, sha256


SDK_ASSETS = ('keenasr-web.js', 'KeenASRCore.js', 'KeenASRCore.wasm',
              'KeenASRCore.aw.js', 'KeenASRCore.ww.js')
PAGE = b'<!doctype html><meta charset="utf-8"><title>Keen book replay</title><script type="module" src="/replay.mjs"></script>'


class ReplayHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.headers.get('Host') != f'127.0.0.1:{self.server.server_port}':
            self.send_error(403)
            return
        asset = self.server.routes.get(self.path)
        if asset is None:
            self.send_error(404)
            return
        kind, body = asset
        data = body.read_bytes() if isinstance(body, Path) else body
        self.send_response(200)
        self.send_header('Cross-Origin-Opener-Policy', 'same-origin')
        self.send_header('Cross-Origin-Embedder-Policy', 'require-corp')
        self.send_header('Cross-Origin-Resource-Policy', 'same-origin')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Type', kind)
        self.send_header('Content-Security-Policy',
                         "default-src 'none'; connect-src 'self'; script-src 'self' 'unsafe-eval' blob:; worker-src 'self' blob:")
        if self.path == self.server.bundle_path:
            self.send_header('Content-Encoding', 'gzip')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


def run_page(browser, url, timeout):
    with tempfile.TemporaryDirectory(prefix='keen-replay-') as profile:
        # An isolated browser profile, no real capture device and no sound.
        process = subprocess.Popen([str(browser), '--headless=new', '--mute-audio', '--no-first-run',
                                    '--disable-extensions', '--disable-background-networking',
                                    '--use-fake-device-for-media-stream',
                                    '--autoplay-policy=no-user-gesture-required', '--remote-debugging-port=0',
                                    '--user-data-dir=' + profile, url], stdout=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            debugging = Path(profile) / 'DevToolsActivePort'
            deadline = time.monotonic() + 15
            while not debugging.exists():
                if process.poll() is not None or time.monotonic() > deadline:
                    raise RuntimeError('Keen benchmark browser did not start.')
                time.sleep(.1)
            port = int(debugging.read_text().splitlines()[0])
            with urlopen(f'http://127.0.0.1:{port}/json/list', timeout=5) as response:
                target = next(target for target in json.load(response) if target['type'] == 'page')
            with closing(websocket.create_connection(target['webSocketDebuggerUrl'], timeout=8, suppress_origin=True)) as ws:
                deadline = time.monotonic() + timeout
                message_id = 0
                while time.monotonic() < deadline:
                    message_id += 1
                    ws.send(json.dumps({'id': message_id, 'method': 'Runtime.evaluate',
                                        'params': {'expression': '({trial: window.keenTrial, stage: window.keenStage})',
                                                   'returnByValue': True}}))
                    reply = json.loads(ws.recv())
                    value = reply.get('result', {}).get('result', {}).get('value', {})
                    if value.get('trial') is not None:
                        ws.send(json.dumps({'id': message_id + 1, 'method': 'Browser.close'}))
                        return value['trial']
                    time.sleep(.25)
            raise TimeoutError(f'Keen returned no final response. Last stage: {value.get("stage")}')
        finally:
            try:
                process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                process.terminate()
                process.wait(timeout=10)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--sdk', type=Path, required=True)
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--browser', type=Path, required=True)
    parser.add_argument('--case', help='Run only this frozen recording for a smoke check or a retry.')
    args = parser.parse_args()
    dataset = json.loads((args.output / 'dataset.json').read_text(encoding='utf-8'))
    assets = {f'/sdk/{name}': ('application/wasm' if name.endswith('.wasm') else 'text/javascript', args.sdk / name)
              for name in SDK_ASSETS}
    bundle_hash = sha256(args.bundle)
    server = ThreadingHTTPServer(('127.0.0.1', 0), ReplayHandler)
    server.bundle_path = '/' + args.bundle.name
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        for case in dataset['cases']:
            ident = case['id']
            if args.case and ident != args.case:
                continue
            audio = Path(case['audio'])
            result_path = args.output / f'keen-book--{ident}.json'
            if sha256(audio) != case['audio_sha256']:
                raise ValueError(f'Audio changed for {ident}.')
            if result_path.exists():
                previous = json.loads(result_path.read_text(encoding='utf-8'))
                if previous['status'] != 'ok' or previous['audio_sha256'] != case['audio_sha256']:
                    raise ValueError(f'Preserve the failed attempt before retrying {ident}.')
                print('VERIFIED Keen', ident, flush=True)
                continue
            config = {key: case[key] for key in ('id', 'duration_seconds', 'keen_book_text')}
            config['tail_seconds'] = dataset['tail_seconds']
            config['bundle_path'] = server.bundle_path
            server.routes = {**assets, '/': ('text/html', PAGE),
                             '/replay.mjs': ('text/javascript', Path(__file__).with_name('keen_book_replay.mjs')),
                             '/case.json': ('application/json', json.dumps(config).encode('utf-8')),
                             '/recording.wav': ('audio/wav', audio), server.bundle_path: ('application/octet-stream', args.bundle)}
            print('START Keen', ident, flush=True)
            try:
                data = run_page(args.browser, f'http://127.0.0.1:{server.server_port}/', case['duration_seconds'] + 55)
            except Exception as error:
                data = {'status': 'failed', 'error': repr(error), 'events': []}
            events = data.pop('events')
            data.update(profile='keen-book', case=ident, audio_sha256=case['audio_sha256'],
                        bundle_sha256=bundle_hash, replay='silent browser stream, book graph, real-time clock')
            with result_path.with_suffix('.events.jsonl').open('w', encoding='utf-8') as log:
                for event in events:
                    log.write(json.dumps(event, ensure_ascii=False) + '\n')
            atomic_json(result_path, data)
            print(data['status'].upper(), 'Keen', ident, data.get('error', ''), flush=True)
            if data['status'] != 'ok':
                raise RuntimeError(data.get('error', 'Keen failed'))
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


if __name__ == '__main__':
    main()
