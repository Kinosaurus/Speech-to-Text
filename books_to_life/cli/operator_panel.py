"""Serve the Reading Pod operator panel and manage a single microphone session."""

import argparse
from datetime import datetime
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys
from threading import Lock, Thread, Timer

from books_to_life.runtime.audio_runtime import input_devices, microphone_label


ROOT = Path(__file__).resolve().parents[2]
DIST = ROOT / 'operator-panel/dist'
STORIES = ROOT / 'recordings/library/stories'
MODELS = {
    'parakeet-nemo': ('Parakeet NeMo', 9097, True),
    'base.en': ('Whisper Base (English)', 9090, True),
    'tiny.en': ('Whisper Tiny (English)', 9090, True),
    'medium.en': ('Whisper Medium (English)', 9090, True),
    'parakeet': ('Parakeet ONNX', 9091, False),
    'moonshine': ('Moonshine', 9091, False),
}
HINT_LEVELS = {'low': (0, 24), 'medium': (2, 64), 'high': (4, 96)}
TRIGGER = re.compile(r'^\[TRIGGER\] ([^:]+):')
TRANSCRIPT_PREFIX = '[PANEL_TRANSCRIPT] '
MICROPHONE_PREFIX = '[MICROPHONE] '


def list_microphones():
    import pyaudio

    audio = pyaudio.PyAudio()
    try:
        return [{'id': str(device['index']), 'label': microphone_label(audio, device)}
                for device in input_devices(audio)]
    finally:
        audio.terminate()


def load_passages():
    passages = {}
    for manifest in sorted(STORIES.glob('*/readers/*/checkpoints.json')):
        story, _, reader, _ = manifest.relative_to(STORIES).parts
        if reader != story and (story, reader) != ('sample', 'demo'):
            continue
        data = json.loads(manifest.read_text(encoding='utf-8-sig'))
        passages[story] = (manifest, {
            'id': story,
            'title': data['title'],
            'pages': data.get('pages', []),
            'checkpoints': sorted(data['checkpoints'], key=lambda item: item['checkpoint_position']),
        })
    return passages


class MapMapCue:
    def __init__(self, path, port):
        spec = importlib.util.spec_from_file_location('reading_pod_mapmap_bridge', path)
        self.bridge = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.bridge)
        self.port = port
        self.timer = None
        self.lock = Lock()

    def reset(self):
        with self.lock:
            if self.timer:
                self.timer.cancel()
                self.timer = None
            self.bridge.reset_video(self.port)

    def play(self):
        with self.lock:
            self.bridge.send_source(self.port, 'rewind')
            self.bridge.send_source(self.port, 'volume', 1.0)
            self.bridge.send_source(self.port, 'opacity', 1.0)
            self.bridge.send_source(self.port, 'play')
            timer = Timer(self.bridge.VIDEO_HOLD_SECONDS, lambda: self.hold(timer))
            timer.daemon = True
            self.timer = timer
            timer.start()

    def hold(self, timer):
        with self.lock:
            if self.timer is timer:
                self.bridge.hold_video(self.port)
                self.timer = None


class Sessions:
    def __init__(self, passages, ports, cue=None):
        self.passages = passages
        self.ports = ports
        self.cue = cue
        self.lock = Lock()
        self.process = None
        self.update_thread = None
        self.state = {'phase': 'idle', 'fired': [], 'message': '', 'settings': None,
                      'transcript': '', 'partial': [], 'scores': {}, 'cue_status': {}}

    def status(self):
        with self.lock:
            return {**self.state, 'fired': self.state['fired'][:], 'scores': self.state['scores'].copy(),
                    'cue_status': self.state['cue_status'].copy()}

    def catalog(self):
        try:
            microphones = list_microphones()
        except (ImportError, OSError):
            microphones = []
        return {
            'passages': [data for _, data in self.passages.values()],
            'models': [
                {'id': key, 'label': name, 'port': self.ports.get(key, port), 'hints': hints}
                for key, (name, port, hints) in MODELS.items()
            ],
            'projection': self.cue is not None,
            'microphones': microphones,
        }

    def start(self, settings):
        if not isinstance(settings, dict):
            raise ValueError('Choose a passage and model.')
        passage, model, level = (settings.get(field) for field in ('passage', 'model', 'strength'))
        if not all(isinstance(value, str) for value in (passage, model, level)):
            raise ValueError('Choose a passage, model, and hint strength.')
        if passage not in self.passages or model not in MODELS or level not in HINT_LEVELS:
            raise ValueError('Choose a listed passage, model, and hint strength.')
        hints = settings.get('hints')
        save = settings.get('save')
        microphone = settings.get('microphone', 'default')
        if not isinstance(microphone, str) or not re.fullmatch(r'default|[0-9]{1,6}', microphone):
            raise ValueError('Choose a listed microphone.')
        if type(hints) is not bool or type(save) is not bool:
            raise ValueError('Choose whether to enable hints and save the recording.')

        manifest, _ = self.passages[passage]
        _, default_port, supports_hints = MODELS[model]
        hints = hints and supports_hints
        folder = ROOT / 'output/operator-sessions' / datetime.now().strftime('%Y%m%d-%H%M%S-%f')
        command = [
            sys.executable, '-X', 'utf8', '-u', '-m', 'books_to_life.cli.run_client',
            '--model', model, '--server', '127.0.0.1',
            '--port', str(self.ports.get(model, default_port)),
            '--checkpoints', str(manifest), '--matching_mode', 'split',
            '--connection_timeout', '20', '--stop-on-stdin-close', '--live-transcript',
            '--transcript_file', str(folder / 'transcript.srt'),
        ]
        if microphone != 'default':
            command += ['--input_device', microphone]
        if save:
            command += ['--save_output_recording', '--output_file', str(folder / 'recording.wav')]
        else:
            command += ['--no-save-output-recording']
        if hints:
            lookahead, words = HINT_LEVELS[level]
            command += ['--book_context_lookahead', str(lookahead), '--book_context_words', str(words)]
        else:
            command += ['--no_book_context']
        if passage == 'sample' and self.cue:
            command += ['--mute-checkpoint-sound', 'seed_found']

        with self.lock:
            if self.process is not None:
                raise ValueError('End the current session before starting another.')
            if self.cue:
                self.cue.reset()
            self.process = subprocess.Popen(
                command, cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, encoding='utf-8', errors='replace',
            )
            self.state = {
                'phase': 'starting', 'fired': [], 'message': '', 'transcript': '', 'microphone': None,
                'partial': [], 'scores': {}, 'cue_status': {},
                'settings': {'passage': passage, 'model': model, 'strength': level,
                             'hints': hints, 'save': save, 'microphone': microphone},
            }
            self.update_thread = Thread(target=self.monitor, args=(self.process, passage), daemon=True)
            self.update_thread.start()

    def end(self):
        with self.lock:
            if self.process and self.state['phase'] != 'ending':
                self.state['phase'] = 'ending'
                self.process.stdin.close()
                if self.cue:
                    self.cue.reset()

    def monitor(self, process, passage):
        failure = ''
        with process.stdout:
            for raw in process.stdout:
                line = raw.rstrip()
                if raw.startswith(TRANSCRIPT_PREFIX):
                    update = json.loads(raw[len(TRANSCRIPT_PREFIX):])
                    with self.lock:
                        self.state['transcript'] = update['text']
                        self.state['partial'] = update['partial']
                        checkpoint = update['checkpoint']
                        if checkpoint is not None and update['score'] is not None and checkpoint not in self.state['fired']:
                            self.state['scores'][checkpoint] = update['score']
                        for ident in update.get('skipped', ()):
                            self.state['cue_status'][ident] = 'Skipped'
                        for ident in update.get('suppressed', ()):
                            self.state['cue_status'][ident] = 'Cue withheld'
                        if update.get('pending'):
                            self.state['cue_status'][update['pending']] = 'Checking ending'
                    continue
                if line.startswith('[STARTUP]') or re.match(r'^(?:\w+Error:|run_client\.py: error:)', line):
                    failure = line[:300]
                with self.lock:
                    if self.state['phase'] == 'ending':
                        continue
                    if raw.startswith(MICROPHONE_PREFIX):
                        self.state['microphone'] = raw[len(MICROPHONE_PREFIX):].strip()
                    if line == '[SESSION] Listening':
                        self.state['phase'] = 'listening'
                    trigger = TRIGGER.match(line)
                    if trigger and trigger[1] not in self.state['fired']:
                        self.state['fired'].append(trigger[1])
                        if self.cue and passage == 'sample' and trigger[1] == 'seed_found':
                            try:
                                self.cue.play()
                            except OSError as error:
                                self.state['message'] = f'MapMap cue failed. {error}'
        code = process.wait()
        process.stdin.close()
        with self.lock:
            if self.cue:
                try:
                    self.cue.reset()
                except OSError as error:
                    self.state['message'] = f'MapMap reset failed. {error}'
            self.state['phase'] = 'error' if code else 'ended'
            if code and not self.state['message']:
                self.state['message'] = failure or f'Speech client exited with code {code}. Check the selected recognition server.'
            self.process = None


class PanelHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, sessions, **kwargs):
        self.sessions = sessions
        super().__init__(*args, directory=str(DIST), **kwargs)

    def send_json(self, data, status=200):
        payload = json.dumps(data).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def local_host(self):
        port = self.server.server_port
        return self.headers.get('Host') in (f'127.0.0.1:{port}', f'localhost:{port}')

    def do_GET(self):
        if not self.local_host():
            self.send_error(403)
        elif self.path == '/api/catalog':
            self.send_json(self.sessions.catalog())
        elif self.path == '/api/session':
            self.send_json(self.sessions.status())
        elif self.path == '/' or self.path.startswith('/assets/'):
            super().do_GET()
        else:
            self.send_error(404)

    def do_POST(self):
        origin = self.headers.get('Origin')
        if not self.local_host() or origin not in (None, f'http://{self.headers.get("Host")}'):
            self.send_error(403)
            return
        if self.headers.get_content_type() != 'application/json':
            self.send_error(415)
            return
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 1 <= length <= 4096:
                raise ValueError('Invalid request length.')
            body = json.loads(self.rfile.read(length))
            if self.path == '/api/session/start':
                self.sessions.start(body)
            elif self.path == '/api/session/end':
                self.sessions.end()
            else:
                self.send_error(404)
                return
        except (ValueError, OSError) as error:
            self.send_json({'error': str(error)}, 400)
            return
        self.send_json(self.sessions.status())

    def log_message(self, format, *args):
        # Polling is frequent and the session status is already shown in the panel.
        pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--whisper-port', type=int, default=9090)
    parser.add_argument('--nemo-port', type=int, default=9097)
    parser.add_argument('--native-port', type=int, default=9091)
    parser.add_argument('--mapmap-bridge', type=Path, help='Path to the handoff play_cue.py.')
    parser.add_argument('--osc-port', type=int, default=12345)
    args = parser.parse_args()
    if not (DIST / 'index.html').is_file():
        parser.error('Build the React panel first. See operator-panel/README.md.')
    if args.mapmap_bridge and not args.mapmap_bridge.is_file():
        parser.error('--mapmap-bridge must point to the handoff play_cue.py file.')
    cue = MapMapCue(args.mapmap_bridge.resolve(), args.osc_port) if args.mapmap_bridge else None
    ports = {model: {9090: args.whisper_port, 9091: args.native_port, 9097: args.nemo_port}[port]
             for model, (_, port, _) in MODELS.items()}
    sessions = Sessions(load_passages(), ports, cue)
    with ThreadingHTTPServer(('127.0.0.1', args.port), partial(PanelHandler, sessions=sessions)) as server:
        print(f'Reading Pod panel available at http://127.0.0.1:{server.server_port}', flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            sessions.end()
            if sessions.update_thread:
                sessions.update_thread.join()


if __name__ == '__main__':
    main()
