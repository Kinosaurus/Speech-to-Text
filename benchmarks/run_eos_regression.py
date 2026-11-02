"""Freeze an ASR end-of-stream repair and rerun all 51 inspected MPS readings."""
import argparse
import hashlib
import math
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from benchmarks.run_mps_heldout import read, write, digest, check_frozen, old_tracker, audit_and_score, source_files
from benchmarks.run_split_word_regression import controls
from books_to_life.matching.timely_matcher import TimelyEvidenceMatcher

DEST = ROOT/'output/eos-regression-2026-11-02'
PRIOR = (ROOT/'output/split-word-regression-v2-2026-11-02',
         ROOT/'output/mps-heldout-split-word-2026-11-02')


def replay(manifest, events):
    tracker=TimelyEvidenceMatcher(manifest);emitted=[];suppressed=[];skipped=set()
    for event in events:
        if event['kind']!='segments':continue
        segments=event['segments']
        update=tracker.process(' '.join(s['text'] for s in segments),segments)
        skipped.update(update.skipped_checkpoint_ids)
        if update.triggered:emitted.append(update.checkpoint_id)
        if update.effect_suppressed:suppressed.append(update.checkpoint_id)
    return dict(emitted=emitted,suppressed=suppressed,skipped=sorted(skipped),
        unreached=sorted({c['id'] for c in manifest['checkpoints']}-set(emitted)-set(suppressed)-skipped))


def prepare(output):
    jobs={};baseline={};selected={}
    for directory in PRIOR:
        protocol=read(directory/'protocol.json')
        for name,checksum in protocol['source_sha256'].items():
            if name.startswith('books_to_life/') and name!='books_to_life/runtime/nemo_parakeet.py':
                assert digest(ROOT/name)==checksum, name
        previous={r['recording']:r for r in read(directory/'results.json')['recordings']}
        for row in read(directory/'downloaded-jobs.json'):
            assert row['id'] not in jobs
            job=dict(row,group=directory.name)
            path=directory/'streams'/(row['id']+'.events.jsonl')
            job.update(baseline_events=str(path),baseline_events_sha256=digest(path))
            jobs[row['id']]=job;baseline[row['id']]=previous[row['id']]['after']
        selected.update({r['audioID']:r for r in read(directory/'selected.json')})
    targets={
        '5b15k_EN-OL-RC-538_2': ('damaged_wing',True,'Human-heard soft endpoint; silence-padding diagnostic recovered it'),
        '4a35g_EN-OL-RC-426_2': ('hibernate',False,'User-confirmed essential-word omission'),
        '5b2b_EN-OL-RC-538_2': ('escape_enemies',False,'User-confirmed endpoint omission'),
        '5b2b_EN-OL-RC-538_1': ('small_scales',True,'Previously accepted pronunciation'),
        '3a8b_EN-OL-RC-234_1': ('riverside',True,'User-confirmed reading with ASR word split'),
        '4c15g_EN-OL-RC-426_2': ('hibernate',False,'Provider-annotated essential-word omission'),
    }
    order=list(targets)+[key for key in jobs if key not in targets]
    assert len(order)==len(jobs)==51
    output.mkdir(parents=True,exist_ok=False)
    ordered=[]
    for ident in order:
        job=jobs[ident]
        assert digest(Path(job['audio']))==job['audio_sha256']
        assert digest(Path(job['manifest']))==job['manifest_sha256']
        target=output/'inputs'/ident/'checkpoints.json';target.parent.mkdir(parents=True)
        target.write_bytes(Path(job['manifest']).read_bytes());job['manifest']=str(target)
        if ident in targets:
            cp,expected,basis=targets[ident]
            job.update(asserted_checkpoint=cp,expected_emission=expected,assertion_basis=basis)
        ordered.append(job)
    assert len({j['audio_sha256'] for j in ordered})==51
    write(output/'jobs.json',ordered);write(output/'downloaded-jobs.json',ordered)
    write(output/'selected.json',[selected[j['id']] for j in ordered])
    write(output/'original-live-ledgers.json',baseline)
    checks={}
    for name in ('effect_permission.py','timely_matcher.py'):
        target=output/'baseline-snapshot'/name;target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes((ROOT/'books_to_life/matching'/name).read_bytes());checks[name]=digest(target)
    files=sorted(set(source_files()) | {Path(__file__).resolve(),ROOT/'benchmarks/run_split_word_regression.py',
        ROOT/'tests/test_nemo_transport.py',ROOT/'tests/test_nemo_eos_decoder.py'})
    hashes={}
    for path in files:
        name=path.relative_to(ROOT).as_posix();data=path.read_bytes()
        target=output/'source-snapshot'/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
        hashes[name]=hashlib.sha256(data).hexdigest()
    original=read(PRIOR[-1]/'protocol.json')
    write(output/'protocol.json',dict(date='2026-11-02',kind='ASR end-of-stream inspected-data regression',
        ordered_recordings=order,matched_streams=51,unrelated_streams=4,configured=153,
        configuration=original['configuration'],model=original['model'],lexicon=original['lexicon'],
        source_sha256=hashes,baseline_sha256=checks,
        matcher_unchanged_from_prior_batches=True,only_runtime_change='books_to_life/runtime/nemo_parakeet.py',
        raw_audio_unmodified=True,internal_silence_is_context_only=True,
        client_timestamps_use_real_audio_only=True,runs_per_recording=1,
        baseline='Original saved ASR callbacks replayed through the identical unchanged matcher; earlier live ledgers must agree.',
        plan='Six asserted regressions first, then every remaining reading in its previous fixed order; four fresh unrelated streams across six passage policies. All trials retained; no outcome-dependent retry.'))
    check_frozen(output,model_hash=True)
    print('FROZEN 51 original MPS recordings, 153 checkpoints and 4 unrelated streams.',flush=True)


def run(output):
    check_frozen(output,model_hash=True)
    jobs=read(output/'jobs.json');original=read(output/'original-live-ledgers.json')
    Old=old_tracker(output);results=[]
    (output/'streams').mkdir(exist_ok=False)
    for index,job in enumerate(jobs,1):
        check_frozen(output)
        assert digest(Path(job['audio']))==job['audio_sha256']
        assert digest(Path(job['baseline_events']))==job['baseline_events_sha256']
        stem=output/'streams'/job['id']
        print('START',index,'/',len(jobs),job['id'],flush=True)
        command=[sys.executable,'-X','utf8','-u','benchmarks/live_tracker_probe.py',
            '--model','parakeet-nemo','--server','127.0.0.1','--port','9097',
            '--matching_mode','split','--no_book_context','--files',job['audio'],
            '--mute_audio_playback','--checkpoints',job['manifest'],'--transcript_file',str(stem.with_suffix('.srt'))]
        env=dict(os.environ,PYTHONUTF8='1');env.pop('TRACKER_COMPARE_MANIFESTS',None)
        with stem.with_suffix('.log').open('w',encoding='utf-8') as log:
            subprocess.run(command,cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,
                timeout=math.ceil(job['audio_seconds']*1.5)+180,check=True)
        check_frozen(output)
        row=audit_and_score(output,job,Old)
        assert row['before']==row['after'], 'Unchanged matcher observers must agree on the new ASR'
        old_events=[__import__('json').loads(s) for s in Path(job['baseline_events']).read_text(encoding='utf-8').splitlines()]
        baseline=replay(read(Path(job['manifest'])),old_events)
        assert baseline==original[job['id']], 'Original live ledger must match unchanged-matcher replay'
        row['before']=baseline;row['group']=job['group']
        row['added_emissions']=sorted(set(row['after']['emitted'])-set(baseline['emitted']))
        row['removed_emissions']=sorted(set(baseline['emitted'])-set(row['after']['emitted']))
        new_events=[__import__('json').loads(s) for s in stem.with_suffix('.events.jsonl').read_text(encoding='utf-8').splitlines()]
        def partials(events):
            return [e['segments'][-1]['text'] for e in events if e['kind']=='segments' and not e['segments'][-1]['completed']]
        row['pre_eof_transcripts_identical']=partials(old_events)==partials(new_events)
        row['original_asr_final_tail']=' '.join([e for e in old_events if e['kind']=='segments'][-1]['segments'][-1]['text'].split()[-18:])
        row['new_asr_final_tail']=' '.join([e for e in new_events if e['kind']=='segments'][-1]['segments'][-1]['text'].split()[-18:])
        if 'asserted_checkpoint' in job:
            actual=job['asserted_checkpoint'] in row['after']['emitted']
            row['assertion']=dict(checkpoint=job['asserted_checkpoint'],expected_emission=job['expected_emission'],
                actual_emission=actual,passed=actual==job['expected_emission'],basis=job['assertion_basis'])
        results.append(row);write(output/'results.json',dict(recordings=results))
        print('DONE',index,'old/new ASR',len(row['before']['emitted']),len(row['after']['emitted']),
            'added',row['added_emissions'],'removed',row['removed_emissions'],flush=True)
        if row.get('assertion'):assert row['assertion']['passed'],row['assertion']
    controls(output)
    check_frozen(output,model_hash=True)
    write(output/'completed.json',dict(matched_streams=51,unrelated_streams=4,
        all_selected_trials_retained=True,matcher_unchanged=True,model_hash_unchanged=True,
        manifests_unchanged=True,audio_unmodified=True,runtime_unchanged_during_run=True))
    print('COMPLETE all 55 fresh regression streams.',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage',choices=('prepare','run'),required=True)
    parser.add_argument('--output',type=Path,default=DEST)
    args=parser.parse_args();output=args.output.resolve()
    if not output.is_relative_to(ROOT/'output'):parser.error('Raw results must stay under ignored output/.')
    prepare(output) if args.stage=='prepare' else run(output)
