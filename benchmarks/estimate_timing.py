"""Estimate missing checkpoint endpoint times; never treat them as human annotation."""
import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from benchmarks.common import audio


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--audio', type=Path, default=Path('recordings/little_mermaid.wav'))
    parser.add_argument('--cache', type=Path, default=Path('model-cache/asr-benchmark'))
    parser.add_argument('--output', type=Path, default=Path('output/benchmarks/little-mermaid/timing-reference-parakeet.json'))
    args = parser.parse_args()
    cache = args.cache.resolve()
    native = cache / 'transcribe-native-windows-x86_64-cpu-vulkan'
    os.environ['TRANSCRIBE_LIBRARY'] = str(native / 'transcribe.dll')
    dll_directory = os.add_dll_directory(str(native))
    sys.path.insert(0, str(cache / 'api'))
    import transcribe_cpp
    device = next(d for d in transcribe_cpp.backends() if d.kind == 'vulkan' and 'RTX 4060' in d.description)
    with transcribe_cpp.Model(cache / 'parakeet-unified-en-0.6b-F16.gguf', device=device) as model:
        with model.session(n_threads=2) as session:
            result = session.run(audio(args.audio), language='en', timestamps='word')
            report = {'source': 'Parakeet Unified F16 offline, no hints; ASR estimated, not manually verified',
                      'audio': str(args.audio.resolve()), 'text': result.text,
                      'audio_sha256': hashlib.sha256(args.audio.read_bytes()).hexdigest(),
                      'words': [{'word': word.text, 'start': word.t0_ms / 1000, 'end': word.t1_ms / 1000}
                                for word in result.words]}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print('Saved provisional timing reference:', args.output, flush=True)


if __name__ == '__main__':
    main()
