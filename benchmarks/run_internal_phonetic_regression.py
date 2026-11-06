"""Frozen internal-pronunciation permission regression; ASR is unchanged."""
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import cmudict

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from benchmarks.run_mps_heldout import read,write,digest,source_files
from benchmarks.run_shared_policy_regression import fixture,signature
from benchmarks.run_shared_reading import audit
from benchmarks.run_pending_regression import replay
from books_to_life.matching.timely_matcher import TimelyEvidenceMatcher

DEST=ROOT/'output/internal-phonetic-regression-2026-11-03'
PRIOR=ROOT/'output/resumption-regression-v3-2026-11-03'
NEGATIVES={'omitted','negated_prompt','distant_wrong_word','prefix_then_unrelated','skipped'}
TARGET='shared-3a8b_EN-OL-RC-234_1-coaching_before_reading'


def prepare(output):
    assert (output/'baseline.json').exists() and not (output/'protocol.json').exists()
    baseline=read(output/'baseline.json');prior=read(PRIOR/'protocol.json')
    fixtures=[];saved={r['id']:r['outcomes'] for r in read(PRIOR/'saved-after.json')['cases']}
    for j in read(PRIOR/'replay-jobs.json'):
        extra={k:v for k,v in j.items() if k not in ('id','group','manifest','manifest_sha256','events','events_sha256','expected_before')}
        fixtures.append(fixture(output,j['id'],j['group'],Path(j['manifest']),Path(j['events']),saved[j['id']],**extra))
    fresh={r['id']:r['outcomes'] for r in read(PRIOR/'fresh-after.json')['cases']}
    old_jobs=read(PRIOR/'jobs.json')
    for j in old_jobs:
        fixtures.append(fixture(output,'resumption-'+j['id'],'resumption_'+j['group'],Path(j['manifest']),
            PRIOR/'streams'/(j['id']+'.events.jsonl'),fresh[j['id']],category=j['category']))
    assert len(fixtures)==327
    write(output/'replay-jobs.json',fixtures)
    requested=[TARGET,'shared-long_pause','shared-4a35g_EN-OL-RC-426_2-inserted_aside']
    selected=[next(j for j in old_jobs if j['id']==ident) for ident in requested]
    selected += [j for j in old_jobs if j['group']=='reviewed_mps']
    selected += [j for j in old_jobs if j['group']=='synthetic_challenge' and j['category']=='omitted']
    selected += [j for j in old_jobs if j['id'].startswith('phase-')]
    selected += [j for j in old_jobs if j['group']=='unrelated']
    assert len(selected)==25 and len({j['id'] for j in selected})==25
    old_inventory={r['id']:r for r in read(PRIOR/'audio-inventory.json')}
    jobs=[];inventory=[]
    for original in selected:
        j=dict(original);dest=output/'inputs'/j['id']/'checkpoints.json';dest.parent.mkdir(parents=True)
        shutil.copyfile(j['manifest'],dest)
        j.update(manifest=str(dest),manifest_sha256=digest(dest),
            baseline_events=str(PRIOR/'streams'/(j['id']+'.events.jsonl')),
            baseline_emitted=fresh[j['id']]['emitted'])
        if j['id']==TARGET:j['asserted_checkpoint']='lost_sheep'
        jobs.append(j);inventory.append(old_inventory[j['id']])
    write(output/'jobs.json',jobs);write(output/'audio-inventory.json',inventory)
    shutil.copyfile(PRIOR/'offbook-manifests.json',output/'offbook-manifests.json')
    files=set(source_files())|set((ROOT/'tests').glob('*.py'))|{Path(__file__).resolve(),
        ROOT/'benchmarks/replay_policy_batch.py',ROOT/'benchmarks/run_pending_regression.py',
        ROOT/'benchmarks/run_shared_reading.py',ROOT/'benchmarks/run_shared_policy_regression.py'}
    hashes={}
    for path in sorted(files):
        name=path.relative_to(ROOT).as_posix();dest=output/'source-snapshot'/name;dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(path,dest);hashes[name]=digest(path)
    changed=[name for name,sha in hashes.items() if name.startswith('books_to_life/') and sha!=baseline['source_sha256'].get(name)]
    assert changed==['books_to_life/matching/effect_permission.py','books_to_life/matching/timely_matcher.py'],changed
    write(output/'protocol.json',dict(date='2026-11-03',scope=__doc__,configuration=baseline['configuration'],
        model=baseline['model'],lexicon=baseline['lexicon'],source_sha256=hashes,baseline_sha256=baseline['source_sha256'],
        jobs_sha256=digest(output/'jobs.json'),audio_inventory_sha256=digest(output/'audio-inventory.json'),
        replay_jobs_sha256=digest(output/'replay-jobs.json'),changed_runtime_files=changed,
        fresh_streams=25,saved_comparisons=327,ordered_recordings=[j['id'] for j in jobs],
        provider_deletion_controls=prior['provider_deletion_controls'],
        selection_fixed_before_new_recognition=True,one_trial_per_selected_input=True,all_trials_retained=True,
        model_asr_lexicon_thresholds_and_audio_unchanged=True,no_word_exceptions=True,
        rule='After ordinary alignment/confirmation acquires the next checkpoint, one internal observed token can supply the last missing coverage match using the existing pronunciation rule. It must be unambiguously bracketed by exact ordered neighbours, with an exact endpoint and at least three distinct ordinary anchor words. Required words retain stricter spelling. It cannot fill a token gap or supply two extra matches.',
        limits=['These are inspected regressions and reused sources, not held-out child accuracy.',
            'Twenty-five fresh streams are separate from the 327 saved callback comparisons.',
            'The default permission policy is pronunciation-tolerant; close intentional word choices may be indistinguishable from mispronunciation.',
            'The ASR and silence handling are unchanged from the preceding resumption version; microphone/room validation remains pending.']))
    verify(output,model_hash=True,audio=True)
    print('FROZEN 25 fresh streams and 327 saved comparisons; only permission/its local caller change.',flush=True)


def verify(output,model_hash=False,audio=False):
    p=read(output/'protocol.json')
    for name,sha in p['source_sha256'].items():assert digest(ROOT/name)==sha,name
    for name,sha in p['baseline_sha256'].items():assert digest(output/'baseline-snapshot'/name)==sha,name
    for name,key in [('jobs.json','jobs_sha256'),('audio-inventory.json','audio_inventory_sha256'),('replay-jobs.json','replay_jobs_sha256')]:assert digest(output/name)==p[key]
    for j in read(output/'jobs.json'):assert digest(Path(j['manifest']))==j['manifest_sha256']
    if audio:
        for r in read(output/'audio-inventory.json'):assert digest(Path(r['audio']))==r['audio_sha256']
    assert importlib.metadata.version('cmudict')==p['lexicon']['version']
    assert hashlib.sha256(cmudict.dict_string().encode('utf-8')).hexdigest()==p['lexicon']['data_sha256']
    model=ROOT/p['model']['path'];assert model.stat().st_size==p['model']['bytes'] and model.stat().st_mtime_ns==p['model']['mtime_ns']
    if model_hash:assert digest(model)==p['model']['sha256']
    return p


def preflight(output):
    p=verify(output,audio=True)
    for label,old in [('before',True),('after',False)]:
        cmd=[sys.executable,'-X','utf8','-u','benchmarks/replay_policy_batch.py','--jobs',str(output/'replay-jobs.json'),'--output',str(output/f'saved-{label}.json')]
        if old:cmd+=['--snapshot',str(output/'baseline-snapshot')]
        subprocess.run(cmd,cwd=ROOT,check=True)
    jobs=read(output/'replay-jobs.json')
    before={r['id']:r['outcomes'] for r in read(output/'saved-before.json')['cases']}
    after={r['id']:r['outcomes'] for r in read(output/'saved-after.json')['cases']}
    for j in jobs:
        assert before[j['id']]==j['expected_before'],j['id']
        assert set(before[j['id']]['emitted']).issubset(after[j['id']]['emitted']),j['id']
        assert before[j['id']]['skipped']==after[j['id']]['skipped'],j['id']
        if 'unrelated' in j['group']:assert not after[j['id']]['emitted'],j['id']
        if 'challenge' in j['group'] and j['category'] in NEGATIVES:assert 'target' not in after[j['id']]['emitted'],j['id']
    for c in p['provider_deletion_controls']:assert c['checkpoint'] not in after['reading-'+c['recording']]['emitted'],c
    assert 'lost_sheep' in after['resumption-'+TARGET]['emitted']
    changes=[dict(id=j['id'],group=j['group'],added=sorted(set(after[j['id']]['emitted'])-set(before[j['id']]['emitted'])))
             for j in jobs if before[j['id']]!=after[j['id']]]
    write(output/'preflight.json',dict(comparisons=327,all_old_ledgers_reproduced=True,no_emitted_effects_removed=True,
        all_skips_unchanged=True,omission_and_unrelated_controls_pass=True,requested_recovery_pass=True,changes=changes))
    print('PREFLIGHT PASS; added effects',json.dumps(changes),flush=True)


def run(output):
    verify(output,model_hash=True,audio=True);assert read(output/'preflight.json')['comparisons']==327
    (output/'streams').mkdir(exist_ok=False);rows=[];infos={r['id']:r for r in read(output/'audio-inventory.json')}
    for n,j in enumerate(read(output/'jobs.json'),1):
        verify(output);stem=output/'streams'/j['id'];print('START',n,'/25',j['id'],flush=True)
        cmd=[sys.executable,'-X','utf8','-u','benchmarks/live_tracker_probe.py','--model','parakeet-nemo',
            '--server','127.0.0.1','--port','9097','--matching_mode','split','--no_book_context','--files',j['audio'],
            '--mute_audio_playback','--checkpoints',j['manifest'],'--transcript_file',str(stem.with_suffix('.srt'))]
        env=dict(os.environ,PYTHONUTF8='1');env.pop('TRACKER_COMPARE_MANIFESTS',None)
        with stem.with_suffix('.log').open('w',encoding='utf-8') as log:
            subprocess.run(cmd,cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=int(infos[j['id']]['audio_seconds']*1.5)+180,check=True)
        row=audit(output,j,infos[j['id']]);row['asr_callbacks_identical_to_previous']=signature(stem.with_suffix('.events.jsonl'))==signature(Path(j['baseline_events']))
        rows.append(row);write(output/'results.json',dict(cases=rows))
        assert row['asr_callbacks_identical_to_previous'],j['id']
        if j.get('asserted_checkpoint'):assert j['asserted_checkpoint'] in row['outcomes']['emitted'],j['id']
        assert row['target_expectation_met'],j['id']
        assert set(j['baseline_emitted']).issubset(row['outcomes']['emitted']),j['id']
        if j['group']=='unrelated':
            events=[json.loads(s) for s in stem.with_suffix('.events.jsonl').read_text(encoding='utf-8').splitlines()]
            for manifest in read(output/'offbook-manifests.json'):assert not replay(TimelyEvidenceMatcher,read(Path(manifest)),events)['emitted'],j['id']
        print('DONE',n,j['id'],row['outcomes'],flush=True)
    verify(output,model_hash=True,audio=True)
    write(output/'completed.json',dict(fresh_streams=25,asr_unchanged=True,all_trials_retained=True,all_delivery_eof_app_replay_audits_pass=True))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--stage',choices=('prepare','preflight','run'),required=True)
    parser.add_argument('--output',type=Path,default=DEST);args=parser.parse_args();globals()[args.stage](args.output.resolve())
