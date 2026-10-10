"""WhisperLive audio client with negotiated live book-hint updates."""

import json
import threading

from whisper_live.client import Client, TranscriptionTeeClient

from book_context import CONTEXT_PROTOCOL_VERSION, MAX_CONTEXT_CHARS


class BookContextConnection(Client):
    def __init__(self, *args, **kwargs):
        self.book_context_supported = False
        self._context_revision = 0
        self._sent_revision = 0
        self._pending_context = None
        self._context_lock = threading.RLock()
        self._warned_legacy_server = False
        super().__init__(*args, **kwargs)

    def on_message(self, ws, message):
        data = json.loads(message)
        if data.get("uid") == self.uid:
            if data.get("type") == "book_context_capabilities":
                self.book_context_supported = data.get("version") == CONTEXT_PROTOCOL_VERSION
                if self.book_context_supported:
                    print("[BOOK_CONTEXT] Server supports live hint updates.")
                    self._send_pending_context()
                return
            if data.get("type") == "book_context_ack":
                print(f"[BOOK_CONTEXT] Server queued hint revision {data['revision']} for the next inference.")
                return
        super().on_message(ws, message)

    def queue_book_context(self, hints):
        if any(value is not None and len(value) > MAX_CONTEXT_CHARS
               for value in (hints.initial_prompt, hints.hotwords)):
            print("[BOOK_CONTEXT] Explicit hints exceed the live-update limit; retaining startup hints.")
            return
        with self._context_lock:
            self._context_revision += 1
            self._pending_context = {
                "type": "book_context", "revision": self._context_revision,
                "initial_prompt": hints.initial_prompt, "hotwords": hints.hotwords,
            }
        if not self.book_context_supported:
            if self.recording and not self._warned_legacy_server:
                print("[BOOK_CONTEXT] Live updates unavailable; startup hints remain active. "
                      "Restart/rebuild the updated server to enable moving book context.")
                self._warned_legacy_server = True
            return
        self._send_pending_context()

    def _send_pending_context(self):
        with self._context_lock:
            if not self._pending_context or self._sent_revision == self._context_revision:
                return
            message = self._pending_context
            self.client_socket.send(json.dumps(message, ensure_ascii=False))
            self._sent_revision = message["revision"]


class BookTranscriptionClient(TranscriptionTeeClient):
    """Reuse upstream microphone/file streaming with our connection subclass."""

    def __init__(self, *args, **kwargs):
        audio_options = {
            key: kwargs.pop(key, default)
            for key, default in (("save_output_recording", False),
                                 ("output_recording_filename", "./output_recording.wav"),
                                 ("mute_audio_playback", False))
        }
        if (audio_options["save_output_recording"]
                and not audio_options["output_recording_filename"].endswith(".wav")):
            raise ValueError("output_recording_filename must end with .wav")
        transcript_path = kwargs.pop("output_transcription_path", "./output.srt")
        if not transcript_path.endswith(".srt"):
            raise ValueError("output_transcription_path must end with .srt")
        kwargs["srt_file_path"] = transcript_path
        self.client = BookContextConnection(*args, **kwargs)
        super().__init__([self.client], **audio_options)
