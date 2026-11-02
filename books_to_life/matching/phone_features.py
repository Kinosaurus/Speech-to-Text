"""Coarse articulatory features for the complete CMU English phone inventory.

These are phoneme categories, not word substitutions or learned ASR confusion
probabilities. Stress is removed by the pronunciation lookup before use.
"""

# Consonants: sonorant, place, manner, voiced.
CONSONANTS = {
    'B': (False, 'bilabial', 'stop', True),
    'CH': (False, 'postalveolar', 'affricate', False),
    'D': (False, 'alveolar', 'stop', True),
    'DH': (False, 'dental', 'fricative', True),
    'F': (False, 'labiodental', 'fricative', False),
    'G': (False, 'velar', 'stop', True),
    'HH': (False, 'glottal', 'fricative', False),
    'JH': (False, 'postalveolar', 'affricate', True),
    'K': (False, 'velar', 'stop', False),
    'L': (True, 'alveolar', 'lateral', True),
    'M': (True, 'bilabial', 'nasal', True),
    'N': (True, 'alveolar', 'nasal', True),
    'NG': (True, 'velar', 'nasal', True),
    'P': (False, 'bilabial', 'stop', False),
    'R': (True, 'postalveolar', 'approximant', True),
    'S': (False, 'alveolar', 'fricative', False),
    'SH': (False, 'postalveolar', 'fricative', False),
    'T': (False, 'alveolar', 'stop', False),
    'TH': (False, 'dental', 'fricative', False),
    'V': (False, 'labiodental', 'fricative', True),
    'W': (True, 'labiovelar', 'approximant', True),
    'Y': (True, 'palatal', 'approximant', True),
    'Z': (False, 'alveolar', 'fricative', True),
    'ZH': (False, 'postalveolar', 'fricative', True),
}

# Vowels: height, backness, rounded, tense, rhotic, glide destination.
VOWELS = {
    'AA': ('low', 'back', False, False, False, None),
    'AE': ('low', 'front', False, False, False, None),
    'AH': ('mid', 'central', False, False, False, None),
    'AO': ('mid', 'back', True, False, False, None),
    'AW': ('low', 'back', False, False, False, 'UW'),
    'AY': ('low', 'back', False, False, False, 'IY'),
    'EH': ('mid', 'front', False, False, False, None),
    'ER': ('mid', 'central', False, False, True, None),
    'EY': ('mid', 'front', False, True, False, 'IY'),
    'IH': ('high', 'front', False, False, False, None),
    'IY': ('high', 'front', False, True, False, None),
    'OW': ('mid', 'back', True, True, False, 'UW'),
    'OY': ('mid', 'back', True, False, False, 'IY'),
    'UH': ('high', 'back', True, False, False, None),
    'UW': ('high', 'back', True, True, False, None),
}


def close_phone_features(expected, actual):
    """Each changed phone differs by exactly one feature within its class."""
    for inventory in (CONSONANTS, VOWELS):
        if expected in inventory and actual in inventory:
            return sum(a != b for a, b in zip(inventory[expected], inventory[actual])) == 1
    return False


def close_pronunciation_features(expected, actual):
    """Same length and final phone; <=2 substitutions, <=1 consonant change.

No phone insertion/deletion, vowel/consonant interchange, or multi-feature
substitution is supported. At least two consonants and a consonantal onset
are required, as in the original contextual phonetic route.
"""
    if (len(expected) != len(actual) or len(expected) < 3
            or expected[0] not in CONSONANTS or actual[0] not in CONSONANTS
            or expected[-1] != actual[-1]
            or min(sum(p in CONSONANTS for p in expected),
                   sum(p in CONSONANTS for p in actual)) < 2):
        return False
    changes = [(a, b) for a, b in zip(expected, actual) if a != b]
    return (1 <= len(changes) <= 2
            and sum(a in CONSONANTS for a, _ in changes) <= 1
            and all(close_phone_features(a, b) for a, b in changes))
