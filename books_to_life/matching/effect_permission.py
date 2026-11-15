"""Checkpoint-local permission for one-shot effects, independent of progress."""
import math

from books_to_life.matching.checkpoint_matcher import fuzz, normalize_text
from books_to_life.matching.phonetic_endpoint import phonetic_endpoint_match, phonetic_word_credit, pronunciations
from books_to_life.matching.word_boundaries import recent_boundary_spans

PROMPT_WORDS = frozenset({'not', 'never', 'dont', "don't", 'say', 'repeat'})
ARTICLES = frozenset({'a', 'an', 'the'})


def similar(left, right, threshold=75):
    # Preserve ordinary singular/plural variants without rewriting ASR text.
    def singular(word):
        return word[:-1] if len(word) > 4 and word.endswith('s') and not word.endswith('ss') else word
    return singular(left) == singular(right) or fuzz.ratio(left, right) >= threshold


def ordered_support(reference, query, credit=similar):
    """One query word cannot support two different reference words."""
    matrix = [[0] * (len(query) + 1) for _ in range(len(reference) + 1)]
    for i, word in enumerate(reference, 1):
        for j, heard in enumerate(query, 1):
            matrix[i][j] = max(matrix[i-1][j], matrix[i][j-1],
                               matrix[i-1][j-1] + credit(word, heard))
    i, j = len(reference), len(query)
    pairs = []
    while i and j:
        weight = credit(reference[i-1], query[j-1])
        if weight and matrix[i][j] == matrix[i-1][j-1] + weight:
            pairs.append((i-1, j-1)); i -= 1; j -= 1
        elif matrix[i-1][j] >= matrix[i][j-1]:
            i -= 1
        else:
            j -= 1
    return list(reversed(pairs))


def phrase_word_credit(expected, heard):
    if expected == heard:
        return 1.0
    if similar(expected, heard):
        return .75
    return phonetic_word_credit(expected, heard)


class EffectPermission:
    def __init__(self, checkpoint, default_coverage, preceding_words):
        self.policy = checkpoint.get('effect_policy', 'one_shot')
        if self.policy not in ('one_shot', 'ambience'):
            raise ValueError("effect_policy must be 'one_shot' or 'ambience'.")
        self.anchor = normalize_text(checkpoint['checkpoint_text']).split()
        self.content_words = sum(word not in ARTICLES for word in self.anchor)
        self.has_omittable_articles = self.content_words < len(self.anchor) and self.anchor[-1] not in ARTICLES
        required = checkpoint.get('required_words', [])
        if (not isinstance(required, list) or any(not isinstance(w, str) or
                len(normalize_text(w).split()) != 1 or normalize_text(w) not in self.anchor for w in required)):
            raise ValueError('required_words must be a list of single words from checkpoint_text.')
        self.required = [normalize_text(w) for w in required]
        # Load the shared lexicon before streaming callbacks start.
        pronunciations(self.anchor[-1])
        self.coverage = float(checkpoint.get('min_coverage', default_coverage))
        self.preceding = preceding_words

    def permits(self, buffer, *, allow_phonetic_endpoint=False, allow_word_boundaries=False,
                allow_article_omissions=False):
        if self.policy == 'ambience':
            return True, None
        supported, reason = self.supports_anchor(buffer, allow_phonetic_endpoint=allow_phonetic_endpoint,
                                                 allow_word_boundaries=allow_word_boundaries)
        if not supported and allow_article_omissions and self.article_omission_support(buffer):
            return True, None
        return supported, reason

    def supports_anchor(self, buffer, *, allow_phonetic_endpoint=False, allow_word_boundaries=False):
        return self._supports_anchor(buffer, allow_phonetic_endpoint=allow_phonetic_endpoint,
                                     allow_word_boundaries=allow_word_boundaries)

    def supports_phonetic_anchor(self, buffer, *, include_partial=False):
        # Candidate generation must use the same required-word/prompt checks as
        # effect permission, and must actually supply the complete exact prefix.
        return self._supports_anchor(buffer, allow_phonetic_endpoint=True, phonetic_only=True,
                                     include_partial=include_partial)[0]

    def article_omission_support(self, buffer, *, include_partial=False):
        """Return ordered content-word evidence when the cue's articles are missing."""
        return self._supports_anchor(buffer, omitted_articles_only=True, include_partial=include_partial)[0]

    def phonetic_phrase_support(self, buffer, threshold, *, include_partial=False):
        """Find recent ordered phrase evidence, including a supported endpoint."""
        reference = self.anchor
        if len(reference) < 3:
            return None
        query = buffer[-(len(self.anchor) + 8):]
        best = None
        partial = ()
        for end in range(len(query), max(0, len(query) - 4), -1):
            endpoint = query[end - 1]
            end_credit = phrase_word_credit(reference[-1], endpoint)
            if not end_credit:
                continue
            start = max(0, end - len(self.anchor) - 3)
            window = query[start:end]
            pairs = ordered_support(reference[:-1], window[:-1], phrase_word_credit)
            pairs.append((len(reference) - 1, len(window) - 1))
            matches = [(reference[i], window[j]) for i, j in pairs]
            exact = [word for word, heard in matches if word == heard and word not in ARTICLES]
            if len(exact) < math.ceil(.6 * self.content_words):
                continue
            if len(set(exact)) < 2 or not any(phonetic_word_credit(word, heard) for word, heard in matches):
                continue
            omitted = 0
            if self.has_omittable_articles:
                matched_indices = {i for i, _ in pairs}
                omitted = sum(word in ARTICLES and i not in matched_indices for i, word in enumerate(reference))
            comparable_words = len(reference) - omitted
            score = 100 * sum(phrase_word_credit(word, heard) for word, heard in matches) / comparable_words
            if score < max(threshold, 100 * self.coverage):
                continue
            if any(not any(similar(word, heard, 85) for heard in window) for word in self.required):
                continue
            first = start + pairs[0][1]
            prefix = query[max(0, first - 3):first]
            if PROMPT_WORDS.intersection(prefix) and prefix != self.preceding[-len(prefix):]:
                continue
            if PROMPT_WORDS.intersection(query[first:end]) - set(reference):
                continue
            evidence = (score, len(matches), comparable_words)
            if best is None or evidence > best:
                best = evidence
                if include_partial:
                    offset = len(buffer) - len(query) + start
                    partial = tuple((offset + j, word, phrase_word_credit(word, heard))
                                    for (_, j), (word, heard) in zip(pairs, matches) if word != heard)
        if best and include_partial:
            return (*best, partial)
        return best

    def _supports_anchor(self, buffer, *, allow_phonetic_endpoint=False,
                         allow_word_boundaries=False, phonetic_only=False, omitted_articles_only=False,
                         include_partial=False):
        # Only the recent anchor neighbourhood can grant effect permission.
        # A later passage position or an old occurrence elsewhere is insufficient.
        if omitted_articles_only and not self.has_omittable_articles:
            return None, None
        query = buffer[-max(12, len(self.anchor) + 8):]
        for end in range(len(query), max(0, len(query)-4), -1):
            if omitted_articles_only and query[end-1] != self.anchor[-1]:
                continue
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
            full_coverage = len(pairs)+1 >= math.ceil(len(self.anchor)*self.coverage)
            article_support = None
            if omitted_articles_only:
                content = [(i, j) for i, j in pairs if self.anchor[i] not in ARTICLES]
                exact = {self.anchor[i] for i, j in content if self.anchor[i] == window[j]}
                heard_articles = len(pairs) - len(content)
                total = self.content_words + heard_articles
                if len(exact | {self.anchor[-1]}) >= 5 and len(pairs)+1 >= math.ceil(total*self.coverage):
                    article_support = (len(pairs)+1, total)
            if omitted_articles_only and (full_coverage or article_support is None):
                continue
            if not full_coverage and article_support is None:
                continue
            if any(not any(similar(word, heard, 85) for heard in window) for word in self.required):
                continue
            first = start + (pairs[0][1] if pairs else len(window)-1)
            prefix = query[max(0, first-3):first]
            # Do not mistake a prompt for reading, while permitting the same
            # wording when it is actually part of the authored book context.
            prompt = bool(PROMPT_WORDS.intersection(prefix))
            if prompt and prefix != self.preceding[-len(prefix):]:
                continue
            if include_partial and omitted_articles_only:
                offset = len(buffer) - len(query) + start
                partial = tuple((offset + j, self.anchor[i], None) for i, j in content
                                if self.anchor[i] != window[j])
                return (*article_support, partial), None
            if include_partial and phonetic_only:
                return ((len(buffer) - len(query) + end - 1, self.anchor[-1], .75),), None
            return (article_support if omitted_articles_only else True), None
        if allow_word_boundaries and self.supports_split_anchor(buffer):
            return True, None
        return (None if omitted_articles_only else False), 'one-shot requires recent ordered anchor, endpoint, and authored required words'

    def supports_split_anchor(self, buffer):
        # Complete exact content supplies every required word, including a
        # split required word. No ordinary coverage/spelling rule is relaxed.
        for prefix in recent_boundary_spans(self.anchor, buffer):
            prompt = bool(PROMPT_WORDS.intersection(prefix))
            if not prompt or prefix == self.preceding[-len(prefix):]:
                return True
        return False
