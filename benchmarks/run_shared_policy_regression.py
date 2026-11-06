"""Compare shared-reading policy against the complete frozen old runtime.

Saved callbacks are separate from fresh app streams. Audio/manifests stay fixed;
only the positive-coaching veto changes. Old results are never rewritten.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import wave

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from benchmarks.run_mps_heldout import read,write,digest,source_files,check_frozen
from benchmarks.run_shared_reading import audit

DEST=ROOT/'output/shared-policy-regression-2026-11-03'
SHARED=ROOT/'output/shared-reading-2026-11-03'
PHONETIC=ROOT/'output/phonetic-feature-regression-2026-11-02'
LATEST=ROOT/'output/mps-heldout-phonetic-2026-11-02'
SINGAPORE=ROOT/'output/childes-singapore-streaming-2026-11-02'
CHALLENGES=ROOT/'output/false-trigger-challenges-v2-2026-11-02'


def fixture(output,ident,group,manifest,events,expected=None,**extra):
    target=output/'replay-inputs'/ident/'checkpoints.json';target.parent.mkdir(parents=True)
    shutil.copyfile(manifest,target)
    return dict(id=ident,group=group,manifest=str(target),manifest_sha256=digest(target),
        events=str(events),events_sha256=digest(events),expected_before=expected,**extra)


def prepare(output):
    assert (output/'baseline.json').exists() and not (output/'protocol.json').exists()
    baseline=read(output/'baseline.json');fixtures=[]
    expected={r['recording']:r['after'] for r in read(PHONETIC/'preflight-replay.json')['recordings']}
    for job in read(PHONETIC/'jobs.json'):
        fixtures.append(fixture(output,'reading-'+job['id'],'saved_mps',Path(job['manifest']),
            Path(job['baseline_events']),expected[job['id']]))
    expected={r['recording']:r['after'] for r in read(LATEST/'results.json')['recordings']}
    for job in read(LATEST/'downloaded-jobs.json'):
        fixtures.append(fixture(output,'reading-'+job['id'],'saved_mps',Path(job['manifest']),
            LATEST/'streams'/(job['id']+'.events.jsonl'),expected[job['id']]))
    previous={r['id']:r for r in read(SHARED/'results.json')['cases']}
    for job in read(SHARED/'jobs.json'):
        fixtures.append(fixture(output,'shared-'+job['id'],'saved_shared',Path(job['manifest']),
            SHARED/'streams'/(job['id']+'.events.jsonl'),previous[job['id']]['outcomes'],category=job['category']))
    previous={r['id']:r for r in read(SINGAPORE/'results.json')['streams']}
    for job in read(SINGAPORE/'jobs.json'):
        outcome={k:previous[job['id']][k] for k in ('emitted','suppressed','skipped','unreached')}
        fixtures.append(fixture(output,'singapore-'+job['id'],'saved_singapore',Path(job['manifest']),
            SINGAPORE/'streams'/(job['id']+'.events.jsonl'),outcome))
    previous={r['id']:r for r in read(CHALLENGES/'results.json')['cases']}
    for job in read(CHALLENGES/'jobs.json'):
        fixtures.append(fixture(output,'challenge-'+job['id'],'saved_challenge',Path(job['manifest']),
            CHALLENGES/'streams'/(job['id']+'.events.jsonl'),previous[job['id']]['policies']['default']['after'],
            category=job['category'],target='target',expected_target=job['category'] in ('correct','reread','quoted_prompt')))
    policies=[];seen=set()
    for job in read(LATEST/'downloaded-jobs.json'):
        cfg=read(Path(job['manifest']));key=tuple(p['text'] for p in cfg['pages'])
        if key in seen:continue
        seen.add(key);path=output/'offbook-policies'/f'passage-{len(policies)+1}.json';path.parent.mkdir(exist_ok=True)
        shutil.copyfile(job['manifest'],path);policies.append(str(path))
    assert len(policies)==6
    write(output/'offbook-manifests.json',policies)
    for name in ('dog','dragon','nickel','recording_2'):
        for index,path in enumerate(policies,1):
            cfg=read(Path(path));expected=dict(emitted=[],suppressed=[],skipped=[],unreached=sorted(c['id'] for c in cfg['checkpoints']))
            fixtures.append(fixture(output,f'unrelated-{name}-{index}','saved_unrelated',Path(path),
                PHONETIC/'controls'/(name+'.events.jsonl'),expected))
    assert len(fixtures)==214 and len({j['id'] for j in fixtures})==214
    write(output/'replay-jobs.json',fixtures)
    jobs=[];inventory=[]
    def add_job(job,info):
        folder=output/'inputs'/job['id'];folder.mkdir(parents=True)
        manifest=folder/'checkpoints.json';shutil.copyfile(job['manifest'],manifest)
        job.update(manifest=str(manifest),manifest_sha256=digest(manifest))
        with wave.open(job['audio']) as wav:
            assert wav.getframerate()==16000 and wav.getnchannels()==1 and wav.getsampwidth()==2
            count=wav.getnframes()
        info=dict(info,id=job['id'],audio=job['audio'],samples=count,audio_seconds=count/16000,
                  audio_sha256=digest(Path(job['audio'])))
        jobs.append(job);inventory.append(info)
    old_inventory={r['id']:r for r in read(SHARED/'audio-inventory.json')}
    for original in read(SHARED/'jobs.json'):
        job=dict(original);old_id=job['id'];job['id']='shared-'+old_id
        job['baseline_events']=str(SHARED/'streams'/(old_id+'.events.jsonl'))
        if job['category'] in ('coaching_only','coaching_before_reading'):
            job['expected_target_emit']=True
            if job.get('expected_emitted') is not None:job['expected_emitted']=['start','target','finish']
        job['policy_basis']='Either voice saying supported story text counts, including positive coaching. Earlier skipped checkpoints and one-shot history follow existing progress rules.'
        add_job(job,old_inventory[old_id])
    for original in read(PHONETIC/'downloaded-jobs.json'):
        ident=original['id'];target=original['asserted_checkpoint']
        add_job(dict(id='reading-'+ident,group='reviewed_mps',category='original_recording',source_id=ident,
            audio=original['audio'],manifest=original['manifest'],target=target,
            expected_target_emit=original['expected_emission'],baseline_events=str(PHONETIC/'streams'/(ident+'.events.jsonl'))),
            dict(spans=[dict(label='child_full',start=0,end=original['audio_seconds'])]))
    for name in ('dog','dragon','nickel','recording_2'):
        path=ROOT/f'recordings/library/stories/{name}/readers/{name}/audio.wav'
        target=read(Path(policies[0]))['checkpoints'][0]['id']
        with wave.open(str(path)) as wav:duration=wav.getnframes()/16000
        add_job(dict(id='unrelated-'+name,group='unrelated',category='unrelated',source_id=name,
            audio=str(path),manifest=policies[0],target=target,expected_target_emit=False,
            baseline_events=str(PHONETIC/'controls'/(name+'.events.jsonl'))),
            dict(spans=[dict(label='child_full',start=0,end=duration)]))
    assert len(jobs)==31
    write(output/'jobs.json',jobs);write(output/'audio-inventory.json',inventory)
    files=set(source_files())|{Path(__file__).resolve(),ROOT/'benchmarks/replay_policy_batch.py',
        ROOT/'benchmarks/run_shared_reading.py',ROOT/'benchmarks/run_pending_regression.py',*list((ROOT/'tests').glob('*.py'))}
    hashes={}
    for path in sorted(files):
        name=path.relative_to(ROOT).as_posix();data=path.read_bytes()
        target=output/'source-snapshot'/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
        hashes[name]=hashlib.sha256(data).hexdigest()
    changed=[]
    for name,sha in baseline['source_sha256'].items():
        if hashes[name]!=sha:changed.append(name)
    assert set(changed)=={f'books_to_life/matching/{name}.py' for name in ('effect_permission','timely_matcher','boundary_matcher','split_matcher')}
    deleted=read(PHONETIC/'protocol.json')['provider_deletion_controls']
    protocol=dict(date='2026-11-03',scope='Shared-reading policy regression',
        configuration=baseline['configuration'],model=baseline['model'],lexicon=baseline['lexicon'],
        source_sha256=hashes,baseline_sha256=baseline['source_sha256'],
        jobs_sha256=digest(output/'jobs.json'),replay_jobs_sha256=digest(output/'replay-jobs.json'),
        audio_inventory_sha256=digest(output/'audio-inventory.json'),
        ordered_recordings=[j['id'] for j in jobs],saved_comparisons=214,saved_mps_recordings=123,
        fresh_streams=31,fresh_shared_streams=18,fresh_reviewed_mps=9,fresh_unrelated=4,
        changed_runtime_files=changed,provider_deletion_controls=deleted,
        original_asr_unchanged=True,model_lexicon_audio_manifests_thresholds_unchanged=True,
        no_sample_specific_tuning=True,trial_order_and_goals_fixed_before_new_recognition=True,
        policy='Positive coaching counts as reading. Explicit negated instructions remain blocked unless authored context. Both voices use normal alignment and one-shot history.',
        changed_expectations='Positive quoted prompts now count. In shared coaching-only and child coaching-before cases, the adult actually says the full anchor, so target emission is desired; this is not literal-omission evidence.',
        limits=['All samples are inspected regressions; no held-out or natural-family accuracy claim.',
            'Shared inputs are the same constructed audio as the previous frozen test; only goals implied by the user-approved policy change.',
            'Existing overlap, long-pause recognition, missing-word, and close wrong-word limitations are not repaired by this policy.',
            'Whole-sentence parent reading can use existing forward-jump rules and skip earlier checkpoints. No speaker identity is inferred.'])
    write(output/'protocol.json',protocol);verify(output,model_hash=True,audio=True)
    print('FROZEN 214 saved comparisons and 31 fresh streams. Only positive-coaching policy changes.',flush=True)


def verify(output,model_hash=False,audio=False):
    protocol=check_frozen(output,model_hash=model_hash)
    for filename,key in [('jobs.json','jobs_sha256'),('replay-jobs.json','replay_jobs_sha256'),('audio-inventory.json','audio_inventory_sha256')]:
        assert digest(output/filename)==protocol[key]
    for job in read(output/'replay-jobs.json'):
        assert digest(Path(job['events']))==job['events_sha256']
        assert digest(Path(job['manifest']))==job['manifest_sha256']
    if audio:
        for row in read(output/'audio-inventory.json'):assert digest(Path(row['audio']))==row['audio_sha256']
    return protocol


def batch(output,jobs,destination,old=False):
    command=[sys.executable,'-X','utf8','-u','benchmarks/replay_policy_batch.py','--jobs',str(jobs),'--output',str(destination)]
    if old:command+=['--snapshot',str(output/'baseline-snapshot')]
    subprocess.run(command,cwd=ROOT,check=True)


def preflight(output):
    verify(output);jobs=read(output/'replay-jobs.json')
    batch(output,output/'replay-jobs.json',output/'saved-before.json',True)
    batch(output,output/'replay-jobs.json',output/'saved-after.json')
    before={r['id']:r['outcomes'] for r in read(output/'saved-before.json')['cases']}
    after={r['id']:r['outcomes'] for r in read(output/'saved-after.json')['cases']}
    for job in jobs:assert before[job['id']]==job['expected_before'],job['id']
    for case in read(output/'protocol.json')['provider_deletion_controls']:
        assert case['checkpoint'] not in after['reading-'+case['recording']]['emitted'],case
    assert all(not after[j['id']]['emitted'] for j in jobs if j['group']=='saved_unrelated')
    assert all('target' not in after[j['id']]['emitted'] for j in jobs
        if j['group']=='saved_challenge' and j['category'] in ('omitted','negated_prompt','distant_wrong_word','prefix_then_unrelated','skipped'))
    changes=[dict(id=j['id'],group=j['group'],added=sorted(set(after[j['id']]['emitted'])-set(before[j['id']]['emitted'])),
        removed=sorted(set(before[j['id']]['emitted'])-set(after[j['id']]['emitted']))) for j in jobs if before[j['id']]!=after[j['id']]]
    write(output/'preflight.json',dict(comparisons=214,old_replay_matches_all_original_ledgers=True,
        provider_deletion_and_unrelated_controls_pass=True,changes=changes))
    print('PREFLIGHT verified all 214 original ledgers; control assertions pass.',flush=True)
    print('CHANGES',json.dumps(changes),flush=True)


def signature(path):
    return [e['segments'] for e in (json.loads(s) for s in path.read_text(encoding='utf-8').splitlines()) if e['kind']=='segments']


def run(output):
    verify(output,model_hash=True,audio=True);assert read(output/'preflight.json')['comparisons']==214
    jobs=read(output/'jobs.json');inventory={r['id']:r for r in read(output/'audio-inventory.json')}
    (output/'streams').mkdir(exist_ok=False);rows=[]
    for index,job in enumerate(jobs,1):
        verify(output);assert digest(Path(job['audio']))==inventory[job['id']]['audio_sha256']
        stem=output/'streams'/job['id'];print('START',index,'/',len(jobs),job['id'],flush=True)
        command=[sys.executable,'-X','utf8','-u','benchmarks/live_tracker_probe.py','--model','parakeet-nemo',
            '--server','127.0.0.1','--port','9097','--matching_mode','split','--no_book_context','--files',job['audio'],
            '--mute_audio_playback','--checkpoints',job['manifest'],'--transcript_file',str(stem.with_suffix('.srt'))]
        env=dict(os.environ,PYTHONUTF8='1');env.pop('TRACKER_COMPARE_MANIFESTS',None)
        with stem.with_suffix('.log').open('w',encoding='utf-8') as f:
            subprocess.run(command,cwd=ROOT,env=env,stdout=f,stderr=subprocess.STDOUT,
                timeout=math.ceil(inventory[job['id']]['audio_seconds']*1.5)+180,check=True)
        row=audit(output,job,inventory[job['id']]);verify(output)
        row['asr_callbacks_identical_to_original']=signature(stem.with_suffix('.events.jsonl'))==signature(Path(job['baseline_events']))
        rows.append(row);write(output/'results.json',dict(cases=rows))
        print('DONE',job['id'],row['outcomes'],'ASR identical:',row['asr_callbacks_identical_to_original'],flush=True)
    fresh=[]
    for job in jobs:
        path=output/'streams'/(job['id']+'.events.jsonl')
        fresh.append(dict(id=job['id'],group=job['group'],manifest=job['manifest'],manifest_sha256=job['manifest_sha256'],
            events=str(path),events_sha256=digest(path)))
        if job['group']=='unrelated':
            for i,manifest in enumerate(read(output/'offbook-manifests.json'),1):
                fresh.append(dict(id=job['id']+'-policy-'+str(i),group='fresh_unrelated_comparison',manifest=manifest,
                    manifest_sha256=digest(Path(manifest)),events=str(path),events_sha256=digest(path)))
    write(output/'fresh-replay-jobs.json',fresh)
    batch(output,output/'fresh-replay-jobs.json',output/'fresh-before.json',True)
    batch(output,output/'fresh-replay-jobs.json',output/'fresh-after.json')
    current={r['id']:r['outcomes'] for r in read(output/'fresh-after.json')['cases']}
    for row in rows:
        assert current[row['id']]==row['outcomes']
        if row['group']=='reviewed_mps':assert row['target_expectation_met'],row['id']
    assert all(not r['outcomes']['emitted'] for r in read(output/'fresh-after.json')['cases'] if r['group']=='fresh_unrelated_comparison')
    verify(output,model_hash=True,audio=True)
    write(output/'completed.json',dict(fresh_streams=31,saved_comparisons=214,
        one_trial_per_selected_input=True,all_trials_retained=True,all_transport_and_app_replay_audits_pass=True,
        nine_reviewed_mps_assertions_pass=True,fresh_unrelated_comparisons=24,unrelated_effects=0,
        sources_frozen_during_testing=True,asr_model_audio_manifests_unchanged=True))
    print('COMPLETE 31 fresh streams; nine reviewed assertions and 24 unrelated comparisons pass.',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--stage',choices=('prepare','preflight','run'),required=True)
    parser.add_argument('--output',type=Path,default=DEST);args=parser.parse_args();output=args.output.resolve()
    if not output.is_relative_to(ROOT/'output'):parser.error('Raw results must stay under output/.')
    {'prepare':prepare,'preflight':preflight,'run':run}[args.stage](output)
