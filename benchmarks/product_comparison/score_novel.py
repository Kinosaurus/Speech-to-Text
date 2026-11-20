"""Evaluate new captures with frozen causal waveform annotations, locally."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import statistics

import numpy as np

from benchmarks.product_comparison.annotate_novel import Capture, RATE, band_signal, ncc
from benchmarks.product_comparison.score import frame_time


def score(trial, freeze_path):
    freeze=json.loads(freeze_path.read_text(encoding='utf-8'))
    for name,digest in freeze['files'].items():
        if hashlib.sha256(Path(name).read_bytes()).hexdigest()!=digest:
            raise ValueError('Frozen annotation changed: '+name)
    manifest=next(Path(p) for p in freeze['files'] if Path(p).name=='annotations.json')
    annotations=json.loads(manifest.read_text(encoding='utf-8'))
    result=json.loads((trial/'result.json').read_text(encoding='utf-8'))
    if result['status']!='ok' or result['case']['kind']!='full_validation':
        raise ValueError('Requires a completed, independent full validation replay')
    if hashlib.sha256((trial/'input.wav').read_bytes()).hexdigest()!=result['case']['master_wav_sha256']:
        raise ValueError('Source master changed')
    events=[json.loads(line) for line in (trial/'clocks.jsonl').read_text().splitlines()]
    capture=Capture(trial)
    last=next(e['last_frame'] for e in events if e['kind']=='source_eof')
    elapsed=frame_time(last,capture.input_clock)-frame_time(capture.first,capture.input_clock)
    if abs(elapsed-result['case']['source_seconds'])>.05:
        raise ValueError('Source was not presented completely at 1x')
    rows=[]
    for cue in annotations['annotations']:
        if cue['status']!='causally_verified':continue
        offset=cue['template_onset_offset_seconds']
        start=cue['estimated_phrase_start_seconds'];end=cue['estimated_phrase_end_seconds']
        lo,hi=capture.bounds(start-.25-offset,end+5-offset)
        signal=band_signal(capture.signal,cue['band_hz'])
        template=np.load(cue['template'],allow_pickle=False)
        # Include the full template at the upper bound, while preserving the
        # predeclared onset search interval and each fixed calibration offset.
        position,similarity=ncc(signal[lo:min(len(signal),hi+len(template))],template)
        onset_sample=lo+position+offset*RATE
        onset=capture.seconds(onset_sample)
        hit=similarity>=cue['threshold'] and start-.25<=onset<=end+5
        phrase_end=frame_time(capture.first+end*48000,capture.input_clock)
        output_time=frame_time(onset_sample*3,capture.output_clock)
        rows.append(dict(id=cue['id'],anchor=cue['phrase'],hit=hit,similarity=similarity,
                         source_phrase_end_seconds=end,
                         estimated_output_onset_source_seconds=onset if hit else None,
                         effect_delay_seconds=output_time-phrase_end if hit else None,
                         annotation_resolution_seconds=cue.get('onset_resolution_seconds',.01)))
    # Distinct cue templates must not be credited to the same output onset.
    hits=[r for r in rows if r['hit']]
    for i,a in enumerate(hits):
        for b in hits[i+1:]:
            if abs(a['estimated_output_onset_source_seconds']-b['estimated_output_onset_source_seconds'])<.15:
                raise ValueError('Two annotations claim one output event; review without changing frozen detector')
    delays=[r['effect_delay_seconds'] for r in hits]
    summary=dict(status='frozen_component_detector_scored',
                 scope='Three verified phrase-associated responses; not the complete vendor cue set',
                 annotation_freeze=str(freeze_path.resolve()),
                 freeze_sha256=hashlib.sha256(freeze_path.read_bytes()).hexdigest(),
                 source_sha256=result['case']['master_wav_sha256'],
                 nominal_source_seconds=result['case']['source_seconds'],actual_source_seconds=elapsed,
                 checkpoints_hit=len(hits),expected_checkpoints=len(rows),
                 median_effect_delay_seconds=statistics.median(delays) if delays else None,
                 events=rows,excluded_unverified_candidates=[c['id'] for c in annotations['annotations'] if c['status']!='causally_verified'],
                 digital_output_only=True,estimated_synthetic_phrase_endings=True,
                 sound_semantics_human_verified=False)
    (trial/'score.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
    with (trial/'events.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=rows[0].keys());w.writeheader();w.writerows(rows)
    print(json.dumps(summary,indent=2))
    return summary


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('trial',type=Path)
    p.add_argument('--freeze',type=Path,default=Path('output/novel-cue-annotation-20261119-results/annotation-freeze.json'))
    args=p.parse_args();score(args.trial,args.freeze)
