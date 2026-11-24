import json
from pathlib import Path
import subprocess
import sys
import time

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]


def run(command):
    result = subprocess.run(command, cwd=ROOT)
    if result.returncode:
        raise RuntimeError(f'Benchmark stage exited {result.returncode}')


def main():
    dataset = json.loads((OUT / 'dataset.json').read_text(encoding='utf-8'))
    print('Waiting for the three GPU profiles to finish before CPU timing starts.', flush=True)
    deadline = time.monotonic() + 7200
    while time.monotonic() < deadline:
        files = [OUT / f'{profile}--{case["id"]}.json' for profile in dataset['profiles']
                 if profile.startswith(('parakeet-', 'nemotron-')) for case in dataset['cases']]
        if all(path.is_file() for path in files):
            assert all(json.loads(path.read_text(encoding='utf-8'))['status'] == 'ok' for path in files)
            break
        time.sleep(10)
    else:
        raise TimeoutError('GPU replay did not complete within the bounded wait')
    print('START independent acoustic timing estimates', flush=True)
    run([sys.executable, '-u', str(OUT / 'make_timing.py')])
    for profile in ('whisper-tiny-cpu', 'moonshine-cpu'):
        print('START sequential CPU stage', profile, flush=True)
        run([sys.executable, '-u', str(OUT / 'run_cpu.py'), '--profile', profile])
    print('START tracker-free Keen browser stage', flush=True)
    run([sys.executable, '-u', str(OUT / 'run_keen.py')])
    run([sys.executable, '-u', str(OUT / 'summarize.py')])


if __name__ == '__main__':
    main()
