"""Map matcher evidence onto the original text shown to the operator."""

import re

from books_to_life.matching.checkpoint_matcher import normalize_text


def partial_word_ranges(text, buffer, partial_words):
    if not partial_words:
        return []
    words = []
    offsets = []
    for match in re.finditer(r"[\w']+", text):
        normalized = normalize_text(match.group()).split()
        words.extend(normalized)
        offsets.extend([match.span()] * len(normalized))
    start = len(words) - len(buffer)
    if start < 0 or words[start:] != list(buffer):
        return []
    return [
        {'start': offsets[start + index][0], 'end': offsets[start + index][1],
         'expected': expected, 'credit': credit}
        for index, expected, credit in partial_words
    ]


class TranscriptEvidence:
    def __init__(self):
        self.text = ''
        self.confirmed = {}

    def update(self, text, buffer, match):
        partial = partial_word_ranges(text, buffer, getattr(match, 'partial_words', ()))
        # Fired highlights survive only while their position in the ASR text is still valid.
        self.confirmed = {span: detail for span, detail in self.confirmed.items()
                          if text[:span[1]] == self.text[:span[1]]}
        current = {(word['start'], word['end']): word for word in partial}
        if match.triggered:
            self.confirmed.update(current)
        self.text = text
        return {
            'text': text,
            'partial': list({**self.confirmed, **current}.values()),
            'checkpoint': match.checkpoint_id,
            'score': round(match.score, 1) if match.score > 0 else None,
            'skipped': getattr(match, 'skipped_checkpoint_ids', ()),
            'suppressed': (
                *((match.checkpoint_id,) if getattr(match, 'effect_suppressed', False) else ()),
                *getattr(match, 'additional_suppressed_checkpoint_ids', ()),
            ),
            'pending': getattr(match, 'effect_pending_checkpoint_id', None),
        }
