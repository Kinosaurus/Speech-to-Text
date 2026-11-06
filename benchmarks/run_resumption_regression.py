"""Frozen speech-resumption regression: 246 saved comparisons and 81 streams."""
import argparse
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import wave

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from benchmarks.run_mps_heldout import read,write,digest,source_files
from benchmarks.run_shared_reading import audit
from benchmarks.run_shared_policy_regression import fixture
from benchmarks.run_pending_regression import replay
from books_to_life.matching.timely_matcher import TimelyEvidenceMatcher

DEST=ROOT/'output/resumption-regression-v3-2026-11-03'
PRIOR=ROOT/'output/prefix-confirmation-regression-v2-2026-11-03'
PHASE=ROOT/'output/pause-asr-diagnostic-2026-11-03'
CHALLENGE=ROOT/'output/false-trigger-challenges-v2-2026-11-02'
NEGATIVES={'omitted','negated_prompt','distant_wrong_word','prefix_then_unrelated','skipped'}


def prepare(output):
    assert (output/'baseline.json').exists() and not (output/'protocol.json').exists()
    baseline=read(output/'baseline.json');old=read(PRIOR/'protocol.json')
    expected={r['id']:r['outcomes'] for r in read(PRIOR/'saved-after.json')['cases']}
    fixtures=[]
    for j in read(PRIOR/'replay-jobs.json'):
        extra={k:v for k,v in j.items() if k not in ('id','group','manifest','manifest_sha256','events','events_sha256','expected_before')}
        fixtures.append(fixture(output,j['id'],j['group'],Path(j['manifest']),Path(j['events']),expected[j['id']],**extra))
    expected_fresh={r['id']:r['outcomes'] for r in read(PRIOR/'fresh-after.json')['cases']}
    old_jobs=read(PRIOR/'jobs.json')
    for j in old_jobs:
        fixtures.append(fixture(output,'latest-'+j['id'],'latest_'+j['group'],Path(j['manifest']),
            PRIOR/'streams'/(j['id']+'.events.jsonl'),expected_fresh[j['id']]))
    write(output/'replay-jobs.json',fixtures)
    requested=['shared-long_pause','shared-4a35g_EN-OL-RC-426_2-inserted_aside']
    omissions=[j['id'] for j in old_jobs if j['group']=='reviewed_mps' and not j['expected_target_emit']]
    initial=[next(j for j in old_jobs if j['id']==ident) for ident in requested+omissions]
    phase=[dict(j,id='phase-'+j['id'],baseline_events=str(PHASE/'streams'/(j['id']+'.events.jsonl')))
           for j in read(PHASE/'jobs.json')]
    challenges=[]
    old_challenges={r['id']:r['outcomes'] for r in read(PRIOR/'saved-after.json')['cases'] if r['group']=='saved_challenge'}
    for j in sorted(read(CHALLENGE/'jobs.json'),key=lambda j:(j['category'] not in NEGATIVES,j['id'])):
        challenges.append(dict(id='challenge-'+j['id'],group='synthetic_challenge',category=j['category'],
            audio=j['audio'],manifest=j['manifest'],target='target',expected_target_emit=j['category'] not in NEGATIVES,
            baseline_events=str(CHALLENGE/'streams'/(j['id']+'.events.jsonl')),
            baseline_emitted=old_challenges['challenge-'+j['id']]['emitted'],
            expectation_basis='Current shared-reading policy plus five explicit user-accepted pronunciation variants; historical literal trial labels remain unchanged.'))
    remaining=[j for j in old_jobs if j['id'] not in requested+omissions]
    jobs=[];inventory=[]
    for original in initial+phase+challenges+remaining:
        j=dict(original);folder=output/'inputs'/j['id'];folder.mkdir(parents=True)
        path=folder/'checkpoints.json';shutil.copyfile(j['manifest'],path)
        j.update(manifest=str(path),manifest_sha256=digest(path))
        if j['id'] in requested:
            j['asserted_checkpoint']='target' if j['id']==requested[0] else 'clever_bears'
        if 'baseline_events' not in j:j['baseline_events']=str(PRIOR/'streams'/(j['id']+'.events.jsonl'))
        with wave.open(j['audio']) as wav:
            assert (wav.getframerate(),wav.getnchannels(),wav.getsampwidth())==(16000,1,2)
            n=wav.getnframes()
        info=dict(id=j['id'],audio=j['audio'],audio_sha256=digest(Path(j['audio'])),samples=n,
                  audio_seconds=n/16000,spans=[])
        if j.get('expected_emitted') is not None:
            # Only emission-before-reading diagnostics need a composition span.
            original_id=j['id'].removeprefix('phase-')
            source=PHASE if j['id'].startswith('phase-') else PRIOR
            info['spans']=next(r['spans'] for r in read(source/'audio-inventory.json') if r['id']==original_id)
        jobs.append(j);inventory.append(info)
    assert len(jobs)==81 and len(fixtures)==246
    write(output/'jobs.json',jobs);write(output/'audio-inventory.json',inventory)
    shutil.copyfile(PRIOR/'offbook-manifests.json',output/'offbook-manifests.json')
    files=set(source_files())|set((ROOT/'tests').glob('*.py'))|{Path(__file__).resolve(),
        ROOT/'benchmarks/replay_policy_batch.py',ROOT/'benchmarks/run_shared_reading.py',
        ROOT/'benchmarks/run_shared_policy_regression.py',ROOT/'benchmarks/run_pending_regression.py'}
    hashes={}
    for path in sorted(files):
        name=path.relative_to(ROOT).as_posix();target=output/'source-snapshot'/name
        target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,target);hashes[name]=digest(path)
    changed=[name for name,sha in hashes.items() if name.startswith('books_to_life/') and baseline['source_sha256'].get(name)!=sha]
    assert changed==['books_to_life/cli/run_nemo_server.py','books_to_life/matching/timely_matcher.py','books_to_life/runtime/streaming_utterances.py'],changed
    write(output/'protocol.json',dict(date='2026-11-03',scope=__doc__,configuration=baseline['configuration'],
        model=baseline['model'],lexicon=baseline['lexicon'],source_sha256=hashes,baseline_sha256=baseline['source_sha256'],
        changed_runtime_files=changed,jobs_sha256=digest(output/'jobs.json'),
        audio_inventory_sha256=digest(output/'audio-inventory.json'),replay_jobs_sha256=digest(output/'replay-jobs.json'),
        ordered_recordings=[j['id'] for j in jobs],fresh_streams=81,saved_comparisons=246,
        provider_deletion_controls=old['provider_deletion_controls'],requested_recoveries=requested,
        trials_per_selected_input=1,all_trials_retained=True,selection_fixed_before_new_recognition=True,
        same_model_and_numeric_thresholds=True,no_word_exceptions=True,no_added_audio_padding_rule=True,
        limits=['These are inspected regressions, not new-speaker/population accuracy.',
            'Exact digital silence is detected without an amplitude threshold. Room noise is not classified as silence.',
            'The model right-context length determines utterance closure; its normal EOF encoder context is unchanged.',
            'The 32 prior inputs plus 45 challenge inputs and four phase inputs include repeated identical PCM; these are not 81 independent sources.',
            'Fresh challenge streams use the default pod manifest; required-endpoint observers remain historical comparisons.',
            'The two unclear overlap cases have no required positive listening label. Callback markers are not verified word latency.']))
    verify(output,model_hash=True,audio=True)
    print('FROZEN 81 paced streams; 246 saved comparisons.',flush=True)


def verify(output,model_hash=False,audio=False):
    p=read(output/'protocol.json')
    for name,sha in p['source_sha256'].items():assert digest(ROOT/name)==sha,name
    for name,sha in p['baseline_sha256'].items():assert digest(output/'baseline-snapshot'/name)==sha,name
    for name,key in [('jobs.json','jobs_sha256'),('audio-inventory.json','audio_inventory_sha256'),('replay-jobs.json','replay_jobs_sha256')]:
        assert digest(output/name)==p[key]
    for j in read(output/'jobs.json'):assert digest(Path(j['manifest']))==j['manifest_sha256']
    if audio:
        for r in read(output/'audio-inventory.json'):assert digest(Path(r['audio']))==r['audio_sha256']
    assert importlib.metadata.version('cmudict')==p['lexicon']['version']
    model=ROOT/p['model']['path'];assert model.stat().st_size==p['model']['bytes']
    assert model.stat().st_mtime_ns==p['model']['mtime_ns']
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
    for j in jobs:assert before[j['id']]==j['expected_before'],j['id']
    for c in p['provider_deletion_controls']:assert c['checkpoint'] not in after['reading-'+c['recording']]['emitted'],c
    for j in jobs:
        if j['group']=='saved_unrelated':assert not after[j['id']]['emitted'],j['id']
        if j['group']=='saved_challenge' and j['category'] in NEGATIVES:assert 'target' not in after[j['id']]['emitted'],j['id']
    changes=[dict(id=j['id'],before=before[j['id']],after=after[j['id']]) for j in jobs if before[j['id']]!=after[j['id']]]
    assert not changes,changes
    write(output/'preflight.json',dict(comparisons=len(jobs),all_old_ledgers_reproduced=True,omission_and_unrelated_controls_pass=True,changes=changes))
    print('PREFLIGHT PASS; changes',json.dumps(changes),flush=True)


def run(output):
    verify(output,model_hash=True,audio=True);assert read(output/'preflight.json')['comparisons']==246
    (output/'streams').mkdir(exist_ok=False);rows=[]
    infos={r['id']:r for r in read(output/'audio-inventory.json')}
    for number,j in enumerate(read(output/'jobs.json'),1):
        verify(output);stem=output/'streams'/j['id'];print('START',number,'/81',j['id'],flush=True)
        cmd=[sys.executable,'-X','utf8','-u','benchmarks/live_tracker_probe.py','--model','parakeet-nemo',
            '--server','127.0.0.1','--port','9097','--matching_mode','split','--no_book_context',
            '--files',j['audio'],'--mute_audio_playback','--checkpoints',j['manifest'],'--transcript_file',str(stem.with_suffix('.srt'))]
        env=dict(os.environ,PYTHONUTF8='1');env.pop('TRACKER_COMPARE_MANIFESTS',None)
        with stem.with_suffix('.log').open('w',encoding='utf-8') as log:
            subprocess.run(cmd,cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,
                timeout=int(infos[j['id']]['audio_seconds']*1.5)+180,check=True)
        row=audit(output,j,infos[j['id']]);rows.append(row);write(output/'results.json',dict(cases=rows))
        if j.get('asserted_checkpoint'):assert j['asserted_checkpoint'] in row['outcomes']['emitted'],j['id']
        if j['group']=='reviewed_mps':assert row['target_expectation_met'],j['id']
        if j['group']=='synthetic_challenge':
            assert row['target_expectation_met'],j['id']
            assert set(j['baseline_emitted']).issubset(row['outcomes']['emitted']),j['id']
        if j['group']=='unrelated':
            events=[json.loads(s) for s in stem.with_suffix('.events.jsonl').read_text(encoding='utf-8').splitlines()]
            for manifest in read(output/'offbook-manifests.json'):
                assert not replay(TimelyEvidenceMatcher,read(Path(manifest)),events)['emitted'],j['id']
        print('DONE',number,j['id'],row['outcomes'],flush=True)
    verify(output,model_hash=True,audio=True)
    write(output/'completed.json',dict(fresh_streams=81,all_trials_retained=True,all_delivery_eof_app_replay_audits_pass=True))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--stage',choices=('prepare','preflight','run'),required=True)
    parser.add_argument('--output',type=Path,default=DEST);args=parser.parse_args()
    globals()[args.stage](args.output.resolve())
