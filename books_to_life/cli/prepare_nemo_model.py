"""Download the pinned original Parakeet checkpoint for the NeMo GPU adapter."""
import argparse
import json
from pathlib import Path

REPO = 'nvidia/parakeet-unified-en-0.6b'
REVISION = 'fe53cd885760c96b6a5f51a0bfd362cb4584a98b'
FILENAME = 'parakeet-unified-en-0.6b.nemo'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache', type=Path, default=Path('model-cache/parakeet-nemo'))
    args = parser.parse_args()
    from huggingface_hub import hf_hub_download
    print('Original Parakeet Unified checkpoint: about 2.47 GB.', flush=True)
    path = hf_hub_download(REPO, FILENAME, revision=REVISION, local_dir=args.cache)
    (args.cache / 'source.json').write_text(json.dumps(
        {'repo': REPO, 'revision': REVISION, 'file': str(path)}, indent=2), encoding='utf-8')
    print('Prepared:', path, flush=True)


if __name__ == '__main__':
    main()
