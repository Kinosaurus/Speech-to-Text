"""Saved-file production client smoke, with physical audio input/output disabled."""
import json
from pathlib import Path
import runpy
import sys

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / 'output/reading-pod-first-pipeline'
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(APP))
import whisper_live.client

# Upstream allocates an unused microphone in its constructor, including for
# saved-file input. Never open it in this replay; ASR, tracker and transport are real.
real_audio = whisper_live.client.pyaudio.PyAudio
class SilentInput:
    def stop_stream(self): pass
    def close(self): pass
class FileAudio:
    def __init__(self): self.audio = real_audio()
    def __getattr__(self, name): return getattr(self.audio, name)
    def open(self, **options):
        if options.get('input') and not options.get('output'):
            return SilentInput()
        raise AssertionError('Saved-file smoke must never open physical audio')
whisper_live.client.pyaudio.PyAudio = FileAudio
sys.argv = ['run_client', '--model', 'nemotron', '--server', '127.0.0.1', '--port', '9097',
            '--files', str(APP / 'output/product-comparison-20261119/synthetic/moon-normal.wav'),
            '--checkpoints', str(APP / 'output/novel-cue-annotation-20261119-results/pod-moon-manifest.json'),
            '--matching_mode', 'split', '--live-transcript', '--book_context_lookahead', '0',
            '--audio_chunk', '1280', '--mute_audio_playback', '--mute_effects',
            '--transcript_file', str(OUT / 'moon.srt'), '--connection_timeout', '20']
runpy.run_module('books_to_life.cli.run_client', run_name='__main__')
