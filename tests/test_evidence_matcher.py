import unittest
from books_to_life.matching.evidence_matcher import EvidenceAlignmentMatcher

def manifest():
 return {'book_id':'test','title':'test','threshold':82,'stability':2,'min_coverage':.8,'pages':[{'page':1,'text':'alpha bravo cedar delta eagle forest garden harbor island jungle'}],'checkpoints':[{'id':'scene','book_id':'test','checkpoint_position':1,'checkpoint_text':'alpha bravo cedar delta eagle','effect':{'effect_id':'test'}}]}
def seg(text,end,completed=False):
 return [{'start':0,'end':end,'text':text,'completed':completed}]
class EvidenceTests(unittest.TestCase):
 def test_noise_does_not_erase_candidate(self):
  m=EvidenceAlignmentMatcher(manifest())
  self.assertFalse(m.process('',seg('alpha bravo cedar delta eagle',5)).triggered)
  self.assertFalse(m.process('',seg('unrelated words nowhere in this book',6)).triggered)
  self.assertTrue(m.process('',seg('alpha bravo cedar delta eagle forest',7)).triggered)
 def test_same_words_new_timestamp_do_not_confirm(self):
  m=EvidenceAlignmentMatcher(manifest())
  for end in range(1,10):
   self.assertFalse(m.process('',seg('alpha bravo cedar delta eagle',end)).triggered)
 def test_strong_boundary_match_can_confirm_on_completion(self):
  m=EvidenceAlignmentMatcher(manifest()); text='alpha bravo cedar delta eagle'
  m.process('',seg(text,5))
  self.assertTrue(m.process('',seg(text,5,True)).triggered)
  self.assertFalse(m.process('',seg(text,5,True)).triggered)
 def test_revisions_same_audio_do_not_confirm(self):
  m=EvidenceAlignmentMatcher(manifest())
  m.process('',seg('alpha bravo cedar delta eagle',5))
  self.assertFalse(m.process('',seg('alpha bravo cedar delta eagle forest',5)).triggered)
 def test_expired_evidence_needs_new_confirmation(self):
  m=EvidenceAlignmentMatcher(manifest())
  m.process('',seg('alpha bravo cedar delta eagle',5))
  self.assertFalse(m.process('',seg('alpha bravo cedar delta eagle forest',30)).triggered)
 def test_off_book_and_duplicates_never_trigger(self):
  m=EvidenceAlignmentMatcher(manifest())
  for end in range(1,20):
   self.assertFalse(m.process('',seg('please open the door and bring some water',end)).triggered)
 def test_revised_strong_boundary_match_needs_no_later_book_words(self):
  m=EvidenceAlignmentMatcher(manifest())
  m.process('',seg('oh alpha bravo cedar delta eagle',5))
  self.assertTrue(m.process('',seg('alpha bravo cedar delta eagle',6)).triggered)
 def test_final_book_word_can_confirm(self):
  cfg=manifest();cfg['pages'][0]['text']='alpha bravo cedar delta eagle'
  m=EvidenceAlignmentMatcher(cfg)
  m.process('',seg('alpha bravo cedar delta eagle',5))
  self.assertTrue(m.process('',seg('alpha bravo cedar delta eagle',5,True)).triggered)
 def test_identical_callback_never_confirms(self):
  m=EvidenceAlignmentMatcher(manifest());text='alpha bravo cedar delta eagle'
  for _ in range(20):
   self.assertFalse(m.process('',seg(text,5)).triggered)
 def test_weak_same_position_completion_does_not_confirm(self):
  m=EvidenceAlignmentMatcher(manifest());text='alpha bravo cedar delta eaglet'
  m.process('',seg(text,5))
  # A candidate below the strong-stability threshold cannot use finalization.
  m._threshold = lambda scene, recovering: 100
  self.assertFalse(m.process('',seg(text,5,True)).triggered)
if __name__=='__main__':unittest.main()
