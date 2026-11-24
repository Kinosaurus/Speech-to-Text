"""Download the pinned public checkpoint with verified ranged requests."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
from pathlib import Path
import time
import requests

REVISION = 'ebe59e5a817142986528bbbee5dba8db7b38ed50'
SHA256 = '283638054c44f6794e74fe9af9048d78a6d9d6c058c12131856c7859a62ac9cd'
SIZE = 2473041920
URL = f'https://huggingface.co/nvidia/nemotron-speech-streaming-en-0.6b/resolve/{REVISION}/nemotron-speech-streaming-en-0.6b.nemo'
target = Path('model-cache/nemotron-nemo/nemotron-speech-streaming-en-0.6b.nemo')
target.parent.mkdir(parents=True, exist_ok=True)
chunk = 8*1024*1024


def fetch(start):
    end = min(start+chunk, SIZE)-1
    for attempt in range(4):
        try:
            response = requests.get(URL, params={'range_start': start},
                                    headers={'Range': f'bytes={start}-{end}'}, timeout=(20,60))
            response.raise_for_status()
            assert response.status_code == 206
            assert response.headers['Content-Range'] == f'bytes {start}-{end}/{SIZE}'
            assert len(response.content) == end-start+1
            return response.content
        except Exception:
            if attempt == 3:
                raise
            time.sleep(1)


if __name__ == '__main__':
    partial = target.with_suffix('.download')
    if target.exists():
        raise FileExistsError(target)
    count = 0
    sha = hashlib.sha256()
    with partial.open('xb') as output, ThreadPoolExecutor(max_workers=4) as pool:
        for data in pool.map(fetch, range(0, SIZE, chunk)):
            output.write(data)
            sha.update(data)
            count += len(data)
            if count//chunk % 16 == 0:
                print(f'{count}/{SIZE} bytes', flush=True)
    assert sha.hexdigest() == SHA256, sha.hexdigest()
    partial.rename(target)
    print('VERIFIED', target, SHA256, flush=True)
