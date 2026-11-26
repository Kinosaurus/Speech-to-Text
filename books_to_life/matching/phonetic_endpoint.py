"""Conservative dictionary-based endpoint comparison; no book-specific aliases."""
from functools import lru_cache

import cmudict
from books_to_life.matching.phone_features import close_phone_features, close_pronunciation_features


VOWELS = frozenset('AA AE AH AO AW AY EH ER EY IH IY OW OY UH UW'.split())
DEVOICED_STOP_SIBILANT = {
    ('B', 'Z'): ('P', 'S'),
    ('D', 'Z'): ('T', 'S'),
    ('G', 'Z'): ('K', 'S'),
}


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


@lru_cache(maxsize=8192)
def phonetic_word_credit(reference, heard):
    """Score sound-alikes for a phrase whose other words corroborate the cue."""
    if reference == heard:
        return 0.0
    expected_phones, heard_phones = pronunciations(reference), pronunciations(heard)
    if set(expected_phones).intersection(heard_phones) or phonetic_endpoint_match(reference, heard):
        return .75
    credit = 0.0
    for expected in expected_phones:
        for actual in heard_phones:
            # Some Singapore English speakers overlap DRESS and TRAP vowels
            # and weaken final voicing. Credit this combination in a phrase
            # when the onset and the final consonants' place and manner agree.
            if (len(expected) == len(actual) and len(expected) >= 4
                    and expected[:-3] == actual[:-3] and expected[-4] not in VOWELS
                    and {expected[-3], actual[-3]} == {'AE', 'EH'}
                    and (DEVOICED_STOP_SIBILANT.get(expected[-2:]) == actual[-2:]
                         or DEVOICED_STOP_SIBILANT.get(actual[-2:]) == expected[-2:])):
                return .75
            if (min(len(expected), len(actual)) >= 3
                    and expected[0] == actual[0] and expected[0] not in VOWELS
                    and (expected[-1] == actual[-1] or (
                        expected[-1] not in VOWELS and actual[-1] not in VOWELS
                        and close_phone_features(expected[-1], actual[-1])))
                    and _distance(expected, actual, vowel_cost=.25) <= 2.25):
                credit = .5
    return credit


@lru_cache(maxsize=8192)
def phonetic_split_match(reference, left, right):
    """Compare one book word with the combined sounds of two ASR words."""
    for expected in pronunciations(reference):
        if len(expected) < 5:
            continue
        expected_consonants = tuple(phone for phone in expected if phone not in VOWELS)
        for first in pronunciations(left):
            for second in pronunciations(right):
                actual = first + second
                if (abs(len(expected) - len(actual)) > 1
                        or expected[:2] != actual[:2] or expected[-2:] != actual[-2:]):
                    continue
                actual_consonants = tuple(phone for phone in actual if phone not in VOWELS)
                if _distance(expected_consonants, actual_consonants) > 1:
                    continue
                distance = _distance(expected, actual, vowel_cost=.25)
                if distance <= 2.25 and distance <= max(len(expected), len(actual)) / 3:
                    return True
    return False
