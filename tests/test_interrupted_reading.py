import unittest
from books_to_life.matching.timely_matcher import TimelyEvidenceMatcher


class InterruptedReadingTests(unittest.TestCase):
    def setup_reader(self, required=None, repeated=False, phrase='they can smell very well and are very clever'):
        context='we came to the meadow and '
        text=context+phrase+(' later they can walk home' if repeated else '')
        cfg=dict(book_id='interrupted',threshold=82,stability=2,min_coverage=.8,
            pages=[dict(page=1,text=text)],checkpoints=[dict(id='target',book_id='interrupted',checkpoint_position=1,
                checkpoint_text=phrase,required_words=required or [],effect={'effect_id':'target'})])
        matcher=TimelyEvidenceMatcher(cfg)
        self.update(matcher,.5,context)
        self.update(matcher,1,context+phrase.split()[0])
        self.update(matcher,2,context+' '.join(phrase.split()[:2]))
        head=context+' '.join(phrase.split()[:2])+' please bring the blue notebook from the kitchen'
        self.update(matcher,3,head)
        return matcher,head

    def update(self,matcher,time,text,prior=None):
        segments=[] if prior is None else [dict(start=0,end=4,text=prior,completed=True)]
        segments.append(dict(start=0 if prior is None else 5,end=time,text=text,completed=False))
        return matcher.process(' '.join(s['text'] for s in segments),segments)

    def test_observed_prefix_and_resumed_phrase_count_across_aside(self):
        matcher,head=self.setup_reader()
        self.update(matcher,7,'smell well well and are very',head)
        first=self.update(matcher,8,'smell well well and are very clever',head)
        # The independently observed partial continuation can confirm its later
        # endpoint through the existing boundary-evidence route.
        second=self.update(matcher,9,'smell well well and are very clever today',head)
        self.assertEqual(sum(u.triggered for u in (first,second)),1)
        self.assertFalse(self.update(matcher,10,'smell well well and are very clever today again',head).triggered)

    def test_missing_internal_required_word_and_endpoint_are_not_invented(self):
        for tail,required in [('well and are very clever',None),
                              ('smell well well and are very',None),
                              ('smell very and are very clever',['well'])]:
            matcher,head=self.setup_reader(required)
            self.assertFalse(self.update(matcher,8,tail,head).triggered)
            self.assertFalse(self.update(matcher,9,tail+' today',head).triggered)

    def test_expired_or_ambiguous_prefix_cannot_support_resume(self):
        for repeated,time in ((False,16),(True,8)):
            matcher,head=self.setup_reader(repeated=repeated)
            self.assertFalse(self.update(matcher,time,'smell well well and are very clever',head).triggered)
            self.assertFalse(self.update(matcher,time+1,'smell well well and are very clever today',head).triggered)

    def test_retracted_prefix_cannot_survive_revision(self):
        matcher,head=self.setup_reader()
        revised=head.replace('they can','someone else')
        self.update(matcher,4,revised)
        self.assertFalse(self.update(matcher,8,'smell well well and are very clever',revised).triggered)
        self.assertFalse(self.update(matcher,9,'smell well well and are very clever today',revised).triggered)

    def test_negated_aside_abandons_reading_evidence(self):
        matcher,head=self.setup_reader()
        head+=' do not say that'
        self.update(matcher,4,head)
        self.assertFalse(self.update(matcher,8,'smell well well and are very clever',head).triggered)

    def test_timestamp_only_callbacks_cannot_supply_extra_confirmation(self):
        matcher,head=self.setup_reader()
        tail='smell well well and are very clever'
        self.assertFalse(self.update(matcher,8,tail,head).triggered)
        self.assertFalse(self.update(matcher,9,tail,head).triggered)

    def test_unrelated_updates_do_not_consume_reading_evidence(self):
        matcher,head=self.setup_reader()
        for i in range(16):
            self.update(matcher,3+i/8,head+' unrelated'+(' words'*i))
        prior=matcher._segments[-1]['text']
        self.update(matcher,7,'smell well well and are very',prior)
        first=self.update(matcher,8,'smell well well and are very clever',prior)
        second=self.update(matcher,9,'smell well well and are very clever today',prior)
        self.assertEqual(sum(u.triggered for u in (first,second)),1)

    def test_different_story_words_use_the_same_interruption_rule(self):
        matcher,head=self.setup_reader(phrase='she gently placed the blue lantern on the table')
        first=self.update(matcher,8,'placed the blue lantern on the table',head)
        second=self.update(matcher,9,'placed the blue lantern on the table today',head)
        self.assertEqual(sum(u.triggered for u in (first,second)),1)
