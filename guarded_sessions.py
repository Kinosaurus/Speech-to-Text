"""Local reading attempts using the split matcher from main (90a8710)."""
import math
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from uuid import uuid4

from books_to_life.matching.timely_matcher import TimelyEvidenceMatcher


@dataclass
class Attempt:
    matcher: TimelyEvidenceMatcher
    touched: float = field(default_factory=time.monotonic)
    last_seconds: float = 0
    lock: threading.Lock = field(default_factory=threading.Lock)

    def update(self, text, seconds, completed):
        if (not isinstance(text, str) or type(seconds) not in (int, float)
                or not math.isfinite(seconds) or seconds < 0 or type(completed) is not bool):
            raise ValueError("Expected text, elapsed seconds and a completion flag.")
        with self.lock:
            if seconds < self.last_seconds:
                raise ValueError("Transcript callbacks must arrive in order.")
            self.touched = time.monotonic()
            self.last_seconds = seconds
            segment = dict(start=0, end=seconds, text=text, completed=completed)
            update = self.matcher.process(text, [segment])
            return dict(trigger=update.checkpoint_id if update.triggered else None,
                        **self.snapshot())

    def snapshot(self):
        matcher = self.matcher
        return dict(position=matcher.tracked_word_position,
                    checkpoints=[dict(cp, status=self.status(str(cp["id"])))
                                 for cp in matcher.checkpoints])

    def status(self, ident):
        matcher = self.matcher
        if ident in matcher.triggered_checkpoint_ids:
            return "triggered"
        if ident in matcher.suppressed_checkpoint_ids:
            return "withheld"
        if ident in matcher.skipped_checkpoint_ids:
            return "skipped"
        return "pending"


class GuardedSessions:
    def __init__(self, books: Path):
        self.books = books
        self.attempts = {}
        self.lock = threading.Lock()

    def start(self, book):
        if not isinstance(book, str) or book not in ("little-mermaid", "tea"):
            raise ValueError("Unknown book.")
        matcher = TimelyEvidenceMatcher.from_file(self.books / book / "checkpoints.json", stability=2)
        attempt = Attempt(matcher)
        ident = uuid4().hex
        with self.lock:
            now = time.monotonic()
            self.attempts = {key: value for key, value in self.attempts.items()
                             if now - value.touched < 300}
            if len(self.attempts) >= 32:
                raise ValueError("Too many open reading attempts.")
            self.attempts[ident] = attempt
        return dict(attempt=ident, **attempt.snapshot())

    def update(self, ident, text, seconds, completed):
        with self.lock:
            attempt = self.attempts[ident]
        return attempt.update(text, seconds, completed)

    def close(self, ident):
        with self.lock:
            self.attempts.pop(ident, None)
        return {}
