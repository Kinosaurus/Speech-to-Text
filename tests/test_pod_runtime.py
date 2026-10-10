import os
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from asr_runtime import configure_device, describe_device
from audio_runtime import configure_microphone, select_input_device, wait_for_server


def fake_audio():
    devices = [
        {'index': 0, 'name': 'Speakers', 'maxInputChannels': 0},
        {'index': 1, 'name': 'USB microphone', 'maxInputChannels': 1},
        {'index': 2, 'name': 'USB headset', 'maxInputChannels': 1},
    ]
    audio = Mock()
    audio.get_device_count.return_value = len(devices)
    audio.get_device_info_by_index.side_effect = devices.__getitem__
    audio.get_default_input_device_info.return_value = devices[1]
    return audio


class PodRuntimeTests(unittest.TestCase):
    def test_device_selection_rejects_output_only_and_ambiguous_names(self):
        audio = fake_audio()
        self.assertEqual(select_input_device(audio, 'default')['index'], 1)
        self.assertEqual(select_input_device(audio, '2')['name'], 'USB headset')
        self.assertEqual(select_input_device(audio, 'MICROPHONE')['index'], 1)
        for selection in ('0', 'USB', 'not connected'):
            with self.assertRaises(ValueError):
                select_input_device(audio, selection)

    def test_selected_microphone_and_packet_size_reach_portaudio(self):
        old_stream = Mock()
        client = SimpleNamespace(p=fake_audio(), stream=old_stream, chunk=4096,
                                 format=8, channels=1, rate=16000)
        configure_microphone(client, '2', chunk=1024)
        old_stream.stop_stream.assert_called_once()
        old_stream.close.assert_called_once()
        client.p.open.assert_called_once_with(format=8, channels=1, rate=16000,
                                            input=True, input_device_index=2,
                                            frames_per_buffer=1024)
        self.assertEqual(client.chunk, 1024)
        self.assertIs(client.stream, client.p.open.return_value)

    def test_failed_default_microphone_open_can_recover_with_selected_usb(self):
        client = SimpleNamespace(p=fake_audio(), stream=None, chunk=4096,
                                 format=8, channels=1, rate=16000)
        configure_microphone(client, '1')
        client.p.open.assert_called_once()

    def test_ready_wait_yields_cpu_and_returns_after_handshake(self):
        connection = SimpleNamespace(recording=False, server_error=False, waiting=False)
        client = SimpleNamespace(clients=[connection])
        with patch('audio_runtime.time.sleep', side_effect=lambda _: setattr(connection, 'recording', True)) as sleep:
            wait_for_server(client, timeout=1)
        sleep.assert_called_once_with(0.05)

    def test_missing_server_times_out_and_rejection_fails_immediately(self):
        connection = SimpleNamespace(recording=False, server_error=False, waiting=False)
        client = SimpleNamespace(clients=[connection])
        with patch('audio_runtime.time.monotonic', side_effect=[0, 2]):
            with self.assertRaises(TimeoutError):
                wait_for_server(client, timeout=1)
        connection.server_error = True
        with self.assertRaises(ConnectionError):
            wait_for_server(client, timeout=1)

    def test_cpu_mode_masks_cuda_before_backend_import(self):
        with patch.dict(os.environ, {'CUDA_VISIBLE_DEVICES': '0'}):
            configure_device('cpu')
            self.assertEqual(os.environ['CUDA_VISIBLE_DEVICES'], '')
        torch = Mock()
        torch.cuda.is_available.return_value = False
        ct2 = Mock()
        ct2.get_supported_compute_types.return_value = {'int8', 'float32'}
        self.assertEqual(describe_device('cpu', torch, ct2), ('cpu', 'int8'))

    def test_cuda_request_cannot_silently_fall_back_to_cpu(self):
        torch = Mock()
        torch.cuda.is_available.return_value = False
        with self.assertRaises(ValueError):
            describe_device('cuda', torch, Mock())

    def test_orin_gpu_requires_float16_support_from_both_runtimes(self):
        torch = Mock()
        torch.cuda.is_available.return_value = True
        torch.cuda.get_device_capability.return_value = (8, 7)
        ct2 = Mock()
        ct2.get_cuda_device_count.return_value = 1
        ct2.get_supported_compute_types.return_value = {'float16', 'float32'}
        self.assertEqual(describe_device('cuda', torch, ct2), ('cuda', 'float16'))
        ct2.get_supported_compute_types.assert_called_once_with('cuda')
        ct2.get_supported_compute_types.return_value = {'float32'}
        with self.assertRaisesRegex(ValueError, 'float16 on cuda'):
            describe_device('cuda', torch, ct2)

    def test_torch_cuda_alone_cannot_approve_a_cpu_only_ct2_build(self):
        torch = Mock()
        torch.cuda.is_available.return_value = True
        torch.cuda.get_device_capability.return_value = (8, 7)
        ct2 = Mock()
        ct2.get_cuda_device_count.return_value = 0
        with self.assertRaisesRegex(ValueError, 'CTranslate2 does not'):
            describe_device('cuda', torch, ct2)

    def test_missing_cuda_library_gives_an_actionable_startup_error(self):
        torch = Mock()
        torch.cuda.is_available.return_value = True
        torch.cuda.get_device_capability.return_value = (8, 7)
        ct2 = Mock()
        ct2.get_cuda_device_count.return_value = 1
        ct2.get_supported_compute_types.side_effect = RuntimeError('CUDA driver mismatch')
        with self.assertRaisesRegex(ValueError, 'cannot initialize cuda.*driver mismatch'):
            describe_device('cuda', torch, ct2)


if __name__ == '__main__':
    unittest.main()
