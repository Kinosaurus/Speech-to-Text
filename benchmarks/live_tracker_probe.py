"""Live original/split observers on fresh ASR callbacks, with packet audit."""
import json,runpy,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from whisper_live.client import Client,TranscriptionTeeClient
from alignment_matcher import AlignmentMatcher
from split_matcher import SplitEvidenceMatcher
out=Path(sys.argv[sys.argv.index('--transcript_file')+1]).with_suffix('.events.jsonl')
f=out.open('w',encoding='utf-8');samples=0;origin=None
book=Path(sys.argv[sys.argv.index('--checkpoints')+1]).stem.replace('_story','') if '--checkpoints' in sys.argv else None
books=[book] if book else ['horse','fat_cat','tea','little_mermaid']
trackers={name:{'original':AlignmentMatcher.from_file(ROOT/f'examples/{name}_story.json'),'split':SplitEvidenceMatcher.from_file(ROOT/f'examples/{name}_story.json')} for name in books}
def emit(kind,**kw):
 f.write(json.dumps({'kind':kind,'wall':time.perf_counter(),**kw})+'\n');f.flush()
oldsend=TranscriptionTeeClient.multicast_packet
oldmessage=Client.on_message
# Upstream waits for 15 seconds without changed text and can wait indefinitely
# if final hypotheses oscillate. Keep 15-second quiet detection, cap at 30 s.
def bounded_settle(self):
 deadline=time.monotonic()+30
 emit('settle_start',maximum_seconds=30)
 while self.last_response_received and time.time()-self.last_response_received < self.disconnect_if_no_response_for:
  if time.monotonic()>=deadline:
   emit('settle_cap',maximum_seconds=30)
   break
  time.sleep(.05)
Client.wait_before_disconnect=bounded_settle
def send(self,packet,unconditional=False):
 global samples,origin
 if packet!=b'END_OF_AUDIO':
  if origin is None:origin=time.perf_counter();print('[LIVE_AUDIO_START]',flush=True)
  n=len(packet)//4;emit('audio',sample_start=samples,sample_count=n);samples+=n
 else:emit('end_of_audio',samples=samples)
 return oldsend(self,packet,unconditional)
def message(self,ws,raw):
 value=json.loads(raw)
 if value.get('segments'):
  seg=value['segments'];emit('segments',segments=seg)
  text=' '.join(s['text'] for s in seg)
  for name,pair in trackers.items():
   for mode,m in pair.items():
    start=time.perf_counter();u=m.process(text,seg);elapsed=time.perf_counter()-start
    emit('tracker',book=name,mode=mode,triggered=u.triggered,scene=u.checkpoint_id,score=u.score,position=u.tracked_word_position,skipped=list(u.skipped_checkpoint_ids),audio_end=float(seg[-1]['end']),compute_seconds=elapsed)
    if u.triggered:print('[LIVE_TRIGGER]',name,mode,u.checkpoint_id,flush=True)
 return oldmessage(self,ws,raw)
TranscriptionTeeClient.multicast_packet=send
Client.on_message=message
try:runpy.run_path(str(ROOT/'run_client.py'),run_name='__main__')
finally:f.close()
