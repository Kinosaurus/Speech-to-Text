"""Serve the Reading Pod operator panel and manage a single microphone session."""

import argparse
from datetime import datetime
from functools import partial
from hashlib import sha256
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from os.path import normcase
from pathlib import Path
import re
import subprocess
import sys
from threading import Lock, Thread
from uuid import uuid4

import websocket

from books_to_life.runtime.audio_runtime import input_devices, microphone_label
from books_to_life.runtime.mapmap_cues import DEFAULT_FADE_MS, MapMapCue


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
FADE_OPTIONS_MS = (0, 250, DEFAULT_FADE_MS, 750, 1000)
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


def check_nemo(port):
    endpoint = f'127.0.0.1:{port}'
    uid = str(uuid4())
    connection = None
    try:
        connection = websocket.create_connection(
            f'ws://{endpoint}', timeout=3, http_no_proxy=['127.0.0.1'],
        )
        connection.send(json.dumps({'uid': uid, 'model': 'parakeet-nemo', 'language': 'en'}))
        reply = json.loads(connection.recv())
        if (isinstance(reply, dict) and reply.get('uid') == uid
                and reply.get('message') == 'SERVER_READY' and reply.get('backend') == 'parakeet-nemo'):
            return {'state': 'ready', 'detail': f'SERVER_READY from {endpoint}.'}
        if isinstance(reply, dict) and reply.get('uid') == uid and reply.get('status') == 'ERROR':
            return {'state': 'error', 'detail': f'{endpoint} reported: {str(reply.get("message"))[:200]}'}
        return {'state': 'error', 'detail': f'Unexpected reply from {endpoint}. Check the NeMo server.'}
    except (OSError, ValueError, websocket.WebSocketException):
        return {'state': 'error', 'detail': f'No SERVER_READY from {endpoint}. Check the NeMo server in WSL.'}
    finally:
        if connection is not None:
            connection.close(timeout=0.5)


def check_mapmap_listener(port):
    endpoint = f'UDP {port}'
    unavailable = {'state': 'unknown', 'detail': f'Could not verify the MapMap listener on {endpoint}.'}
    if sys.platform != 'win32':
        return unavailable

    command = f'''
$ErrorActionPreference = 'Stop'
$listeners = @(Get-NetUDPEndpoint -ErrorAction Stop | Where-Object {{
    $_.LocalPort -eq {port} -and $_.LocalAddress -in '127.0.0.1', '0.0.0.0'
}})
if ($listeners.Count -eq 0) {{ 'missing'; exit }}
foreach ($listener in $listeners) {{
    $owner = Get-Process -Id $listener.OwningProcess -ErrorAction SilentlyContinue
    if ($owner.ProcessName -ieq 'MapMap') {{ 'mapmap'; exit }}
}}
'other'
'''
    try:
        result = subprocess.run(
            ['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', command],
            capture_output=True, text=True, timeout=5, creationflags=subprocess.CREATE_NO_WINDOW,
        )
    except (OSError, subprocess.TimeoutExpired):
        return unavailable
    if result.returncode:
        return unavailable
    match result.stdout.strip():
        case 'mapmap':
            return {'state': 'ready', 'detail': f'MapMap owns {endpoint}. Use the test cue to check playback.'}
        case 'missing':
            return {'state': 'error', 'detail': f'No listener on {endpoint}. Open MapMap and verify its OSC port.'}
        case 'other':
            return {'state': 'error', 'detail': f'Another process owns {endpoint}. Check the MapMap OSC port.'}
        case _:
            return unavailable


class Sessions:
    def __init__(self, passages, ports, cue=None, *, assignment_file=None):
        self.passages = passages
        self.ports = ports
        self.cue = cue
        self.assignment_file = assignment_file
        self.assignments = {'sample': {'seed_found': cue.silver_seed}} if cue and cue.silver_seed else {}
        self.fade_ms = DEFAULT_FADE_MS
        if assignment_file is not None and assignment_file.is_file():
            stored = json.loads(assignment_file.read_text(encoding='utf-8'))
            assignments = stored
            if isinstance(stored, dict) and stored.get('version') == 1:
                assignments = stored.get('assignments')
                self.fade_ms = stored.get('fade_ms', DEFAULT_FADE_MS)
                if type(self.fade_ms) is not int or self.fade_ms not in FADE_OPTIONS_MS:
                    raise ValueError('Saved MapMap transition duration is invalid.')
            if not isinstance(assignments, dict) or any(
                not isinstance(checkpoints, dict) or any(value is not None and not isinstance(value, str)
                                                           for value in checkpoints.values())
                for checkpoints in assignments.values()
            ):
                raise ValueError('MapMap assignments must map passages and checkpoints to cue IDs or null.')
            self.assignments = assignments
        self.lock = Lock()
        self.process = None
        self.update_thread = None
        self.state = {'phase': 'idle', 'fired': [], 'message': '', 'settings': None,
                      'transcript': '', 'partial': [], 'scores': {}, 'cue_status': {}, 'match_evidence': {},
                      'reading_checkpoint': None}

    def status(self):
        with self.lock:
            return {**self.state, 'fired': self.state['fired'][:], 'scores': self.state['scores'].copy(),
                    'cue_status': self.state['cue_status'].copy(),
                    'match_evidence': self.state['match_evidence'].copy()}

    def mapmap_cues(self, passage):
        if not self.cue:
            return {}
        return {checkpoint: self.cue.cues[cue_id] for checkpoint, cue_id in self.assignments.get(passage, {}).items()
                if cue_id in self.cue.cues}

    def assign_cue(self, body):
        if not isinstance(body, dict) or 'cue' not in body:
            raise ValueError('Choose a passage, checkpoint and MapMap cue.')
        passage, checkpoint, cue_id = (body.get(key) for key in ('passage', 'checkpoint', 'cue'))
        if not isinstance(passage, str) or passage not in self.passages or not isinstance(checkpoint, str):
            raise ValueError('Choose a listed passage and checkpoint.')
        if not any(str(item['id']) == checkpoint for item in self.passages[passage][1]['checkpoints']):
            raise ValueError('Choose a checkpoint in the selected passage.')
        with self.lock:
            if self.process is not None:
                raise ValueError('End the active experience before editing cue assignments.')
            if not self.cue or self.assignment_file is None:
                raise ValueError('The MapMap bridge is not configured for cue assignments.')
            if cue_id is not None and (not isinstance(cue_id, str) or cue_id not in self.cue.cues):
                raise ValueError('Choose a cue from the MapMap project.')
            assignments = {**self.assignments, passage: {**self.assignments.get(passage, {}), checkpoint: cue_id}}
            self.save_mapmap_settings(assignments, self.fade_ms)
            self.assignments = assignments

    def set_transition(self, body):
        fade_ms = body.get('fade_ms') if isinstance(body, dict) else None
        if type(fade_ms) is not int or fade_ms not in FADE_OPTIONS_MS:
            raise ValueError('Choose a listed MapMap transition duration.')
        with self.lock:
            if self.process is not None:
                raise ValueError('End the active experience before editing the MapMap transition.')
            if not self.cue or self.assignment_file is None:
                raise ValueError('The MapMap bridge is not configured for transition settings.')
            self.save_mapmap_settings(self.assignments, fade_ms)
            self.fade_ms = fade_ms

    def save_mapmap_settings(self, assignments, fade_ms):
        payload = {'version': 1, 'assignments': assignments, 'fade_ms': fade_ms}
        self.assignment_file.parent.mkdir(parents=True, exist_ok=True)
        temp = self.assignment_file.with_suffix(f'.{uuid4().hex}.tmp')
        try:
            temp.write_text(json.dumps(payload, indent=2) + '\n', encoding='utf-8')
            temp.replace(self.assignment_file)
        finally:
            temp.unlink(missing_ok=True)

    def catalog(self):
        try:
            microphones = list_microphones()
        except (ImportError, OSError):
            microphones = []
        passages = []
        for passage, (_, data) in self.passages.items():
            cues = self.mapmap_cues(passage)
            checkpoints = []
            for checkpoint in data['checkpoints']:
                ident = str(checkpoint['id'])
                cue = cues.get(ident)
                sound = (checkpoint.get('effect') or {}).get('sound')
                has_sound = isinstance(sound, str) and bool(sound)
                if cue:
                    playback = {'kind': 'mapmap', 'detail': cue.title, 'local_sound': has_sound and not cue.has_audio}
                elif has_sound:
                    playback = {'kind': 'local_sound', 'detail': Path(sound).stem.replace('_', ' ')}
                else:
                    playback = {'kind': 'tracking'}
                checkpoints.append({**checkpoint, 'playback': playback,
                                    'mapmap_cue': self.assignments.get(passage, {}).get(ident)})
            passages.append({**data, 'checkpoints': checkpoints})
        return {
            'passages': passages,
            'models': [
                {'id': key, 'label': name, 'port': self.ports.get(key, port), 'hints': hints}
                for key, (name, port, hints) in MODELS.items()
            ],
            'projection': self.cue is not None,
            'mapmap_project': self.cue.project.name if self.cue else None,
            'mapmap_cues': [{'id': ident, 'title': cue.title} for ident, cue in self.cue.cues.items()] if self.cue else [],
            'silver_seed_test': bool(self.cue and self.cue.silver_seed),
            'mapmap_transition': {'fade_ms': self.fade_ms, 'options_ms': FADE_OPTIONS_MS} if self.cue else None,
            'microphones': microphones,
        }

    def preflight(self):
        # NeMo accepts one session at a time. Keep Start from racing the probe.
        with self.lock:
            if self.process is not None:
                raise ValueError('End the active experience before checking NeMo.')
            nemo = check_nemo(self.ports.get('parakeet-nemo', MODELS['parakeet-nemo'][1]))
        if self.cue:
            mapmap = check_mapmap_listener(self.cue.port)
        else:
            mapmap = {'state': 'unconfigured', 'detail': 'Start the panel with the MapMap bridge to test projection.'}
        return {'nemo': nemo, 'mapmap': mapmap}

    def manual_cue(self, action):
        with self.lock:
            if self.process is not None:
                raise ValueError('End the active experience before testing projection.')
            if not self.cue:
                raise ValueError('The MapMap bridge is not configured.')
            if action == 'test' and not self.cue.silver_seed:
                raise ValueError('The Silver Seed cue is unavailable in this MapMap project.')
            status = check_mapmap_listener(self.cue.port)
            if status['state'] == 'error':
                raise ValueError(status['detail'])
            self.cue.reset()
            if action == 'test':
                self.cue.play(self.cue.cues[self.cue.silver_seed])
                return {'message': 'Silver Seed cue sent. Check the video and soundtrack at the pod.'}
            return {'message': 'Reset sent. Check that MapMap returns to the calibration grid.'}

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

        manifest, passage_data = self.passages[passage]
        checkpoints = passage_data['checkpoints']
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
        with self.lock:
            if self.process is not None:
                raise ValueError('End the current session before starting another.')
            for checkpoint, cue in self.mapmap_cues(passage).items():
                if cue.has_audio:
                    command += ['--mute-checkpoint-sound', checkpoint]
            if self.cue:
                self.cue.reset()
            self.process = subprocess.Popen(
                command, cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, encoding='utf-8', errors='replace',
            )
            self.state = {
                'phase': 'starting', 'fired': [], 'message': '', 'transcript': '', 'microphone': None,
                'partial': [], 'scores': {}, 'cue_status': {}, 'match_evidence': {},
                'reading_checkpoint': str(checkpoints[0]['id']) if checkpoints else None,
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
        mapmap_cues = self.mapmap_cues(passage)
        with process.stdout:
            for raw in process.stdout:
                line = raw.rstrip()
                if raw.startswith(TRANSCRIPT_PREFIX):
                    update = json.loads(raw[len(TRANSCRIPT_PREFIX):])
                    with self.lock:
                        self.state['transcript'] = update['text']
                        self.state['partial'] = update['partial']
                        if 'reading_checkpoint' in update:
                            self.state['reading_checkpoint'] = update['reading_checkpoint']
                        checkpoint = update['checkpoint']
                        terminal = (checkpoint in self.state['fired'] or
                                    self.state['cue_status'].get(checkpoint) in ('Skipped', 'Cue withheld'))
                        if checkpoint is not None and update['score'] is not None and not terminal:
                            self.state['scores'][checkpoint] = update['score']
                            if update.get('evidence'):
                                self.state['match_evidence'][checkpoint] = update['evidence']
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
                        if trigger[1] in mapmap_cues:
                            try:
                                self.cue.play(mapmap_cues[trigger[1]], self.fade_ms)
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
            result = None
            if self.path == '/api/session/start':
                self.sessions.start(body)
            elif self.path == '/api/session/end':
                self.sessions.end()
            elif self.path == '/api/preflight':
                result = self.sessions.preflight()
            elif self.path == '/api/mapmap/assignment':
                self.sessions.assign_cue(body)
                result = self.sessions.catalog()
            elif self.path == '/api/mapmap/transition':
                self.sessions.set_transition(body)
                result = self.sessions.catalog()
            elif self.path in ('/api/mapmap/test', '/api/mapmap/reset'):
                result = self.sessions.manual_cue(self.path.rsplit('/', 1)[1])
            else:
                self.send_error(404)
                return
        except (ValueError, OSError) as error:
            self.send_json({'error': str(error)}, 400)
            return
        self.send_json(self.sessions.status() if result is None else result)

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
    parser.add_argument('--mapmap-project', type=Path, help='Saved MapMap project. Defaults to the bridge’s spoken-cue project.')
    parser.add_argument('--osc-port', type=int, default=12345)
    args = parser.parse_args()
    if not (DIST / 'index.html').is_file():
        parser.error('Build the React panel first. See operator-panel/README.md.')
    if args.mapmap_bridge and not args.mapmap_bridge.is_file():
        parser.error('--mapmap-bridge must point to the handoff play_cue.py file.')
    if args.mapmap_project and not args.mapmap_bridge:
        parser.error('--mapmap-project requires --mapmap-bridge.')
    ports = {model: {9090: args.whisper_port, 9091: args.native_port, 9097: args.nemo_port}[port]
             for model, (_, port, _) in MODELS.items()}
    try:
        cue = MapMapCue(args.mapmap_bridge.resolve(), args.osc_port, args.mapmap_project) if args.mapmap_bridge else None
        assignment_file = None
        if cue:
            project_key = sha256(normcase(str(cue.project)).encode()).hexdigest()[:24]
            assignment_file = ROOT / 'output/operator-mapmap' / f'{project_key}.json'
        sessions = Sessions(load_passages(), ports, cue, assignment_file=assignment_file)
    except (OSError, ValueError, AttributeError, KeyError, TypeError) as error:
        parser.error(f'Could not load operator panel configuration. {error}')
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
