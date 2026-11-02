"""Frozen pending-effect regression: 75 callback replays and 35 fresh streams."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from benchmarks.run_mps_heldout import read,write,digest,check_frozen,old_tracker,audit_and_score,source_files
from benchmarks.run_split_word_regression import controls
from books_to_life.matching.timely_matcher import TimelyEvidenceMatcher

DEST=ROOT/'output/pending-regression-2026-11-02'
PRIOR=(ROOT/'output/eos-regression-2026-11-02',ROOT/'output/mps-heldout-eos-2026-11-02')
TARGETS={
    '5b4k_EN-OL-RC-538_2':('escape_enemies',True,'User-confirmed word restart'),
    '4a35g_EN-OL-RC-426_2':('hibernate',False,'User-confirmed essential-word omission'),
    '5b2b_EN-OL-RC-538_2':('escape_enemies',False,'User-confirmed endpoint omission'),
    '5b2b_EN-OL-RC-538_1':('small_scales',True,'Previously accepted pronunciation'),
    '3a8b_EN-OL-RC-234_1':('riverside',True,'User-confirmed split-word reading'),
    '5b15k_EN-OL-RC-538_2':('damaged_wing',True,'Reviewed soft endpoint recovered by EOF repair'),
    '4b19g_EN-OL-RC-426_2':('begging_paws',True,'User-confirmed correct endpoint trigger'),
    '4c15g_EN-OL-RC-426_2':('hibernate',False,'Provider-annotated essential-word omission'),
}


def replay(Tracker,manifest,events):
    matcher=Tracker(manifest);emitted=[];suppressed=[];skipped=set()
    for event in events:
        if event['kind']!='segments':continue
        seg=event['segments'];update=matcher.process(' '.join(s['text'] for s in seg),seg)
        skipped.update(update.skipped_checkpoint_ids)
        suppressed.extend(getattr(update,'additional_suppressed_checkpoint_ids',()))
        if update.triggered:emitted.append(update.checkpoint_id)
        if update.effect_suppressed:suppressed.append(update.checkpoint_id)
    assert not(set(emitted)&set(suppressed))
    assert len(emitted)==len(set(emitted)) and len(suppressed)==len(set(suppressed))
    assert getattr(matcher,'_pending_effect',None) is None
    return dict(emitted=emitted,suppressed=suppressed,skipped=sorted(skipped),
        unreached=sorted({c['id'] for c in manifest['checkpoints']}-set(emitted)-set(suppressed)-skipped))


def prepare(output):
    jobs={};expected={};selected={};deleted=[]
    allowed={'books_to_life/matching/alignment_matcher.py','books_to_life/matching/timely_matcher.py',
             'books_to_life/cli/run_client.py'}
    for directory in PRIOR:
        proto=read(directory/'protocol.json')
        for name,sha in proto['source_sha256'].items():
            if name.startswith('books_to_life/') and name not in allowed:
                assert digest(ROOT/name)==sha,name
        previous={r['recording']:r for r in read(directory/'results.json')['recordings']}
        for source in read(directory/'downloaded-jobs.json'):
            ident=source['id'];assert ident not in jobs
            events=directory/'streams'/(ident+'.events.jsonl')
            job=dict(source,baseline_events=str(events),baseline_events_sha256=digest(events),
                     group=directory.name)
            jobs[ident]=job;expected[ident]=previous[ident]['after']
            deleted.extend(dict(recording=ident,checkpoint=cp['id']) for cp in previous[ident]['checkpoints']
                if cp['provider_endpoint_deleted'] or cp['provider_required_word_deleted'])
        selected.update({r['audioID']:r for r in read(directory/'selected.json')})
    assert len(jobs)==75
    latest=[j['id'] for j in read(PRIOR[-1]/'jobs.json')]
    fresh=list(TARGETS)+[ident for ident in latest if ident not in TARGETS]
    assert len(fresh)==31
    output.mkdir(parents=True,exist_ok=False)
    for ident,job in jobs.items():
        assert digest(Path(job['audio']))==job['audio_sha256']
        assert digest(Path(job['manifest']))==job['manifest_sha256']
        target=output/'inputs'/ident/'checkpoints.json';target.parent.mkdir(parents=True)
        target.write_bytes(Path(job['manifest']).read_bytes());job['manifest']=str(target)
        if ident in TARGETS:
            cp,emit,basis=TARGETS[ident]
            job.update(asserted_checkpoint=cp,expected_emission=emit,assertion_basis=basis)
    write(output/'jobs.json',list(jobs.values()))
    write(output/'downloaded-jobs.json',[jobs[key] for key in fresh])
    write(output/'selected.json',list(selected.values()))
    write(output/'original-live-ledgers.json',expected)
    baseline={}
    for name in ('effect_permission.py','timely_matcher.py'):
        src=PRIOR[-1]/'source-snapshot/books_to_life/matching'/name
        target=output/'baseline-snapshot'/name;target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes(src.read_bytes());baseline[name]=digest(target)
    files=sorted(set(source_files())|{Path(__file__).resolve(),ROOT/'tests/test_pending_effects.py',
        ROOT/'benchmarks/run_split_word_regression.py'})
    hashes={}
    for path in files:
        name=path.relative_to(ROOT).as_posix();data=path.read_bytes()
        target=output/'source-snapshot'/name;target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes(data);hashes[name]=hashlib.sha256(data).hexdigest()
    original=read(PRIOR[-1]/'protocol.json')
    write(output/'protocol.json',dict(date='2026-11-02',kind='Pending-effect inspected-data regression',
        configuration=original['configuration'],model=original['model'],lexicon=original['lexicon'],
        source_sha256=hashes,baseline_sha256=baseline,provider_deletion_controls=deleted,
        replay_recordings=list(jobs),ordered_recordings=fresh,
        saved_callback_recordings=75,fresh_reading_streams=31,fresh_unrelated_streams=4,
        asr_unchanged=True,permission_rules_unchanged=True,audio_and_manifests_unmodified=True,
        pending_bounds=dict(audio_seconds=2,fresh_updates=4,max_book_words_past_anchor=3),
        plan='Replay every saved streaming timeline; then one fresh stream per latest-24/reviewed-seven recording and four unrelated streams. Eight assertions first; no outcome-dependent replacements or tuning.'))
    check_frozen(output,model_hash=True)
    print('FROZEN 75 callback replays, 31 fresh readings and 4 fresh unrelated streams.',flush=True)


def preflight(output):
    check_frozen(output);Old=old_tracker(output);expected=read(output/'original-live-ledgers.json');rows=[]
    for job in read(output/'jobs.json'):
        assert digest(Path(job['baseline_events']))==job['baseline_events_sha256']
        events=[json.loads(s) for s in Path(job['baseline_events']).read_text(encoding='utf-8').splitlines()]
        manifest=read(Path(job['manifest']))
        before=replay(Old,manifest,events);assert before==expected[job['id']]
        after=replay(TimelyEvidenceMatcher,manifest,events)
        row=dict(recording=job['id'],before=before,after=after,
            added=sorted(set(after['emitted'])-set(before['emitted'])),
            removed=sorted(set(before['emitted'])-set(after['emitted'])))
        rows.append(row)
        if 'asserted_checkpoint' in job:
            assert (job['asserted_checkpoint'] in after['emitted'])==job['expected_emission'],job['id']
    write(output/'preflight-replay.json',dict(kind='Saved streaming callbacks; not fresh ASR trials',recordings=rows))
    print('PREFLIGHT',len(rows),'saved streaming timelines; eight asserted cases pass.',flush=True)
    print('ADDED',[(r['recording'],r['added']) for r in rows if r['added']],flush=True)
    print('REMOVED',[(r['recording'],r['removed']) for r in rows if r['removed']],flush=True)


def run(output):
    check_frozen(output,model_hash=True);assert len(read(output/'preflight-replay.json')['recordings'])==75
    jobs=read(output/'downloaded-jobs.json');Old=old_tracker(output);results=[]
    assert [j['id'] for j in jobs]==read(output/'protocol.json')['ordered_recordings']
    (output/'streams').mkdir(exist_ok=False)
    for index,job in enumerate(jobs,1):
        check_frozen(output);assert digest(Path(job['audio']))==job['audio_sha256']
        stem=output/'streams'/job['id'];print('START',index,'/',len(jobs),job['id'],flush=True)
        command=[sys.executable,'-X','utf8','-u','benchmarks/live_tracker_probe.py',
            '--model','parakeet-nemo','--server','127.0.0.1','--port','9097',
            '--matching_mode','split','--no_book_context','--files',job['audio'],'--mute_audio_playback',
            '--checkpoints',job['manifest'],'--transcript_file',str(stem.with_suffix('.srt'))]
        env=dict(os.environ,PYTHONUTF8='1');env.pop('TRACKER_COMPARE_MANIFESTS',None)
        with stem.with_suffix('.log').open('w',encoding='utf-8') as log:
            subprocess.run(command,cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,
                timeout=math.ceil(job['audio_seconds']*1.5)+180,check=True)
        check_frozen(output);row=audit_and_score(output,job,Old)
        events=[json.loads(s) for s in stem.with_suffix('.events.jsonl').read_text(encoding='utf-8').splitlines()]
        pending={e['scene'] for e in events if e['kind']=='pending_effect' and e['mode']=='timely'}
        row['pending_checkpoints']=sorted(pending)
        row['recovered_pending']=sorted(pending&set(row['after']['emitted']))
        row['expired_pending']=sorted(pending&set(row['after']['suppressed']))
        row['group']=job['group']
        assert not(set(row['after']['emitted'])&set(row['after']['suppressed']))
        if 'asserted_checkpoint' in job:
            actual=job['asserted_checkpoint'] in row['after']['emitted']
            row['assertion']=dict(checkpoint=job['asserted_checkpoint'],expected_emission=job['expected_emission'],
                actual_emission=actual,passed=actual==job['expected_emission'],basis=job['assertion_basis'])
        results.append(row);write(output/'results.json',dict(recordings=results))
        print('DONE',index,'before/after',len(row['before']['emitted']),len(row['after']['emitted']),
              'added',row['added_emissions'],'removed',row['removed_emissions'],flush=True)
        if row.get('assertion'):assert row['assertion']['passed'],row['assertion']
    controls(output);check_frozen(output,model_hash=True)
    write(output/'completed.json',dict(fresh_reading_streams=31,fresh_unrelated_streams=4,saved_callback_recordings=75,
        sources_unchanged_during_run=True,asr_unchanged=True,model_hash_unchanged=True,
        all_trials_retained=True,audio_and_manifests_unchanged=True))
    print('COMPLETE 35 fresh streams and 75 saved-callback regressions.',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage',choices=('prepare','preflight','run'),required=True)
    parser.add_argument('--output',type=Path,default=DEST)
    args=parser.parse_args();output=args.output.resolve()
    if not output.is_relative_to(ROOT/'output'):parser.error('Raw results must remain under ignored output/.')
    {'prepare':prepare,'preflight':preflight,'run':run}[args.stage](output)
