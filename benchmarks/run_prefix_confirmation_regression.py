"""General exact-prefix confirmation regression; ASR/settings remain unchanged."""
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
from benchmarks.run_shared_policy_regression import fixture,signature

DEST=ROOT/'output/prefix-confirmation-regression-v2-2026-11-03'
PRIOR=ROOT/'output/shared-policy-regression-2026-11-03'
SINGAPORE=ROOT/'output/childes-singapore-streaming-2026-11-02'
RECOVERIES=[dict(id='singapore-full_recording',checkpoint='utterance_03'),
            dict(id='shared-4a35g_EN-OL-RC-426_2-coaching_before_reading',checkpoint='hibernate')]


def prepare(output):
    assert (output/'baseline.json').exists() and not (output/'protocol.json').exists()
    baseline=read(output/'baseline.json');original=read(PRIOR/'protocol.json')
    prior_results={r['id']:r['outcomes'] for r in read(PRIOR/'saved-after.json')['cases']}
    fixtures=[]
    for job in read(PRIOR/'replay-jobs.json'):
        extras={k:v for k,v in job.items() if k not in ('id','group','manifest','manifest_sha256','events','events_sha256','expected_before')}
        fixtures.append(fixture(output,job['id'],job['group'],Path(job['manifest']),Path(job['events']),prior_results[job['id']],**extras))
    write(output/'replay-jobs.json',fixtures)
    policies=[]
    for index,path in enumerate(read(PRIOR/'offbook-manifests.json'),1):
        target=output/'offbook-policies'/f'passage-{index}.json';target.parent.mkdir(exist_ok=True)
        shutil.copyfile(path,target);policies.append(str(target))
    write(output/'offbook-manifests.json',policies)
    jobs=[];inventory=[]
    def add(job,info):
        folder=output/'inputs'/job['id'];folder.mkdir(parents=True)
        target=folder/'checkpoints.json';shutil.copyfile(job['manifest'],target)
        job.update(manifest=str(target),manifest_sha256=digest(target))
        with wave.open(job['audio']) as wav:
            assert wav.getframerate()==16000 and wav.getnchannels()==1 and wav.getsampwidth()==2
            count=wav.getnframes()
        info=dict(info,id=job['id'],audio=job['audio'],samples=count,audio_seconds=count/16000,
                  audio_sha256=digest(Path(job['audio'])))
        jobs.append(job);inventory.append(info)
    singapore=next(j for j in read(SINGAPORE/'jobs.json') if j['id']=='full_recording')
    add(dict(id='singapore-full_recording',group='singapore_conversation',category='full_recording',source_id='e5d6a',
        audio=singapore['audio'],manifest=singapore['manifest'],target='utterance_03',expected_target_emit=True,
        baseline_events=str(SINGAPORE/'streams/full_recording.events.jsonl')),
        dict(spans=[dict(label='child_full',start=0,end=singapore['audio_seconds'])]))
    old_inventory={r['id']:r for r in read(PRIOR/'audio-inventory.json')}
    for prior in read(PRIOR/'jobs.json'):
        job=dict(prior,baseline_events=str(PRIOR/'streams'/(prior['id']+'.events.jsonl')))
        add(job,old_inventory[job['id']])
    assert len(jobs)==32 and len(fixtures)==214
    write(output/'jobs.json',jobs);write(output/'audio-inventory.json',inventory)
    files=set(source_files())|{Path(__file__).resolve(),ROOT/'benchmarks/replay_policy_batch.py',
        ROOT/'benchmarks/run_shared_reading.py',ROOT/'benchmarks/run_shared_policy_regression.py',
        ROOT/'benchmarks/run_pending_regression.py',*list((ROOT/'tests').glob('*.py'))}
    hashes={}
    for path in sorted(files):
        name=path.relative_to(ROOT).as_posix();data=path.read_bytes()
        target=output/'source-snapshot'/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
        hashes[name]=hashlib.sha256(data).hexdigest()
    changed=[name for name,sha in baseline['source_sha256'].items() if hashes[name]!=sha]
    assert changed==['books_to_life/matching/timely_matcher.py'],changed
    protocol=dict(date='2026-11-03',scope='General exact-prefix confirmation regression',
        configuration=baseline['configuration'],model=baseline['model'],lexicon=baseline['lexicon'],
        source_sha256=hashes,baseline_sha256=baseline['source_sha256'],
        jobs_sha256=digest(output/'jobs.json'),replay_jobs_sha256=digest(output/'replay-jobs.json'),
        audio_inventory_sha256=digest(output/'audio-inventory.json'),
        ordered_recordings=[j['id'] for j in jobs],fresh_streams=32,saved_comparisons=214,
        fresh_shared_streams=18,fresh_reviewed_mps=9,fresh_unrelated=4,fresh_singapore_full=1,
        changed_runtime_files=changed,provider_deletion_controls=original['provider_deletion_controls'],
        asserted_recoveries=RECOVERIES,
        prefix_rule='Unique exact leading anchor prefix, length at least minimum_words minus one, three distinct words, no more than three anchor words remaining; optionally one proper partial next token. A later accepted ordinary candidate must contain the entire exact recent anchor in a newer callback over newer audio within the same segment and existing 12-second/12-update bounds.',
        asr_model_lexicon_thresholds_audio_manifests_unchanged=True,shared_reading_policy_unchanged=True,
        no_word_exceptions=True,no_sample_specific_tuning=True,one_trial_per_selected_input=True,
        selection_and_goals_fixed_before_fresh_recognition=True,
        limits=['All inputs are inspected regressions, not new held-out accuracy evidence.',
            'Singapore adds one continuous classroom source, not an authored reading passage or multiple independent sources.',
            'Existing shared audio is constructed from two adult TTS voices and two reused child recordings; not natural family/room audio.',
            'The new evidence path requires exact complete anchor text and retains ordinary candidate filters; fuzzy and split routes remain unchanged.',
            'Known close wrong-word false fires and ASR errors remain separate limitations. No word-latency score is claimed.'])
    write(output/'protocol.json',protocol);verify(output,model_hash=True,audio=True)
    print('FROZEN 214 saved comparisons and 32 fresh streams; only timely_matcher changes.',flush=True)


def verify(output,model_hash=False,audio=False):
    protocol=check_frozen(output,model_hash=model_hash)
    for file,key in [('jobs.json','jobs_sha256'),('replay-jobs.json','replay_jobs_sha256'),('audio-inventory.json','audio_inventory_sha256')]:
        assert digest(output/file)==protocol[key]
    for job in read(output/'replay-jobs.json'):
        assert digest(Path(job['events']))==job['events_sha256']
        assert digest(Path(job['manifest']))==job['manifest_sha256']
    if audio:
        for row in read(output/'audio-inventory.json'):assert digest(Path(row['audio']))==row['audio_sha256']
    return protocol


def batch(output,jobs,destination,old=False):
    command=[sys.executable,'-X','utf8','-u','benchmarks/replay_policy_batch.py','--jobs',str(jobs),'--output',str(destination)]
    if old:command+=['--snapshot',str(output/'baseline-snapshot')]
    else:command+=['--prefix-evidence']
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
    assert all('target' not in after[j['id']]['emitted'] for j in jobs if j['group']=='saved_challenge'
        and j['category'] in ('omitted','negated_prompt','distant_wrong_word','prefix_then_unrelated','skipped'))
    for case in RECOVERIES:assert case['checkpoint'] in after[case['id']]['emitted'],case
    changes=[dict(id=j['id'],group=j['group'],added=sorted(set(after[j['id']]['emitted'])-set(before[j['id']]['emitted'])),
        removed=sorted(set(before[j['id']]['emitted'])-set(after[j['id']]['emitted']))) for j in jobs if before[j['id']]!=after[j['id']]]
    assert not any(r['removed'] for r in changes)
    write(output/'preflight.json',dict(comparisons=214,old_replay_matches_all_original_ledgers=True,
        provider_deletion_and_unrelated_controls_pass=True,both_requested_recoveries_pass=True,changes=changes))
    print('PREFLIGHT all 214 ledgers verified; both recoveries and omission controls pass.',flush=True)
    print('CHANGES',json.dumps(changes),flush=True)


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
            for index,manifest in enumerate(read(output/'offbook-manifests.json'),1):
                fresh.append(dict(id=job['id']+'-policy-'+str(index),group='fresh_unrelated_comparison',manifest=manifest,
                    manifest_sha256=digest(Path(manifest)),events=str(path),events_sha256=digest(path)))
    write(output/'fresh-replay-jobs.json',fresh)
    batch(output,output/'fresh-replay-jobs.json',output/'fresh-before.json',True)
    batch(output,output/'fresh-replay-jobs.json',output/'fresh-after.json')
    current={r['id']:r['outcomes'] for r in read(output/'fresh-after.json')['cases']}
    for row in rows:
        assert current[row['id']]==row['outcomes']
        if row['group']=='reviewed_mps':assert row['target_expectation_met'],row['id']
    for case in RECOVERIES:assert case['checkpoint'] in current[case['id']]['emitted'],case
    assert all(not r['outcomes']['emitted'] for r in read(output/'fresh-after.json')['cases'] if r['group']=='fresh_unrelated_comparison')
    verify(output,model_hash=True,audio=True)
    write(output/'completed.json',dict(fresh_streams=32,saved_comparisons=214,one_trial_per_input=True,
        all_trials_retained=True,all_transport_app_replay_audits_pass=True,both_requested_recoveries_pass=True,
        nine_reviewed_assertions_pass=True,fresh_unrelated_comparisons=24,unrelated_effects=0,
        sources_frozen_during_testing=True,asr_model_thresholds_audio_manifests_unchanged=True))
    print('COMPLETE 32 fresh streams; both recoveries, nine reviewed assertions and unrelated controls pass.',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--stage',choices=('prepare','preflight','run'),required=True)
    parser.add_argument('--output',type=Path,default=DEST);args=parser.parse_args();output=args.output.resolve()
    if not output.is_relative_to(ROOT/'output'):parser.error('Raw results must stay under output/.')
    {'prepare':prepare,'preflight':preflight,'run':run}[args.stage](output)
