"""Quiet paired real-output latency experiments; preserves every attempt."""
import argparse
import json
from pathlib import Path
import statistics
import subprocess
import sys

from benchmarks.product_comparison.score import score_pod


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True)
    p.add_argument('--profiles',nargs='+',default=['baseline','balanced','fast'])
    p.add_argument('--repeat',type=int,default=1);args=p.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    root=Path('output/product-comparison-20261119');work=Path('output/novel-cue-annotation-20261119-results')
    cases=[('moon',work/'pod-moon-manifest.json',root/'synthetic/moon-normal'),
           ('lion',root/'readmio-pod-manifest.json',root/'synthetic/readmio-lion-normal')]
    tool=root/'ProcessAudio-v3.exe';client=Path('.venv/Scripts/python.exe')
    summaries=[]
    for repeat in range(args.repeat):
        for i,(case,manifest,source) in enumerate(cases):
            order=args.profiles if (repeat+i)%2==0 else list(reversed(args.profiles))
            for profile in order:
                trial=args.output/f'{case}-{profile}-{repeat+1:02d}'
                if trial.exists():raise ValueError('Preserve prior output; choose fresh root: '+str(trial))
                print('START',trial.name,flush=True)
                command=[str(client),'-m','benchmarks.product_comparison.pod_replay',
                         '--manifest',str(manifest),'--audio',str(source.with_suffix('.wav')),
                         '--output',str(trial),'--capture-tool',str(tool),'--nemo-url','ws://127.0.0.1:9099',
                         '--latency-profile',profile,'--packet-samples','4096' if profile=='baseline' else '1280']
                if case=='lion':
                    command+=['--reference-text','benchmarks/product_comparison/readmio_lion_excerpt.txt']
                with (args.output/(trial.name+'.log')).open('w',encoding='utf-8') as log:
                    subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,check=True)
                score=score_pod(root,trial,source,manifest if case=='moon' else None)
                events=[json.loads(x) for x in (trial/'recognition.events.jsonl').read_text(encoding='utf-8').splitlines()]
                timings=[e for e in events if e['kind']=='server_timing']
                item=dict(case=case,profile=profile,trial=str(trial),
                          hits=score['checkpoints_hit'],expected=score['expected_checkpoints'],
                          hit_ids=[e['id'] for e in score['events'] if e['hit']],
                          effect_median_seconds=score['median_effect_delay_seconds'],
                          wer=score['estimated_synthetic_wer'],
                          decoder_average_seconds_per_chunk=(timings[-1]['decode_seconds']/timings[-1]['decode_count']) if timings else None)
                summaries.append(item)
                (args.output/'summary.json').write_text(json.dumps(summaries,indent=2),encoding='utf-8')
                print('RESULT',json.dumps(item),flush=True)


if __name__=='__main__':main()
