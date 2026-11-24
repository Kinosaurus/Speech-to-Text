"""Serve the Reading Pod operator panel and manage a single microphone session."""

import argparse
from datetime import datetime
from functools import partial
from hashlib import sha256
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from os import fstat
from os.path import normcase, relpath
from pathlib import Path
import re
import subprocess
import sys
from threading import Lock, Thread
from urllib.parse import quote
from uuid import uuid4

import websocket

from books_to_life.runtime.audio_runtime import input_devices, microphone_label
from books_to_life.runtime.mapmap_cues import DEFAULT_FADE_MS, MapMapCue
from books_to_life.runtime.mapmap_output import detect_output_size
from books_to_life.runtime.mapmap_story import StoryProject
from books_to_life.runtime.mapmap_application import MapMapApplication
from books_to_life.runtime.recognition_server import RecognitionServer
from books_to_life.runtime.nemo_defaults import DEFAULT_RECOGNITION_MODEL, NEMO_MODELS, microphone_arguments


ROOT = Path(__file__).resolve().parents[2]
DIST = ROOT / 'operator-panel/dist'
STORIES = ROOT / 'recordings/library/stories'
SCENES = ROOT / 'scenes'
MODELS = {
    'parakeet-nemo': ('Parakeet NeMo', 9097, True),
    'nemotron': ('Nemotron · 160 ms', 9097, True),
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


def cue_preview_url(passage, checkpoint):
    return '/cue-preview/' + quote(passage, safe='') + '/' + quote(str(checkpoint), safe='') + '.mp4'


def check_nemo(port, backend='parakeet-nemo'):
    endpoint = f'127.0.0.1:{port}'
    uid = str(uuid4())
    connection = None
    try:
        connection = websocket.create_connection(
            f'ws://{endpoint}', timeout=3, http_no_proxy=['127.0.0.1'],
        )
        connection.send(json.dumps({'uid': uid, 'model': backend, 'language': 'en'}))
        reply = json.loads(connection.recv())
        if (isinstance(reply, dict) and reply.get('uid') == uid
                and reply.get('message') == 'SERVER_READY' and reply.get('backend') == backend):
            detail=f'SERVER_READY from {endpoint}.'
            if isinstance(reply.get('chunk_ms'),int) and isinstance(reply.get('right_ms'),int):
                detail+=f' Updates every {reply["chunk_ms"]} ms; future context {reply["right_ms"]} ms.'
            elif isinstance(reply.get('chunk_ms'), int):
                detail += f' Nemotron streams in {reply["chunk_ms"]} ms chunks.'
            return {'state': 'ready', 'detail': detail}
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
    if ($owner.ProcessName -ieq 'MapMap') {{ "mapmap:$($owner.Id)"; exit }}
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
    reply = result.stdout.strip()
    if match := re.fullmatch(r'mapmap:(\d+)', reply):
        return {'state': 'ready', 'detail': f'MapMap owns {endpoint}. Use the test cue to check playback.',
                'pid': int(match[1])}
    match reply:
        case 'missing':
            return {'state': 'error', 'detail': f'No listener on {endpoint}. Open MapMap and verify its OSC port.'}
        case 'other':
            return {'state': 'error', 'detail': f'Another process owns {endpoint}. Check the MapMap OSC port.',
                    'reason': 'port_in_use'}
        case _:
            return unavailable


class Sessions:
    def __init__(self, passages, ports, cue=None, *, assignment_file=None, assignment_defaults=None, scene_directory=SCENES,
                 story_directory=None, recognition_options=None, mapmap_launcher=None):
        self.passages = passages
        self.preview_files = {}
        for passage, (manifest, data) in passages.items():
            for checkpoint in data['checkpoints']:
                preview = (checkpoint.get('effect') or {}).get('preview')
                if not isinstance(preview, str) or not preview:
                    continue
                path = (manifest.parent / preview).resolve()
                if path.suffix.lower() == '.mp4' and path.is_relative_to(manifest.parents[2]) and path.is_file():
                    self.preview_files[cue_preview_url(passage, checkpoint['id'])] = path
        self.ports = ports
        self.cue = cue
        self.assignment_file = assignment_file
        self.scene_directory = scene_directory if cue and cue.has_project_file else None
        self.assignments = {'sample': {'seed_found': cue.silver_seed}} if cue and cue.silver_seed else {}
        self.fade_ms = DEFAULT_FADE_MS
        settings_file = assignment_file if assignment_file and assignment_file.is_file() else assignment_defaults
        if settings_file is not None:
            stored = json.loads(settings_file.read_text(encoding='utf-8-sig'))
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
        self.recognition = RecognitionServer(ROOT, ports.get(DEFAULT_RECOGNITION_MODEL, 9097),
                                             self.probe_recognition, **(recognition_options or {}))
        self.state = {'phase': 'idle', 'fired': [], 'message': '', 'settings': None,
                      'transcript': '', 'partial': [], 'scores': {}, 'cue_status': {}, 'match_evidence': {},
                      'reading_checkpoint': None}
        self.story_project = StoryProject(story_directory, cue.project, cue.port) if story_directory else None
        self.mapmap_application = None
        if self.story_project:
            cue.story_project = self.story_project
            launcher = mapmap_launcher
            if launcher is None and cue.bridge is not None:
                launcher = Path(cue.bridge.__file__).resolve().parents[2] / 'Start-Reading-Pod-MapMap.ps1'
            self.mapmap_application = MapMapApplication(launcher, self.story_project, cue.port, check_mapmap_listener)
        self.story_passage = None
        if self.story_project and passages:
            saved = self.story_project.saved_passage()
            passage = saved if saved in passages else ('sample' if 'sample' in passages else next(iter(passages)))
            self.prepare_story(passage)

    def status(self):
        with self.lock:
            return {**self.state, 'fired': self.state['fired'][:], 'scores': self.state['scores'].copy(),
                    'recognition': self.recognition.snapshot(),
                    'mapmap': self.mapmap_application.snapshot() if self.mapmap_application else None,
                    'cue_status': self.state['cue_status'].copy(),
                      'match_evidence': self.state['match_evidence'].copy(),
                      'message': self.state['message'] or (self.cue.playback_error if self.cue else '') or ''}

    def probe_recognition(self):
        with self.lock:
            if (self.process is not None and self.process.poll() is None
                    and self.state['settings']['model'] == self.recognition.backend):
                return {'state': 'ready', 'detail': 'NeMo is serving the active reading session.'}
            return check_nemo(self.recognition.port, self.recognition.backend)

    def recognition_action(self, action, backend=None):
        if backend is not None and backend not in NEMO_MODELS:
            raise ValueError('Choose Parakeet NeMo or Nemotron.')
        if action == 'start' and self.process is not None:
            raise ValueError('End the current experience before starting or switching recognition servers.')
        def finish_reading():
            self.end()
            process = self.process
            if process is not None:
                process.wait(timeout=75)

        if backend is None:
            return self.recognition.request(action, finish_reading if action == 'restart' else None)
        return self.recognition.request(action, finish_reading if action == 'restart' else None, backend=backend)

    def open_mapmap(self):
        with self.lock:
            if self.process is not None:
                raise ValueError('End the active experience before opening MapMap.')
            if not self.mapmap_application:
                raise ValueError('Start the panel with the Reading Pod master project and selected-story directory.')
            return self.mapmap_application.open()

    def mapmap_cues(self, passage):
        if not self.cue:
            return {}
        cues = self.cue.cues
        return {checkpoint: cues[cue_id] for checkpoint, cue_id in self.assignments.get(passage, {}).items()
                if cue_id in cues}

    def next_projection_video(self, passage, cues, after=None):
        checkpoints = self.passages[passage][1]['checkpoints']
        current = cues.get(after)
        position = next((i for i, item in enumerate(checkpoints) if str(item['id']) == after), -1)
        for checkpoint in checkpoints[position + 1:]:
            cue = cues.get(str(checkpoint['id']))
            if cue and cue.hold_seconds is not None and cue != current:
                return cue
        return None

    def prepare_story(self, passage, listener=None):
        cues = self.mapmap_cues(passage)
        revision, layers = self.story_project.prepare(passage, cues)
        pid = listener.get('pid') if listener and listener['state'] == 'ready' else None
        self.cue.set_story_scope((revision, pid), cues, layers)
        if pid is not None:
            self.story_project.load(revision, pid)
        self.story_passage = passage
        return len({cue.source for cue in cues.values()}), pid is not None

    def select_story(self, body):
        passage = body.get('passage') if isinstance(body, dict) else None
        if not isinstance(passage, str) or passage not in self.passages:
            raise ValueError('Choose a listed story.')
        with self.lock:
            if self.process is not None:
                raise ValueError('End the active experience before switching stories.')
            if self.mapmap_application and self.mapmap_application.snapshot(refresh=False)['state'] == 'starting':
                raise ValueError('Wait for MapMap to finish opening before switching stories.')
            if not self.story_project:
                raise ValueError('Story switching is not configured for this panel.')
            count, ready = self.prepare_story(passage, check_mapmap_listener(self.cue.port))
        title = self.passages[passage][1]['title']
        detail = f'{title} loaded in MapMap' if ready else f'{title} prepared for the next MapMap launch'
        return {'message': f'{detail}. {count} projection scene{"s" if count != 1 else ""}.'}

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
            if self.story_project and passage == self.story_passage:
                self.prepare_story(passage, check_mapmap_listener(self.cue.port))

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

    def update_scenes(self, action):
        with self.lock:
            purpose = 'importing scenes' if action == 'import' else 'applying the wall layout'
            if self.process is not None:
                raise ValueError(f'End the active experience before {purpose}.')
            if self.scene_directory is None:
                raise ValueError(f'Start the panel with a saved MapMap project before {purpose}.')
            try:
                result = (self.cue.import_scenes(self.scene_directory) if action == 'import'
                          else self.cue.apply_wall_layout())
                if self.story_passage:
                    self.prepare_story(self.story_passage)
                return result
            except (KeyError, TypeError) as error:
                raise ValueError('The saved MapMap project has an invalid source or layer.') from error

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
                url = cue_preview_url(passage, ident)
                checkpoints.append({**checkpoint, 'playback': playback,
                                    'preview_url': url if url in self.preview_files else None,
                                    'mapmap_cue': self.assignments.get(passage, {}).get(ident)})
            passages.append({**data, 'checkpoints': checkpoints})
        return {
            'passages': passages,
            'models': [
                {'id': key, 'label': name, 'port': self.ports.get(key, port), 'hints': hints, 'managed': key in NEMO_MODELS}
                for key, (name, port, hints) in MODELS.items()
            ],
            'default_model': DEFAULT_RECOGNITION_MODEL,
            'projection': self.cue is not None,
            'mapmap_project': self.cue.project.name if self.cue else None,
            'mapmap_story': self.story_passage,
            'mapmap_scene_directory': str(self.scene_directory) if self.scene_directory else None,
            'mapmap_cues': [{'id': ident, 'title': cue.title} for ident, cue in self.cue.cues.items()] if self.cue else [],
            'silver_seed_test': bool(self.cue and self.cue.silver_seed),
            'mapmap_transition': {'fade_ms': self.fade_ms, 'options_ms': FADE_OPTIONS_MS} if self.cue else None,
            'mapmap_layout': bool(self.cue and self.cue.output_layers),
            'microphones': microphones,
        }

    def preflight(self, backend=DEFAULT_RECOGNITION_MODEL):
        if backend not in NEMO_MODELS:
            raise ValueError('Choose Parakeet NeMo or Nemotron.')
        # NeMo accepts one session at a time. Keep Start from racing the probe.
        with self.lock:
            if self.process is not None:
                raise ValueError('End the active experience before checking NeMo.')
            nemo = check_nemo(self.ports.get(backend, MODELS[backend][1]), backend)
        if self.cue:
            mapmap = check_mapmap_listener(self.cue.port)
        else:
            mapmap = {'state': 'unconfigured', 'detail': 'Start the panel with the MapMap bridge to test projection.'}
        return {'nemo': nemo, 'mapmap': mapmap}

    def manual_cue(self, action, body):
        with self.lock:
            if self.process is not None:
                raise ValueError('End the active experience before testing projection.')
            if not self.cue:
                raise ValueError('The MapMap bridge is not configured.')
            if action == 'test' and not self.cue.silver_seed:
                raise ValueError('The Silver Seed cue is unavailable in this MapMap project.')
            selected = None
            if action == 'preview':
                ident = body.get('cue') if isinstance(body, dict) else None
                if not isinstance(ident, str) or ident not in self.cue.cues:
                    raise ValueError('Choose a scene from the MapMap project.')
                selected = self.cue.cues[ident]
            status = check_mapmap_listener(self.cue.port)
            if status['state'] == 'error':
                raise ValueError(status['detail'])
            if self.story_passage:
                self.prepare_story(self.story_passage, status)
                requested = selected or (self.cue.cues[self.cue.silver_seed] if action == 'test' else None)
                if requested and requested.source not in self.cue.story_cues:
                    raise ValueError('Choose a scene assigned to the selected story.')
            if selected is not None:
                self.cue.play(selected, self.fade_ms)
                return {'message': f'{selected.title} sent to MapMap.'}
            self.cue.reset()
            if action == 'test':
                self.cue.play(self.cue.cues[self.cue.silver_seed])
                return {'message': 'Silver Seed cue sent. Check the video and soundtrack at the pod.'}
            return {'message': 'Reset sent. Check that MapMap returns to the calibration grid.'}

    def apply_layout(self, body):
        if not isinstance(body, dict) or body.get('mode') not in ('auto', 'fit', 'original'):
            raise ValueError('Choose Fit output or Restore original.')
        size = None
        if body['mode'] == 'fit':
            size = (body.get('width'), body.get('height'))
            if any(type(value) is not int or not 240 <= value <= 8192 for value in size):
                raise ValueError('Enter output dimensions between 240 and 8192 pixels.')
        with self.lock:
            if self.process is not None:
                raise ValueError('End the active experience before adjusting the output layout.')
            if not self.cue:
                raise ValueError('The MapMap bridge is not configured.')
            status = check_mapmap_listener(self.cue.port)
            if status['state'] == 'error':
                raise ValueError(status['detail'])
            if body['mode'] == 'auto':
                size = detect_output_size(status.get('pid'))
                if size is None:
                    raise ValueError('Could not detect the MapMap output. Open it fullscreen or use Manual dimensions.')
            self.cue.set_output_layout(size, pid=status.get('pid'))
        action = 'applied and confirmed' if self.story_project else 'sent'
        return {'message': f'Fit {action} for {size[0]} × {size[1]}.' if size else f'Original output layout {action}.'}

    def wall_layout(self, action=None, body=None):
        with self.lock:
            if self.process is not None:
                raise ValueError('End the active experience before editing the wall layout.')
            if self.scene_directory is None:
                raise ValueError('Start the panel with a saved MapMap project to edit its wall layout.')
            try:
                if action is None:
                    status = check_mapmap_listener(self.cue.port)
                    layout = self.cue.wall_layout(pid=status.get('pid'))
                    layout['output_size'] = detect_output_size(status.get('pid'))
                    return layout
                if not isinstance(body, dict) or not isinstance(body.get('revision'), str):
                    raise ValueError('Open the wall editor to load the saved layout.')
                if action == 'preview':
                    status = check_mapmap_listener(self.cue.port)
                    if status['state'] == 'error':
                        raise ValueError(status['detail'])
                    return self.cue.preview_wall_layout(body['revision'], body.get('corners'), pid=status.get('pid'))
                status = check_mapmap_listener(self.cue.port)
                live = status['state'] == 'ready' and self.story_project is not None
                if live:
                    self.story_project.require_live_layout(status['pid'])
                saved = self.cue.save_wall_layout(body['revision'], body.get('corners'), live=live)
                saved['live_applied'] = False
                if live:
                    try:
                        self.story_project.apply_layout(self.cue.output_layers, status['pid'], saved['revision'])
                        saved['live_applied'] = True
                    except (OSError, ValueError) as error:
                        saved['apply_error'] = f'Layout saved to all scenes. Live update failed: {error}'
                elif self.story_passage:
                    self.prepare_story(self.story_passage)
                return saved
            except (KeyError, TypeError, IndexError) as error:
                raise ValueError('The saved MapMap project has an invalid wall layout.') from error

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
        command += microphone_arguments(model)
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
            if self.mapmap_application and self.mapmap_application.snapshot(refresh=False)['state'] == 'starting':
                raise ValueError('Wait for MapMap to finish opening before starting the experience.')
            if model in NEMO_MODELS and self.recognition.snapshot(refresh=False)['busy']:
                raise ValueError('Wait for the recognition server to finish starting or checking readiness.')
            if model in NEMO_MODELS and self.recognition.backend != model:
                raise ValueError('Start the selected recognition model under Preflight first.')
            ready = True
            if self.story_project:
                _, ready = self.prepare_story(passage, check_mapmap_listener(self.cue.port))
            projection_cues = self.mapmap_cues(passage)
            for checkpoint, cue in projection_cues.items():
                if cue.has_audio and ready:
                    command += ['--mute-checkpoint-sound', checkpoint]
            if self.cue:
                self.cue.reset()
                if self.story_project and ready:
                    self.cue.preload(self.next_projection_video(passage, projection_cues))
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
                                next_cue = self.next_projection_video(passage, mapmap_cues, after=trigger[1])
                                self.cue.play(mapmap_cues[trigger[1]], self.fade_ms, next_cue=next_cue)
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

    def send_head(self):
        if not self.path.startswith('/cue-preview/'):
            return super().send_head()
        if not self.local_host():
            self.send_error(403)
            return None
        path = self.sessions.preview_files.get(self.path)
        try:
            stream = path.open('rb') if path else None
        except OSError:
            stream = None
        if stream is None:
            self.send_error(404)
            return None
        self.send_response(200)
        self.send_header('Content-Type', 'video/mp4')
        self.send_header('Content-Length', str(fstat(stream.fileno()).st_size))
        self.send_header('Cross-Origin-Resource-Policy', 'same-origin')
        self.end_headers()
        return stream

    def do_GET(self):
        if not self.local_host():
            self.send_error(403)
        elif self.path == '/api/catalog':
            self.send_json(self.sessions.catalog())
        elif self.path == '/api/session':
            self.send_json(self.sessions.status())
        elif self.path == '/api/mapmap/wall-layout':
            try:
                self.send_json(self.sessions.wall_layout())
            except (ValueError, OSError) as error:
                self.send_json({'error': str(error)}, 400)
        elif self.path == '/' or self.path.startswith(('/assets/', '/cue-preview/')):
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
            elif self.path in ('/api/recognition/start', '/api/recognition/restart'):
                result = self.sessions.recognition_action(self.path.rsplit('/', 1)[1], body.get('model'))
            elif self.path == '/api/mapmap/open':
                result = self.sessions.open_mapmap()
            elif self.path == '/api/preflight':
                result = self.sessions.preflight(body.get('model', DEFAULT_RECOGNITION_MODEL))
            elif self.path == '/api/mapmap/assignment':
                self.sessions.assign_cue(body)
                result = self.sessions.catalog()
            elif self.path == '/api/mapmap/story':
                result = self.sessions.select_story(body)
            elif self.path == '/api/mapmap/transition':
                self.sessions.set_transition(body)
                result = self.sessions.catalog()
            elif self.path in ('/api/mapmap/scenes/import', '/api/mapmap/scenes/apply-layout'):
                update = self.sessions.update_scenes(self.path.rsplit('/', 1)[1])
                result = {'catalog': self.sessions.catalog(), **update}
            elif self.path == '/api/mapmap/layout':
                result = self.sessions.apply_layout(body)
            elif self.path in ('/api/mapmap/wall-layout/preview', '/api/mapmap/wall-layout/save'):
                result = self.sessions.wall_layout(self.path.rsplit('/', 1)[1], body)
            elif self.path in ('/api/mapmap/test', '/api/mapmap/reset', '/api/mapmap/preview'):
                result = self.sessions.manual_cue(self.path.rsplit('/', 1)[1], body)
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


def initialize_mapmap_project(template, project):
    if project.is_file():
        return
    data = json.loads(template.read_text(encoding='utf-8-sig'))
    for source in data['sources']:
        if source.get('uri'):
            media = (template.parent / source['uri']).resolve(strict=True)
            source['uri'] = Path(relpath(media, project.parent)).as_posix()
    project.parent.mkdir(parents=True, exist_ok=True)
    try:
        with project.open('x', encoding='utf-8') as stream:
            json.dump(data, stream, indent=2, ensure_ascii=False)
            stream.write('\n')
    except FileExistsError:
        pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--open-browser', action='store_true')
    parser.add_argument('--whisper-port', type=int, default=9090)
    parser.add_argument('--nemo-port', type=int, default=9097)
    parser.add_argument('--nemo-distro', default='Ubuntu', help='WSL distribution used by the NeMo server controls.')
    parser.add_argument('--nemo-python',
                        help='Installed Python executable inside the NeMo WSL environment.')
    parser.add_argument('--nemo-model', type=Path, help='Windows path to the cached NeMo model.')
    parser.add_argument('--nemotron-model', type=Path, help='Windows path to the cached Nemotron checkpoint.')
    parser.add_argument('--native-port', type=int, default=9091)
    parser.add_argument('--mapmap-bridge', type=Path, help='Path to the handoff play_cue.py.')
    parser.add_argument('--mapmap-project', type=Path, help='Saved MapMap project. Defaults to the bridge’s spoken-cue project.')
    parser.add_argument('--mapmap-template', type=Path, help='Template for initializing a new local MapMap project.')
    parser.add_argument('--mapmap-story-dir', type=Path, help='Directory for the generated selected-story MapMap project.')
    parser.add_argument('--mapmap-launcher', type=Path, help='Path to Start-Reading-Pod-MapMap.ps1, inferred from the bridge by default.')
    parser.add_argument('--mapmap-default-assignments', type=Path, help='Initial cue assignments for a new local project.')
    parser.add_argument('--osc-port', type=int, default=12345)
    args = parser.parse_args()
    if not (DIST / 'index.html').is_file():
        parser.error('Build the React panel first. See operator-panel/README.md.')
    if args.mapmap_bridge and not args.mapmap_bridge.is_file():
        parser.error('--mapmap-bridge must point to the handoff play_cue.py file.')
    if args.mapmap_template and not args.mapmap_project:
        parser.error('--mapmap-template requires --mapmap-project.')
    if args.mapmap_story_dir and not args.mapmap_project:
        parser.error('--mapmap-story-dir requires --mapmap-project.')
    if args.mapmap_story_dir and not (args.mapmap_bridge or args.mapmap_launcher):
        parser.error('--mapmap-story-dir requires a MapMap launcher or handoff bridge.')
    ports = {model: {9090: args.whisper_port, 9091: args.native_port, 9097: args.nemo_port}[port]
             for model, (_, port, _) in MODELS.items()}
    try:
        if args.mapmap_template:
            initialize_mapmap_project(args.mapmap_template.resolve(), args.mapmap_project.resolve())
        cue = (MapMapCue(args.mapmap_bridge, args.osc_port, args.mapmap_project)
               if args.mapmap_bridge or args.mapmap_project else None)
        assignment_file = None
        if cue:
            project_key = sha256(normcase(str(cue.project)).encode()).hexdigest()[:24]
            assignment_file = ROOT / 'output/operator-mapmap' / f'{project_key}.json'
        story_directory = args.mapmap_story_dir.resolve() if args.mapmap_story_dir else None
        sessions = Sessions(load_passages(), ports, cue, assignment_file=assignment_file, story_directory=story_directory,
                            assignment_defaults=args.mapmap_default_assignments,
                            mapmap_launcher=args.mapmap_launcher,
                            recognition_options={'distro': args.nemo_distro, 'python': args.nemo_python,
                                                 'model': args.nemo_model, 'nemotron_model': args.nemotron_model})
    except (OSError, ValueError, AttributeError, KeyError, TypeError) as error:
        parser.error(f'Could not load operator panel configuration. {error}')
    with ThreadingHTTPServer(('127.0.0.1', args.port), partial(PanelHandler, sessions=sessions)) as server:
        url = f'http://127.0.0.1:{server.server_port}'
        print(f'Reading Pod panel available at {url}', flush=True)
        if args.open_browser:
            import webbrowser

            webbrowser.open(url)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            sessions.end()
            if sessions.update_thread:
                sessions.update_thread.join()


if __name__ == '__main__':
    main()
