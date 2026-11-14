"""Checkpoint-local permission for one-shot effects, independent of progress."""
import math

from books_to_life.matching.checkpoint_matcher import fuzz, normalize_text
from books_to_life.matching.phonetic_endpoint import phonetic_endpoint_match, pronunciations
from books_to_life.matching.word_boundaries import recent_boundary_spans

# Positive coaching counts as shared reading. Explicit negation still needs
# authored book context; it must not supply permission or extra prefix evidence.
NEGATION_WORDS = frozenset({'not', 'never', 'dont', "don't"})
PROMPT_WORDS = NEGATION_WORDS | {'say', 'repeat'}


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
        tracking_anchor = normalize_text(checkpoint['checkpoint_text']).split()
        self.has_explicit_cue = 'effect_cue' in checkpoint
        if self.has_explicit_cue:
            cue = checkpoint['effect_cue']
            if not isinstance(cue, str) or not normalize_text(cue):
                raise ValueError('effect_cue must be a non-empty phrase from checkpoint_text.')
            self.anchor = normalize_text(cue).split()
            offsets = [i for i in range(len(tracking_anchor)-len(self.anchor)+1)
                       if tracking_anchor[i:i+len(self.anchor)] == self.anchor]
            if len(offsets) != 1:
                raise ValueError('effect_cue must occur exactly once within checkpoint_text.')
            self.cue_offset = offsets[0]
        else:
            self.anchor = tracking_anchor
            self.cue_offset = 0
        required = checkpoint.get('required_words', [])
        if (not isinstance(required, list) or any(not isinstance(w, str) or
                len(normalize_text(w).split()) != 1 or normalize_text(w) not in self.anchor for w in required)):
            raise ValueError('required_words must be a list of single words from the effect cue.')
        self.required = [normalize_text(w) for w in required]
        # Load the shared lexicon before streaming callbacks start.
        pronunciations(self.anchor[-1])
        self.coverage = float(checkpoint.get('min_coverage', default_coverage))
        self.preceding = (preceding_words + tracking_anchor[:self.cue_offset])[-3:]

    def permits(self, buffer, *, allow_phonetic_endpoint=False, allow_word_boundaries=False,
                allow_phonetic_internal=False, allow_context_suffix=False):
        if self.policy == 'ambience':
            return True, None
        result = self.supports_anchor(buffer, allow_phonetic_endpoint=allow_phonetic_endpoint,
                                      allow_word_boundaries=allow_word_boundaries,
                                      allow_phonetic_internal=allow_phonetic_internal)
        if not result[0] and allow_context_suffix and self.has_explicit_cue and self.supports_context_suffix(buffer):
            return True, None
        return result

    def supports_context_suffix(self, buffer):
        """An optional leading cue fragment may be absent after a full context
        alignment has passed ordinary score/coverage/confirmation. This helper
        alone cannot grant progress. Require three distinct exact remaining cue
        words, its endpoint and every essential word; no sound substitutions.
        """
        query = buffer[-max(12, len(self.anchor)+8):]
        for offset in range(1, len(self.anchor)-2):
            suffix = self.anchor[offset:]
            if len(set(suffix)) < 3 or any(word not in suffix for word in self.required):
                continue
            for end in range(len(query), max(0, len(query)-4), -1):
                begin = end-len(suffix)
                if begin < 0 or query[begin:end] != suffix:
                    continue
                prefix = query[max(0, begin-3):begin]
                preceding = (self.preceding+self.anchor[:offset])[-len(prefix):]
                if not (set(prefix) & PROMPT_WORDS) or prefix == preceding:
                    return True
        return False

    def supports_anchor(self, buffer, *, allow_phonetic_endpoint=False, allow_word_boundaries=False,
                        allow_phonetic_internal=False):
        return self._supports_anchor(buffer, allow_phonetic_endpoint=allow_phonetic_endpoint,
                                     allow_word_boundaries=allow_word_boundaries,
                                     allow_phonetic_internal=allow_phonetic_internal)

    def supports_phonetic_anchor(self, buffer):
        # Candidate generation must use the same required-word/negation checks as
        # effect permission, and must actually supply the complete exact prefix.
        return self._supports_anchor(buffer, allow_phonetic_endpoint=True, phonetic_only=True)[0]

    def _supports_anchor(self, buffer, *, allow_phonetic_endpoint=False,
                         allow_word_boundaries=False, phonetic_only=False,
                         allow_phonetic_internal=False):
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
            needed = math.ceil(len(self.anchor)*self.coverage)
            support = len(pairs)+1
            if (allow_phonetic_internal and support == needed-1
                    and self.anchor[-1] == window[-1]
                    and self._internal_phonetic_support(window,pairs)):
                support += 1
            if support < needed:
                continue
            if any(not any(similar(word, heard, 85) for heard in window) for word in self.required):
                continue
            first = start + (pairs[0][1] if pairs else len(window)-1)
            prefix = query[max(0, first-3):first]
            # Either voice may supply the phrase, including positive coaching.
            # Quoted prompts and negation need matching authored context.
            prompted = bool(PROMPT_WORDS.intersection(prefix))
            if prompted and prefix != self.preceding[-len(prefix):]:
                continue
            return True, None
        if allow_word_boundaries and self.supports_split_anchor(buffer):
            return True, None
        return False, 'one-shot requires recent ordered anchor, endpoint, and authored required words'

    def _internal_phonetic_support(self, window, pairs):
        """One observed substitution, bracketed by exact ordered neighbours.

        This uses the existing pronunciation rule. A gap supplies no query
        token; an already matched token cannot count twice. Essential words
        keep their ordinary stricter spelling requirement.
        """
        matched = dict(pairs+[(len(self.anchor)-1,len(window)-1)])
        used = set(matched.values())
        if len({self.anchor[i] for i in matched}) < 3:
            return False
        candidates = []
        for i in range(1,len(self.anchor)-1):
            if i in matched or self.anchor[i] in self.required:
                continue
            left,right = matched.get(i-1),matched.get(i+1)
            if left is None or right != left+2:
                continue
            j = left+1
            if (j not in used and self.anchor[i-1] == window[left]
                    and self.anchor[i+1] == window[right]
                    and phonetic_endpoint_match(self.anchor[i],window[j])):
                candidates.append((i,j))
        return len(candidates) == 1

    def supports_split_anchor(self, buffer):
        # Complete exact content supplies every required word, including a
        # split required word. No ordinary coverage/spelling rule is relaxed.
        for prefix in recent_boundary_spans(self.anchor, buffer):
            prompted = bool(PROMPT_WORDS.intersection(prefix))
            if not prompted or prefix == self.preceding[-len(prefix):]:
                return True
        return False
