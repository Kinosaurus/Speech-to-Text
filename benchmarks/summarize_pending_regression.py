"""Summarize paired pending-effect streams and the full saved-callback regression."""
import argparse
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from benchmarks.run_mps_heldout import read,write,check_frozen,digest
from benchmarks.run_pending_regression import DEST,PRIOR
from benchmarks.summarize_mps_heldout import listening_review


def totals(rows,label):
    return {k:sum(len(r[label][k]) for r in rows) for k in ('emitted','suppressed','skipped','unreached')}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=DEST)
    output=parser.parse_args().output.resolve()
    done=read(output/'completed.json');proto=check_frozen(output,model_hash=True)
    assert done['fresh_reading_streams']==31 and done['fresh_unrelated_streams']==4
    rows=read(output/'results.json')['recordings'];pre=read(output/'preflight-replay.json')['recordings']
    controls=read(output/'controls-results.json');jobs=read(output/'jobs.json')
    assert len(rows)==31 and len(pre)==75 and len(controls)==4
    assert [r['recording'] for r in rows]==proto['ordered_recordings']
    for job in jobs:
        assert digest(Path(job['audio']))==job['audio_sha256']
        assert digest(Path(job['baseline_events']))==job['baseline_events_sha256']
    assert all(r['delivery_audit_pass'] and r['app_observer_agreement'] and r['stream_done'] for r in rows)
    assertions=[dict(recording=r['recording'],**r['assertion']) for r in rows if r.get('assertion')]
    assert len(assertions)==8 and all(r['passed'] for r in assertions)
    assert all(set(r['pending_checkpoints'])==set(r['recovered_pending'])|set(r['expired_pending']) for r in rows)
    assert not any(r['removed_emissions'] for r in rows) and not any(r['removed'] for r in pre)
    assert sum(r['emitted'] for r in controls)==sum(r['suppressed'] for r in controls)==0
    for prior in PRIOR:
        old=read(prior/'protocol.json')['source_sha256']
        for name,checksum in proto['source_sha256'].items():
            if name.startswith('books_to_life/runtime/') or name=='books_to_life/cli/run_nemo_server.py':
                assert old[name]==checksum,name
        for name in ('effect_permission.py','phonetic_endpoint.py','word_boundaries.py','checkpoint_matcher.py',
                     'split_matcher.py','boundary_matcher.py','evidence_matcher.py'):
            path='books_to_life/matching/'+name
            assert old[path]==proto['source_sha256'][path],name
    indexed={r['recording']:r for r in pre}
    replay_omissions=[dict(**c,emitted=c['checkpoint'] in indexed[c['recording']]['after']['emitted'])
                     for c in proto['provider_deletion_controls']]
    assert not any(r['emitted'] for r in replay_omissions)
    portable=[];deleted=[]
    for row in rows:
        item={k:v for k,v in row.items() if k not in ('checkpoints','phonetic_calls')};item['checkpoints']=[]
        for cp in row['checkpoints']:
            e=cp['provider_evidence']
            item['checkpoints'].append({k:v for k,v in cp.items() if k!='provider_evidence'} | {
                'provider_annotation_status':e['status'],
                'provider_counts':{k:e.get(k) for k in ('correct','substitutions','deletions')}})
            if cp['provider_endpoint_deleted'] or cp['provider_required_word_deleted']:
                deleted.append(dict(recording=row['recording'],checkpoint=cp['id'],emitted=cp['emitted'],
                    suppressed=cp['suppressed'],unreached=cp['id'] in row['after']['unreached']))
        portable.append(item)
    assert not any(r['emitted'] for r in deleted)
    diff=subprocess.run(['git','diff','--check'],cwd=ROOT,capture_output=True,text=True)
    assert diff.returncode==0,diff.stdout+diff.stderr
    report=dict(date='2026-11-02',scope='General premature-rejection repair: inspected-data regression',
        change=dict(no_word_specific_exceptions=True,no_asr_changes=True,no_transcript_rewriting=True,
            existing_permission_rules_unchanged=True,reading_progress_independent=True,
            acquired_exact_prefix_required=True,max_pending_effects=1,pending_bounds=proto['pending_bounds'],
            requires_fresh_supported_endpoint=True,completion_can_close_pending=True,
            timers_and_duplicates_cannot_trigger=True,late_checkpoints_do_not_stall=True),
        configuration=proto['configuration'],model=proto['model'],lexicon=proto['lexicon'],
        execution=dict(fresh_reading_streams=31,fresh_unrelated_streams=4,configured_fresh_reading=93,
            fresh_reading_audio_seconds=sum(r['audio_seconds'] for r in rows),
            all_samples_delivered=True,all_partial_before_eof=True,all_stream_done=True,
            all_app_observer_agreement=True,all_pending_effects_resolved=True,
            one_trial_per_recording=True,all_trials_retained=True),
        totals=dict(before=totals(rows,'before'),after=totals(rows,'after')),
        saved_callback_regression=dict(recordings=75,configured=225,kind='Not fresh ASR trials',
            before=totals(pre,'before'),after=totals(pre,'after'),
            added=[dict(recording=r['recording'],checkpoints=r['added']) for r in pre if r['added']],
            removed=[dict(recording=r['recording'],checkpoints=r['removed']) for r in pre if r['removed']],
            omission_controls=replay_omissions),
        assertions=assertions,provider_deletion_controls_fresh=deleted,
        added_emissions=[dict(recording=r['recording'],checkpoints=r['added_emissions']) for r in rows if r['added_emissions']],
        removed_emissions=[dict(recording=r['recording'],checkpoints=r['removed_emissions']) for r in rows if r['removed_emissions']],
        pending_decisions=dict(created=sum(len(r['pending_checkpoints']) for r in rows),
            recovered=sum(len(r['recovered_pending']) for r in rows),
            finalized_suppressed=sum(len(r['expired_pending']) for r in rows)),
        unrelated_controls=dict(fresh_streams=4,passage_policies=6,comparisons=sum(r['comparisons'] for r in controls),
            emitted=0,suppressed=0,results=controls),
        integrity=dict(asr_and_eof_runtime_unchanged=True,permission_helpers_unchanged=True,
            model_hash_unchanged=True,lexicon_unchanged=True,source_sha256=proto['source_sha256'],
            sources_unchanged_during_run=True,audio_and_manifests_unchanged=True),
        validation=dict(windows_tests_run=164,windows_passed=163,windows_skipped_requiring_nemo=1,
            new_pending_tests=11,unit_log_sha256=digest(ROOT/'output/pending-unit-tests.log'),
            diff_check_passed=True),
        recordings=portable,
        limits=['All recordings have been inspected; these are regression results, not a new held-out accuracy score.',
            'The 75 saved-timeline cases exercise the unchanged ASR callbacks. Thirty-one matched recordings and four unrelated controls were freshly streamed.',
            'Pending eligibility requires local acquisition and an exact recent prefix; other recognition errors can still withhold an effect.',
            'The window closes on fresh callbacks after its bounds, utterance completion, prompts, loss of locality or a later checkpoint. It never emits on a timer.',
            'Omission checks cover user-confirmed omissions and provider-marked deletions. They cannot rule out every ASR hallucination.',
            'Callback times are not human-verified word-end latency measurements.'],
        artifacts=output.relative_to(ROOT).as_posix()+': frozen sources/manifests, preflight timelines, streaming events/logs, paired decisions and listening review.')
    review=output/'review';review.mkdir(exist_ok=True);human={}
    for source in PRIOR:
        path=source/'review/human_reviews.json'
        if path.exists():human.update(read(path)['cases'])
    if (review/'human_reviews.json').exists():human.update(read(review/'human_reviews.json')['cases'])
    write(review/'human_reviews.json',dict(source='Prior user listening of these exact unchanged recordings; original pre-fix judgments retained',cases=human))
    count=listening_review(output,report,title='Pending-effect regression listening review',
        introduction='The matcher decision lifecycle was rerun with frozen code and unchanged ASR. User notes refer to the same source audio and may describe pre-fix behavior. Current automated outcomes are shown separately.')
    report['listening_review']=dict(flagged_checkpoints=count,source_audio_reviews=len(human))
    write(output/'summary.json',report)
    write(ROOT/'benchmarks/results/pending-regression-2026-11-02.json',report)
    import json
    print(json.dumps({k:report[k] for k in ('execution','totals','assertions','added_emissions','removed_emissions','pending_decisions','provider_deletion_controls_fresh','unrelated_controls')},indent=2))


if __name__=='__main__':main()
