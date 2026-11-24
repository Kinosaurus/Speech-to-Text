"""Two counterbalanced 1x replays per story and Nemotron setting."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
OLD = ROOT / 'output/reading-pod-first-pipeline'
os.environ['PYTHONPATH'] = os.pathsep.join([str(OUT / 'frozen'), str(OLD)])
sys.path[:0] = [str(OUT / 'frozen'), str(OLD)]
from benchmarks.product_comparison.score import score_pod


def main():
    os.chdir(OLD)
    root = OLD / 'output/product-comparison-20261119'
    cases = [
        ('moon', OLD / 'output/novel-cue-annotation-20261119-results/pod-moon-manifest.json', root / 'synthetic/moon-normal'),
        ('lion', root / 'readmio-pod-manifest.json', root / 'synthetic/readmio-lion-normal')]
    summaries = []
    for repeat in range(2):
        for index, (case, manifest, source) in enumerate(cases):
            for ms in ((160,320) if (repeat + index) % 2 == 0 else (320,160)):
                trial = OUT / f'{case}-nemotron-{ms}-{repeat+1:02d}'
                completed = trial.exists() and (trial / 'result.json').exists() and json.loads((trial / 'result.json').read_text())['status'] == 'ok'
                if trial.exists() and not completed:
                    raise RuntimeError('Preserve unsuccessful attempt: ' + str(trial))
                print('START', trial.name, flush=True)
                command = [sys.executable, str(OUT / 'replay.py'), '--manifest', str(manifest),
                           '--audio', str(source.with_suffix('.wav')), '--output', str(trial),
                           '--capture-tool', str(root / 'ProcessAudio-v3.exe'),
                           '--nemo-url', 'ws://127.0.0.1:9100', '--chunk-ms', str(ms),
                           '--packet-samples', '1280', '--calibrate-output']
                if case == 'lion':
                    command += ['--reference-text', str(OLD / 'benchmarks/product_comparison/readmio_lion_excerpt.txt')]
                if not completed:
                    with (OUT / (trial.name + '.log')).open('w', encoding='utf-8') as log:
                        subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, check=True, cwd=OLD, env=os.environ)
                score = score_pod(root, trial, source, manifest if case == 'moon' else None)
                row = dict(case=case, chunk_ms=ms, repeat=repeat+1, trial=str(trial),
                           hits=score['checkpoints_hit'], expected=score['expected_checkpoints'],
                           median_seconds=score['median_effect_delay_seconds'])
                summaries.append(row)
                (OUT / 'summary.json').write_text(json.dumps(summaries, indent=2), encoding='utf-8')
                print('RESULT', json.dumps(row), flush=True)
    print('All eight real-output replays complete', flush=True)


if __name__ == '__main__':
    main()
