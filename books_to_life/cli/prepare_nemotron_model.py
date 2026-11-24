"""Download and verify the pinned Nemotron checkpoint used by the local panel."""
import argparse
import hashlib
import json
from pathlib import Path

REPO = 'nvidia/nemotron-speech-streaming-en-0.6b'
REVISION = 'ebe59e5a817142986528bbbee5dba8db7b38ed50'
FILENAME = 'nemotron-speech-streaming-en-0.6b.nemo'
SHA256 = '283638054c44f6794e74fe9af9048d78a6d9d6c058c12131856c7859a62ac9cd'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache', type=Path, default=Path('model-cache/nemotron-nemo'))
    args = parser.parse_args()
    from huggingface_hub import hf_hub_download
    path = Path(hf_hub_download(REPO, FILENAME, revision=REVISION, local_dir=args.cache))
    with path.open('rb') as stream:
        actual = hashlib.file_digest(stream, 'sha256').hexdigest()
    if actual != SHA256:
        raise ValueError('Nemotron checkpoint failed SHA256 verification.')
    (args.cache / 'source.json').write_text(json.dumps(dict(repo=REPO, revision=REVISION,
                                                         file=str(path), sha256=actual), indent=2), encoding='utf-8')
    print('Prepared:', path, flush=True)


if __name__ == '__main__':
    main()
