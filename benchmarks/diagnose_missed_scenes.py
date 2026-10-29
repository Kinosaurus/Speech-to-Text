import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from split_matcher import SplitEvidenceMatcher
from alignment_matcher import align_words
root=Path(__file__).resolve().parents[1]
r=json.load(open(root/'output/evidence-replay/comparison.json'))
report=[]
for row in r['matched']:
 manifest=json.load(open(root/f"recordings/library/stories/{row['book']}/readers/{row['book']}/checkpoints.json"))
 missing=[c for c in manifest['checkpoints'] if c['id'] not in {x['id'] for x in row['split']}]
 if not missing:continue
 m=SplitEvidenceMatcher(manifest);accepted=[];raw={c['id']:[] for c in missing}
 for e in map(json.loads,open(root/'output/fair-streaming-2026-10-20'/row['stream'])):
  if e.get('kind')!='segments':continue
  seg=e['segments'];u=m.process('',seg)
  if u.alignment_end is not None:accepted.append({'end':u.alignment_end,'score':u.score,'confirmations':u.confirmations,'scene':u.checkpoint_id,'time':seg[-1]['end']})
  lengths={len(m._buffer),max(m.minimum_words,len(m._buffer)//2),m.minimum_words,min(len(m._buffer),m.minimum_words+3)}
  for n in lengths:
   spans=align_words(m._buffer[-n:],m.words,0,m.minimum_words,m._minimum_coverage)
   for c in missing:
    idx=m.checkpoints.index(c);lo=m.checkpoint_ranges[idx][1];hi=m.checkpoint_ranges[idx+1][1] if idx+1<len(m.checkpoints) else len(m.words)+1
    for s in spans:
     if lo<=s.end<hi:raw[c['id']].append({'score':round(s.score,2),'start':s.start,'end':s.end,'time':float(seg[-1]['end']),'text':' '.join(m._buffer[-n:])})
 for c in missing:
  top=sorted(raw[c['id']],key=lambda x:x['score'],reverse=True)[:3]
  item={'stream':row['stream'],'scene':c['id'],'expected':c['checkpoint_text'],'best_raw_candidates':top,'accepted_updates':accepted,'final_position':m.tracked_word_position}
  report.append(item)
 print('\nSTREAM',row['stream'],'missing',[c['id'] for c in missing],'final',m.tracked_word_position,'accepted',accepted)
 print('TRANSCRIPT',json.load(open(root/'output/fair-streaming-2026-10-20'/row['stream'].replace('.events.jsonl','.json')))['transcript'])
 for c in missing:print(c['id'],'RAW',sorted(raw[c['id']],key=lambda x:x['score'],reverse=True)[:2])
(root/'output/evidence-replay/missed-scenes.json').write_text(json.dumps(report,indent=2))
