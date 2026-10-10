import contextlib
import io
import json
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import numpy as np

from book_context import BookHints, ContextState
from book_context_client import BookContextConnection, BookTranscriptionClient
try:
    from book_context_server import BookContextServer
except ModuleNotFoundError:
    # The lightweight client image intentionally omits server-only dependencies.
    BookContextServer = None


class BookContextTransportTests(unittest.TestCase):
    def test_audio_wrapper_preserves_capture_options_and_transcript_path(self):
        with patch("book_context_client.BookContextConnection") as connection, \
                patch("book_context_client.TranscriptionTeeClient.__init__", return_value=None) as audio:
            wrapper = BookTranscriptionClient(
                "localhost", 9090, model="small.en", initial_prompt="Passage", hotwords="Mermaid",
                mute_audio_playback=True, save_output_recording=True,
                output_recording_filename="reading.wav", output_transcription_path="reading.srt",
            )
        self.assertIs(wrapper.client, connection.return_value)
        self.assertEqual(connection.call_args.kwargs["srt_file_path"], "reading.srt")
        self.assertEqual(connection.call_args.kwargs["hotwords"], "Mermaid")
        audio.assert_called_once_with([connection.return_value], mute_audio_playback=True,
                                      save_output_recording=True, output_recording_filename="reading.wav")

    def test_audio_wrapper_rejects_invalid_output_paths_before_connecting(self):
        with patch("book_context_client.BookContextConnection") as connection:
            for options in ({"save_output_recording": True, "output_recording_filename": "reading.mp3"},
                            {"output_transcription_path": "reading.txt"}):
                with self.assertRaises(ValueError):
                    BookTranscriptionClient("localhost", 9090, **options)
            connection.assert_not_called()

    @unittest.skipIf(BookContextServer is None, "ASR server dependencies are not installed")
    def test_controls_are_acknowledged_and_never_enter_pcm_audio(self):
        server = BookContextServer()
        state = ContextState("Old", "Words")
        client = SimpleNamespace(client_uid="reading", book_context_state=state)
        server.client_manager = SimpleNamespace(get_client=lambda socket: client)
        socket = Mock()
        pcm = np.array([0.25, -0.5], dtype=np.float32)
        socket.recv.side_effect = [
            json.dumps({"type": "book_context", "revision": 1, "initial_prompt": "New", "hotwords": "Hints"}),
            pcm.tobytes(), b"END_OF_AUDIO",
        ]
        np.testing.assert_array_equal(server.get_audio_from_websocket(socket), pcm)
        self.assertEqual(state.snapshot(), (BookHints("New", "Hints"), 1))
        self.assertEqual(json.loads(socket.send.call_args.args[0])["type"], "book_context_ack")
        self.assertFalse(server.get_audio_from_websocket(socket))

    @unittest.skipIf(BookContextServer is None, "ASR server dependencies are not installed")
    def test_invalid_control_preserves_hints_and_audio_format(self):
        server = BookContextServer()
        client = SimpleNamespace(client_uid="reading", book_context_state=ContextState("Keep", "These"))
        server.client_manager = SimpleNamespace(get_client=lambda socket: client)
        socket = Mock()
        server.audio_formats[socket] = "int16"
        socket.recv.side_effect = ["not json", np.array([16384], dtype=np.int16).tobytes()]
        np.testing.assert_array_equal(server.get_audio_from_websocket(socket), [0.5])
        self.assertEqual(client.book_context_state.snapshot()[0], BookHints("Keep", "These"))
        self.assertEqual(json.loads(socket.send.call_args.args[0])["status"], "WARNING")
        self.assertEqual(server.audio_formats, {socket: "int16"})

    def connection(self):
        connection = object.__new__(BookContextConnection)
        connection.uid = "reading"
        connection.recording = True
        connection.book_context_supported = False
        connection._context_revision = 0
        connection._sent_revision = 0
        connection._pending_context = None
        connection._context_lock = threading.RLock()
        connection._warned_legacy_server = False
        connection.client_socket = Mock()
        return connection

    def test_old_server_gets_no_control_frames_and_pending_hints_send_after_negotiation(self):
        connection = self.connection()
        with contextlib.redirect_stdout(io.StringIO()):
            connection.queue_book_context(BookHints("Next passage", "Next words"))
            connection.client_socket.send.assert_not_called()
            connection.on_message(None, json.dumps({
                "uid": "reading", "type": "book_context_capabilities", "version": 1,
            }))
        message = json.loads(connection.client_socket.send.call_args.args[0])
        self.assertEqual(message["initial_prompt"], "Next passage")
        self.assertEqual(message["hotwords"], "Next words")
        self.assertEqual(message["revision"], 1)
        connection._send_pending_context()
        connection.client_socket.send.assert_called_once()


if __name__ == "__main__":
    unittest.main()
