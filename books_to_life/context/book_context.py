"""Bounded, optional book hints for ASR; these do not confirm checkpoints."""

from dataclasses import dataclass
import json
import threading


CONTEXT_PROTOCOL_VERSION = 1
MAX_CONTEXT_CHARS = 6000


@dataclass(frozen=True)
class BookHints:
    initial_prompt: str | None
    hotwords: str | None


def _bounded_words(text, word_limit, char_limit):
    words = text.split()[:word_limit]
    while words and len(" ".join(words)) > char_limit:
        words.pop()
    return " ".join(words) or None


class BookContext:
    """Use the next checkpoint plus lookahead; advance only on confirmed progress."""

    def __init__(self, matcher, lookahead=2, prompt_words=64,
                 initial_prompt=None, hotwords=None):
        if not 0 <= lookahead <= 10 or not 8 <= prompt_words <= 128:
            raise ValueError("Book context needs lookahead 0–10 and prompt_words 8–128.")
        self.matcher = matcher
        self.lookahead = lookahead
        self.prompt_words = prompt_words
        # Explicit CLI hints override their respective automatic field.
        self.manual_prompt = initial_prompt
        self.manual_hotwords = hotwords
        self._index = -1
        self._position = -1
        self.hints = None
        self.refresh(force=True)

    def refresh(self, force=False):
        position = getattr(self.matcher, "tracked_word_position", 0)
        index = min(self.matcher.current_index, len(self.matcher.checkpoints) - 1)
        if not force and index == self._index and position < self._position + 16:
            return None
        self._index, self._position = index, position
        selected = self.matcher.checkpoints[index:index + self.lookahead + 1]
        phrases = []
        words_used = 0
        for checkpoint in selected:
            phrase = _bounded_words(checkpoint["checkpoint_text"], 16, 100)
            if phrase is None:
                continue
            if phrase.casefold() in {item.casefold() for item in phrases}:
                continue
            word_count = len(phrase.split())
            if words_used + word_count > 48 or len(", ".join(phrases + [phrase])) > 320:
                break
            phrases.append(phrase)
            words_used += word_count
        automatic_hotwords = ", ".join(phrases) or None
        if hasattr(self.matcher, "words"):
            # A short lookback retains context for corrections and unfinished ASR.
            start = max(0, position - 8)
            passage = " ".join(self.matcher.words[start:start + self.prompt_words])
        else:
            # Phrase-only manifests have no full-page text.
            passage = ". ".join(phrases)
        automatic_prompt = _bounded_words(passage, self.prompt_words, 480)
        hints = BookHints(
            self.manual_prompt if self.manual_prompt is not None else automatic_prompt,
            self.manual_hotwords if self.manual_hotwords is not None else automatic_hotwords,
        )
        if hints == self.hints:
            return None
        self.hints = hints
        return hints


class ContextState:
    """Atomically queue a hint pair for the next inference of this session."""

    def __init__(self, initial_prompt=None, hotwords=None):
        self._lock = threading.Lock()
        self._hints = BookHints(initial_prompt, hotwords)
        self._revision = 0

    def snapshot(self):
        with self._lock:
            return self._hints, self._revision

    def queue(self, revision, hints):
        with self._lock:
            if revision > self._revision:
                self._hints, self._revision = hints, revision
            return self._revision


def parse_context_message(message):
    """Validate a bounded control frame before changing a running session."""
    if not isinstance(message, str) or len(message) > MAX_CONTEXT_CHARS * 2 + 1024:
        raise ValueError("Book context message is too large or is not text.")
    data = json.loads(message)
    if not isinstance(data, dict) or data.get("type") != "book_context":
        raise ValueError("Unknown book context control message.")
    revision = data.get("revision")
    if type(revision) is not int or revision < 1:
        raise ValueError("Book context revision must be a positive integer.")
    for field in ("initial_prompt", "hotwords"):
        value = data.get(field)
        if value is not None and (not isinstance(value, str) or len(value) > MAX_CONTEXT_CHARS):
            raise ValueError(f"Book context {field} must be text within {MAX_CONTEXT_CHARS} characters or null.")
    return revision, BookHints(data.get("initial_prompt"), data.get("hotwords"))


def install_context_updates(client):
    """Apply queued hints on the ASR thread, keeping each inference's pair consistent."""
    state = ContextState(client.initial_prompt, client.hotwords)
    original_transcribe = client.transcribe_audio

    def transcribe_with_context(audio):
        hints, _ = state.snapshot()
        client.initial_prompt, client.hotwords = hints.initial_prompt, hints.hotwords
        return original_transcribe(audio)

    client.transcribe_audio = transcribe_with_context
    client.book_context_state = state
    return state
