import contextlib
import json
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import numpy as np

from books_to_life.cli.run_native_server import handle_stream
from books_to_life.runtime.native_stream_client import NativeConnection


class NativeStreamTests(unittest.TestCase):
    def test_stream_updates_and_final_words_precede_done(self):
        socket = Mock()
        socket.recv.return_value = json.dumps({'uid': 'test', 'model': 'moonshine', 'language': 'en'})
        socket.__iter__ = Mock(return_value=iter([np.zeros(4096, dtype='<f4').tobytes(), b'END_OF_AUDIO']))
        stream = Mock()
        stream.text.side_effect = [SimpleNamespace(full='a'), SimpleNamespace(full='a child')]
        session = Mock()
        session.stream.return_value = contextlib.nullcontext(stream)
        model = Mock()
        model.session.return_value = contextlib.nullcontext(session)
        args = SimpleNamespace(model='moonshine', threads=2, max_seconds=60)
        lock = threading.Lock()
        handle_stream(socket, model, Mock(), args, lock)
        messages = [json.loads(call.args[0]) for call in socket.send.call_args_list]
        self.assertEqual(messages[0]['message'], 'SERVER_READY')
        self.assertEqual(messages[-2]['segments'][0]['text'], 'a child')
        self.assertTrue(messages[-2]['segments'][0]['completed'])
        self.assertEqual(messages[-2]['segments'][0]['end'], 0.256)
        self.assertEqual(messages[-1]['message'], 'STREAM_DONE')
        stream.finalize.assert_called_once()
        self.assertFalse(lock.locked())

    def test_wrong_model_rejected_before_inference(self):
        socket = Mock()
        socket.recv.return_value = json.dumps({'uid': 'test', 'model': 'small.en'})
        model = Mock()
        handle_stream(socket, model, Mock(), SimpleNamespace(model='moonshine'), threading.Lock())
        self.assertEqual(json.loads(socket.send.call_args.args[0])['status'], 'ERROR')
        model.session.assert_not_called()

    def test_client_sends_end_before_waiting_and_avoids_duplicate_end(self):
        client = NativeConnection.__new__(NativeConnection)
        client.finished = Mock()
        client.finished.wait.return_value = True
        client.finished.is_set.return_value = True
        with patch('books_to_life.context.book_context_client.BookContextConnection.send_packet_to_server') as send:
            client.wait_before_disconnect()
            client.send_packet_to_server(b'END_OF_AUDIO')
        send.assert_called_once_with(b'END_OF_AUDIO')


if __name__ == '__main__':
    unittest.main()
