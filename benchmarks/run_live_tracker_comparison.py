"""Fresh paced audio via application; fixed hints keep tracker input identical."""
import argparse,json,os,socket,subprocess,time,wave,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];os.chdir(ROOT)
OUT=ROOT/'output/live-tracker-2026-10-24';OUT.mkdir(exist_ok=True)
PY=str(ROOT/'.venv/Scripts/python.exe');FLAGS=subprocess.CREATE_NO_WINDOW
p=argparse.ArgumentParser();p.add_argument('--model',choices=['medium.en','parakeet-nemo'],required=True);p.add_argument('--external-server',action='store_true');p.add_argument('--resume',action='store_true');args=p.parse_args()
port=9096 if args.model=='medium.en' else 9097
matched=[('horse','farm, family, horse, brown, run fast'),('fat_cat','cat, mat, rat, fat cat, bat, hat'),('tea','mouse, pot of tea, phone, teapot, stove, cups, little house, Toad'),('little_mermaid','mermaid, legs, prince, deep blue eyes')]
jobs=[(name,condition,hints) for name,vocab in matched for condition,hints in [('no-hints',None),('fixed-hints',vocab)]]+[(n,'off-book',None) for n in ['dog','dragon','nickel','recording_2']]
server=None;serverlog=None;results=[]
if args.resume and (OUT/f'{args.model}-results.json').exists():
 results=json.loads((OUT/f'{args.model}-results.json').read_text())
def status(s):
 print(s,flush=True)
 with (OUT/f'{args.model}-status.txt').open('a') as f:f.write(s+'\n')
try:
 if not args.external_server:
  serverlog=(OUT/f'{args.model}-server.log').open('w')
  server=subprocess.Popen([PY,'-u','run_server.py','--device','cuda','--host','127.0.0.1','--port',str(port)],stdout=serverlog,stderr=subprocess.STDOUT,creationflags=FLAGS,env=dict(os.environ,HF_HUB_OFFLINE='1'))
 deadline=time.monotonic()+240
 while True:
  if server and server.poll() is not None:raise RuntimeError('Server exited; inspect server log')
  try:
   with socket.create_connection(('127.0.0.1',port),timeout=1):break
  except OSError:
   if time.monotonic()>deadline:raise TimeoutError('server startup')
   time.sleep(1)
 for name,condition,hints in jobs:
  if any(r['audio']==name and r['condition']==condition for r in results):continue
  stem=f'{args.model.replace(".","_")}-{name}-{condition}'
  path=OUT/stem;audio=ROOT/f'recordings/library/stories/{name}/readers/{name}/audio.wav'
  status(f'START {stem}')
  cmd=[PY,'-u','benchmarks/live_tracker_probe.py','--model',args.model,'--server','127.0.0.1','--port',str(port),'--files',str(audio),'--mute_audio_playback','--no_book_context','--matching_mode','split','--transcript_file',str(path.with_suffix('.srt'))]
  if condition!='off-book':cmd+=['--checkpoints',str(ROOT/f'recordings/library/stories/{name}/readers/{name}/checkpoints.json')]
  if hints:cmd+=['--hotwords',hints]
  with path.with_suffix('.log').open('w',encoding='utf-8') as log:
   result=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,timeout=240,creationflags=FLAGS)
  if result.returncode:raise RuntimeError(f'client exit {result.returncode}: {stem}')
  events=[json.loads(l) for l in path.with_suffix('.events.jsonl').read_text().splitlines()]
  aud=[e for e in events if e['kind']=='audio'];texts=[e for e in events if e['kind']=='segments'];triggers=[e for e in events if e['kind']=='tracker' and e['triggered']]
  with wave.open(str(audio)) as w:expected=w.getnframes();rate=w.getframerate()
  sent=sum(e['sample_count'] for e in aud)
  if sent!=expected or not texts or not any(e['kind']=='end_of_audio' for e in events):raise RuntimeError('Incomplete audio/transcript audit '+stem)
  gpu=subprocess.run(['nvidia-smi','--query-gpu=clocks.current.graphics,power.limit,memory.used','--format=csv,noheader'],capture_output=True,text=True,creationflags=FLAGS).stdout.strip()
  row={'model':args.model,'audio':name,'condition':condition,'audio_sha256':hashlib.sha256(audio.read_bytes()).hexdigest(),'audio_seconds':expected/rate,'samples_sent':sent,'expected_samples':expected,'packet_samples':sorted({e['sample_count'] for e in aud}),'audio_delivery_seconds':aud[-1]['wall']-aud[0]['wall']+aud[-1]['sample_count']/rate,'first_text_seconds':texts[0]['wall']-aud[0]['wall'],'audio_sent_before_first_text_seconds':sum(e['sample_count'] for e in aud if e['wall']<=texts[0]['wall'])/rate,'triggers':[{**t,'arrival_seconds':t['wall']-aud[0]['wall']} for t in triggers],'gpu_after':gpu,'exit_code':result.returncode}
  results.append(row);(OUT/f'{args.model}-results.json').write_text(json.dumps(results,indent=2))
  status(f'DONE {stem} original={sum(t["mode"]=="original" for t in triggers)} split={sum(t["mode"]=="split" for t in triggers)} audio={row["audio_delivery_seconds"]:.2f}s')
 status('COMPLETE')
finally:
 if server and server.poll() is None:
  server.terminate()
  try:server.wait(timeout=20)
  except subprocess.TimeoutExpired:server.kill();server.wait()
 if serverlog:serverlog.close()
