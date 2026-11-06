import unittest

from books_to_life.matching.timely_matcher import TimelyEvidenceMatcher


ANCHOR = 'the silver lantern shone beside the doorway'


def config(anchor=ANCHOR, later=False, stability=2, repeat_prefix=False):
    intro='we crossed the bridge before sunrise'
    text=(intro+' then ' if later else '')+anchor+' and walked home'
    if repeat_prefix:text+=' then '+ ' '.join(anchor.split()[:4])+' again'
    phrases=[intro,anchor] if later else [anchor]
    cfg=dict(book_id='prefix',threshold=82,stability=stability,min_coverage=.8,
        pages=[dict(page=1,text=text)],checkpoints=[])
    tokens=text.split()
    for index,phrase in enumerate(phrases,1):
        words=phrase.split();start=next(i for i in range(len(tokens)) if tokens[i:i+len(words)]==words)
        cfg['checkpoints'].append(dict(id=str(index),book_id='prefix',checkpoint_position=index,
            checkpoint_text=phrase,word_start=start,word_end=start+len(words),effect={}))
    return cfg


def feed(m,text,time,start=0,completed=False):
    return m.process(text,[dict(start=start,end=time,text=text,completed=completed)])


class PrefixConfirmationTests(unittest.TestCase):
    def test_exact_unaligned_prefix_can_confirm_a_fresh_complete_anchor(self):
        for anchor in (ANCHOR,'brown squirrel waits beside the garden gate',
                       'winter animals sleep from autumn until spring'):
            with self.subTest(anchor=anchor):
                m=TimelyEvidenceMatcher(config(anchor))
                self.assertFalse(feed(m,' '.join(anchor.split()[:4]),1).triggered)
                self.assertEqual(m.tracked_word_position,0)
                self.assertTrue(feed(m,anchor,2).triggered)
                self.assertFalse(feed(m,anchor,3).triggered)

    def test_partial_final_token_and_later_scene_recovery_are_general(self):
        for anchor,partial in [(ANCHOR,'door'),
                               ('bright birds circled above the meadow','mea')]:
            m=TimelyEvidenceMatcher(config(anchor,later=True))
            prefix=' '.join(anchor.split()[:-1])+' '+partial
            self.assertFalse(feed(m,prefix,1).triggered)
            update=feed(m,anchor,2)
            self.assertTrue(update.triggered)
            self.assertEqual(update.checkpoint_id,'2')
            self.assertEqual(update.skipped_checkpoint_ids,('1',))

    def test_one_full_hypothesis_or_timestamp_only_updates_do_not_confirm(self):
        m=TimelyEvidenceMatcher(config())
        for time in range(1,8):
            self.assertFalse(feed(m,ANCHOR,time).triggered)
        m=TimelyEvidenceMatcher(config())
        prefix=' '.join(ANCHOR.split()[:4])
        feed(m,prefix,1)
        self.assertFalse(feed(m,ANCHOR,1).triggered)

    def test_silence_expiry_and_repeated_prefix_updates_do_not_refresh_evidence(self):
        prefix=' '.join(ANCHOR.split()[:4])
        m=TimelyEvidenceMatcher(config());feed(m,prefix,1)
        self.assertFalse(feed(m,ANCHOR,30).triggered)
        m=TimelyEvidenceMatcher(config());feed(m,prefix,1)
        for i in range(1,14):self.assertFalse(feed(m,prefix,1+i*.01).triggered)
        self.assertFalse(feed(m,ANCHOR,2).triggered)

    def test_omitted_or_wrong_words_cannot_use_the_exact_completion_route(self):
        prefix=' '.join(ANCHOR.split()[:4])
        for text in ('the silver lantern shone beside the',
                     'the silver lantern beside the doorway',
                     'the silver lantern shone beside the kitchen',
                     'the silver lantern shone beside the doorways'):
            with self.subTest(text=text):
                m=TimelyEvidenceMatcher(config());feed(m,prefix,1)
                self.assertFalse(feed(m,text,2).triggered)

    def test_unrelated_continuation_or_contradictory_revision_abandons_prefix(self):
        prefix=' '.join(ANCHOR.split()[:4])
        for text in (prefix+' please bring water','we discussed a completely different subject'):
            m=TimelyEvidenceMatcher(config());feed(m,prefix,1);feed(m,text,2)
            self.assertFalse(feed(m,ANCHOR,3).triggered)

    def test_new_segment_cannot_borrow_an_old_incomplete_prefix(self):
        m=TimelyEvidenceMatcher(config());feed(m,' '.join(ANCHOR.split()[:4]),1)
        self.assertFalse(feed(m,ANCHOR,3,start=2).triggered)

    def test_new_partial_segment_cannot_reacquire_retained_prefix_words(self):
        m=TimelyEvidenceMatcher(config())
        feed(m,'the silver lantern shone',1,completed=True)
        feed(m,'bes',3,start=2)
        self.assertIsNone(m._confirmation_prefix)
        self.assertFalse(feed(m,'beside the doorway',4,start=2).triggered)

    def test_revising_an_older_segment_does_not_refresh_latest_prefix(self):
        m=TimelyEvidenceMatcher(config());prefix='the silver lantern shone'
        old=dict(start=0,end=1,text='some unrelated earlier speech',completed=True)
        latest=dict(start=2,end=3,text=prefix,completed=False)
        m.process('',[old,latest]);self.assertEqual(m._confirmation_prefix['time'],3)
        old=dict(old,text='revised unrelated earlier speech')
        m.process('',[old,dict(latest,end=4)])
        self.assertEqual(m._confirmation_prefix['time'],3)
        self.assertFalse(feed(m,ANCHOR,20,start=2).triggered)

    def test_repeated_book_prefix_or_negation_does_not_supply_credit(self):
        prefix=' '.join(ANCHOR.split()[:4])
        m=TimelyEvidenceMatcher(config(repeat_prefix=True));feed(m,prefix,1)
        self.assertFalse(feed(m,ANCHOR,2).triggered)

    def test_prior_completed_negation_cannot_poison_a_new_clean_prefix(self):
        m=TimelyEvidenceMatcher(config())
        prior=dict(start=0,end=1,text='never mention the old broken window',completed=True)
        prefix=' '.join(ANCHOR.split()[:4])
        self.assertFalse(m.process('',[prior,dict(start=2,end=3,text=prefix,completed=False)]).triggered)
        self.assertTrue(m.process('',[prior,dict(start=2,end=4,text=ANCHOR,completed=True)]).triggered)
        m=TimelyEvidenceMatcher(config());feed(m,'never repeat '+prefix,1)
        self.assertFalse(feed(m,ANCHOR,2).triggered)

    def test_ambiguity_clears_prefix_and_three_votes_still_requires_three(self):
        prefix=' '.join(ANCHOR.split()[:4])
        m=TimelyEvidenceMatcher(config());feed(m,prefix,1);m._reject_candidate(True)
        self.assertFalse(feed(m,ANCHOR,2).triggered)
        m=TimelyEvidenceMatcher(config(stability=3));feed(m,prefix,1)
        update=feed(m,ANCHOR,2)
        self.assertFalse(update.triggered);self.assertEqual(update.confirmations,2)
        self.assertTrue(feed(m,ANCHOR+' and',3).triggered)


if __name__=='__main__':unittest.main()
