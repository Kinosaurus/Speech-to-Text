"""Conservative dictionary-based endpoint comparison; no book-specific aliases."""
from functools import lru_cache

import cmudict
from books_to_life.matching.phone_features import close_pronunciation_features


VOWELS = frozenset('AA AE AH AO AW AY EH ER EY IH IY OW OY UH UW'.split())


@lru_cache(maxsize=1)
def _dictionary():
    return cmudict.dict()


@lru_cache(maxsize=8192)
def pronunciations(word):
    return tuple(tuple(phone.rstrip('012') for phone in phones)
                 for phones in _dictionary().get(word, ()))


def _distance(left, right, vowel_cost=1.0):
    previous = list(range(len(right) + 1))
    for i, a in enumerate(left, 1):
        current = [i]
        for j, b in enumerate(right, 1):
            substitution = 0 if a == b else vowel_cost if a in VOWELS and b in VOWELS else 1
            current.append(min(previous[j] + 1, current[j-1] + 1, previous[j-1] + substitution))
        previous = current
    return previous[-1]


@lru_cache(maxsize=8192)
def phonetic_endpoint_match(reference, heard):
    """Dictionary-based structural or articulatory endpoint support.

    Vowel substitutions cost 0.25, other edits cost 1. The total must be at
    most 1.25 and at most 25% of the longer pronunciation. This deliberately
    tolerates some pronunciation/ASR variants only under the caller's strong
    exact-context and prior-acquisition checks. A second route supports equal
    length pronunciations with the same last phone and at most two one-feature
    substitutions, at most one consonantal. It permits no phone gaps. These are
    text/lexicon heuristics, not acoustic verification. Unknown words fail closed.
    """
    for expected in pronunciations(reference):
        for actual in pronunciations(heard):
            if close_pronunciation_features(expected, actual):
                return True
            if (min(len(expected), len(actual)) < 3 or expected[0] in VOWELS
                    or expected[0] != actual[0] or expected[-2:] != actual[-2:]):
                continue
            consonants = tuple(p for p in expected if p not in VOWELS)
            heard_consonants = tuple(p for p in actual if p not in VOWELS)
            if min(len(consonants), len(heard_consonants)) < 2:
                continue
            if _distance(consonants, heard_consonants) > 1:
                continue
            distance = _distance(expected, actual, vowel_cost=.25)
            if distance <= 1.25 and distance <= .25 * max(len(expected), len(actual)):
                return True
    return False
