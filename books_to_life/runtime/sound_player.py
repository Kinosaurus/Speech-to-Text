"""Preloaded WAV effects mixed on a separate PortAudio output thread."""
import atexit
import logging
import math
from pathlib import Path
import threading
import time
import wave

import numpy as np


RATE = 44100
CHUNK = 1024


def load_sound(path):
    """Convert uncompressed 16-bit mono/stereo WAV to output-rate stereo."""
    from scipy.signal import resample_poly

    with wave.open(str(path), 'rb') as audio:
        channels, width, rate, frames, compression, _ = audio.getparams()
        if width != 2 or channels not in (1, 2) or compression != 'NONE' or frames == 0:
            raise ValueError('Use a nonempty, uncompressed 16-bit mono or stereo WAV.')
        raw = audio.readframes(frames)
        if len(raw) != frames * channels * width:
            raise ValueError('WAV data is truncated.')
    samples = np.frombuffer(raw, dtype='<i2').reshape(-1, channels).astype(np.float32) / 32768
    if channels == 1:
        samples = np.repeat(samples, 2, axis=1)
    if rate != RATE:
        divisor = math.gcd(rate, RATE)
        samples = resample_poly(samples, RATE // divisor, rate // divisor, axis=0)
    return samples


class SoundPlayer:
    """One sound per checkpoint per session; concurrent effects can overlap.

    Paths are relative to sound_dir, or the checkpoint manifest's directory.
    Missing/invalid assets are reported and skipped without stopping reading.
    sound_delay is milliseconds. Ambience currently plays once, without looping.
    """

    def __init__(self, checkpoints, manifest_path, *, sound_dir=None, volume=0.5,
                 output_device=None):
        if not math.isfinite(volume) or not 0 <= volume <= 1:
            raise ValueError('Sound volume must be between 0 and 1.')
        self.volume = volume
        self.output_device = output_device
        self.error = None
        self.sounds = {}
        self._seen = set()
        self._pending = []
        self._condition = threading.Condition()
        self._closing = False
        self._stop = False
        self._thread = None
        root = Path(sound_dir).resolve() if sound_dir else Path(manifest_path).resolve().parent
        cache = {}
        for checkpoint in checkpoints:
            ident = str(checkpoint['id'])
            effect = checkpoint.get('effect') or {}
            name = effect.get('sound')
            if not name:
                continue
            try:
                delay = float(effect.get('sound_delay', 0)) / 1000
                if not math.isfinite(delay) or delay < 0:
                    raise ValueError('sound_delay must be finite, nonnegative milliseconds.')
                path = (root / name).resolve()
                if path not in cache:
                    cache[path] = load_sound(path)
                self.sounds[ident] = (cache[path], delay)
            except (OSError, ValueError, TypeError, wave.Error, EOFError) as error:
                logging.warning('[SOUND] %s skipped (%s): %s', ident, name, error)
        if self.sounds:
            self._thread = threading.Thread(target=self._run, name='story-sounds', daemon=True)
            self._thread.start()
            atexit.register(self.close)

    def handle_update(self, update):
        """Only emitted updates can schedule sound; pending/suppressed stay quiet."""
        if not update.triggered:
            return False
        ident = str(update.checkpoint_id)
        with self._condition:
            if self._closing or ident in self._seen or ident not in self.sounds:
                return False
            self._seen.add(ident)
            samples, delay = self.sounds[ident]
            self._pending.append((time.monotonic() + delay, samples, 0, ident))
            self._condition.notify_all()
        return True

    def close(self, *, drain=False):
        """Finish sounds on normal completion; cancel promptly on interruption."""
        with self._condition:
            self._closing = True
            self._stop = self._stop or not drain
            self._condition.notify_all()
        if self._thread is not None and self._thread is not threading.current_thread():
            try:
                self._thread.join()
            except KeyboardInterrupt:
                self.close()
                raise
        atexit.unregister(self.close)

    def _run(self):
        audio = stream = None
        try:
            import pyaudio

            audio = pyaudio.PyAudio()
            while True:
                with self._condition:
                    while not self._stop and not self._pending and not self._closing:
                        self._condition.wait()
                    if self._stop or (self._closing and not self._pending):
                        break
                    now = time.monotonic()
                    due = [voice for voice in self._pending if voice[0] <= now]
                    if not due:
                        self._condition.wait(min(voice[0] for voice in self._pending) - now)
                        continue
                    self._pending = [voice for voice in self._pending if voice[0] > now]
                if stream is None:
                    stream = audio.open(format=pyaudio.paInt16, channels=2, rate=RATE,
                                        output=True, output_device_index=self.output_device,
                                        frames_per_buffer=CHUNK)
                mixed = np.zeros((CHUNK, 2), dtype=np.float32)
                remaining = []
                used = 0
                for started, samples, position, ident in due:
                    if position == 0:
                        logging.info('[SOUND] Playing %s', ident)
                    part = samples[position:position + CHUNK]
                    mixed[:len(part)] += part * self.volume
                    used = max(used, len(part))
                    position += len(part)
                    if position < len(samples):
                        remaining.append((started, samples, position, ident))
                stream.write((np.clip(mixed[:used], -1, 1) * 32767).astype('<i2').tobytes())
                with self._condition:
                    self._pending.extend(remaining)
        except Exception as error:
            self.error = error
            logging.exception('[SOUND] Playback stopped; speech tracking continues.')
        finally:
            with self._condition:
                self._closing = True
                self._pending.clear()
            try:
                if stream is not None:
                    try:
                        stream.stop_stream()
                    finally:
                        stream.close()
            finally:
                if audio is not None:
                    audio.terminate()
