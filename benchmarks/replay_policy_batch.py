"""Replay one implementation in its own process, including all matcher bases."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--jobs',type=Path,required=True)
parser.add_argument('--output',type=Path,required=True)
parser.add_argument('--snapshot',type=Path)
parser.add_argument('--prefix-evidence',action='store_true')
args=parser.parse_args()
implementation=args.snapshot.resolve() if args.snapshot else ROOT
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(implementation))
from books_to_life.matching.timely_matcher import TimelyEvidenceMatcher
from benchmarks.run_pending_regression import replay
import books_to_life.matching.timely_matcher as module
assert Path(module.__file__).resolve().is_relative_to(implementation/'books_to_life')
jobs=json.loads(args.jobs.read_text(encoding='utf-8'));rows=[]
for index,job in enumerate(jobs,1):
    path=Path(job['events']);data=path.read_bytes()
    assert hashlib.sha256(data).hexdigest()==job['events_sha256'],job['id']
    manifest=Path(job['manifest']);data_manifest=manifest.read_bytes()
    assert hashlib.sha256(data_manifest).hexdigest()==job['manifest_sha256'],job['id']
    events=[json.loads(line) for line in data.decode('utf-8').splitlines()]
    uses=[];Tracker=TimelyEvidenceMatcher
    if args.prefix_evidence and hasattr(Tracker,'_confirm_from_prefix'):
        class Observed(Tracker):
            def _confirm_from_prefix(self,scene,best):
                prior=self._confirmation_prefix
                used=super()._confirm_from_prefix(scene,best)
                if used:
                    start,end=self.checkpoint_ranges[scene]
                    uses.append(dict(checkpoint=self.checkpoints[scene]['id'],audio_end=self._audio_time,
                        prior_audio_end=prior['time'],prefix_words=prior['end']-start,
                        alignment_score=best.score,book_end=best.end))
                return used
        Tracker=Observed
    result=dict(id=job['id'],group=job['group'],outcomes=replay(Tracker,json.loads(data_manifest),events))
    if args.prefix_evidence:result['prefix_confirmation_uses']=uses
    rows.append(result)
    if index%25==0:print('REPLAY',index,'/',len(jobs),flush=True)
args.output.write_text(json.dumps(dict(implementation_root=str(implementation),cases=rows),indent=2)+'\n',encoding='utf-8')
print('REPLAY COMPLETE',len(rows),str(implementation),flush=True)
