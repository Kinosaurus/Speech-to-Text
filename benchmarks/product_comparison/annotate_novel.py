"""Causal, local waveform annotations for the synthetic Novel Effect pilot.

Annotation uses before/after prefix controls and a separate full-read calibration.
Only new, reproducible waveform components qualify. Sound names describe the
associated phrase, not a human-verified semantic sound classification.
"""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from scipy.signal import butter, sosfiltfilt, fftconvolve

from benchmarks.product_comparison.score import clock, frame_time

RATE=16000


class Capture:
    def __init__(self, folder):
        self.folder=folder
        events=[json.loads(line) for line in (folder/'clocks.jsonl').read_text().splitlines()]
        self.input_clock=clock(events,'source_clock')
        self.output_clock=clock(events,'output_clock')
        self.first=next(e['first_frame'] for e in events if e['kind']=='source_start')
        from scipy.signal import resample_poly
        raw=np.fromfile(folder/'output.pcm',dtype='<i2').reshape(-1,2).mean(axis=1)/32768
        self.signal=resample_poly(raw,1,3)
    def index(self, seconds):
        absolute=frame_time(self.first+seconds*48000,self.input_clock)
        return float(np.interp(absolute,self.output_clock[1],self.output_clock[0])/3)
    def seconds(self, sample):
        absolute=frame_time(sample*3,self.output_clock)
        return float((np.interp(absolute,self.input_clock[1],self.input_clock[0])-self.first)/48000)
    def bounds(self,start,end):
        return max(0,round(self.index(start))),min(len(self.signal),round(self.index(end)))


def ncc(signal,template):
    template=template-template.mean()
    if len(signal)<len(template):raise ValueError('Search shorter than template')
    energy=np.concatenate([[0.],np.cumsum(signal*signal)])
    energy=energy[len(template):]-energy[:-len(template)]
    dot=fftconvolve(signal,template[::-1],mode='valid')
    values=dot/np.sqrt(np.maximum(energy,1e-18)*max(float(np.dot(template,template)),1e-18))
    index=int(np.argmax(values))
    return index,float(values[index])


def band_signal(signal,band):
    if band is None:return signal
    sos=butter(4,band,btype='bandpass',fs=RATE,output='sos')
    return sosfiltfilt(sos,signal)


def shared_component_edge(positive,full,lo,hi,lag):
    """Leading edge of an already control-verified distinct waveform motif.

    Short notes can recur anywhere in the negative capture, so negative-control
    specificity is assessed on the 500 ms motif, not every individual 80 ms note.
    An existing continuously coherent background is not a new leading edge.
    """
    trace=[];window=round(.08*RATE);step=round(.02*RATE)
    for i in range(lo,hi,step):
        j=i+lag
        if j<0 or j+window>len(full) or i+window>len(positive):continue
        x=positive[i:i+window];y=full[j:j+window]
        corr=float(np.dot(x,y)/np.sqrt(max(np.dot(x,x)*np.dot(y,y),1e-18)))
        trace.append(dict(sample=i,correlation=corr))
    for i in range(3,len(trace)-2):
        run=trace[i:i+3];prior=trace[max(0,i-25):i]
        if all(t['correlation']>.55 for t in run) and sum(t['correlation']<.25 for t in prior)>=3:
            return run[0]['sample'],trace
    return None,trace


def opening(before,after,full,out):
    # Excludes the session-start chime by searching only after the first spoken
    # word in the identical synthetic master (2.1 s).
    lo,hi=after.bounds(2.1,7)
    frame=RATE//100
    signal=after.signal[lo:hi]
    rms=np.sqrt(np.mean(signal[:len(signal)//frame*frame].reshape(-1,frame)**2,axis=1))
    active=np.flatnonzero((rms[:-1]>.003)&(rms[1:]>.003))
    if not len(active):raise ValueError('No speech-dependent opening response')
    onset=lo+int(active[0])*frame
    blo,bhi=before.bounds(2.1,9)
    control=before.signal[blo:bhi]
    control_rms=float(np.sqrt(np.mean(control*control)))
    if control_rms>.001:raise ValueError('Silent control contains sustained post-speech audio')
    flo,fhi=full.bounds(2.1,7)
    choices=[]
    for duration in [.25,.5,.8]:
        core=onset+round(.04*RATE);template=after.signal[core:core+round(duration*RATE)]
        p,score=ncc(full.signal[flo:fhi],template)
        _,negative=ncc(control,template)
        choices.append(dict(duration=duration,score=score,negative=negative,core=core,full=flo+p))
    valid=[c for c in choices if c['score']>=.65 and c['negative']<.45]
    if not valid:raise ValueError('Opening component failed calibration/control verification')
    best=max(valid,key=lambda c:(c['duration'],c['score']))
    template=after.signal[best['core']:best['core']+round(best['duration']*RATE)]
    path=out/'opening-template.npy';np.save(path,template)
    return dict(id='opening',phrase='The moon has a face',semantic_label='opening audio response',
                status='causally_verified',template=str(path.resolve()),band_hz=None,
                template_onset_offset_seconds=(onset-best['core'])/RATE,
                estimated_calibration_onset_seconds=after.seconds(onset),
                estimated_phrase_start_seconds=2.1,estimated_phrase_end_seconds=3.105,
                calibration_match_ncc=best['score'],negative_control_ncc=best['negative'],
                negative_control_post_speech_rms=control_rms,threshold=.55,
                onset_method='first two consecutive 10 ms RMS frames above 0.003 after speech starts',
                before_capture=str(before.folder),after_capture=str(after.folder))


def phrase(ident,anchor,start,end,before,after,full,out):
    blo,bhi=before.bounds(2.1,end+6)
    flo,fhi=full.bounds(max(2.1,start-.5),end+4)
    p_lo,p_hi=after.bounds(max(2.1,start-.25),end+2.5)
    bands=[None,[100,800],[500,2000],[2000,7000]]
    choices=[]
    for band in bands:
        p=band_signal(after.signal,band)
        c=band_signal(before.signal,band)[blo:bhi]
        f=band_signal(full.signal,band)[flo:fhi]
        length=round(.5*RATE)
        for index in range(p_lo,min(p_hi,len(p)-length),round(.12*RATE)):
            template=p[index:index+length]
            if np.sqrt(np.mean(template*template))<.001:continue
            _,negative=ncc(c,template)
            if negative>=.45:continue
            position,score=ncc(f,template)
            if score>=.65 and score-negative>=.25:
                choices.append(dict(core=index,full=flo+position,score=score,negative=negative,band=band))
    if not choices:
        result=dict(id=ident,phrase=anchor,status='unverified_no_distinct_causal_component',
                    expected_phrase_start_seconds=start,expected_phrase_end_seconds=end)
        (out/(ident+'-candidates.json')).write_text(json.dumps(result,indent=2),encoding='utf-8')
        return result
    best=max(choices,key=lambda c:c['score']-c['negative'])
    p=band_signal(after.signal,best['band']);f=band_signal(full.signal,best['band'])
    # Trace the component's shared leading edge in the full and positive capture.
    # A stable, new correlated component must persist for at least 60 ms.
    lo,_=after.bounds(max(2.1,start-1),end+2.5)
    onset,trace=shared_component_edge(p,f,lo,best['core']+round(.1*RATE),best['full']-best['core'])
    if onset is None:
        return dict(id=ident,phrase=anchor,status='component_verified_onset_unresolved',
                    best_match=best,candidates=choices,trace=trace)
    path=out/(ident+'-template.npy');np.save(path,p[best['core']:best['core']+round(.5*RATE)])
    result=dict(id=ident,phrase=anchor,semantic_label=ident+'-phrase-associated audio response',
                status='causally_verified',template=str(path.resolve()),band_hz=best['band'],
                template_onset_offset_seconds=(onset-best['core'])/RATE,
                estimated_calibration_onset_seconds=after.seconds(onset),
                estimated_phrase_start_seconds=start,estimated_phrase_end_seconds=end,
                calibration_match_ncc=best['score'],negative_control_ncc=best['negative'],
                threshold=.55,onset_method='correlated component leading edge; 80 ms windows, 20 ms step, three-frame persistence',
                before_capture=str(before.folder),after_capture=str(after.folder),
                onset_resolution_seconds=.08)
    (out/(ident+'-candidates.json')).write_text(json.dumps(dict(selected=result,choices=choices,trace=trace),indent=2),encoding='utf-8')
    return result


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--opening-root',type=Path,required=True)
    parser.add_argument('--controls-root',type=Path,required=True);parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args();args.out.mkdir(parents=True,exist_ok=True)
    full=Capture(Path('output/product-comparison-20261119/novel-trial-01'))
    annotations=[opening(Capture(args.opening_root/'opening-before'),Capture(args.opening_root/'opening-after'),full,args.out)]
    plan=json.loads((args.controls_root/'plan.json').read_text())
    for ident in ['cat','mouse','dog']:
        case=next(c for c in plan['cases'] if c['id']==ident+'-after')
        before=args.controls_root/(ident+'-before');after=args.controls_root/(ident+'-after')
        if not (before/'output.pcm').exists() or not (after/'output.pcm').exists():
            annotations.append(dict(id=ident,phrase=case['phrase'],status='control_capture_pending'));continue
        annotations.append(phrase(ident,case['phrase'],case['expected_phrase_start_seconds'],case['expected_phrase_end_seconds'],Capture(before),Capture(after),full,args.out))
    result=dict(status='calibration_annotations',method='causal prefix controls plus repeatable waveform matching',
                evaluation_runs_used_for_fitting=False,annotations=annotations,
                rejected_candidate=dict(id='clock',reason='Clock-prefix control contains the opening response; not treated as a separate verified event without distinct-component evidence.'))
    (args.out/'annotations.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
