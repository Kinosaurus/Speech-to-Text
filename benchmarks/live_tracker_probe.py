"""Live original/split observers on fresh ASR callbacks, with packet audit."""
import json,runpy,sys,time,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from whisper_live.client import Client,TranscriptionTeeClient
from books_to_life.matching.alignment_matcher import AlignmentMatcher
from books_to_life.matching.split_matcher import SplitEvidenceMatcher
from books_to_life.matching.boundary_matcher import BoundaryEvidenceMatcher
from books_to_life.matching.timely_matcher import TimelyEvidenceMatcher
from books_to_life.runtime.native_stream_client import NativeConnection
from books_to_life.context.book_context_client import BookContextConnection
out=Path(sys.argv[sys.argv.index('--transcript_file')+1]).with_suffix('.events.jsonl')
f=out.open('w',encoding='utf-8');samples=0;origin=None
from benchmarks.observer_manifests import observer_manifest_paths
checkpoint_path = sys.argv[sys.argv.index('--checkpoints')+1] if '--checkpoints' in sys.argv else None
manifest_paths = observer_manifest_paths(ROOT, checkpoint_path)
if os.environ.get('TRACKER_COMPARE_MANIFESTS'):
 manifest_paths = {name:ROOT/path for name,path in json.loads(os.environ['TRACKER_COMPARE_MANIFESTS']).items()}
trackers={name:{'original':AlignmentMatcher.from_file(path),'split':SplitEvidenceMatcher.from_file(path),
                'boundary':BoundaryEvidenceMatcher.from_file(path),
                'timely':TimelyEvidenceMatcher.from_file(path)}
          for name,path in manifest_paths.items()}

def emit(kind,**kw):
 f.write(json.dumps({'kind':kind,'wall':time.perf_counter(),**kw})+'\n');f.flush()
oldsend=TranscriptionTeeClient.multicast_packet
oldmessage=Client.on_message
oldnative=NativeConnection.on_message
oldhintsend=BookContextConnection._send_pending_context
def hint_send(self):
 before=self._sent_revision
 result=oldhintsend(self)
 if self._sent_revision!=before:
  emit('book_context_sent',revision=self._sent_revision,hints=self._pending_context)
 return result
BookContextConnection._send_pending_context=hint_send
def native_message(self,ws,raw):
 value=json.loads(raw)
 if value.get('message')=='STREAM_DONE':emit('status',message='STREAM_DONE',status=value.get('status'))
 if value.get('type') in ('book_context_capabilities','book_context_ack'):
  emit('book_context_control',data=value)
 return oldnative(self,ws,raw)
NativeConnection.on_message=native_message
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
 if value.get('message') or value.get('status'):
  emit('status',message=value.get('message'),status=value.get('status'))
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
try:runpy.run_module("books_to_life.cli.run_client", run_name='__main__')
finally:f.close()
