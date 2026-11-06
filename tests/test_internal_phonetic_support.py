import unittest

from books_to_life.matching.effect_permission import EffectPermission
from books_to_life.matching.timely_matcher import TimelyEvidenceMatcher


class InternalPhoneticTests(unittest.TestCase):
    def permission(self, phrase, required=()):
        return EffectPermission(dict(checkpoint_text=phrase,required_words=list(required)),.8,[])

    def test_same_rule_handles_different_internal_pronunciations(self):
        for reference,heard in [
            ('the young sheep stood beside the wooden gate','the young ship stood above the wooden gate'),
            ('a small fan stood beside the wooden door','a small van stood under the wooden door'),
            ('the old full bucket stood beside the fence','the old fool bucket lay beside the fence'),
            ('she carried a red pen into the room','she pushed a red pin into the room')]:
            with self.subTest(reference=reference):
                p=self.permission(reference)
                self.assertFalse(p.permits(heard.split())[0])
                self.assertTrue(p.permits(heard.split(),allow_phonetic_internal=True)[0])

    def test_missing_word_cannot_supply_an_observed_phonetic_token(self):
        p=self.permission('a small fan stood beside the wooden door')
        for heard in ('a small stood under the wooden door',
                      'a small stood beside the door',
                      'a small xqzz stood under the wooden door'):
            self.assertFalse(p.permits(heard.split(),allow_phonetic_internal=True)[0])

    def test_required_words_keep_stricter_spelling_support(self):
        p=self.permission('a small fan stood beside the wooden door',['fan'])
        self.assertFalse(p.permits('a small van stood under the wooden door'.split(),
                                  allow_phonetic_internal=True)[0])

    def test_two_eligible_sound_substitutions_are_ambiguous(self):
        p=self.permission('the small sheep stood beside a red fan today')
        self.assertFalse(p.permits('the small ship stood beside a red van today'.split(),
                                  allow_phonetic_internal=True)[0])

    def test_uncertain_endpoint_or_neighbours_cannot_stack_extra_credit(self):
        p=self.permission('a small fan stood beside the wooden door')
        for heard in ('a small van waited beside the wooden door',
                      'a small van stood under the wooden doors',
                      'a small van beside the wooden door'):
            self.assertFalse(p.permits(heard.split(),allow_phonetic_internal=True)[0])

    def test_negation_still_vetoes_a_supported_phrase(self):
        p=self.permission('a small fan stood beside the wooden door')
        self.assertFalse(p.permits('never say a small van stood under the wooden door'.split(),
                                  allow_phonetic_internal=True)[0])

    def test_production_gate_requires_previous_acquisition_and_normal_anchor_length(self):
        phrase='the young sheep stood beside the wooden gate'
        cfg=dict(book_id='internal',threshold=82,stability=1,min_coverage=.8,
            pages=[dict(page=1,text=phrase)],checkpoints=[dict(id='anchor',book_id='internal',
                checkpoint_position=1,checkpoint_text=phrase,effect={})])
        matcher=TimelyEvidenceMatcher(cfg)
        update=matcher.process('the young ship stood above the wooden gate')
        self.assertFalse(update.triggered)
