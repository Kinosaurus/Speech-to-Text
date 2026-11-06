import unittest

from books_to_life.matching.effect_permission import EffectPermission
from books_to_life.matching.timely_matcher import TimelyEvidenceMatcher


INTRO = 'we walked across the old bridge'


def config(cue='one sheep was lost', required='lost', gap='', stability=2):
    tracking = cue + '. The lantern was bright.'
    text = INTRO + ' then ' + (gap + ' ' if gap else '') + tracking
    return dict(book_id='cues', threshold=82, stability=stability, min_coverage=.8,
        pages=[dict(page=1, text=text)], checkpoints=[
            dict(id='intro', book_id='cues', checkpoint_position=1,
                 checkpoint_text=INTRO, effect={}),
            dict(id='event', book_id='cues', checkpoint_position=2,
                 checkpoint_text=tracking, effect_cue=cue, required_words=[required], effect={})])


def feed(m, text, time, completed=False):
    return m.process(text, [dict(start=0, end=time, text=text, completed=completed)])


def acquire(m):
    feed(m, ' '.join(INTRO.split()[:4]), 1)
    assert feed(m, INTRO, 2).triggered


class EffectCueTests(unittest.TestCase):
    def test_cue_is_a_unique_contiguous_part_of_tracking_text(self):
        for cue in ('', None, ['one'], 'a completely different event', 'one was lost'):
            cfg = config(); cfg['checkpoints'][1]['effect_cue'] = cue
            with self.subTest(cue=cue), self.assertRaises(ValueError):
                TimelyEvidenceMatcher(cfg)
        cfg = config(); cfg['checkpoints'][1]['checkpoint_text'] += ' one sheep was lost'
        cfg['pages'][0]['text'] += ' one sheep was lost'
        with self.assertRaises(ValueError):
            TimelyEvidenceMatcher(cfg)

    def test_required_words_must_belong_to_effect_cue(self):
        cfg = config(); cfg['checkpoints'][1]['required_words'] = ['lantern']
        with self.assertRaises(ValueError):
            TimelyEvidenceMatcher(cfg)

    def test_interior_cue_keeps_book_position_and_negation_context(self):
        cp = dict(checkpoint_text='we never saw the small frog jump into the pond',
                  effect_cue='the small frog jump into the pond', required_words=['jump'])
        p = EffectPermission(cp, .8, ['before'])
        self.assertEqual(p.cue_offset, 3)
        self.assertEqual(p.preceding, ['we', 'never', 'saw'])
        self.assertTrue(p.permits('we never saw the small frog jump into the pond'.split())[0])
        self.assertFalse(p.permits('never say the small frog jump into the pond'.split())[0])

    def test_no_explicit_cue_preserves_original_boundary(self):
        cfg = config(); del cfg['checkpoints'][1]['effect_cue']
        m = TimelyEvidenceMatcher(cfg)
        self.assertEqual(tuple(m.checkpoint_ranges), m.tracking_checkpoint_ranges)

    def test_early_cue_uses_full_book_context_and_fires_once(self):
        m = TimelyEvidenceMatcher(config()); acquire(m)
        feed(m, INTRO + ' then one sheep was', 3)
        update = feed(m, INTRO + ' then one sheep was lost', 4)
        self.assertTrue(update.triggered)
        self.assertEqual(update.checkpoint_id, 'event')
        self.assertLess(m.checkpoint_ranges[1][1], m.tracking_checkpoint_ranges[1][1])
        self.assertFalse(feed(m, INTRO + ' then one sheep was lost again', 5).triggered)

    def test_bounded_acquisition_handles_different_pronunciations(self):
        for cue, heard, required in (
            ('one sheep was lost', 'one ship was lost', 'lost'),
            ('a small fan stopped', 'a small van stopped', 'stopped'),
            ('a red pen broke', 'a red pin broke', 'broke')):
            with self.subTest(cue=cue):
                m = TimelyEvidenceMatcher(config(cue, required)); acquire(m)
                self.assertLess(m.tracked_word_position, m.checkpoint_ranges[1][0])
                self.assertFalse(feed(m, heard + ' the', 3).triggered)
                self.assertTrue(feed(m, heard + ' the lantern', 4).triggered)

    def test_cold_or_distant_cue_cannot_acquire_by_sound(self):
        for distant in (False, True):
            m = TimelyEvidenceMatcher(config(gap=' '.join('unread'+str(i) for i in range(40)) if distant else ''))
            if distant:
                acquire(m)
            for t, text in enumerate(('one ship was lost the', 'one ship was lost the lantern'), 3):
                self.assertFalse(feed(m, text, t).triggered)

    def test_optional_cue_prefix_uses_confirmed_context_not_bare_suffix(self):
        for cue, heard, required in (
            ('one sheep was lost', 'sheep was lost', 'lost'),
            ('a small rabbit jumped', 'small rabbit jumped', 'jumped'),
            ('the red balloon popped', 'red balloon popped', 'popped')):
            with self.subTest(cue=cue):
                for prefix in ('', INTRO+' then ', INTRO+' thenxx '):
                    m = TimelyEvidenceMatcher(config(cue, required)); acquire(m)
                    self.assertFalse(feed(m, prefix+heard+' the lantern', 3).triggered)
                    self.assertTrue(feed(m, prefix+heard+' the lantern was', 4).triggered)
                p = EffectPermission(config(cue, required)['checkpoints'][1], .8, [])
                self.assertFalse(p.permits(heard.split())[0])
        m = TimelyEvidenceMatcher(config(required='one')); acquire(m)
        self.assertFalse(feed(m, 'sheep was lost the lantern', 3).triggered)
        self.assertFalse(feed(m, 'sheep was lost the lantern was', 4).triggered)

    def test_confirmation_requires_independent_updates_and_configured_count(self):
        m = TimelyEvidenceMatcher(config()); acquire(m)
        self.assertFalse(feed(m, 'one ship was lost the', 3).triggered)
        self.assertFalse(feed(m, 'one ship was lost the lantern', 3).triggered)
        m = TimelyEvidenceMatcher(config(stability=3))
        # Acquire ordinary book context using separate, progressing hypotheses.
        for t, n in enumerate((4, 5, 6), 1):
            feed(m, ' '.join(INTRO.split()[:n]), t)
        if m.current_index == 0:
            feed(m, INTRO + ' then', 4)
        for t, tail in ((5, 'the'), (6, 'the lantern')):
            self.assertFalse(feed(m, 'one ship was lost ' + tail, t).triggered)
        self.assertTrue(feed(m, 'one ship was lost the lantern was', 7).triggered)

    def test_missing_or_sound_substituted_essential_word_stays_off(self):
        for heard in ('one sheep was the lantern was bright', 'one sheep was locked the lantern was bright'):
            m = TimelyEvidenceMatcher(config()); acquire(m)
            self.assertFalse(feed(m, heard, 3).triggered)
            self.assertFalse(feed(m, heard + ' outside', 4, True).triggered)
            self.assertNotIn('event', m.triggered_checkpoint_ids)
        m = TimelyEvidenceMatcher(config('a small fan stopped', 'fan')); acquire(m)
        self.assertFalse(feed(m, 'a small van stopped the', 3).triggered)
        self.assertFalse(feed(m, 'a small van stopped the lantern', 4).triggered)

    def test_negation_and_two_sound_uncertainties_cannot_acquire(self):
        m = TimelyEvidenceMatcher(config()); acquire(m)
        for t, tail in ((3, 'the'), (4, 'the lantern')):
            self.assertFalse(feed(m, 'never say one ship was lost ' + tail, t).triggered)
        m = TimelyEvidenceMatcher(config('the sheep and fan stood still', 'stood')); acquire(m)
        self.assertFalse(feed(m, 'the ship and van stood still the', 3).triggered)
        self.assertFalse(feed(m, 'the ship and van stood still the lantern', 4).triggered)

    def test_revised_old_segment_cannot_impersonate_new_context(self):
        m = TimelyEvidenceMatcher(config()); acquire(m)
        segments = [dict(start=0, end=3, text='one ship was lost the', completed=True),
                    dict(start=3, end=4, text='some unrelated conversation about breakfast', completed=False)]
        self.assertFalse(m.process(' '.join(s['text'] for s in segments), segments).triggered)
        segments[0]['text'] += ' lantern'
        segments[1]['end'] = 5
        self.assertFalse(m.process(' '.join(s['text'] for s in segments), segments).triggered)


if __name__ == '__main__':
    unittest.main()
