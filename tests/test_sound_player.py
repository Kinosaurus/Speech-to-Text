import contextlib
import io
import json
from pathlib import Path
import runpy
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import wave

import numpy as np

from books_to_life.runtime.sound_player import SoundPlayer, load_sound


def update(ident='first', triggered=True):
    return SimpleNamespace(checkpoint_id=ident, triggered=triggered)


class SoundPlayerTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.path = self.root / 'sound.wav'
        with wave.open(str(self.path), 'wb') as audio:
            audio.setparams((1, 2, 44100, 0, 'NONE', 'not compressed'))
            audio.writeframes(np.full(256, 8192, dtype='<i2').tobytes())
        self.checkpoints = [dict(id=ident, effect=dict(sound='sound.wav')) for ident in ('first', 'second')]

    def backend(self):
        backend = Mock(paInt16=8)
        audio = backend.PyAudio.return_value
        stream = audio.open.return_value
        return backend, audio, stream

    def test_real_pcm_decoding_and_resampling(self):
        samples = load_sound(self.path)
        self.assertEqual(samples.shape, (256, 2))
        np.testing.assert_allclose(samples, .25)
        with wave.open(str(self.path), 'wb') as audio:
            audio.setparams((1, 2, 16000, 0, 'NONE', 'not compressed'))
            audio.writeframes(np.zeros(16000, dtype='<i2').tobytes())
        self.assertEqual(load_sound(self.path).shape, (44100, 2))

    def test_portaudio_lifecycle_stays_on_caller_thread(self):
        backend, audio, stream = self.backend()
        caller = threading.get_ident()
        initialized, terminated = [], []

        def initialize_audio():
            initialized.append(threading.get_ident())
            return audio

        def terminate_audio():
            terminated.append(threading.get_ident())

        backend.PyAudio.side_effect = initialize_audio
        audio.terminate.side_effect = terminate_audio
        with patch.dict(sys.modules, pyaudio=backend):
            player = SoundPlayer(self.checkpoints, self.root / 'book.json')
            self.assertEqual(initialized, [caller])
            player.close()
            player.close()
        self.assertEqual(terminated, [caller])
        stream.write.assert_not_called()

    def test_audio_initialization_failure_disables_sounds(self):
        backend, audio, stream = self.backend()
        backend.PyAudio.side_effect = OSError('audio device unavailable')
        with patch.dict(sys.modules, pyaudio=backend), self.assertLogs(level='ERROR'):
            player = SoundPlayer(self.checkpoints, self.root / 'book.json')
        self.assertIsInstance(player.error, OSError)
        self.assertFalse(player.handle_update(update()))
        player.close()
        audio.terminate.assert_not_called()

    def test_emitted_checkpoints_overlap_without_duplicate_or_suppressed_playback(self):
        backend, audio, stream = self.backend()
        with patch.dict(sys.modules, pyaudio=backend):
            player = SoundPlayer(self.checkpoints, self.root / 'book.json', volume=1, output_device=7)
            self.addCleanup(player.close)
            with player._condition:
                self.assertFalse(player.handle_update(update(triggered=False)))
                self.assertTrue(player.handle_update(update()))
                self.assertFalse(player.handle_update(update()))
                self.assertTrue(player.handle_update(update('second')))
            player.close(drain=True)
        self.assertEqual(stream.write.call_count, 1)
        mixed = np.frombuffer(stream.write.call_args.args[0], dtype='<i2')
        np.testing.assert_allclose(mixed, 16383, atol=1)
        self.assertEqual(audio.open.call_args.kwargs['output_device_index'], 7)
        stream.close.assert_called_once()
        audio.terminate.assert_called_once()
        self.assertFalse(player.handle_update(update('second')))

    def test_delayed_sound_is_cancelled_without_opening_output(self):
        self.checkpoints[0]['effect']['sound_delay'] = 10000
        backend, audio, stream = self.backend()
        with patch.dict(sys.modules, pyaudio=backend):
            player = SoundPlayer(self.checkpoints[:1], self.root / 'book.json')
            self.assertTrue(player.handle_update(update()))
            player.close()
        audio.open.assert_not_called()

    def test_delay_is_in_milliseconds_and_does_not_play_before_due(self):
        self.checkpoints[0]['effect']['sound_delay'] = 1000
        backend, audio, stream = self.backend()
        with patch.dict(sys.modules, pyaudio=backend):
            player = SoundPlayer(self.checkpoints[:1], self.root / 'book.json')
            self.addCleanup(player.close)
            with player._condition, patch('books_to_life.runtime.sound_player.time.monotonic', return_value=50):
                player.handle_update(update())
                self.assertEqual(player._pending[0][0], 51)
                stream.write.assert_not_called()
            player.close()

    def test_playback_is_off_callback_thread_and_can_be_stopped(self):
        backend, audio, stream = self.backend()
        entered, release = threading.Event(), threading.Event()
        stream.write.side_effect = lambda _: (entered.set(), release.wait(2))
        with patch.dict(sys.modules, pyaudio=backend):
            player = SoundPlayer(self.checkpoints, self.root / 'book.json')
            try:
                self.assertTrue(player.handle_update(update()))
                self.assertTrue(entered.wait(2))
                self.assertTrue(player.handle_update(update('second')))
            finally:
                release.set()
                player.close()

    def test_asset_errors_do_not_prevent_other_sounds_loading(self):
        self.checkpoints[0]['effect']['sound'] = 'missing.wav'
        self.checkpoints.append(dict(id='bad_delay', effect=dict(sound='sound.wav', sound_delay=float('nan'))))
        with patch.object(SoundPlayer, '_run'), self.assertLogs(level='WARNING'):
            player = SoundPlayer(self.checkpoints, self.root / 'book.json')
            player.close()
        self.assertEqual(set(player.sounds), {'second'})

    def test_output_failure_is_reported_and_resources_close(self):
        backend, audio, stream = self.backend()
        stream.write.side_effect = OSError('speaker disconnected')
        with patch.dict(sys.modules, pyaudio=backend), self.assertLogs(level='ERROR') as logs:
            player = SoundPlayer(self.checkpoints, self.root / 'book.json')
            player.handle_update(update())
            player.close(drain=True)
        self.assertIn('speaker disconnected', '\n'.join(logs.output))
        stream.close.assert_called_once()
        audio.terminate.assert_called_once()

    def test_client_routes_real_matcher_event_to_sound_and_drains_on_completion(self):
        manifest = self.root / 'book.json'
        text = 'the small frog jumped into the pond'
        manifest.write_text(json.dumps(dict(book_id='sound-test', title='Sound test', stability=1,
            pages=[dict(page=1, text=text)], checkpoints=[dict(id='first', book_id='sound-test', checkpoint_position=1,
                checkpoint_text=text, effect=dict(sound='sound.wav'))])), encoding='utf-8')
        factory = Mock()
        def read_file(*args):
            callback = factory.call_args.kwargs['transcription_callback']
            for _ in range(2):
                callback(text, [dict(start=0, end=2, text=text, completed=True)])
        factory.return_value.side_effect = read_file
        argv = ['run_client', '--files', str(self.path), '--checkpoints', str(manifest),
                '--no_book_context', '--matching_mode', 'split']
        with patch.object(sys, 'argv', argv), patch('whisper_live.client.TranscriptionClient', factory), \
                patch('books_to_life.runtime.audio_runtime.wait_for_server'), \
                patch('books_to_life.runtime.sound_player.SoundPlayer') as player_type, \
                contextlib.redirect_stdout(io.StringIO()):
            runpy.run_module('books_to_life.cli.run_client', run_name='__main__')
        player = player_type.return_value
        player.handle_update.assert_called_once()
        self.assertTrue(player.handle_update.call_args.args[0].triggered)
        self.assertEqual(player.handle_update.call_args.args[0].checkpoint_id, 'first')
        player.close.assert_called_once_with(drain=True)


if __name__ == '__main__':
    unittest.main()
