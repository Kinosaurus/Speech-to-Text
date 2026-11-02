"""Exercise the real NeMo buffer/tensor decoder budget in the WSL environment."""
import importlib.util
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import numpy as np

from books_to_life.runtime.nemo_parakeet import NemoParakeetSession


@unittest.skipUnless(importlib.util.find_spec('nemo') is not None,
                     'Requires the isolated WSL NeMo environment.')
class NemoEndDecoderTests(unittest.TestCase):
    def test_padding_can_supply_context_but_cannot_add_decoded_frames(self):
        import torch
        from nemo.collections.asr.parts.utils.streaming_utils import ContextSize, StreamingBatchedAudioBuffer

        class Encoder:
            device = 'cpu'
            tokenizer = SimpleNamespace(ids_to_text=lambda ids: 'recognized')

            def __call__(self, input_signal, input_signal_length):
                frames = (int(input_signal_length[0])+1279)//1280
                return torch.zeros(1, 1, frames), torch.tensor([frames])

        for valid_samples, expected in ((0, 0), (1280, 1), (1281, 2), (8960, 7)):
            with self.subTest(valid_samples=valid_samples):
                session = NemoParakeetSession.__new__(NemoParakeetSession)
                session.torch = torch
                session.model = Encoder()
                session.context = ContextSize(left=89600, chunk=8960, right=8960)
                session.buffer = StreamingBatchedAudioBuffer(1, session.context, torch.float32, 'cpu')
                session.computer = Mock(return_value=(object(), None))
                session.state = session.hyps = None
                session.text = ''
                session.bias_ids = torch.tensor([-1])
                hyp = SimpleNamespace(y_sequence=torch.tensor([1]))
                with patch('nemo.collections.asr.parts.utils.rnnt_utils.batched_hyps_to_hypotheses', return_value=[hyp]):
                    session._decode(np.zeros(17920, dtype=np.float32), decode_samples=valid_samples)
                self.assertEqual(session.buffer.samples.shape[1], 17920)
                if expected:
                    self.assertEqual(int(session.computer.call_args.kwargs['out_len'][0]), expected)
                    self.assertEqual(session.text, 'recognized')
                else:
                    session.computer.assert_not_called()


if __name__ == '__main__':
    unittest.main()
