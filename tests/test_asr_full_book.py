import unittest

from benchmarks.compare_book_asr import full_book_hints
from benchmarks.metrics import words
from books_to_life.runtime.nemo_parakeet import hint_phrases


class FullBookHintTests(unittest.TestCase):
    def test_preserves_all_words_and_repetitions_without_selecting_checkpoints(self):
        text = '"Yes, yes", said the mouse.\nShe hung up the phone.\nWho are you?'
        hints = full_book_hints(text)
        self.assertEqual(words(hints), words(text))
        self.assertIn('hung up the phone', hints)
        self.assertEqual(len(hint_phrases(hints)), 3)

    def test_splits_long_sentences_without_losing_words(self):
        text = ' '.join('garden' for _ in range(100)) + '.'
        hints = full_book_hints(text)
        self.assertTrue(all(len(phrase) <= 200 for phrase in hint_phrases(hints)))
        self.assertGreater(len(hint_phrases(hints)), 1)
        self.assertEqual(words(hints), words(text))

    def test_excessive_book_is_rejected_instead_of_silently_truncated(self):
        with self.assertRaises(ValueError):
            full_book_hints(' '.join(f'Sentence {i}.' for i in range(33)))

    def test_empty_book_is_rejected(self):
        with self.assertRaises(ValueError):
            full_book_hints('  ... ')
