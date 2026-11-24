"""Checkpoint-local permission for one-shot effects, independent of progress."""
import math

from books_to_life.matching.checkpoint_matcher import WordEvidence, fuzz, normalize_text
from books_to_life.matching.phonetic_endpoint import (
    phonetic_endpoint_match, phonetic_split_match, phonetic_word_credit, pronunciations,
)
from books_to_life.matching.word_boundaries import PROMPT_WORDS, recent_boundary_matches

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


def anchor_word_evidence(reference, window, pairs, *, waive_articles=False,
                         phonetic_phrase=False, phonetic_endpoint=False):
    matched = dict(pairs)
    for index, expected in enumerate(reference):
        if index not in matched:
            kind = 'article_waived' if waive_articles and expected in ARTICLES else 'omitted'
            yield WordEvidence(expected, None, kind)
            continue
        heard = window[matched[index]]
        if heard == expected:
            yield WordEvidence(expected, heard, 'exact', 1.0)
        elif phonetic_phrase:
            kind = 'spelling' if similar(expected, heard) else 'sound'
            yield WordEvidence(expected, heard, kind, phrase_word_credit(expected, heard))
        else:
            kind = 'sound' if phonetic_endpoint and index == len(reference) - 1 else 'spelling'
            yield WordEvidence(expected, heard, kind)


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
                allow_article_omissions=False, allow_endpoint_fragment=False, word_evidence=None):
        if self.policy == 'ambience':
            return True, None
        supported, reason = self.supports_anchor(buffer, allow_phonetic_endpoint=allow_phonetic_endpoint,
                                                  allow_word_boundaries=allow_word_boundaries,
                                                  word_evidence=word_evidence)
        if not supported and allow_article_omissions and self.article_omission_support(
                buffer, word_evidence=word_evidence):
            return True, None
        if not supported and allow_endpoint_fragment and self.supports_endpoint_fragment(
                buffer, word_evidence=word_evidence):
            return True, None
        return supported, reason

    def supports_endpoint_fragment(self, buffer, *, word_evidence=None):
        """Accept a recent partial ending when the preceding cue is clear."""
        endpoint = self.anchor[-1]
        fragment = buffer[-1] if buffer else ''
        if (endpoint in self.required or fragment in {'a', 'i'} or fragment in PROMPT_WORDS
                or not fragment.isalpha() or fragment == endpoint or not endpoint.startswith(fragment)):
            return False
        # Require five distinct exact words and allow at most one fewer
        # supported word than ordinary coverage for longer cues.
        minimum_context = max(5, math.ceil(len(self.anchor) * self.coverage) - 2)
        for offset in range(len(self.anchor) - minimum_context):
            context = self.anchor[offset:-1]
            start = len(buffer) - len(context) - 1
            if (start < 0 or buffer[start:-1] != context or len(set(context)) < 5
                    or any(word not in context for word in self.required)):
                continue
            prefix = buffer[max(0, start - 3):start]
            if PROMPT_WORDS.intersection(prefix) and prefix != (self.preceding + self.anchor[:offset])[-len(prefix):]:
                continue
            if word_evidence is not None:
                pairs = [(i, i - offset) for i in range(offset, len(self.anchor))]
                word_evidence[:] = anchor_word_evidence(self.anchor, buffer[start:], pairs)
            return True
        return False

    def supports_anchor(self, buffer, *, allow_phonetic_endpoint=False, allow_word_boundaries=False,
                        word_evidence=None):
        return self._supports_anchor(buffer, allow_phonetic_endpoint=allow_phonetic_endpoint,
                                     allow_word_boundaries=allow_word_boundaries, word_evidence=word_evidence)

    def supports_phonetic_anchor(self, buffer, *, include_partial=False, word_evidence=None):
        # Candidate generation must use the same required-word/prompt checks as
        # effect permission, and must actually supply the complete exact prefix.
        return self._supports_anchor(buffer, allow_phonetic_endpoint=True, phonetic_only=True,
                                     include_partial=include_partial, word_evidence=word_evidence)[0]

    def article_omission_support(self, buffer, *, include_partial=False, word_evidence=None):
        """Return ordered content-word evidence when the cue's articles are missing."""
        return self._supports_anchor(buffer, omitted_articles_only=True, include_partial=include_partial,
                                     word_evidence=word_evidence)[0]

    def phonetic_phrase_support(self, buffer, threshold, *, include_partial=False, word_evidence=None):
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
                if word_evidence is not None:
                    word_evidence[:] = anchor_word_evidence(reference, window, pairs,
                                                           waive_articles=self.has_omittable_articles,
                                                           phonetic_phrase=True)
                if include_partial:
                    offset = len(buffer) - len(query) + start
                    partial = tuple((offset + j, word, phrase_word_credit(word, heard))
                                    for (_, j), (word, heard) in zip(pairs, matches) if word != heard)
        split_words = [] if word_evidence is not None else None
        split = self.phonetic_split_support(buffer, threshold, word_evidence=split_words)
        if split and (best is None or split > best):
            best = split
            # A grouped sound match has two transcript tokens. The cue evidence
            # records both without treating either token alone as the match.
            partial = ()
            if word_evidence is not None:
                word_evidence[:] = split_words
        if best and include_partial:
            return (*best, partial)
        return best

    def phonetic_split_support(self, buffer, threshold, *, word_evidence=None):
        """Credit one grouped ASR pair given four other distinct exact words."""
        cue_length = len(self.anchor)
        if cue_length < 5:
            return None
        query = buffer[-(cue_length + 7):]
        best = None
        for end in range(len(query), max(cue_length, len(query) - 4), -1):
            start = end - cue_length - 1
            prefix = query[max(0, start - 3):start]
            if PROMPT_WORDS.intersection(prefix) and prefix != self.preceding[-len(prefix):]:
                continue
            heard = query[start:end]
            if PROMPT_WORDS.intersection(heard) - set(self.anchor):
                continue
            for i, word in enumerate(self.anchor):
                left, right = heard[i:i + 2]
                if (word in self.required or word in PROMPT_WORDS or {left, right} & PROMPT_WORDS
                        or word == left + right):
                    continue
                grouped = heard[:i] + [left + ' ' + right] + heard[i + 2:]
                context = [(expected, token) for j, (expected, token) in
                           enumerate(zip(self.anchor, grouped)) if j != i]
                if len({expected for expected, token in context if expected == token}) < 4:
                    continue
                if any(not similar(expected, token, 85 if expected in self.required else 75)
                       for expected, token in context):
                    continue
                if not phonetic_split_match(word, left, right):
                    continue
                credits = [fuzz.ratio(expected, token) / 100 for expected, token in context]
                credits.insert(i, .75)
                score = 100 * sum(credits) / cue_length
                if score < max(threshold, 100 * self.coverage) or (best and score <= best[0]):
                    continue
                best = (score, cue_length, cue_length)
                if word_evidence is not None:
                    word_evidence[:] = [
                        WordEvidence(expected, token, 'sound' if j == i else 'exact' if expected == token else 'spelling', credit)
                        for j, (expected, token, credit) in enumerate(zip(self.anchor, grouped, credits))
                    ]
        return best

    def _supports_anchor(self, buffer, *, allow_phonetic_endpoint=False,
                         allow_word_boundaries=False, phonetic_only=False, omitted_articles_only=False,
                         include_partial=False, word_evidence=None):
        # Only the recent anchor neighbourhood can grant effect permission.
        # A later passage position or an old occurrence elsewhere is insufficient.
        if omitted_articles_only and not self.has_omittable_articles:
            return None, None
        query = buffer[-max(12, len(self.anchor) + 8):]
        for end in range(len(query), max(0, len(query)-4), -1):
            if omitted_articles_only and query[end-1] != self.anchor[-1]:
                continue
            phonetic_endpoint = phonetic_only or not similar(self.anchor[-1], query[end-1])
            if phonetic_endpoint:
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
            if word_evidence is not None:
                word_evidence[:] = anchor_word_evidence(
                    self.anchor, window, [*pairs, (len(self.anchor)-1, len(window)-1)],
                    waive_articles=omitted_articles_only, phonetic_endpoint=phonetic_endpoint,
                )
            if include_partial and omitted_articles_only:
                offset = len(buffer) - len(query) + start
                partial = tuple((offset + j, self.anchor[i], None) for i, j in content
                                if self.anchor[i] != window[j])
                return (*article_support, partial), None
            if include_partial and phonetic_only:
                return ((len(buffer) - len(query) + end - 1, self.anchor[-1], .75),), None
            return (article_support if omitted_articles_only else True), None
        if allow_word_boundaries and self.supports_split_anchor(buffer, word_evidence=word_evidence):
            return True, None
        return (None if omitted_articles_only else False), 'one-shot requires recent ordered anchor, endpoint, and authored required words'

    def supports_split_anchor(self, buffer, *, word_evidence=None):
        return self.word_boundary_score(buffer, word_evidence=word_evidence) is not None

    def word_boundary_score(self, buffer, *, word_evidence=None):
        def word_credit(word, heard):
            if heard in PROMPT_WORDS and heard != word:
                return None
            if similar(word, heard, 85 if word in self.required else 75):
                return fuzz.ratio(word, heard) / 100
            return None

        best = max(((credit, groups) for prefix, credit, groups in
                    recent_boundary_matches(self.anchor, buffer, word_credit)
                    if not PROMPT_WORDS.intersection(prefix) or prefix == self.preceding[-len(prefix):]),
                   key=lambda result: result[0], default=None)
        if best is None:
            return None
        credit, groups = best
        if word_evidence is not None:
            word_evidence.clear()
            for expected, heard, group_credit in groups:
                if len(expected) != len(heard):
                    kind = 'split'
                else:
                    kind = 'exact' if expected == heard else 'spelling'
                word_evidence.append(WordEvidence(' '.join(expected), ' '.join(heard), kind, group_credit))
        return 100 * credit / len(self.anchor)
