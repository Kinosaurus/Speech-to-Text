"""Audit fresh live streams and compare trackers at the same ASR callback."""
import json,statistics,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'output/live-tracker-2026-10-24'
books={n:json.loads((ROOT/f'recordings/library/stories/{n}/readers/{n}/checkpoints.json').read_text()) for n in ['horse','fat_cat','tea','little_mermaid']}
rows=[]
for results in sorted(OUT.glob('*-results.json')):
 for r in json.loads(results.read_text()):
  stem=f"{r['model'].replace('.','_')}-{r['audio']}-{r['condition']}"
  events=[json.loads(l) for l in (OUT/f'{stem}.events.jsonl').read_text().splitlines()]
  original={};split={};receipt=None;first_stove=None;origin=next(e['wall'] for e in events if e['kind']=='audio');costs={'original':[],'split':[]}
  for e in events:
   if e['kind']=='segments':
    receipt=e['wall']-origin
    text=' '.join(s['text'] for s in e['segments']).lower()
    if first_stove is None and 'stove' in text.split():first_stove=receipt
   if e['kind']=='tracker':
    costs[e['mode']].append(e['compute_seconds'])
    if e['triggered']:
     target=original if e['mode']=='original' else split
     target[(e['book'],e['scene'])]={'arrival_seconds':receipt,'decision_seconds':e['wall']-origin,'audio_end':e['audio_end'],'score':e['score'],'skipped':e['skipped']}
  expected=[(r['audio'],c['id']) for c in books[r['audio']]['checkpoints']] if r['audio'] in books else []
  common=original.keys()&split.keys()
  row={**{k:v for k,v in r.items() if k!='triggers'},'original':[{'book':k[0],'scene':k[1],**v} for k,v in original.items()],'split':[{'book':k[0],'scene':k[1],**v} for k,v in split.items()],'original_unactivated':[k[1] for k in expected if k not in original],'split_unactivated':[k[1] for k in expected if k not in split],'added':[k[1] for k in split.keys()-original.keys()],'lost':[k[1] for k in original.keys()-split.keys()],'timing':[{'scene':k[1],'split_minus_original_seconds':split[k]['arrival_seconds']-original[k]['arrival_seconds']} for k in common],'first_stove_callback_seconds':first_stove,'tracker_compute_max_ms':{k:1000*max(v,default=0) for k,v in costs.items()}}
  stove=split.get(('tea','teapot_on_stove'))
  row['stove_wait_after_first_stove_text_seconds']=stove['arrival_seconds']-first_stove if stove and first_stove is not None else None
  rows.append(row)
aggregates=[]
for model in sorted({r['model'] for r in rows}):
 for condition in ['no-hints','fixed-hints','off-book']:
  group=[r for r in rows if r['model']==model and r['condition']==condition]
  if not group:continue
  deltas=[t['split_minus_original_seconds'] for r in group for t in r['timing']]
  aggregates.append({'model':model,'condition':condition,'runs':len(group),'original_activations':sum(len(r['original']) for r in group),'split_activations':sum(len(r['split']) for r in group),'original_unactivated':sum(len(r['original_unactivated']) for r in group),'split_unactivated':sum(len(r['split_unactivated']) for r in group),'common_timing_count':len(deltas),'median_extra_seconds':statistics.median(deltas) if deltas else None,'max_extra_seconds':max(deltas) if deltas else None})
report={'protocol':'Fresh WAV audio paced through actual application WebSocket client; original and split trackers evaluated online at each new ASR callback, fixed shared hints; normal GPU clocks/power (no throttle changes). Sources and clips hashed. GPU models run sequentially.','limits':'No fresh microphone acoustics; scene correctness and phrase-end latency not manually annotated. Eight clips, one run per model/condition, development recordings. Off-book clips have no matching manifests and are tested against all four available books.','source_sha256':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ['alignment_matcher.py','evidence_matcher.py','split_matcher.py','benchmarks/live_tracker_probe.py','benchmarks/run_live_tracker_comparison.py']},'aggregate':aggregates,'runs':rows}
(OUT/'comparison.json').write_text(json.dumps(report,indent=2))
print(json.dumps(aggregates,indent=2))
for r in rows:
 print(r['model'],r['audio'],r['condition'],'original',len(r['original']),'split',len(r['split']),'missing',r['split_unactivated'],'stove_wait',r['stove_wait_after_first_stove_text_seconds'])
