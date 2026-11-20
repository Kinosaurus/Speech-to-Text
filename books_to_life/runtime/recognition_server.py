"""Manage the installed WSL NeMo server without blocking panel requests."""

from pathlib import Path
import subprocess
import sys
from threading import Lock, Thread
from time import monotonic, sleep


def wsl_path(path):
    path = Path(path).resolve()
    if sys.platform == 'win32':
        return f'/mnt/{path.drive[0].lower()}{path.as_posix()[2:]}'
    return str(path)


class RecognitionServer:
    def __init__(self, root, port, probe, *, distro='Ubuntu',
                 python=None, model=None):
        if not 1 <= port <= 65535:
            raise ValueError('The NeMo port must be between 1 and 65535.')
        self.root, self.port, self.probe = root, port, probe
        self.distro, self.python = distro, python
        model_path = Path('model-cache/parakeet-nemo/parakeet-unified-en-0.6b.nemo')
        candidates = [root / model_path, *(parent / model_path for parent in root.parents)]
        self.model = model or next((path for path in candidates if path.is_file()), candidates[0])
        self.log = root / 'output/operator-server/nemo.log'
        self.lock = Lock()
        self.worker = None
        self.next_check = 0
        self.state = {'state': 'unknown', 'detail': 'Checking the recognition server.', 'busy': False,
                      'log': str(self.log), 'managed': sys.platform == 'win32'}

    def snapshot(self, *, refresh=True):
        with self.lock:
            if refresh and not self.state['busy'] and monotonic() >= self.next_check:
                self._start_worker('check')
            return self.state.copy()

    def request(self, action, before_restart=None):
        if action not in ('start', 'restart'):
            raise ValueError('Choose Start or Restart recognition server.')
        with self.lock:
            if self.state['busy']:
                raise ValueError('The recognition server is already being checked or started.')
            if not self.state['managed']:
                raise ValueError('Panel server controls require the Windows WSL setup.')
            self._start_worker(action, before_restart)
            return self.state.copy()

    def _start_worker(self, action, before_restart=None):
        labels = {'check': ('checking', 'Checking NeMo readiness.'),
                  'start': ('starting', 'Starting NeMo and loading the cached model.'),
                  'restart': ('restarting', 'Restarting NeMo and loading the cached model.')}
        state, detail = labels[action]
        self.state.update(state=state, detail=detail, busy=True)
        self.worker = Thread(target=self._run, args=(action, before_restart), daemon=True)
        self.worker.start()

    def _run(self, action, before_restart):
        try:
            if action == 'check':
                result = self.probe()
            elif action == 'start' and (result := self.probe())['state'] == 'ready':
                pass
            else:
                if before_restart:
                    before_restart()
                python = [self.python] if self.python else ['bash', 'scripts/reading-pod/nemo-python.sh']
                command = ['wsl.exe', '-d', self.distro, '--cd', wsl_path(self.root), '--exec',
                           *python, '-m', 'books_to_life.cli.manage_nemo_server', action,
                           '--port', str(self.port), '--model-path', wsl_path(self.model),
                           '--log-file', wsl_path(self.log)]
                completed = subprocess.run(command, capture_output=True, text=True, encoding='utf-8',
                                           errors='replace', timeout=45,
                                           creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                if completed.returncode:
                    detail = (completed.stderr or completed.stdout).strip().replace('\x00', '')
                    raise ValueError(f'NeMo could not {action}. {detail[-600:]}')
                deadline = monotonic() + 300
                while True:
                    result = self.probe()
                    if result['state'] == 'ready':
                        break
                    if monotonic() >= deadline:
                        raise ValueError(f'NeMo did not become ready. Check {self.log}.')
                    sleep(1)
        except (OSError, ValueError, subprocess.TimeoutExpired) as error:
            result = {'state': 'error', 'detail': str(error)}
        with self.lock:
            self.state.update(result, busy=False)
            self.next_check = monotonic() + 15
