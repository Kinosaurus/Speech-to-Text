import json
from pathlib import Path
import unittest
from books_to_life.matching.split_matcher import SplitEvidenceMatcher,split_similarity
ROOT=Path(__file__).resolve().parents[1]

def ready():
 m=SplitEvidenceMatcher(json.loads((ROOT/'recordings/library/stories/tea/readers/tea/checkpoints.json').read_text()))
 text='I will make us a pot of tea'
 m.process(text, [{'start':0,'end':10,'text':text,'completed':False}])
 m.process(text, [{'start':0,'end':10,'text':text,'completed':True}])
 assert m.current_index==1
 return m

def feed(m,text,end):
 return m.process(text,[{'start':11,'end':end,'text':text,'completed':False}])

class SplitTests(unittest.TestCase):
 def test_split_boundary_confirms_without_following_words(self):
  for variant in ['key pot','key put']:
   m=ready()
   self.assertFalse(feed(m,'see put the '+variant+' on the',20).triggered)
   self.assertFalse(feed(m,'see put the '+variant+' on the st',21).triggered)
   u=feed(m,'see put the '+variant+' on the stove',22)
   self.assertTrue(u.triggered)
   self.assertEqual(u.checkpoint_id,'teapot_on_stove')
 def test_requires_prior_acquisition(self):
  m=SplitEvidenceMatcher(json.loads((ROOT/'recordings/library/stories/tea/readers/tea/checkpoints.json').read_text()))
  feed(m,'see put the key pot on the',20)
  self.assertFalse(feed(m,'see put the key pot on the stove',22).triggered)
 def test_no_trigger_from_one_hypothesis_or_duplicates(self):
  m=ready()
  for _ in range(4):
   self.assertFalse(feed(m,'see put the key pot on the stove',22).triggered)
 def test_reject_negation_prompt_and_wrong_objects(self):
  for prefix in ['do not','never','can you say','please repeat','she said']:
   m=ready()
   feed(m,prefix+' see put the key pot on the',20)
   self.assertFalse(feed(m,prefix+' see put the key pot on the stove',22).triggered)
  for noun in ['cups','phone','cat']:
   m=ready();feed(m,'see put the '+noun+' on the',20)
   self.assertFalse(feed(m,'see put the '+noun+' on the stove',22).triggered)
 def test_old_prefix_cannot_confirm(self):
  m=ready();feed(m,'see put the key pot on the',20)
  self.assertFalse(feed(m,'see put the key pot on the stove',40).triggered)
 def test_prefix_on_same_audio_cannot_confirm(self):
  m=ready();feed(m,'see put the key pot on the',20)
  self.assertFalse(feed(m,'see put the key pot on the stove',20).triggered)
 def test_generic_exact_split_compound(self):
  self.assertEqual(split_similarity('sun','flower','sunflower'),.9)
  self.assertEqual(split_similarity('any','thing','teapot'),0)
if __name__=='__main__':unittest.main()
