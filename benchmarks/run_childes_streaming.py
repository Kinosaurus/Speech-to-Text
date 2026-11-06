"""Frozen Singapore CHILDES conversation probe with transcript-derived anchors.

One available source recording plus its three previously selected context clips.
This is neither a held-out-book evaluation nor independently labelled word timing.
"""
import argparse
import hashlib
import html
import importlib.metadata
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import wave

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import numpy as np
import soundfile as sf
from scipy.signal import resample_poly
from benchmarks.run_mps_heldout import read,write,digest,source_files,check_frozen
from benchmarks.run_pending_regression import replay
from benchmarks.metrics import edit_alignment,words
from books_to_life.matching.checkpoint_matcher import normalize_text
from books_to_life.matching.effect_permission import ordered_support
from books_to_life.matching.timely_matcher import TimelyEvidenceMatcher

SOURCE=ROOT/'output/childes-singapore-2026-11-02'
REFERENCE=ROOT/'output/mps-heldout-phonetic-2026-11-02'
DEST=ROOT/'output/childes-singapore-streaming-2026-11-02'


def clean_chat(text):
    """Remove annotation syntax, keeping spoken repetitions and contractions."""
    text=re.sub(r'\x15[^\x15]*\x15',' ',text)
    text=re.sub(r'\[[^\]]*\]',' ',text)
    text=re.sub(r'&[^\s]+',' ',text)
    text=re.sub(r'@[^\s.,?!<>]+','',text)
    text=re.sub(r'\+(?:\.{1,3}|[/?.!<>^]+)',' ',text)
    text=re.sub(r'\((?:[.\d\s]+)\)',' ',text)
    text=text.replace('_',' ').replace('<',' ').replace('>',' ')
    text=re.sub(r'\b(?:xxx|yyy|www)\b',' ',text,flags=re.I)
    return normalize_text(text)


def main_tiers(text):
    """Never append dependent (%mor/%wor/etc.) continuations to speech."""
    tiers=[];current=None
    for line in text.splitlines():
        match=re.match(r'^\*([^:]+):\s*(.*)',line)
        if match:
            current=dict(speaker=match[1],raw=match[2]);tiers.append(current)
        elif line.startswith(('\t',' ')) and current is not None:
            current['raw']+=' '+line.strip()
        else:
            current=None
    for tier in tiers:
        tier['clean']=clean_chat(tier['raw'])
        spans=re.findall(r'\x15(\d+)_(\d+)\x15',tier['raw'])
        tier['span_ms']=list(map(int,spans[0])) if spans else None
    return tiers


def make_manifest(name,text,anchors):
    book=dict(book_id=name,threshold=82,stability=2,min_coverage=.8,
              pages=[dict(page=1,text=text)],checkpoints=[])
    tokens=normalize_text(text).split()
    for position,(ident,anchor) in enumerate(anchors,1):
        target=anchor.split();hits=[i for i in range(len(tokens)-len(target)+1) if tokens[i:i+len(target)]==target]
        assert len(hits)==1,(ident,hits)
        book['checkpoints'].append(dict(id=ident,book_id=name,checkpoint_position=position,
            checkpoint_text=anchor,word_start=hits[0],word_end=hits[0]+len(target),effect_policy='one_shot',effect={'effect_id':ident}))
    TimelyEvidenceMatcher(book)
    return book


def prepare(output):
    assert not output.exists();output.mkdir(parents=True)
    baseline=check_frozen(REFERENCE,model_hash=True)
    reviews=read(SOURCE/'inspection-clips.json');assert len(reviews)==3
    transcript=SOURCE/'transcripts/e5d6a.cha';raw_audio=SOURCE/'audio/e5d6a.mp3'
    tiers=main_tiers(transcript.read_text(encoding='utf-8-sig'))
    anchors=[];target_rows=[]
    for number,row in enumerate(reviews,1):
        match=[t for t in tiers if t['speaker']==row['speaker'] and t['span_ms']
               and t['span_ms'][0]==round(row['original_start_seconds']*1000)]
        assert len(match)==1
        ident=f'utterance_{number:02d}';anchor=match[0]['clean']
        assert len(anchor.split())>=5
        anchors.append((ident,anchor));target_rows.append(dict(row,id=ident,anchor=anchor))
    text=' '.join(t['clean'] for t in tiers if t['clean'])
    inputs=output/'inputs';inputs.mkdir()
    data,rate=sf.read(str(raw_audio),dtype='float32',always_2d=True)
    factor=math.gcd(rate,16000);mono=resample_poly(data.mean(axis=1),16000//factor,rate//factor)
    full=inputs/'full_recording';full.mkdir();full_wav=full/'audio.wav'
    sf.write(str(full_wav),mono,16000,subtype='PCM_16')
    manifest_path=full/'checkpoints.json';write(manifest_path,make_manifest('singapore-full',text,anchors))
    (full/'reference.txt').write_text(text+'\n',encoding='utf-8')
    jobs=[dict(id='full_recording',audio=str(full_wav),manifest=str(manifest_path),
               kind='Continuous complete classroom source, converted once to mono 16 kHz PCM16',
               source_start_seconds=0,source_recordings=1,targets=target_rows)]
    for row in target_rows:
        ident='clip_'+row['id'].split('_')[-1];folder=inputs/ident;folder.mkdir()
        audio=folder/'audio.wav';shutil.copyfile(Path(row['clip']),audio)
        manifest_path=folder/'checkpoints.json'
        write(manifest_path,make_manifest('singapore-'+ident,row['anchor'],[(row['id'],row['anchor'])]))
        jobs.append(dict(id=ident,audio=str(audio),manifest=str(manifest_path),
            kind='Previously selected context clip from the same source; not an independent recording',
            source_start_seconds=row['clip_start_seconds'],source_recordings=1,targets=[row]))
    for job in jobs:
        with wave.open(job['audio']) as wav:
            assert wav.getframerate()==16000 and wav.getnchannels()==1 and wav.getsampwidth()==2
            job['audio_seconds']=wav.getnframes()/16000
        job['audio_sha256']=digest(Path(job['audio']));job['manifest_sha256']=digest(Path(job['manifest']))
    policies={}
    for job in read(REFERENCE/'downloaded-jobs.json'):
        cfg=read(Path(job['manifest']));key=tuple(p['text'] for p in cfg['pages'])
        if key in policies:continue
        path=output/'offbook-policies'/f'passage-{len(policies)+1}.json';path.parent.mkdir(exist_ok=True)
        path.write_bytes(Path(job['manifest']).read_bytes());policies[key]=str(path)
    assert len(policies)==6
    write(output/'offbook-manifests.json',list(policies.values()))
    write(output/'jobs.json',jobs)
    hashes={}
    for path in sorted(set(source_files())|{Path(__file__).resolve(),ROOT/'benchmarks/metrics.py'}):
        name=path.relative_to(ROOT).as_posix();data=path.read_bytes()
        target=output/'source-snapshot'/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
        hashes[name]=hashlib.sha256(data).hexdigest()
        if name.startswith('books_to_life/'):
            assert hashes[name]==baseline['source_sha256'][name],name
    source_hashes={str(p):digest(p) for p in (raw_audio,transcript,SOURCE/'inspection-clips.json')}
    write(output/'protocol.json',dict(date='2026-11-02',scope='Initial Singapore CHILDES conversation streaming diagnostic',
        commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        configuration=baseline['configuration'],model=baseline['model'],lexicon=baseline['lexicon'],
        source_sha256=hashes,baseline_sha256={},original_inputs_sha256=source_hashes,
        offbook_policy_sha256={p:digest(Path(p)) for p in policies.values()},
        reference_runtime_protocol=str(REFERENCE/'protocol.json'),ordered_recordings=[j['id'] for j in jobs],
        streams=4,independent_source_recordings=1,configured_checkpoint_opportunities=6,
        unique_transcript_anchors=3,preselected_child_codes=sorted({r['speaker'] for r in reviews}),
        source_has_other_speakers=True,no_asr_or_matcher_tuning=True,thresholds_and_hints_unchanged=True,
        selection='Use the one complete downloaded source and all three existing inspection clips, without outcome-dependent replacements.',
        audio_conversion='Stereo average to mono, scipy resample_poly to 16 kHz, PCM16; no gain, denoising or added silence. Existing review WAVs copied byte-for-byte.',
        normalization='Main CHAT speech tiers only; dependent tiers excluded. Annotation syntax/unknown spans removed; repetitions retained and underscore compounds separated.',
        timestamps='CHAT contains machine-aligned timing; these are not independently verified acoustic or word-end labels.',
        notes=['Transcript-derived reference is what was transcribed, not an independent authored reading passage.',
               'Group classroom audio has other/background speakers and incomplete teacher transcription; no population WER or reading correctness score.',
               'Three cropped streams repeat source material and cannot count as new speakers or independent samples.',
               'Every selected trial is retained once. No outcome-based tuning or crop replacement.']))
    verify(output,model_hash=True)
    print('FROZEN four streams, one source, three transcript anchors, six off-book replay policies.',flush=True)
    print('AUDIO_SECONDS',sum(j['audio_seconds'] for j in jobs),flush=True)


def verify(output,model_hash=False):
    protocol=check_frozen(output,model_hash=model_hash)
    for key in ('original_inputs_sha256','offbook_policy_sha256'):
        for path,sha in protocol[key].items():assert digest(Path(path))==sha,path
    for job in read(output/'jobs.json'):assert digest(Path(job['audio']))==job['audio_sha256']
    return protocol


def audit(output,job):
    stem=output/'streams'/job['id'];events=[json.loads(s) for s in stem.with_suffix('.events.jsonl').read_text(encoding='utf-8').splitlines()]
    packets=[e for e in events if e['kind']=='audio'];callbacks=[e for e in events if e['kind']=='segments'];count=0
    for packet in packets:assert packet['sample_start']==count;count+=packet['sample_count']
    with wave.open(job['audio']) as wav:assert wav.getnframes()==count
    assert callbacks
    partial_before_eof=any(e['wall']<packets[-1]['wall'] and any(not s['completed'] for s in e['segments'])
                           for e in callbacks)
    assert callbacks[-1]['segments'][-1]['completed']
    assert abs(callbacks[-1]['segments'][-1]['end']-count/16000)<.001
    assert any(e['kind']=='status' and e.get('message')=='STREAM_DONE' for e in events)
    assert not any(e['kind']=='status' and e.get('status')=='ERROR' for e in events)
    assert not any(e['kind']=='book_context_sent' for e in events)
    cfg=read(Path(job['manifest']));matcher=TimelyEvidenceMatcher(cfg);decisions=[];pending=set();skipped=set()
    texts=[]
    for event in callbacks:
        seg=event['segments'];text=' '.join(s['text'] for s in seg);texts.append(text);update=matcher.process(text,seg)
        skipped.update(update.skipped_checkpoint_ids)
        if update.effect_pending_checkpoint_id:pending.add(update.effect_pending_checkpoint_id)
        for ident in update.additional_suppressed_checkpoint_ids:
            decisions.append(dict(id=ident,emitted=False,suppressed=True,audio_end=seg[-1]['end'],buffer=list(matcher._buffer)))
        if update.triggered or update.effect_suppressed:
            decisions.append(dict(id=update.checkpoint_id,emitted=update.triggered,suppressed=update.effect_suppressed,
                audio_end=seg[-1]['end'],callback_seconds=event['wall']-packets[0]['wall'],buffer=list(matcher._buffer),
                reason=update.effect_suppression_reason))
    assert matcher._pending_effect is None
    emitted=[d['id'] for d in decisions if d['emitted']];suppressed=[d['id'] for d in decisions if d['suppressed']]
    assert len(emitted)==len(set(emitted)) and not(set(emitted)&set(suppressed))
    observed=[e for e in events if e['kind']=='tracker' and e['mode']=='timely']
    assert [e['scene'] for e in observed if e['triggered']]==emitted
    assert [e['scene'] for e in observed if e.get('suppressed')]==suppressed
    log=stem.with_suffix('.log').read_text(encoding='utf-8')
    assert re.findall(r'^\[TRIGGER\] (\S+):',log,re.M)==emitted
    assert re.findall(r'^\[SUPPRESSED\] (\S+):',log,re.M)==suppressed
    normalized=[' '.join(words(t)) for t in texts];targets=[]
    for target in job['targets']:
        ident=target['id'];ref=words(target['anchor']);phrase=' '.join(ref)
        decision=next((d for d in decisions if d['id']==ident),None)
        max_support=max((len(ordered_support(ref,normalize_text(t).split()))/len(ref) for t in texts),default=0)
        targets.append(dict(id=ident,speaker=target['speaker'],age_from_chat=target['age_from_chat'],
            reference=target['anchor'],chat_start_original=target['original_start_seconds'],chat_end_original=target['original_end_seconds'],
            emitted=ident in emitted,suppressed=ident in suppressed,skipped=ident in skipped,
            exact_phrase_in_any_callback=any(' '+phrase+' ' in ' '+t+' ' for t in normalized),
            best_ordered_word_support=max_support,decision=decision))
    write(stem.with_suffix('.decisions.json'),decisions)
    return dict(id=job['id'],kind=job['kind'],audio_seconds=job['audio_seconds'],audio_sha256=job['audio_sha256'],
        manifest_sha256=job['manifest_sha256'],samples_delivered=count,partial_before_eof=partial_before_eof,stream_done=True,
        app_observer_replay_agreement=True,delivery_audit_pass=True,emitted=emitted,suppressed=suppressed,
        skipped=sorted(skipped),unreached=sorted({c['id'] for c in cfg['checkpoints']}-set(emitted)-set(suppressed)-skipped),
        pending=sorted(pending),targets=targets,final_asr=texts[-1],callback_count=len(callbacks))


def run(output,resume=False):
    protocol=verify(output,model_hash=True);jobs=read(output/'jobs.json');assert [j['id'] for j in jobs]==protocol['ordered_recordings']
    (output/'streams').mkdir(exist_ok=resume);rows=[]
    for i,job in enumerate(jobs,1):
        verify(output);stem=output/'streams'/job['id'];print('START',i,'/',len(jobs),job['id'],flush=True)
        if resume and stem.with_suffix('.events.jsonl').exists():
            # Audit the original trial without replacing or replaying its audio.
            assert stem.with_suffix('.log').exists() and stem.with_suffix('.srt').exists()
            print('RETAIN original stream',job['id'],flush=True)
        else:
            assert not any(stem.with_suffix(ext).exists() for ext in ('.log','.srt','.events.jsonl'))
            command=[sys.executable,'-X','utf8','-u','benchmarks/live_tracker_probe.py','--model','parakeet-nemo',
                '--server','127.0.0.1','--port','9097','--matching_mode','split','--no_book_context',
                '--files',job['audio'],'--mute_audio_playback','--checkpoints',job['manifest'],'--transcript_file',str(stem.with_suffix('.srt'))]
            env=dict(os.environ,PYTHONUTF8='1');env.pop('TRACKER_COMPARE_MANIFESTS',None)
            with stem.with_suffix('.log').open('w',encoding='utf-8') as f:
                subprocess.run(command,cwd=ROOT,env=env,stdout=f,stderr=subprocess.STDOUT,
                    timeout=math.ceil(job['audio_seconds']*1.5)+180,check=True)
        verify(output);row=audit(output,job);rows.append(row);write(output/'results.json',dict(streams=rows))
        print('DONE',job['id'],'emitted',row['emitted'],'suppressed',row['suppressed'],'unreached',row['unreached'],flush=True)
    verify(output,model_hash=True)
    write(output/'completed.json',dict(streams=4,independent_source_recordings=1,all_trials_retained=True,
        source_model_manifest_audio_hashes_unchanged=True,all_transport_app_replay_audits_pass=True))
    print('COMPLETE four fresh streams; runtime and samples unchanged.',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--stage',choices=('prepare','run','resume'),required=True)
    parser.add_argument('--output',type=Path,default=DEST);args=parser.parse_args();output=args.output.resolve()
    if not output.is_relative_to(ROOT/'output'):parser.error('Raw artifacts must remain under output/.')
    if args.stage=='resume':run(output,resume=True)
    else:{'prepare':prepare,'run':run}[args.stage](output)
