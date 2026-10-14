"""Save ASR-estimated word times from a real-paced Parakeet stream.

These are recognition estimates, never human-verified checkpoint endpoints.
The stream has no book hints, whole-file pass, warmup or matcher/effect output.
"""
import argparse
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from benchmarks.common import audio, paced_chunks


def timed_words(tokens):
    """Group the runtime's space-delimited subword tokens without inventing times."""
    text = ''.join(token['text'] for token in tokens)
    spans = []
    offset = 0
    for token in tokens:
        spans.append((offset, offset + len(token['text']), token))
        offset += len(token['text'])
    result = []
    for match in re.finditer(r"[a-zA-Z0-9]+(?:['\u2019][a-zA-Z0-9]+)?", text):
        pieces = [token for start, end, token in spans
                  if start < match.end() and end > match.start()]
        if not pieces or any(token['start'] < 0 or token['end'] < token['start']
                             for token in pieces):
            raise ValueError('Native tokens have missing or reversed word times.')
        result.append({'word': match.group(), 'start': min(t['start'] for t in pieces),
                       'end': max(t['end'] for t in pieces)})
    return text, result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--audio', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--cache', type=Path, default=Path('model-cache/asr-benchmark'))
    args = parser.parse_args()
    cache = args.cache.resolve()
    native = cache / 'transcribe-native-windows-x86_64-cpu-vulkan'
    os.environ['TRANSCRIBE_LIBRARY'] = str(native / 'transcribe.dll')
    dll_directory = os.add_dll_directory(str(native))
    sys.path.insert(0, str(cache / 'api'))
    import transcribe_cpp

    pcm = audio(args.audio)
    device = next(d for d in transcribe_cpp.backends()
                  if d.kind == 'vulkan' and 'RTX 4060' in d.description)
    snapshots = []
    with transcribe_cpp.Model(cache / 'parakeet-unified-en-0.6b-F16.gguf', device=device) as model:
        with model.session(n_threads=2) as session:
            family = transcribe_cpp.ParakeetBufferedStreamOptions(left_ms=5600, chunk_ms=560, right_ms=560)
            with session.stream(language='en', timestamps='token', family=family) as stream:
                started = time.perf_counter()
                lags = []

                def capture(audio_end, final=False):
                    snapshot = stream.snapshot()
                    tokens = [{'text': t.text, 'start': t.t0_ms / 1000, 'end': t.t1_ms / 1000}
                              for t in snapshot.tokens]
                    token_text, words = timed_words(tokens)
                    # Ignore punctuation for this consistency check; retain both views.
                    normalize = lambda text: re.findall(r'[a-z0-9]+', text.lower())
                    if normalize(token_text) != normalize(snapshot.text):
                        raise ValueError('Token text differs from structured stream text.')
                    if any(w['end'] > len(pcm) / 16000 + 1.5 for w in words):
                        raise ValueError('Native timestamp is outside the replayed audio.')
                    snapshots.append({'audio_end_seconds': audio_end,
                                      'arrival_wall_seconds': time.perf_counter() - started,
                                      'text': snapshot.text, 'words': words,
                                      'tokens': tokens, 'final': final})

                for chunk, end, lag in paced_chunks(pcm):
                    update = stream.feed(chunk)
                    if update.result_changed:
                        capture(end)
                    lags.append(lag)
                stream.finalize()
                capture(len(pcm) / 16000, final=True)
                wall_seconds = time.perf_counter() - started
    report = {'source': 'Parakeet Unified F16, transcribe.cpp 0.4.0, real-paced streaming, no hints',
              'reference_timing_kind': 'ASR estimates; not listened to or manually verified',
              'audio': str(args.audio.resolve()),
              'audio_sha256': hashlib.sha256(args.audio.read_bytes()).hexdigest(),
              'audio_seconds': len(pcm) / 16000, 'whole_file_inference': False,
              'stream_repetitions': 1, 'warmup': 'none',
              'buffer_geometry_ms': {'left': 5600, 'chunk': 560, 'right': 560},
              'timestamp_note': 'Token/frame alignment is approximate; repeated or misheard phrases can be assigned incorrectly.',
              'wall_seconds': wall_seconds, 'max_feed_lateness_seconds': max(lags),
              'text': snapshots[-1]['text'], 'words': snapshots[-1]['words'],
              'snapshots': snapshots}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps({key: report[key] for key in ('audio_seconds', 'wall_seconds', 'text')}, indent=2), flush=True)
    print('Saved ASR-estimated streaming word times:', args.output, flush=True)


if __name__ == '__main__':
    main()
