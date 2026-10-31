"""Replay saved application callbacks; no ASR rerun or audio ground truth."""
import json, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from books_to_life.matching.alignment_matcher import AlignmentMatcher
from books_to_life.matching.evidence_matcher import EvidenceAlignmentMatcher
from books_to_life.matching.split_matcher import SplitEvidenceMatcher
ROOT=Path(__file__).resolve().parents[1]
BOOKS={n:json.loads((ROOT/f'recordings/library/stories/{n}/readers/{n}/checkpoints.json').read_text()) for n in ['horse','fat_cat','tea','little_mermaid']}
def replay(cls,book,events):
 m=cls(book); hits=[]
 for e in events:
  if e.get('kind')!='segments':continue
  seg=e['segments']; text=' '.join(s['text'] for s in seg)
  u=m.process(text,segments=seg)
  if u.triggered:hits.append({'id':u.checkpoint_id,'audio_end':float(seg[-1]['end']),'callback_wall':e['wall'],'score':u.score,'skipped':list(u.skipped_checkpoint_ids)})
 return hits
rows=[]; negatives=[]
for path in sorted((ROOT/'output/fair-streaming-2026-10-20').glob('*.events.jsonl')):
 events=[json.loads(l) for l in path.read_text().splitlines()]
 name=next((n for n in BOOKS if f'-{n}-' in path.name),None)
 if name:
  rows.append({'stream':path.name,'book':name,'baseline':replay(AlignmentMatcher,BOOKS[name],events),'prior_evidence':replay(EvidenceAlignmentMatcher,BOOKS[name],events),'split':replay(SplitEvidenceMatcher,BOOKS[name],events)})
 for book,manifest in BOOKS.items():
  if book!=name:
   negatives.append({'stream':path.name,'book':book,'baseline':replay(AlignmentMatcher,manifest,events),'prior_evidence':replay(EvidenceAlignmentMatcher,manifest,events),'split':replay(SplitEvidenceMatcher,manifest,events)})
result={'experimental_mode':'split','qualification':'Transcript callback replay, not fresh audio inference. Scene correctness/timing needs annotated audio. Wrong-book streams are negative controls, not a live conversation test.','matched':rows,'wrong_book':negatives}
out=ROOT/'output/evidence-replay';out.mkdir(exist_ok=True);(out/'comparison.json').write_text(json.dumps(result,indent=2))
for r in rows:print(r['stream'],len(r['baseline']),len(r['split']),[(x['id'],round(x['audio_end'],2)) for x in r['split']])
print('TOTAL',sum(len(r['baseline']) for r in rows),sum(len(r['split']) for r in rows),'streams',len(rows))
print('NEGATIVE',len(negatives),'baseline',sum(len(r['baseline']) for r in negatives),'evidence',sum(len(r['split']) for r in negatives))

# Older runs retained text callbacks but not segment timestamps. Replay these
# separately; never present them as equivalent to timestamped callback replay.
logs=[]
recordings=['little_mermaid','fat_cat','recording_2','horse','tea','dog','dragon','nickel']
for path in sorted((ROOT/'output').rglob('*.log')):
 name=next((n for n in recordings if n in path.stem),None)
 if not name or path.parent.name=='fair-streaming-2026-10-20' or path.parent.name.startswith('live-tracker-'):continue
 texts=[line.split('[TRANSCRIPT] ',1)[1] for line in path.read_text(errors='replace').splitlines() if '[TRANSCRIPT] ' in line]
 if not texts:continue
 books=[name] if name in BOOKS else list(BOOKS)
 for book in books:
  r={'stream':str(path.relative_to(ROOT)),'recording':name,'book':book,'off_book':name not in BOOKS}
  for key,cls in [('baseline',AlignmentMatcher),('prior_evidence',EvidenceAlignmentMatcher),('split',SplitEvidenceMatcher)]:
   m=cls(BOOKS[book]);hits=[]
   for text in texts:
    u=m.process(text)
    if u.triggered:hits.append(u.checkpoint_id)
   r[key]=hits
  logs.append(r)
result['text_only_legacy']=logs
(out/'comparison.json').write_text(json.dumps(result,indent=2))
print('LEGACY',len(logs),'comparisons',sorted(set(r['recording'] for r in logs)))
print('LEGACY MATCHED',sum(len(r['baseline']) for r in logs if not r['off_book']),sum(len(r['split']) for r in logs if not r['off_book']))
print('LEGACY OFFBOOK',sum(r['off_book'] for r in logs),sum(len(r['baseline']) for r in logs if r['off_book']),sum(len(r['split']) for r in logs if r['off_book']))

# Relative callback arrival times compare tracker delay without confusing audio
# endpoints with actual recognition delivery. These are NOT phrase-end latency.
from statistics import median
pairs=[]; added=[]; lost=[]
for row in rows:
 a={x['id']:x for x in row['baseline']};b={x['id']:x for x in row['split']}
 for key in a.keys() & b.keys():
  pairs.append({'stream':row['stream'],'scene':key,'arrival_delta_seconds':b[key]['callback_wall']-a[key]['callback_wall']})
 for key in b.keys()-a.keys():added.append({'stream':row['stream'],**b[key]})
 for key in a.keys()-b.keys():lost.append({'stream':row['stream'],**a[key]})
expected=sum(len(BOOKS[r['book']]['checkpoints']) for r in rows)
result['summary']={'configured_scene_opportunities':expected,'baseline_unactivated':expected-sum(len(r['baseline']) for r in rows),'split_unactivated':expected-sum(len(r['split']) for r in rows),'added':added,'lost':lost,'shared_scene_timing':pairs,'timing_note':'Experimental minus baseline callback arrival; positive means later. No manually annotated phrase ends.'}
(out/'comparison.json').write_text(json.dumps(result,indent=2))
deltas=[p['arrival_delta_seconds'] for p in pairs]
print('TIMING shared',len(deltas),'median',median(deltas),'min',min(deltas),'max',max(deltas),'later',sum(d>0 for d in deltas),'earlier',sum(d<0 for d in deltas))
print('UNACTIVATED',result['summary']['baseline_unactivated'],result['summary']['split_unactivated'],'ADDED',len(added),'LOST',len(lost))
