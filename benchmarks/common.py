import json
import subprocess
import threading
import time
import wave
from pathlib import Path

import numpy as np

from alignment_matcher import AlignmentMatcher
from book_context import BookContext
from benchmarks.metrics import edit_alignment, latest_text


def audio(path):
    with wave.open(str(path), 'rb') as source:
        if (source.getframerate(), source.getnchannels(), source.getsampwidth()) != (16000, 1, 2):
            raise ValueError('Use a 16 kHz mono 16-bit PCM WAV for this benchmark.')
        return np.frombuffer(source.readframes(source.getnframes()), dtype='<i2').astype(np.float32) / 32768


class Recorder:
    def __init__(self, manifest, hints=False):
        self.matcher = AlignmentMatcher(manifest)
        self.context = BookContext(self.matcher) if hints else None
        self.start = None
        self.events = []
        self.invalid_updates = []
        self.lock = threading.RLock()
        self.last_text = ''
        self.previous_signature = None
        self.wall_origin = None

    def begin(self):
        self.start = time.perf_counter()

    def receive(self, text, segments=None, audio_end=None, final=False):
        if self.start is None:
            return
        with self.lock:
            elapsed = time.perf_counter() - self.start
            # Backend output revisions are snapshots, not transcript additions.
            signature = json.dumps(segments, sort_keys=True) if segments else (text, final)
            if signature == self.previous_signature:
                return
            self.previous_signature = signature
            self.last_text = text
            try:
                update = self.matcher.process(text, segments=segments)
            except ValueError as error:
                # Keep malformed ASR output visible. Never advance or repair its timings.
                if str(error) not in ('Transcript segment times must be finite and ordered.',
                                      'Transcript segments require start, end and text.'):
                    raise
                self.invalid_updates.append({'wall_seconds': elapsed, 'audio_end_seconds': audio_end,
                                             'text': text, 'segments': segments, 'error': str(error)})
                return
            event = {'wall_seconds': elapsed, 'audio_end_seconds': audio_end,
                     'text': text, 'final': final, 'checkpoint_id': update.checkpoint_id,
                     'triggered': update.triggered, 'skipped': list(update.skipped_checkpoint_ids),
                     'confirmed_position': update.tracked_word_position, 'score': update.score,
                     'duplicate': update.duplicate, 'ambiguous': update.ambiguous,
                     'recovering': update.recovering}
            self.events.append(event)
            if self.context:
                return self.context.refresh()

    def summary(self, reference):
        scoring, _ = edit_alignment(reference, self.last_text)
        return {'text': self.last_text, 'reference_score': scoring,
                'wall_seconds': time.perf_counter() - self.start,
                'invalid_update_count': len(self.invalid_updates), 'invalid_updates': self.invalid_updates,
                'triggered_ids': sorted(self.matcher.triggered_checkpoint_ids),
                'skipped_ids': sorted(self.matcher.skipped_checkpoint_ids),
                'event_count': len(self.events), 'events': self.events}


def paced_chunks(pcm, chunk_samples=1024, tail_seconds=1.5):
    """Schedule samples by absolute deadlines; inference cannot accelerate the recording."""
    stream = np.concatenate((pcm, np.zeros(round(tail_seconds * 16000), dtype=np.float32)))
    origin = time.perf_counter()
    for offset in range(0, len(stream), chunk_samples):
        end = min(offset + chunk_samples, len(stream))
        deadline = origin + end / 16000
        remaining = deadline - time.perf_counter()
        if remaining > 0:
            time.sleep(remaining)
        yield stream[offset:end], end / 16000, max(0, time.perf_counter() - deadline)


def gpu_memory_mib():
    try:
        result = subprocess.run(['nvidia-smi', '--query-gpu=memory.used', '--format=csv,noheader,nounits'],
                                capture_output=True, text=True, timeout=5)
        return int(result.stdout.splitlines()[0]) if result.returncode == 0 else None
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return None


class MemorySampler:
    """Sample process RSS only; device VRAM is reported separately as a snapshot."""
    def __init__(self):
        self.peak = 0
        self.stop = threading.Event()
        self.thread = None

    def __enter__(self):
        try:
            import psutil
        except ImportError:
            return self
        process = psutil.Process()
        def sample():
            while not self.stop.is_set():
                self.peak = max(self.peak, process.memory_info().rss)
                self.stop.wait(0.05)
        self.thread = threading.Thread(target=sample, daemon=True)
        self.thread.start()
        return self

    def __exit__(self, *_):
        self.stop.set()
        if self.thread:
            self.thread.join()
