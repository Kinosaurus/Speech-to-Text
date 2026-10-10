"""WhisperLive extension: accept text hint controls alongside binary audio."""

import json
import logging

from whisper_live.server import TranscriptionServer

from book_context import CONTEXT_PROTOCOL_VERSION, install_context_updates, parse_context_message


class BookContextServer(TranscriptionServer):
    def initialize_client(self, websocket, options, *args, **kwargs):
        super().initialize_client(websocket, options, *args, **kwargs)
        client = self.client_manager.get_client(websocket)
        if client and self.backend.is_faster_whisper():
            install_context_updates(client)
            websocket.send(json.dumps({
                "uid": client.client_uid, "type": "book_context_capabilities",
                "version": CONTEXT_PROTOCOL_VERSION,
            }))

    def get_audio_from_websocket(self, websocket):
        # Controls never enter VAD or the audio buffer. Continue to the next audio frame.
        while True:
            frame = websocket.recv()
            if isinstance(frame, str):
                client = self.client_manager.get_client(websocket)
                try:
                    revision, hints = parse_context_message(frame)
                    state = getattr(client, "book_context_state", None)
                    if state is None:
                        raise ValueError("This backend does not support live book hints.")
                    revision = state.queue(revision, hints)
                    websocket.send(json.dumps({
                        "uid": client.client_uid, "type": "book_context_ack", "revision": revision,
                    }))
                    logging.info("[BOOK_CONTEXT] Queued session hint revision %s", revision)
                except (ValueError, TypeError) as error:
                    websocket.send(json.dumps({
                        "uid": getattr(client, "client_uid", ""), "status": "WARNING", "message": str(error),
                    }))
                continue
            # Delegate upstream PCM conversion and END_OF_AUDIO handling without a second recv.
            class ReceivedFrame:
                def recv(self):
                    return frame

            proxy = ReceivedFrame()
            # The upstream converter looks up the connection's negotiated audio format.
            audio_format = self.audio_formats.get(websocket)
            if audio_format is not None:
                self.audio_formats[proxy] = audio_format
            try:
                return super().get_audio_from_websocket(proxy)
            finally:
                self.audio_formats.pop(proxy, None)
