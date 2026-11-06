"""Frozen offline handoff/interruption stress tests; no ASR or matcher tuning.

Two synthetic adult voices proxy reading roles. Two previously inspected child
recordings separately test inserted/mixed adult speech. Neither is a new-speaker,
natural family-reading, Singapore, or room evaluation.
"""
import argparse
import hashlib
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
from benchmarks.run_mps_heldout import read,write,digest,source_files,check_frozen
from benchmarks.run_pending_regression import replay
from books_to_life.matching.checkpoint_matcher import normalize_text
from books_to_life.matching.timely_matcher import TimelyEvidenceMatcher

DEST=ROOT/'output/shared-reading-2026-11-03'
REFERENCE=ROOT/'output/mps-heldout-phonetic-2026-11-02'
CHILDREN=ROOT/'output/phonetic-feature-regression-2026-11-02/downloaded-jobs.json'
SENTENCES={
    'start':'Maya opened the wooden gate and stepped into the garden.',
    'target':'A small rabbit rested beside the old apple tree.',
    'finish':'She filled the watering can and walked back home.',
}
ASIDE='Please bring my blue notebook from the kitchen. We need to check the shopping list.'
ZIRA='Microsoft Zira Desktop'
DAVID='Microsoft David Desktop'
RATE=16000


def story_manifest():
    text=' '.join(SENTENCES.values());tokens=normalize_text(text).split()
    cfg=dict(book_id='shared-reading',threshold=82,stability=2,min_coverage=.8,
             pages=[dict(page=1,text=text)],checkpoints=[])
    for index,(ident,phrase) in enumerate(SENTENCES.items(),1):
        anchor=normalize_text(phrase).split()
        start=next(i for i in range(len(tokens)) if tokens[i:i+len(anchor)]==anchor)
        cfg['checkpoints'].append(dict(id=ident,book_id='shared-reading',checkpoint_position=index,
            checkpoint_text=phrase,word_start=start,word_end=start+len(anchor),
            effect_policy='one_shot',effect={'effect_id':ident}))
    TimelyEvidenceMatcher(cfg)
    return cfg


def prepare(output):
    assert not output.exists();reference=check_frozen(REFERENCE,model_hash=True)
    output.mkdir(parents=True);parts=output/'parts';parts.mkdir()
    synthesis=[]
    def part(ident,voice,text):
        synthesis.append(dict(id=ident,voice=voice,text=text,audio=str(parts/(ident+'.wav'))))
        return ident
    for ident,text in SENTENCES.items():
        part('zira_'+ident,ZIRA,text);part('david_'+ident,DAVID,text)
    part('aside',DAVID,ASIDE)
    part('coach',DAVID,'Can you say, '+SENTENCES['target'])
    jobs=[]
    plans=[
        ('single_voice',['zira_start','zira_target','zira_finish']),
        ('handoff_and_back',['zira_start','david_target','zira_finish']),
        ('parent_finishes',['zira_start','david_target','david_finish']),
        ('repeat_line',['zira_start','david_target','zira_target','zira_finish']),
        ('unrelated_aside',['zira_start','aside','zira_target','zira_finish']),
        ('long_pause',['zira_start',15.0,'david_target','zira_finish']),
        ('coaching_then_reading',['zira_start','coach','zira_target','zira_finish']),
        ('coaching_only',['zira_start','coach','zira_finish']),
        ('omitted',['zira_start','zira_finish']),
        ('overlap',['zira_start',dict(primary='zira_target',overlay='aside'),'zira_finish']),
    ]
    for ident,plan in plans:
        folder=output/'inputs'/ident;folder.mkdir(parents=True)
        path=folder/'checkpoints.json';write(path,story_manifest())
        jobs.append(dict(id=ident,group='controlled_synthetic_roles',category=ident,plan=plan,
            audio=str(folder/'audio.wav'),manifest=str(path),manifest_sha256=digest(path),
            expected_emitted=['start','finish'] if ident in ('omitted','coaching_only') else ['start','target','finish'],
            target='target',expected_target_emit=ident not in ('omitted','coaching_only'),
            expectation_basis='Constructed script; synthesis has not been independently transcribed. Overlap acceptance needs listening.'))
    available=read(CHILDREN);originals={}
    for source_id,target,expected in [('3a8b_EN-OL-RC-234_1','riverside',True),
                                      ('4a35g_EN-OL-RC-426_2','hibernate',False)]:
        source=next(j for j in available if j['id']==source_id)
        audio=Path(source['audio']);manifest=Path(source['manifest'])
        assert digest(audio)==source['audio_sha256'] and digest(manifest)==source['manifest_sha256']
        originals[str(audio)]=digest(audio);originals[str(manifest)]=digest(manifest)
        cfg=read(manifest);anchor=next(c['checkpoint_text'] for c in cfg['checkpoints'] if c['id']==target)
        coach=part(source_id+'_coach',DAVID,'Can you say, '+anchor)
        for category in ('baseline','inserted_aside','coaching_before_reading','overlap'):
            ident=source_id+'-'+category;folder=output/'inputs'/ident;folder.mkdir(parents=True)
            path=folder/'checkpoints.json';shutil.copyfile(manifest,path)
            jobs.append(dict(id=ident,group='recorded_child_constructed_interruption',category=category,
                source_id=source_id,source_audio=str(audio),source_audio_sha256=source['audio_sha256'],
                coach_part=coach,audio=str(folder/'audio.wav'),manifest=str(path),manifest_sha256=digest(path),
                target=target,expected_target_emit=expected,
                expectation_basis='Prior user accepted riverside / confirmed omitted hibernate on the original. Modified audio audibility is not newly confirmed.'))
    write(output/'jobs.json',jobs);write(output/'synthesis-jobs.json',synthesis)
    files=set(source_files())|{Path(__file__).resolve(),ROOT/'benchmarks/synthesize_shared_reading.ps1',
                             ROOT/'benchmarks/run_pending_regression.py'}
    hashes={}
    for path in sorted(files):
        name=path.relative_to(ROOT).as_posix();data=path.read_bytes()
        target=output/'source-snapshot'/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
        hashes[name]=hashlib.sha256(data).hexdigest()
        if name.startswith('books_to_life/'):assert hashes[name]==reference['source_sha256'][name],name
    protocol=dict(date='2026-11-03',scope='Offline shared-reading handoff and interruption stress test',
        commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        configuration=reference['configuration'],model=reference['model'],lexicon=reference['lexicon'],
        source_sha256=hashes,baseline_sha256={},original_inputs_sha256=originals,
        synthesis_jobs_sha256=digest(output/'synthesis-jobs.json'),jobs_sha256=digest(output/'jobs.json'),
        ordered_recordings=[j['id'] for j in jobs],fresh_streams=18,controlled_synthetic_streams=10,
        child_composite_streams=8,independent_child_recordings=2,child_recordings_previously_inspected=True,
        synthetic_voices=[ZIRA,DAVID],synthetic_rate=0,synthetic_volume=100,
        composition=dict(sample_rate=RATE,sentence_gap_seconds=.4,source_gain=.4,
            child_interruption_position='Exactly half the original sample count, regardless of ASR or book words; may split a word.',
            no_child_frames_removed=True,mixing='Add a David aside at the midpoint, equal RMS to the complete child source before common attenuation; retain both tracks. Peak safety scaling recorded.',
            coaching='Explicit Can you say prompt. Whole anchor is coaching, not a reading event. Subsequent legitimate reading should remain eligible.',
            repeat_policy='Reading either voice counts. Repeat a previously emitted line without duplicate one-shot effects.'),
        no_asr_or_matcher_tuning=True,all_trials_retained=True,selection_frozen_before_synthesis_and_asr=True,
        limits=['Two adult TTS voices proxy controlled reading roles; neither is a child or natural parent-child handoff.',
            'Recorded child variants reuse two inspected Indian MPS sources; not new speakers, Singapore or held-out accuracy.',
            'Midpoint insertions can interrupt a word. They preserve every child sample but do not simulate a natural pause.',
            'Digital equal-RMS mixing is not room acoustics or a microphone test. Human listening fields start blank.',
            'Expected outcomes are predeclared design goals. Failed outcomes are retained, never repaired by sample tuning.',
            'No latency or population accuracy is claimed. Existing close-word false-trigger limitations remain unresolved.'])
    write(output/'protocol.json',protocol);verify(output,model_hash=True)
    print('FROZEN 18 streams: 10 controlled synthetic + 8 variants of 2 recorded children.',flush=True)


def verify(output,model_hash=False,audio=False):
    protocol=check_frozen(output,model_hash=model_hash)
    assert digest(output/'jobs.json')==protocol['jobs_sha256']
    assert digest(output/'synthesis-jobs.json')==protocol['synthesis_jobs_sha256']
    for name,sha in protocol['original_inputs_sha256'].items():assert digest(Path(name))==sha,name
    if audio:
        inventory=read(output/'audio-inventory.json')
        assert [r['id'] for r in inventory]==protocol['ordered_recordings']
        for row in inventory:assert digest(Path(row['audio']))==row['audio_sha256'],row['id']
        for row in read(output/'synthesis-inventory.json'):assert digest(Path(row['audio']))==row['audio_sha256']
    return protocol


def load_audio(path):
    data,rate=sf.read(str(path),dtype='float64')
    assert rate==RATE and data.ndim==1
    return data


def matched_level(overlay,primary):
    rms=lambda x:float(np.sqrt(np.mean(x*x)))
    assert rms(overlay)>0 and rms(primary)>0
    return overlay*(rms(primary)/rms(overlay))


def compose(output):
    verify(output);synthesis=read(output/'synthesis-jobs.json');parts={};inventory=[]
    for row in synthesis:
        parts[row['id']]=load_audio(row['audio'])
        inventory.append(dict(id=row['id'],audio=row['audio'],audio_sha256=digest(Path(row['audio'])),samples=len(parts[row['id']])))
    assert not (output/'audio-inventory.json').exists()
    write(output/'synthesis-inventory.json',inventory);rows=[];gap=np.zeros(round(.4*RATE))
    for job in read(output/'jobs.json'):
        assert not Path(job['audio']).exists()
        chunks=[];spans=[];cursor=0
        def add(data,label):
            nonlocal cursor
            spans.append(dict(label=label,start=cursor/RATE,end=(cursor+len(data))/RATE))
            chunks.append(data);cursor+=len(data)
        if job['group']=='controlled_synthetic_roles':
            for index,step in enumerate(job['plan']):
                if index:add(gap,'sentence_gap')
                if isinstance(step,(float,int)):add(np.zeros(round(step*RATE)),'pause')
                elif isinstance(step,str):add(parts[step],step)
                else:
                    primary=parts[step['primary']];overlay=matched_level(parts[step['overlay']],primary)
                    data=np.zeros(max(len(primary),len(overlay)));data[:len(primary)]+=primary;data[:len(overlay)]+=overlay
                    add(data,step['primary']+'+overlap_'+step['overlay'])
        else:
            child=load_audio(job['source_audio']);cut=len(child)//2;aside=parts['aside']
            if job['category']=='baseline':add(child,'child_full')
            elif job['category']=='coaching_before_reading':
                add(parts[job['coach_part']],'parent_coaching');add(gap,'sentence_gap');add(child,'child_full')
            elif job['category']=='inserted_aside':
                add(child[:cut],'child_first_half');add(gap,'sentence_gap');add(aside,'parent_aside')
                add(gap,'sentence_gap');add(child[cut:],'child_second_half')
                assert len(chunks[0])+len(chunks[-1])==len(child)
                assert np.array_equal(np.concatenate((chunks[0],chunks[-1])),child)
            else:
                overlay=matched_level(aside,child);data=child.copy()
                stop=min(len(data),cut+len(overlay));data[cut:stop]+=overlay[:stop-cut]
                assert stop-cut==len(overlay)
                add(data,'child_full_with_parent_overlap')
                spans.append(dict(label='parent_overlap',start=cut/RATE,end=stop/RATE))
        data=np.concatenate(chunks)*.4;peak=float(np.max(np.abs(data)))
        safety=min(1.0,.95/peak) if peak else 1.0;data*=safety
        sf.write(job['audio'],data,RATE,subtype='PCM_16')
        reread=load_audio(job['audio']);assert len(reread)==len(data) and np.max(np.abs(reread-data))<1/32768+1e-10
        rows.append(dict(id=job['id'],audio=job['audio'],audio_sha256=digest(Path(job['audio'])),
            samples=len(data),audio_seconds=len(data)/RATE,source_gain=.4,peak_safety_gain=safety,spans=spans,
            composition_only=True,human_audio_labels=False))
    write(output/'audio-inventory.json',rows);verify(output,model_hash=True,audio=True)
    print('COMPOSED',len(rows),'streams;',round(sum(r['audio_seconds'] for r in rows),2),'seconds. No child samples removed.',flush=True)


def audit(output,job,info):
    stem=output/'streams'/job['id']
    events=[json.loads(s) for s in stem.with_suffix('.events.jsonl').read_text(encoding='utf-8').splitlines()]
    packets=[e for e in events if e['kind']=='audio'];callbacks=[e for e in events if e['kind']=='segments'];count=0
    for event in packets:assert event['sample_start']==count;count+=event['sample_count']
    assert count==info['samples'] and callbacks
    assert callbacks[-1]['segments'][-1]['completed']
    assert abs(callbacks[-1]['segments'][-1]['end']-info['audio_seconds'])<.001
    assert any(e['kind']=='status' and e.get('message')=='STREAM_DONE' for e in events)
    assert not any(e['kind']=='status' and e.get('status')=='ERROR' for e in events)
    assert not any(e['kind']=='book_context_sent' for e in events)
    cfg=read(Path(job['manifest']));ledger=replay(TimelyEvidenceMatcher,cfg,events)
    observed=[e for e in events if e['kind']=='tracker' and e['mode']=='timely']
    decisions=[dict(id=e['scene'],audio_end=e['audio_end']) for e in observed if e['triggered']]
    assert [e['id'] for e in decisions]==ledger['emitted']
    assert [e['scene'] for e in observed if e.get('suppressed')]==ledger['suppressed']
    log=stem.with_suffix('.log').read_text(encoding='utf-8')
    assert re.findall(r'^\[TRIGGER\] (\S+):',log,re.M)==ledger['emitted']
    assert re.findall(r'^\[SUPPRESSED\] (\S+):',log,re.M)==ledger['suppressed']
    row=dict(id=job['id'],group=job['group'],category=job['category'],source_id=job.get('source_id'),
        target=job['target'],expected_target_emit=job['expected_target_emit'],
        target_emitted=job['target'] in ledger['emitted'],outcomes=ledger,decisions=decisions,
        final_asr=' '.join(s['text'] for s in callbacks[-1]['segments']),
        samples_delivered=count,audio_seconds=info['audio_seconds'],audio_sha256=info['audio_sha256'],
        delivery_audit_pass=True,stream_done=True,app_observer_replay_agreement=True,
        partial_before_eof=any(e['wall']<packets[-1]['wall'] and not e['segments'][-1]['completed'] for e in callbacks))
    row['target_expectation_met']=row['target_emitted']==job['expected_target_emit']
    if job.get('expected_emitted') is not None:
        row['expected_emitted']=job['expected_emitted']
        row['missing_expected']=sorted(set(job['expected_emitted'])-set(ledger['emitted']))
        row['unexpected_emitted']=sorted(set(ledger['emitted'])-set(job['expected_emitted']))
        target_parts=[s for s in info['spans'] if s['label'] in ('zira_target','david_target','zira_target+overlap_aside')]
        row['target_before_legitimate_reading']=[e for e in decisions if e['id']=='target'
            and (not target_parts or e['audio_end']<target_parts[0]['start'])]
    elif any(s['label'].startswith('child') for s in info['spans']):
        child_start=next(s['start'] for s in info['spans'] if s['label'].startswith('child'))
        row['emissions_before_child_reading']=[e for e in decisions if e['audio_end']<child_start]
    return row


def run(output):
    protocol=verify(output,model_hash=True,audio=True);jobs=read(output/'jobs.json')
    inventory={r['id']:r for r in read(output/'audio-inventory.json')}
    assert [j['id'] for j in jobs]==protocol['ordered_recordings']
    (output/'streams').mkdir(exist_ok=False);rows=[]
    for index,job in enumerate(jobs,1):
        verify(output);assert digest(Path(job['audio']))==inventory[job['id']]['audio_sha256']
        stem=output/'streams'/job['id'];print('START',index,'/',len(jobs),job['id'],flush=True)
        command=[sys.executable,'-X','utf8','-u','benchmarks/live_tracker_probe.py','--model','parakeet-nemo',
            '--server','127.0.0.1','--port','9097','--matching_mode','split','--no_book_context',
            '--files',job['audio'],'--mute_audio_playback','--checkpoints',job['manifest'],
            '--transcript_file',str(stem.with_suffix('.srt'))]
        env=dict(os.environ,PYTHONUTF8='1');env.pop('TRACKER_COMPARE_MANIFESTS',None)
        with stem.with_suffix('.log').open('w',encoding='utf-8') as f:
            subprocess.run(command,cwd=ROOT,env=env,stdout=f,stderr=subprocess.STDOUT,
                timeout=math.ceil(inventory[job['id']]['audio_seconds']*1.5)+180,check=True)
        verify(output);row=audit(output,job,inventory[job['id']]);rows.append(row)
        write(output/'results.json',dict(cases=rows))
        print('DONE',job['id'],row['outcomes'],'desired target met:',row['target_expectation_met'],flush=True)
    verify(output,model_hash=True,audio=True)
    write(output/'completed.json',dict(fresh_streams=18,all_trials_retained=True,one_trial_per_input=True,
        runtime_model_manifest_audio_hashes_unchanged=True,all_delivery_eof_app_replay_audits_pass=True))
    print('COMPLETE 18 streams. Semantic failures retained; runtime unchanged.',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage',choices=('prepare','compose','run'),required=True)
    parser.add_argument('--output',type=Path,default=DEST);args=parser.parse_args();output=args.output.resolve()
    if not output.is_relative_to(ROOT/'output'):parser.error('Raw artifacts must stay under output/.')
    {'prepare':prepare,'compose':compose,'run':run}[args.stage](output)
