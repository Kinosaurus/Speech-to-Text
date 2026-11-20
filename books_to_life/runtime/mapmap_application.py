"""Open the Reading Pod MapMap launcher and report its OSC readiness."""

import json
import subprocess
import sys
from threading import Lock, Thread
from time import monotonic, sleep


class MapMapApplication:
    def __init__(self, launcher, project, port, probe):
        self.launcher, self.project, self.port, self.probe = launcher, project, port, probe
        self.lock = Lock()
        self.next_check = 0
        self.worker = None
        self.state = {'state': 'unknown', 'detail': 'Checking MapMap.', 'busy': False,
                      'managed': sys.platform == 'win32' and launcher.is_file()}

    def snapshot(self, *, refresh=True):
        with self.lock:
            if refresh and not self.state['busy'] and monotonic() >= self.next_check:
                self._start(False)
            return self.state.copy()

    def open(self):
        with self.lock:
            if self.state['busy']:
                raise ValueError('Wait for MapMap to finish opening or checking its connection.')
            if not self.state['managed']:
                raise ValueError(f'The Reading Pod MapMap launcher is unavailable at {self.launcher}.')
            self._start(True)
            return self.state.copy()

    def _start(self, launch):
        self.state.update(busy=True)
        if launch:
            self.state.update(state='starting', detail='Opening MapMap with the selected story.')
        self.worker = Thread(target=self._run, args=(launch,), daemon=True)
        self.worker.start()

    def _run(self, launch):
        try:
            result = self.probe(self.port)
            if launch and result['state'] != 'ready':
                if result.get('reason') == 'port_in_use':
                    raise ValueError(result['detail'])
                if not self.project.path.is_file():
                    raise ValueError('Choose a story before opening MapMap.')
                command = ['powershell.exe', '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass',
                           '-File', str(self.launcher), '-ProjectPath', str(self.project.path),
                           '-OscPort', str(self.port)]
                completed = subprocess.run(command, capture_output=True, text=True,
                                           encoding='utf-8', errors='replace', timeout=20,
                                           creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                if completed.returncode:
                    detail = (completed.stderr or completed.stdout).strip()
                    raise ValueError(f'MapMap could not open. {detail[-600:]}')
                deadline = monotonic() + 30
                while True:
                    result = self.probe(self.port)
                    if result['state'] == 'ready' and self._project_loaded(result['pid']):
                        result['detail'] = f'MapMap loaded the selected story and is listening on UDP {self.port}.'
                        break
                    if monotonic() >= deadline:
                        raise ValueError('MapMap did not confirm the selected story. Check the MapMap window and OSC port.')
                    sleep(.5)
        except (OSError, ValueError, subprocess.TimeoutExpired) as error:
            result = {'state': 'error', 'detail': str(error)}
        with self.lock:
            self.state.pop('pid', None)
            self.state.update(result, busy=False)
            self.next_check = monotonic() + 10

    def _project_loaded(self, pid):
        try:
            reply = json.loads(self.project.status_path.read_text(encoding='utf-8'))
            project = json.loads(self.project.path.read_text(encoding='utf-8-sig'))
            return (reply.get('pid') == pid and not reply.get('error')
                    and reply.get('revision') == project.get('readingPodRevision'))
        except (OSError, ValueError, AttributeError):
            return False
