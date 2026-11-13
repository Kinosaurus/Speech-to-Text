"""Build the private transfer ZIP from this PC's recorded timing test."""
import argparse
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path, help='Checkout containing the original output/ folders')
    args = parser.parse_args()
    source = args.source.resolve()
    output = source / 'output'
    paired = output / 'pod-paired-timing'
    browser_runs = output / 'keen-tea-hold-test/stove-graph/branch-pod-timing'
    cases = json.loads((paired / 'cases.json').read_text(encoding='utf-8'))
    destination = output / 'pod-pc-transfer.zip'

    with ZipFile(destination, 'w', compression=ZIP_DEFLATED) as bundle:
        for case in cases:
            name = case['name']
            audio = Path(case['audio'])
            bundle.write(audio, f'audio/{name}.wav')
            for filename in (f'{name}.events.jsonl', f'{name}.log', f'{name}.srt'):
                bundle.write(paired / filename, f'results/parakeet/{filename}')
            bundle.write(browser_runs / f'{name}.json', f'results/keen/{name}.json')
        bundle.writestr('cases.json', json.dumps([
            dict(name=c['name'], book=c['book'], audio=f'audio/{c["name"]}.wav',
                 expected=c['expected'], samples=c['samples']) for c in cases
        ], indent=2))
        bundle.write(paired / 'summary.json', 'results/paired-timing.json')
        for name in ('summary.json', 'by-recording.csv'):
            bundle.write(output / 'keen-corpus-21750e9' / name, f'results/keen-corpus/{name}')
        scripts = Path(__file__).resolve().parent
        bundle.write(scripts / 'replay_pod_parakeet.py', 'parakeet.py')
        bundle.writestr('README.md', r"""# Books to Life private test bundle

The eight WAVs are in `audio/`. See the [PC handoff checklist](https://github.com/Kinosaurus/Speech-to-Text/blob/codex/pod-pc-handoff/docs/POD_PC_HANDOFF.md).
The original cue counts and software timing are in `results/paired-timing.json`.

After starting Parakeet NeMo on port 9097, run this from the main checkout in
PowerShell. Replace the paths with your extracted bundle and Keen checkout.

```powershell
.\.venv\Scripts\python.exe 'D:/PodData/parakeet.py' . '../Speech-to-Text-Keen'
```

The script streams the WAVs in real time and writes matcher events and SRTs
in a new directory beside the script. Use the recorded audio selector in the
Keen app for the same WAVs. Keep this bundle private.
""")
        bundle.write(output / 'benchmark-75ce880-20261113/probe.py', 'probe.py')
        for name, mapmap in (
            ('MapMap-Reading-Pod', source / 'tmp/MapMap-Reading-Pod'),
            ('Reading Pod MapMap', scripts.parent / 'Reading Pod MapMap'),
        ):
            for file in sorted(mapmap.rglob('*')):
                if file.is_file():
                    bundle.write(file, name + '/' + file.relative_to(mapmap).as_posix())
    with ZipFile(destination) as bundle:
        if error := bundle.testzip():
            raise RuntimeError(f'ZIP verification failed for {error}')
        print(f'{destination} ({len(bundle.namelist())} files)')


if __name__ == '__main__':
    main()
