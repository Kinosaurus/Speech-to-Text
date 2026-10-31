import json
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

import numpy as np

from books_to_life.runtime.nemo_parakeet import NemoParakeetSession, hint_phrases, reset_phrase_state
from books_to_life.cli.run_nemo_server import handle_connection


class Socket:
    def __init__(self, packets):
        self.packets = packets
        self.sent = []
    def recv(self, timeout=None):
        return json.dumps({'uid': 'test', 'model': 'parakeet-nemo', 'language': 'en', 'hotwords': 'Mermaid'})
    def __iter__(self):
        return iter(self.packets)
    def send(self, value):
        self.sent.append(json.loads(value))


class NemoTransportTests(unittest.TestCase):
    def test_audio_is_buffered_until_right_context_arrives_and_tail_is_flushed(self):
        session = NemoParakeetSession.__new__(NemoParakeetSession)
        session.context = SimpleNamespace(chunk=4, right=2)
        session.pending = np.empty(0, dtype=np.float32)
        session.first = True
        session.finalized = False
        session.text = ''
        session._decode = Mock()
        session.feed(np.arange(5, dtype=np.float32))
        session._decode.assert_not_called()
        session.feed(np.arange(5, 10, dtype=np.float32))
        self.assertEqual([len(c.args[0]) for c in session._decode.call_args_list], [6, 4])
        session.finish()
        # Even with no unsent input, the retained right context must be decoded.
        self.assertEqual(len(session._decode.call_args.args[0]), 0)
        self.assertTrue(session._decode.call_args.kwargs['final'])
        session.finish()
        self.assertEqual(session._decode.call_count, 3)

    def test_live_hints_stay_out_of_audio_and_stale_revision_is_rejected(self):
        pcm = np.array([0.25, -0.5], dtype='<f4')
        hint = json.dumps({'type': 'book_context', 'revision': 1, 'hotwords': 'Prince', 'initial_prompt': 'passage'})
        socket = Socket([pcm.tobytes(), hint, hint, b'END_OF_AUDIO'])
        session = Mock()
        session.feed.return_value = ['a mermaid']
        session.finish.return_value = 'a mermaid and a prince'
        lock = threading.Lock()
        handle_connection(socket, lambda: session, lock)
        self.assertEqual([c.args[0] for c in session.set_hints.call_args_list], ['Mermaid', 'Prince'])
        self.assertEqual(session.feed.call_count, 1)
        np.testing.assert_array_equal(session.feed.call_args.args[0], pcm)
        self.assertEqual(socket.sent[-1]['message'], 'STREAM_DONE')
        self.assertEqual(socket.sent[-2]['segments'][0]['text'], 'a mermaid and a prince')
        self.assertTrue(any(m.get('status') == 'WARNING' for m in socket.sent))
        session.close.assert_called_once()
        self.assertFalse(lock.locked())

    def test_hint_update_keeps_predictor_and_non_biasing_state(self):
        predictor = object()
        other_state = object()
        fresh = object()
        tree = Mock()
        tree.get_init_states.return_value = fresh
        computer = Mock()
        computer._all_fusion_models_with_params.return_value = [
            SimpleNamespace(is_multi_model=False), SimpleNamespace(is_multi_model=True, model=tree)]
        state = SimpleNamespace(predictor_states=predictor, fusion_states_list=[other_state, object()])
        reset_phrase_state(computer, state)
        self.assertIs(state.predictor_states, predictor)
        self.assertIs(state.fusion_states_list[0], other_state)
        self.assertIs(state.fusion_states_list[1], fresh)

    def test_hint_bounds_and_clearing(self):
        self.assertEqual(hint_phrases(None), [])
        self.assertEqual(hint_phrases(' Mermaid, Prince, Mermaid '), ['Mermaid', 'Prince'])
        for bad in [42, 'x' * 201, ','.join(str(i) for i in range(33))]:
            with self.assertRaises(ValueError):
                hint_phrases(bad)

    def test_session_cleanup_on_inference_error(self):
        socket = Socket([np.zeros(2, dtype='<f4').tobytes()])
        session = Mock()
        session.feed.side_effect = ValueError('bad audio')
        lock = threading.Lock()
        handle_connection(socket, lambda: session, lock)
        self.assertEqual(socket.sent[-1]['status'], 'ERROR')
        session.close.assert_called_once()
        self.assertFalse(lock.locked())


if __name__ == '__main__':
    unittest.main()
