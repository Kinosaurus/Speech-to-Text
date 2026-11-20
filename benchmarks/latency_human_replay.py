"""Local, silent ASR/matcher regression on existing provisional human references."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import statistics
from types import SimpleNamespace
import wave

import numpy as np

from benchmarks.asr_only import ASRRecorder,sha256
from benchmarks.asr_only_worker import nemo
from benchmarks.asr_reference import word_arrivals
from benchmarks.compare_book_asr import full_book_hints,cue_replay
from benchmarks.metrics import edit_alignment
from books_to_life.matching.timely_matcher import TimelyEvidenceMatcher


def native_cue_replay(events,manifest):
    """Use the same server audio clock as the live client, never queued input."""
    matcher=TimelyEvidenceMatcher(deepcopy(manifest),stability=2);triggers={};duplicates=0
    for event in events:
        if not event.get('segments'):raise ValueError('Missing native server segment clock')
        update=matcher.process(event['text'],segments=event['segments'])
        if update.triggered:
            ident=str(update.checkpoint_id)
            if ident in triggers:duplicates+=1
            else:triggers[ident]=dict(callback_seconds=event['wall_seconds'],final_callback=event['final'])
    return triggers,duplicates


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True)
    p.add_argument('--profiles',nargs='+',required=True);args=p.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    old=Path('output/asr-only/20261119-nemo-boost-sweep')
    dataset=json.loads((old/'dataset.json').read_text(encoding='utf-8'))
    summaries=[]
    for i,case in enumerate(dataset['cases']):
        if sha256(case['audio'])!=case['audio_sha256']:raise ValueError('Source changed')
        with wave.open(case['audio']) as w:
            pcm=np.frombuffer(w.readframes(w.getnframes()),dtype='<i2').astype(np.float32)/32768
        ref=json.loads((old/(case['id']+'.reference.json')).read_text(encoding='utf-8'))
        reference=' '.join(w['text'] for w in ref['words'])
        for profile in (args.profiles if i%2==0 else list(reversed(args.profiles))):
            path=args.output/(case['id']+'-'+profile+'.json')
            if path.exists():raise ValueError('Preserve existing trial')
            print('START',path.stem,flush=True)
            recorder=ASRRecorder(path.with_suffix('.events.jsonl'),delivery='queued')
            config=SimpleNamespace(nemo_url='ws://127.0.0.1:9099',latency_profile=profile)
            try:
                runtime=nemo(config,pcm,recorder,dict(packet_samples=4096 if profile=='baseline' else 1280,tail_seconds=3),
                             hotwords=full_book_hints(case['keen_book_text']))
                updates=[e for e in recorder.events if e['kind']=='transcript']
                final=[e for e in updates if e['final']]
                if len(final)!=1 or recorder.sent_samples!=len(pcm)+48000:raise ValueError('Incomplete replay')
                errors,_=edit_alignment(reference,final[0]['text'])
                triggers,duplicates=native_cue_replay(updates,case['cue_manifest'])
                arrivals=word_arrivals(updates,ref)
                delays=[w['stable_delay_seconds'] for w in arrivals if w['stable_delay_seconds'] is not None]
                summary=dict(case=case['id'],profile=profile,status='ok',audio_sha256=case['audio_sha256'],
                             runtime=runtime,wer=errors,reference_kind='provisional ASR draft; not human-verified',
                             word_median_seconds=statistics.median(delays) if delays else None,
                             hit_ids=list(triggers),hits=len(triggers),expected=len(case['cue_manifest']['checkpoints']),
                             duplicate_cues=duplicates,triggers=triggers)
                path.write_text(json.dumps(summary,indent=2),encoding='utf-8');summaries.append(summary)
                (args.output/'summary.json').write_text(json.dumps(summaries,indent=2),encoding='utf-8')
                print('RESULT',path.stem,summary['hits'],summary['expected'],'WER',errors['wer'],flush=True)
            finally:recorder.close()


if __name__=='__main__':main()
