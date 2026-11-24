"""Unpaced quality-only regression: no physical playback, no latency claims."""
import argparse
import json
from pathlib import Path
from types import SimpleNamespace
import wave

import numpy as np

from benchmarks.asr_only import ASRRecorder,sha256
from benchmarks.asr_only_worker import nemo
from benchmarks.latency_human_replay import native_cue_replay
from benchmarks.metrics import edit_alignment


class Unpaced(ASRRecorder):
    def chunks(self,pcm,packet_samples=4096,tail_seconds=3):
        stream=np.concatenate([pcm,np.zeros(round(tail_seconds*16000),dtype=np.float32)])
        self.begin()
        for offset in range(0,len(stream),packet_samples):
            end=min(offset+packet_samples,len(stream));self.sent_samples=end
            self.emit('audio',sample_start=offset,sample_count=end-offset,unpaced=True)
            yield stream[offset:end]
        self.emit('end_of_audio',samples=self.sent_samples)


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    old=Path('output/asr-only/20261119-nemo-boost-sweep');root=Path('output/product-comparison-20261119')
    data=json.loads((old/'dataset.json').read_text(encoding='utf-8'));cases=[]
    for c in data['cases']:
        ref=json.loads((old/(c['id']+'.reference.json')).read_text(encoding='utf-8'))
        cases.append(dict(id=c['id'],audio=Path(c['audio']),manifest=c['cue_manifest'],
                          reference=' '.join(w['text'] for w in ref['words']),reference_kind='provisional ASR draft'))
    for ident,manifest,source,reference in [
        ('moon',Path('output/novel-cue-annotation-20261119-results/pod-moon-manifest.json'),root/'synthetic/moon-normal.wav',Path('benchmarks/product_comparison/novel_effect_moon.txt')),
        ('lion',root/'readmio-pod-manifest.json',root/'synthetic/readmio-lion-normal.wav',Path('benchmarks/product_comparison/readmio_lion_excerpt.txt'))]:
        cases.append(dict(id=ident,audio=source,manifest=json.loads(manifest.read_text(encoding='utf-8')),
                          reference=reference.read_text(encoding='utf-8'),reference_kind='canonical synthetic reading text'))
    summaries=[]
    for c in cases:
        with wave.open(str(c['audio'])) as w:
            assert (w.getframerate(),w.getnchannels(),w.getsampwidth())==(16000,1,2)
            pcm=np.frombuffer(w.readframes(w.getnframes()),dtype='<i2').astype(np.float32)/32768
        for profile in ['baseline','short-chunk']:
            path=args.output/(c['id']+'-'+profile+'.json')
            if path.exists():raise ValueError('Preserve existing output')
            print('START no-hints',path.stem,flush=True)
            rec=Unpaced(path.with_suffix('.events.jsonl'))
            try:
                runtime=nemo(SimpleNamespace(nemo_url='ws://127.0.0.1:9099',latency_profile=profile,nemo_drain_timeout=180,flow_control_packets=20),
                             pcm,rec,dict(packet_samples=4096 if profile=='baseline' else 1280,tail_seconds=3))
                updates=[e for e in rec.events if e['kind']=='transcript']
                finals=[e for e in updates if e['final']]
                if len(finals)!=1 or rec.sent_samples!=len(pcm)+48000:raise ValueError('Incomplete source')
                triggers,duplicates=native_cue_replay(updates,c['manifest'])
                errors,_=edit_alignment(c['reference'],finals[0]['text'])
                result=dict(case=c['id'],profile=profile,hints=False,delivery='unpaced quality-only; latency invalid',
                            latency_valid=False,audio_sha256=sha256(c['audio']),runtime=runtime,status='ok',
                            hit_ids=list(triggers),hits=len(triggers),expected=len(c['manifest']['checkpoints']),
                            duplicate_cues=duplicates,wer=errors,reference_kind=c['reference_kind'])
                path.write_text(json.dumps(result,indent=2),encoding='utf-8');summaries.append(result)
                (args.output/'summary.json').write_text(json.dumps(summaries,indent=2),encoding='utf-8')
                print('RESULT no-hints',path.stem,result['hits'],result['expected'],flush=True)
            finally:rec.close()


if __name__=='__main__':main()
