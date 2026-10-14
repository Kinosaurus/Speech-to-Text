"""Fetch bounded, pinned inference assets; never build NeMo or a Docker image."""
import argparse
import hashlib
import json
import shutil
import sys
import tarfile
import urllib.request
import zipfile
from pathlib import Path

ASSETS = [
    ('runtime.tar.gz', 18036555, '9d5bd89f720d7979323e73f5220fe50fad5e38a7b0c2525225d453bd09adf2b0',
     'https://github.com/handy-computer/transcribe.cpp/releases/download/v0.4.0/transcribe-native-0.4.0-windows-x86_64-cpu-vulkan.tar.gz'),
    ('api.whl', 47190, None,
     'https://github.com/handy-computer/transcribe.cpp/releases/download/v0.4.0/transcribe_cpp-0.4.0-py3-none-any.whl'),
    ('parakeet-unified-en-0.6b-F16.gguf', 1239114240, '4a284b229bff9dc66aa00666fdcc2419c0f82a5adb5a36f7a48a4e0713c35492',
     'https://huggingface.co/handy-computer/parakeet-unified-en-0.6b-gguf/resolve/d5249700b2382bf5c5024c2421d101b8db54a629/parakeet-unified-en-0.6b-F16.gguf'),
    ('moonshine-streaming-medium-F16.gguf', 533781408, 'cf2ab2c366df44e8885e1c127c23275dc9a0aa0d10557c2fec325506058b9de8',
     'https://huggingface.co/handy-computer/moonshine-streaming-medium-gguf/resolve/0f99e956a9e63d591ddd7f2a20dfead255e96c68/moonshine-streaming-medium-F16.gguf'),
]


def sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def prepare(cache):
    cache.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(cache).free < 8 * 1024**3:
        raise RuntimeError('Need at least 8 GiB free before preparing this bounded benchmark.')
    for name, size, digest, url in ASSETS:
        target = cache / name
        if target.exists() and target.stat().st_size == size and (not digest or sha256(target) == digest):
            print('Cached:', name, flush=True)
            continue
        print(f'Downloading {name}: {size / 1e6:.1f} MB', flush=True)
        request = urllib.request.Request(url, headers={'User-Agent': 'Books-to-Life-ASR-benchmark'})
        partial = target.with_suffix(target.suffix + '.partial')
        received = 0
        with urllib.request.urlopen(request, timeout=60) as source, partial.open('wb') as output:
            while block := source.read(1024 * 1024):
                received += len(block)
                if received > size:
                    raise RuntimeError(f'{name} exceeded its declared download budget.')
                output.write(block)
        if received != size or (digest and sha256(partial) != digest):
            raise RuntimeError(f'Integrity check failed for {name}; no model was loaded.')
        partial.replace(target)
    with tarfile.open(cache / 'runtime.tar.gz') as archive:
        archive.extractall(cache, filter='data')
    with zipfile.ZipFile(cache / 'api.whl') as archive:
        archive.extractall(cache / 'api')
    (cache / 'sources.json').write_text(json.dumps([
        {'name': name, 'bytes': size, 'sha256': digest, 'url': url}
        for name, size, digest, url in ASSETS
    ], indent=2), encoding='utf-8')
    print('Prepared. Whisper uses the existing container and model volume.', flush=True)


def prepare_official_moonshine(cache):
    sys.path.insert(0, str(cache / 'moonshine-python'))
    from moonshine_voice import ModelArch
    from moonshine_voice.download import find_model_info, _primary_stt_group, download_model_from_info
    info = find_model_info('en', ModelArch.MEDIUM_STREAMING)
    group = _primary_stt_group(info)
    if sum(item['size'] for item in group['files']) > 350_000_000:
        raise RuntimeError('Official Moonshine assets exceed the declared 350 MB budget.')
    path, _ = download_model_from_info(info, cache_root=cache / 'moonshine-model',
                                       include_word_timestamps=False)
    (cache / 'moonshine-model-path.txt').write_text(str(path), encoding='utf-8')
    (cache / 'moonshine-sources.json').write_text(json.dumps(group, indent=2), encoding='utf-8')
    print('Official Moonshine prepared:', path, flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache', type=Path, default=Path('model-cache/asr-benchmark'))
    parser.add_argument('--official-moonshine', action='store_true', help='Also prepare the isolated official runtime assets.')
    args = parser.parse_args()
    prepare(args.cache.resolve())
    if args.official_moonshine:
        prepare_official_moonshine(args.cache.resolve())
