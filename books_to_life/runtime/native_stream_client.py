"""Use WhisperLive's audio transport with native streaming model snapshots."""
import json
import threading

from whisper_live import utils
from books_to_life.context.book_context_client import BookContextConnection, BookTranscriptionClient


class NativeConnection(BookContextConnection):
    def __init__(self, *args, **kwargs):
        self.finished = threading.Event()
        super().__init__(*args, **kwargs)

    def on_message(self, ws, message):
        value = json.loads(message)
        if value.get('uid') == self.uid and value.get('message') == 'STREAM_DONE':
            self.finished.set()
            return
        super().on_message(ws, message)

    def process_segments(self, segments, translated=False):
        if not segments:
            return
        # Native output is a revised full snapshot, not appended Whisper segments.
        self.transcript = list(segments)
        self.last_segment = None
        super().process_segments(segments, translated)

    def wait_before_disconnect(self):
        # The upstream file player calls this BEFORE sending END_OF_AUDIO.
        # Finalization must happen before it writes the transcript and closes.
        super().send_packet_to_server(self.END_OF_AUDIO.encode('utf-8'))
        if not self.finished.wait(60):
            raise TimeoutError('Native server did not finalize the audio within 60 seconds.')

    def send_packet_to_server(self, message):
        if message == self.END_OF_AUDIO.encode('utf-8') and self.finished.is_set():
            return
        super().send_packet_to_server(message)

    def write_srt_file(self, output_path='output.srt'):
        utils.create_srt_file(self.transcript, output_path)


class NativeTranscriptionClient(BookTranscriptionClient):
    connection_type = NativeConnection

    def finalize_recording(self, n_audio_file):
        try:
            self.client.wait_before_disconnect()
        finally:
            super().finalize_recording(n_audio_file)
