"""Diagnostic only: explicit Tea alias, not installed in either tracker."""
import json,re,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from evidence_matcher import EvidenceAlignmentMatcher
from checkpoint_matcher import normalize_text
root=Path(__file__).resolve().parents[1]
manifest=json.loads((root/'recordings/library/stories/tea/readers/tea/checkpoints.json').read_text())
def phrase(text):
 words=normalize_text(text).split()
 # Bounded recent context; retain negation guard beyond the matched phrase.
 tail=' '.join(words[-16:])
 if set(words[-16:]) & {'not','never','dont','no'}:return False
 # Explicit exploratory alias. No global token replacement.
 return re.search(r'(?:she|see) put the (?:teapot|key pot) on the stove(?: she)?$',tail) is not None
rows=[]
for path in sorted((root/'output/fair-streaming-2026-10-20').glob('*.events.jsonl')):
 m=EvidenceAlignmentMatcher(manifest);first=None; stove=None
 for e in map(json.loads,path.read_text().splitlines()):
  if e.get('kind')!='segments':continue
  seg=e['segments'];text=' '.join(s['text'] for s in seg)
  u=m.process(text,seg)
  if u.triggered and u.checkpoint_id=='make_a_pot_of_tea':first=e['wall']
  if phrase(text) and stove is None:
   stove={'audio_end':float(seg[-1]['end']),'arrival_wall':e['wall'],'prior_tea_confirmed':first is not None,'text':text}
 rows.append({'stream':path.name,'candidate':stove})
print(json.dumps([r for r in rows if r['candidate']],indent=2))
print('Non-Tea candidate streams',sum(r['candidate'] is not None and '-tea-' not in r['stream'] for r in rows))
for t in ['she put the key pot on the stove','see put the key pot on the stove','she did not put the key pot on the stove','she put the key pot beside the stove','she put the cups on the stove','the stove is hot','can you say she put the key pot on the stove']:
 print('SYNTHETIC',phrase(t),t)
out=root/'output/evidence-replay/stove-diagnostic.json';out.write_text(json.dumps({'note':'Explicit alias experiment, no runtime change. Candidate detection not validated correct trigger. Synthetic quotation intentionally demonstrates unresolved false-positive risk.','streams':rows},indent=2))
