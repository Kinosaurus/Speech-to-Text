"""Checkpoint-local permission for one-shot effects, independent of progress."""
import math

from books_to_life.matching.checkpoint_matcher import fuzz, normalize_text
from books_to_life.matching.phonetic_endpoint import phonetic_endpoint_match, pronunciations
from books_to_life.matching.word_boundaries import recent_boundary_spans


def similar(left, right, threshold=75):
    # Preserve ordinary singular/plural variants without rewriting ASR text.
    def singular(word):
        return word[:-1] if len(word) > 4 and word.endswith('s') and not word.endswith('ss') else word
    return singular(left) == singular(right) or fuzz.ratio(left, right) >= threshold


def ordered_support(reference, query):
    """One query word cannot support two different reference words."""
    matrix = [[0] * (len(query) + 1) for _ in range(len(reference) + 1)]
    for i, word in enumerate(reference, 1):
        for j, heard in enumerate(query, 1):
            matrix[i][j] = max(matrix[i-1][j], matrix[i][j-1],
                               matrix[i-1][j-1] + int(similar(word, heard)))
    i, j = len(reference), len(query)
    pairs = []
    while i and j:
        if similar(reference[i-1], query[j-1]) and matrix[i][j] == matrix[i-1][j-1] + 1:
            pairs.append((i-1, j-1)); i -= 1; j -= 1
        elif matrix[i-1][j] >= matrix[i][j-1]:
            i -= 1
        else:
            j -= 1
    return list(reversed(pairs))


class EffectPermission:
    def __init__(self, checkpoint, default_coverage, preceding_words):
        self.policy = checkpoint.get('effect_policy', 'one_shot')
        if self.policy not in ('one_shot', 'ambience'):
            raise ValueError("effect_policy must be 'one_shot' or 'ambience'.")
        self.anchor = normalize_text(checkpoint['checkpoint_text']).split()
        required = checkpoint.get('required_words', [])
        if (not isinstance(required, list) or any(not isinstance(w, str) or
                len(normalize_text(w).split()) != 1 or normalize_text(w) not in self.anchor for w in required)):
            raise ValueError('required_words must be a list of single words from checkpoint_text.')
        self.required = [normalize_text(w) for w in required]
        # Load the shared lexicon before streaming callbacks start.
        pronunciations(self.anchor[-1])
        self.coverage = float(checkpoint.get('min_coverage', default_coverage))
        self.preceding = preceding_words

    def permits(self, buffer, *, allow_phonetic_endpoint=False, allow_word_boundaries=False):
        if self.policy == 'ambience':
            return True, None
        return self.supports_anchor(buffer, allow_phonetic_endpoint=allow_phonetic_endpoint,
                                    allow_word_boundaries=allow_word_boundaries)

    def supports_anchor(self, buffer, *, allow_phonetic_endpoint=False, allow_word_boundaries=False):
        return self._supports_anchor(buffer, allow_phonetic_endpoint=allow_phonetic_endpoint,
                                     allow_word_boundaries=allow_word_boundaries)

    def supports_phonetic_anchor(self, buffer):
        # Candidate generation must use the same required-word/prompt checks as
        # effect permission, and must actually supply the complete exact prefix.
        return self._supports_anchor(buffer, allow_phonetic_endpoint=True, phonetic_only=True)[0]

    def _supports_anchor(self, buffer, *, allow_phonetic_endpoint=False,
                         allow_word_boundaries=False, phonetic_only=False):
        # Only the recent anchor neighbourhood can grant effect permission.
        # A later passage position or an old occurrence elsewhere is insufficient.
        query = buffer[-max(12, len(self.anchor) + 8):]
        for end in range(len(query), max(0, len(query)-4), -1):
            if phonetic_only or not similar(self.anchor[-1], query[end-1]):
                # Phonetic support applies only after local acquisition and
                # the ENTIRE exact contiguous prefix, without rewriting ASR.
                # Required words remain independently checked below.
                prefix = self.anchor[:-1]
                if not (allow_phonetic_endpoint and len(prefix) >= 4
                        and len(set(prefix)) >= 4
                        and query[max(0, end-len(self.anchor)):end-1] == prefix
                        and phonetic_endpoint_match(self.anchor[-1], query[end-1])):
                    continue
            start = max(0, end-len(self.anchor)-3)
            window = query[start:end]
            pairs = ordered_support(self.anchor[:-1], window[:-1])
            if len(pairs)+1 < math.ceil(len(self.anchor)*self.coverage):
                continue
            if any(not any(similar(word, heard, 85) for heard in window) for word in self.required):
                continue
            first = start + (pairs[0][1] if pairs else len(window)-1)
            prefix = query[max(0, first-3):first]
            # Do not mistake a prompt for reading, while permitting the same
            # wording when it is actually part of the authored book context.
            prompt = any(w in {'not', 'never', 'say', 'repeat'} for w in prefix)
            if prompt and prefix != self.preceding[-len(prefix):]:
                continue
            return True, None
        if allow_word_boundaries and self.supports_split_anchor(buffer):
            return True, None
        return False, 'one-shot requires recent ordered anchor, endpoint, and authored required words'

    def supports_split_anchor(self, buffer):
        # Complete exact content supplies every required word, including a
        # split required word. No ordinary coverage/spelling rule is relaxed.
        for prefix in recent_boundary_spans(self.anchor, buffer):
            prompt = any(w in {'not', 'never', 'say', 'repeat'} for w in prefix)
            if not prompt or prefix == self.preceding[-len(prefix):]:
                return True
        return False
