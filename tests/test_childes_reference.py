import unittest

from benchmarks.run_childes_streaming import clean_chat,main_tiers


class ChildesReferenceTests(unittest.TestCase):
    def test_dependent_tier_continuations_cannot_become_spoken_words(self):
        text=('\ufeff@UTF8\n*STA:\tthe child says\n\tthis again . \x151000_2000\x15\n'
              '%mor:\tnoun|child\n\tverb|fake_hidden_annotation\n'
              '%wor:\tincorrect \x151000_2000\x15\n*IVA:\twe heard it .\n')
        rows=main_tiers(text)
        self.assertEqual([r['clean'] for r in rows],['the child says this again','we heard it'])
        self.assertEqual(rows[0]['span_ms'],[1000,2000])

    def test_actual_repetitions_and_negation_are_retained(self):
        self.assertEqual(clean_chat("you [/] you don't need xxx never_mind (..) okay . \x151_2000\x15"),
                         "you you don't need never mind okay")
        self.assertEqual(clean_chat('<everybody can see> [/] everybody can see .'),
                         'everybody can see everybody can see')

    def test_annotation_words_and_unintelligible_spans_are_not_reference_words(self):
        self.assertEqual(clean_chat('draw &~yah@i here [+ bch] www +...'), 'draw here')


if __name__=='__main__':unittest.main()
