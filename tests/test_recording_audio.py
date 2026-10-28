from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import wave

import audio_runtime
from book_context_client import BookTranscriptionClient

ROOT = Path(__file__).resolve().parents[1]


def wav(path, rate=16000):
    with wave.open(str(path), 'wb') as out:
        out.setparams((1,2,rate,0,'NONE','not compressed'))
        out.writeframes(b'\0\0' * rate)


class RecordingAudioTests(unittest.TestCase):
    def test_ready_pcm_reuses_original_audio_bytes(self):
        with TemporaryDirectory(dir=ROOT) as directory:
            source=Path(directory)/'input.wav';wav(source)
            before=source.read_bytes()
            self.assertEqual(audio_runtime.prepare_stream_audio(source),str(source.resolve()))
            self.assertEqual(source.read_bytes(),before)
            self.assertEqual(list(Path(directory).iterdir()),[source])

    def test_conversion_preserves_duration_and_uses_managed_cache(self):
        with TemporaryDirectory(dir=ROOT) as directory:
            source=Path(directory)/'input.wav';wav(source,8000)
            with patch.object(audio_runtime,'__file__',str(Path(directory)/'audio_runtime.py')):
                target=Path(audio_runtime.prepare_stream_audio(source))
                self.assertEqual(target.parent,Path(directory)/'recordings/cache')
                with wave.open(str(target)) as data:
                    self.assertEqual((data.getframerate(),data.getnchannels(),data.getsampwidth()),(16000,1,2))
                    self.assertEqual(data.getnframes(),16000)
                self.assertEqual(audio_runtime.prepare_stream_audio(source),str(target))
            self.assertFalse((Path(directory)/'input_resampled.wav').exists())

    def test_managed_client_keeps_the_existing_paced_player(self):
        with TemporaryDirectory(dir=ROOT) as directory:
            source=Path(directory)/'input.wav';wav(source)
            client=object.__new__(BookTranscriptionClient)
            client.clients=[SimpleNamespace(recording=True)]
            client.play_file=Mock()
            client(str(source))
            client.play_file.assert_called_once_with(str(source.resolve()))


if __name__=='__main__':unittest.main()
