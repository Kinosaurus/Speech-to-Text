"""Start or restart the local NeMo process from inside its existing WSL environment."""

import argparse
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time

from books_to_life.runtime.nemo_defaults import CHUNK_MS, RIGHT_MS, NEMO_MODELS


def server_processes(port, backend=None):
    processes = []
    parser = argparse.ArgumentParser(add_help=False, exit_on_error=False)
    parser.add_argument('--port', type=int, default=9097)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--backend', default='parakeet-nemo')
    for entry in Path('/proc').iterdir():
        if not entry.name.isdigit():
            continue
        try:
            if entry.stat().st_uid != os.getuid():
                continue
            args = entry.joinpath('cmdline').read_bytes().decode().strip('\0').split('\0')
            module_position = args.index('-m')
            if ['-m', 'books_to_life.cli.run_nemo_server'] != args[module_position:][:2]:
                continue
            options, _ = parser.parse_known_args(args[module_position + 2:])
            if (options.port == port and options.host in ('127.0.0.1', '0.0.0.0', 'localhost')
                    and (backend is None or options.backend == backend)):
                processes.append(int(entry.name))
        except (OSError, ValueError, UnicodeError, IndexError, argparse.ArgumentError):
            continue
    return processes


def port_in_use(port):
    with socket.socket() as connection:
        connection.settimeout(1)
        return connection.connect_ex(('127.0.0.1', port)) == 0


def manage(action, port, model, log, chunk_ms=CHUNK_MS, right_ms=RIGHT_MS, backend='parakeet-nemo'):
    if backend not in NEMO_MODELS:
        raise ValueError('Choose Parakeet NeMo or Nemotron.')
    if backend == 'nemotron' and chunk_ms not in (80, 160, 560, 1120):
        raise ValueError('Nemotron chunk size must be 80, 160, 560 or 1120 ms.')
    if backend == 'parakeet-nemo' and any(value<=0 or value%80 or value>1040 for value in (chunk_ms,right_ms)):
        raise ValueError('Chunk/right context must be multiples of 80 ms between 80 and 1040.')
    if not model.is_file():
        flag = '--nemotron-model' if backend == 'nemotron' else '--nemo-model'
        raise ValueError(f'NeMo model is missing at {model}. Configure {flag} in the panel launcher.')
    processes = server_processes(port)
    if port_in_use(port) and not processes:
        raise ValueError(f'Port {port} belongs to another process. Check the port before starting NeMo.')
    switching = action == 'start' and bool(processes) and not server_processes(port, backend)
    if action == 'restart' or switching:
        for pid in processes:
            os.kill(pid, signal.SIGTERM)
        deadline = time.monotonic() + 10
        while server_processes(port) and time.monotonic() < deadline:
            time.sleep(.1)
        for pid in server_processes(port):
            os.kill(pid, signal.SIGKILL)
        deadline = time.monotonic() + 5
        while port_in_use(port) and time.monotonic() < deadline:
            time.sleep(.1)
        processes = server_processes(port)
    if processes:
        return {'pid': processes[0], 'reused': True}
    if port_in_use(port):
        raise ValueError(f'Port {port} is still occupied. NeMo could not start.')
    log.parent.mkdir(parents=True, exist_ok=True)
    command = [sys.executable, '-u', '-m', 'books_to_life.cli.run_nemo_server',
               '--model-path', str(model), '--host', '127.0.0.1', '--port', str(port),
               '--chunk-ms', str(chunk_ms), '--right-ms', str(right_ms), '--boost', '1.0']
    command += ['--backend', backend]
    with log.open('ab', buffering=0) as output:
        environment = {**os.environ, 'TMPDIR': '/tmp', 'TEMP': '/tmp', 'TMP': '/tmp'}
        process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=output,
                                   stderr=subprocess.STDOUT, start_new_session=True, env=environment)
    return {'pid': process.pid, 'reused': False}


def main():
    import fcntl

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('start', 'restart'))
    parser.add_argument('--port', type=int, required=True)
    parser.add_argument('--model-path', type=Path, required=True)
    parser.add_argument('--log-file', type=Path, required=True)
    parser.add_argument('--chunk-ms', type=int, default=CHUNK_MS)
    parser.add_argument('--right-ms', type=int, default=RIGHT_MS)
    parser.add_argument('--backend', choices=NEMO_MODELS, default='parakeet-nemo')
    args = parser.parse_args()
    # Serialize launch requests across panel instances and browser tabs.
    lock_path = Path('/tmp') / f'reading-pod-nemo-{os.getuid()}-{args.port}.lock'
    with lock_path.open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        print(json.dumps(manage(args.action, args.port, args.model_path, args.log_file,args.chunk_ms,args.right_ms,args.backend)))


if __name__ == '__main__':
    main()
