import unittest

from books_to_life.matching.phonetic_endpoint import phonetic_endpoint_match
from books_to_life.matching.phone_features import CONSONANTS, VOWELS
import cmudict


class PhoneticEndpointTests(unittest.TestCase):
    def test_pronunciation_comparison_is_not_tied_to_one_word_pair(self):
        for reference, heard in [('scales', 'cells'), ('rough', 'ruff'),
                                 ('stairs', 'stares'), ('scene', 'seen'),
                                 ('weight', 'wait'), ('crane', 'cane'),
                                 ('plates', 'pates')]:
            with self.subTest(reference=reference, heard=heard):
                self.assertTrue(phonetic_endpoint_match(reference, heard))

    def test_wrong_onsets_endings_and_excessive_edits_are_rejected(self):
        for reference, heard in [('scales', 'coils'), ('scales', 'birds'),
                                 ('bush', 'burst'), ('bright', 'night'),
                                 ('can', 'cant'), ('thick', 'thin'),
                                 ('string', 'sing'), ('enemies', 'a'),
                                 ('hibernate', 'from')]:
            with self.subTest(reference=reference, heard=heard):
                self.assertFalse(phonetic_endpoint_match(reference, heard))

    def test_unknown_words_have_no_inferred_pronunciation(self):
        for reference, heard in [('zzqnotaword', 'cells'), ('scales', 'zzqnotaword'), ('scales', '')]:
            with self.subTest(reference=reference, heard=heard):
                self.assertFalse(phonetic_endpoint_match(reference, heard))

    def test_articulatory_route_spans_multiple_sound_classes(self):
        for reference, heard in [('sheep', 'chip'), ('coat', 'goat'),
                                 ('fan', 'van'), ('seal', 'zeal'), ('full', 'fool')]:
            with self.subTest(reference=reference, heard=heard):
                self.assertTrue(phonetic_endpoint_match(reference, heard))

    def test_articulatory_route_cannot_supply_gaps_or_a_missing_final_sound(self):
        for reference, heard in [('sheep', 'she'), ('sheep', 'cheaply'),
                                 ('sheep', 'beep'), ('coat', 'cone'),
                                 ('fan', 'fat'), ('seal', 'seat'), ('full', 'foot')]:
            with self.subTest(reference=reference, heard=heard):
                self.assertFalse(phonetic_endpoint_match(reference, heard))

    def test_feature_inventory_covers_dictionary_phones(self):
        with cmudict.phones_stream() as stream:
            phones = {line.decode('ascii').split()[0] for line in stream}
        self.assertEqual(set(CONSONANTS) | set(VOWELS), phones)


if __name__ == '__main__':
    unittest.main()
