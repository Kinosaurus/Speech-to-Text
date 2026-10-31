import contextlib
import io
import os
import sys
from types import ModuleType
import unittest
from unittest.mock import Mock, patch

from books_to_life.cli import prepare_models


class ModelPreparationTests(unittest.TestCase):
    def run_preparation(self, arguments, cuda):
        torch = Mock()
        torch.cuda.is_available.return_value = cuda
        torch.cuda.get_device_capability.return_value = (8, 7)
        ct2 = Mock()
        ct2.get_cuda_device_count.return_value = int(cuda)
        ct2.get_supported_compute_types.return_value = {'int8', 'float16', 'float32'}
        transcriber = ModuleType('whisper_live.transcriber.transcriber_faster_whisper')
        transcriber.WhisperModel = Mock()
        vad = ModuleType('whisper_live.vad')
        vad.VoiceActivityDetector = Mock()
        modules = {'torch': torch, 'ctranslate2': ct2,
                   'whisper_live.transcriber.transcriber_faster_whisper': transcriber,
                   'whisper_live.vad': vad}
        with patch.dict(os.environ), patch.dict(sys.modules, modules), patch.object(sys, 'argv', ['books_to_life/cli/prepare_models.py', *arguments]), \
                contextlib.redirect_stdout(io.StringIO()):
            prepare_models.main()
        vad.VoiceActivityDetector.assert_called_once()
        return transcriber.WhisperModel

    def test_medium_model_preparation_uses_gpu_instead_of_forcing_cpu(self):
        model = self.run_preparation(['--model', 'medium.en', '--device', 'cuda'], cuda=True)
        model.assert_called_once_with('medium.en', device='cuda', compute_type='float16', cpu_threads=2)

    def test_existing_pi_model_preparation_keeps_cpu_int8_default(self):
        model = self.run_preparation([], cuda=False)
        model.assert_called_once_with('base.en', device='cpu', compute_type='int8', cpu_threads=2)


if __name__ == '__main__':
    unittest.main()
