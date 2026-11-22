"""Freeze inputs and adapt only the ASR transport of the old real-output runner."""
import hashlib
import json
from pathlib import Path
import shutil

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
OLD = ROOT / 'output/reading-pod-first-pipeline'

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    source = OLD / 'benchmarks/product_comparison/pod_replay.py'
    text = source.read_text()
    text = text.replace('from benchmarks.asr_only_worker import nemo', 'from transport import nemo')
    text = text.replace('if args.latency_profile:', 'if True:')
    text = text.replace("'Resident Parakeet NeMo; full excerpt hints; managed default boost'", "f'Nemotron {args.chunk_ms} ms; same fixed full-excerpt hints; boost 1.0'")
    text = text.replace("    parser.add_argument('--calibrate-output',action='store_true')", "    parser.add_argument('--calibrate-output',action='store_true')\n    parser.add_argument('--chunk-ms',type=int,choices=(160,320),required=True)")
    (OUT / 'replay.py').write_text(text, encoding='utf-8')
    worker = (OLD / 'benchmarks/asr_only_worker.py').read_text()
    transport = worker[worker.index('def nemo('):worker.index('\ndef native(')]
    transport = transport.replace("'model': 'parakeet-nemo'", "'model': 'nemotron', 'chunk_ms': args.chunk_ms")
    insert = '''        import hashlib
        expected_hash = hashlib.sha256((hotwords or '').encode()).hexdigest()
        if (reply.get('backend') != 'nemotron' or reply.get('chunk_ms') != args.chunk_ms
                or reply.get('boost') != 1.0 or reply.get('applied_hotwords_sha256') != expected_hash):
            raise RuntimeError('Nemotron did not acknowledge the frozen configuration')
        configuration = dict(reply)
'''
    transport = transport.replace('        boost_ack = {}', insert + '        boost_ack = {}')
    transport = transport.replace("'backend': 'NeMo WebSocket'", "'backend': 'Nemotron WebSocket', 'acknowledged_configuration': configuration")
    transport = transport.replace("else 'legacy managed NeMo server; buffering not acknowledged'", "else f'Nemotron native {args.chunk_ms} ms; context {configuration[\"att_context\"]}'")
    (OUT / 'transport.py').write_text('import json\nimport threading\nimport time\nimport uuid\n\n' + transport, encoding='utf-8')
    prior = json.loads((OLD / 'output/latency-investigation-20261119/provenance.json').read_text())
    frozen = OUT / 'frozen/books_to_life'
    shutil.copytree(OLD / 'books_to_life', frozen, ignore=shutil.ignore_patterns('__pycache__'), dirs_exist_ok=True)
    original_tracker = ROOT / 'output/pod-publication-check/books_to_life/matching/timely_matcher.py'
    assert digest(original_tracker) == prior['matcher_hashes']['books_to_life\\matching\\timely_matcher.py']
    shutil.copy2(original_tracker, frozen / 'matching/timely_matcher.py')
    hashes = {name:digest(OUT / 'frozen' / name) for name in prior['matcher_hashes']}
    assert hashes == prior['matcher_hashes'], 'Historical tracker implementation changed'
    files = [source, OLD / 'books_to_life/runtime/sound_player.py',
             OLD / 'benchmarks/product_comparison/score.py',
             OLD / 'output/product-comparison-20261119/readmio-pod-manifest.json',
             OLD / 'output/novel-cue-annotation-20261119-results/pod-moon-manifest.json']
    for name in ('moon-normal', 'readmio-lion-normal'):
        files += [OLD / f'output/product-comparison-20261119/synthetic/{name}{suffix}' for suffix in ('.wav', '.marks.json')]
    for manifest in [p for p in files if p.name.endswith('manifest.json')]:
        book = json.loads(manifest.read_text())
        for cp in book['checkpoints']:
            sound = Path(cp['effect']['sound'])
            files.append(sound if sound.is_absolute() else manifest.parent / sound)
    files += list(frozen.rglob('*.py'))
    files += [OUT / name for name in ('server.py', 'replay.py', 'transport.py')]
    freeze = dict(status='frozen_before_replays', matcher_hashes=hashes,
                  tracker_source=str(original_tracker),
                  settings=dict(threshold=82, stability=2, coverage=.8, boost=1.0, packet_samples=1280),
                  hints='identical full manifest text, fixed before each replay',
                  repetitions=2, same_subset=dict(moon=['opening','cat','mouse'], lion=['readmio_1','readmio_2','readmio_3','readmio_4']),
                  metric='Captured digital sound onset minus saved synthetic cue-word ending',
                  files={str(p):digest(p) for p in files})
    (OUT / 'provenance.json').write_text(json.dumps(freeze, indent=2), encoding='utf-8')
    print('Frozen exact old tracker, inputs, cue times, effects manifests and new transport')

if __name__ == '__main__':
    main()
