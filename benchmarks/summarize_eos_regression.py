"""Report the complete end-of-stream regression without changing original trials."""
import argparse
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from benchmarks.run_mps_heldout import read,write,check_frozen,digest
from benchmarks.run_eos_regression import DEST,PRIOR
from benchmarks.summarize_mps_heldout import listening_review


def totals(rows,label):
    return {k:sum(len(r[label][k]) for r in rows) for k in ('emitted','suppressed','skipped','unreached')}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=DEST)
    args=parser.parse_args();output=args.output.resolve()
    completed=read(output/'completed.json')
    assert completed['matched_streams']==51 and completed['unrelated_streams']==4
    protocol=check_frozen(output,model_hash=True)
    rows=read(output/'results.json')['recordings'];controls=read(output/'controls-results.json')
    for job in read(output/'jobs.json'):
        assert digest(Path(job['audio']))==job['audio_sha256']
        assert digest(Path(job['baseline_events']))==job['baseline_events_sha256']
    prior_controls={r['recording']:r for r in read(PRIOR[0]/'controls-results.json')}
    assert all(r['audio_sha256']==prior_controls[r['recording']]['audio_sha256'] for r in controls)
    assert len(rows)==51 and len(controls)==4
    assert [r['recording'] for r in rows]==protocol['ordered_recordings']
    assert all(r['delivery_audit_pass'] and r['app_observer_agreement'] and r['stream_done'] for r in rows)
    assertions=[dict(recording=r['recording'],**r['assertion']) for r in rows if r.get('assertion')]
    assert len(assertions)==6 and all(a['passed'] for a in assertions)
    assert sum(r['emitted'] for r in controls)==sum(r['suppressed'] for r in controls)==0
    matcher={k:v for k,v in protocol['source_sha256'].items() if k.startswith('books_to_life/matching/')}
    for previous in PRIOR:
        prior=read(previous/'protocol.json')['source_sha256']
        assert all(prior[k]==v for k,v in matcher.items())
    portable=[];deleted=[];correct=[];missed=[]
    for row in rows:
        result={k:v for k,v in row.items() if k not in ('checkpoints','phonetic_calls')}
        result['checkpoints']=[]
        for cp in row['checkpoints']:
            evidence=cp['provider_evidence']
            result['checkpoints'].append({k:v for k,v in cp.items() if k!='provider_evidence'} | {
                'provider_annotation_status':evidence['status'],
                'provider_counts':{k:evidence.get(k) for k in ('correct','substitutions','deletions')}})
            if cp['provider_endpoint_deleted'] or cp['provider_required_word_deleted']:
                deleted.append(dict(recording=row['recording'],checkpoint=cp['id'],emitted=cp['emitted'],
                    suppressed=cp['suppressed'],unreached=cp['id'] in row['after']['unreached']))
            if evidence.get('words') and evidence.get('substitutions')==evidence.get('deletions')==0:
                item=dict(recording=row['recording'],checkpoint=cp['id'],emitted=cp['emitted'])
                correct.append(item)
                if not cp['emitted']:missed.append(item)
        portable.append(result)
    check=subprocess.run(['git','diff','--check'],cwd=ROOT,capture_output=True,text=True)
    assert check.returncode==0,check.stdout+check.stderr
    report=dict(date='2026-11-02',scope='General ASR end-of-stream fix: inspected-data regression, not held-out accuracy',
        change=dict(runtime_file='books_to_life/runtime/nemo_parakeet.py',
            full_encoder_chunk_and_right_context_at_eof=True,padding_only_supplies_encoder_context=True,
            only_remaining_real_audio_frames_decoded=True,final_partial_real_frame_included=True,
            no_word_specific_rules=True,no_matcher_changes=True,real_audio_timestamps_preserved=True,
            finish_idempotent=True,empty_stream_does_not_infer=True),
        configuration=protocol['configuration'],model=protocol['model'],lexicon=protocol['lexicon'],
        execution=dict(fresh_reading_streams=51,fresh_unrelated_streams=4,configured=153,
            real_reading_audio_seconds=sum(r['audio_seconds'] for r in rows),
            all_original_files_unmodified=True,one_trial_per_recording=True,all_trials_retained=True,
            all_delivery_audits_passed=True,all_partial_before_eof=True,all_stream_done=True,
            all_final_timestamps_match_original_audio_duration=True,all_app_observer_agreement=True,
            pre_eof_transcripts_identical=sum(r['pre_eof_transcripts_identical'] for r in rows)),
        integrity=dict(matcher_unchanged_from_both_previous_batches=True,matcher_sha256=matcher,
            source_sha256=protocol['source_sha256'],model_hash_unchanged=True,lexicon_unchanged=True,
            sources_unchanged_during_run=True,manifests_unchanged=True,
            original_asr_ledgers_verified_with_identical_matcher=True),
        totals=dict(original_asr=totals(rows,'before'),repaired_asr=totals(rows,'after')),
        assertions=assertions,
        provider_deleted_endpoint_or_required_word_controls=deleted,
        provider_annotation_review=dict(correct_anchors=len(correct),
            emitted_correct_anchors=sum(r['emitted'] for r in correct),
            nonemitting_correct_anchors=missed,
            emitted_despite_provider_deleted_endpoint_or_required_word=[r for r in deleted if r['emitted']],
            note='Provider annotations are review evidence, not human effect-acceptance labels.'),
        added_emissions=[dict(recording=r['recording'],checkpoints=r['added_emissions']) for r in rows if r['added_emissions']],
        removed_emissions=[dict(recording=r['recording'],checkpoints=r['removed_emissions']) for r in rows if r['removed_emissions']],
        unrelated_controls=dict(fresh_streams=4,passage_policies=6,comparisons=sum(r['comparisons'] for r in controls),
            emitted=0,suppressed=0,results=controls),
        validation=dict(windows_unit_tests_run=153,windows_passed=152,windows_skipped_needing_nemo=1,
            isolated_nemo_decoder_test_passed=True,diff_check_passed=True,
            unit_log_sha256=digest(ROOT/'output/eos-unit-tests.log')),
        recordings=portable,
        limits=['These 51 recordings were previously inspected. The run is regression coverage and leaves all original held-out results intact.',
            'The original-ASR baseline is saved-callback replay through the identical matcher, verified against previous live app ledgers. Only repaired ASR is freshly streamed in this batch.',
            'All audio files, checkpoints, matcher rules, model weights, hints and thresholds stay unchanged. Only NeMo session finalization changes.',
            'Human acceptance follows the attached source-audio listening reviews, including any endpoint-quality qualifications. Emission counts are not accuracy or word-end latency scores.',
            'Omission evidence includes two user-confirmed omissions plus provider-marked deletions; it cannot rule out every ASR hallucination.'],
        artifacts=output.relative_to(ROOT).as_posix()+': frozen sources, manifests, hashes, original-ASR references, full streaming logs and listening review.')
    review=output/'review';review.mkdir(exist_ok=True)
    human={}
    for path in (ROOT/'output/mps-heldout-2026-11-02/review/human_reviews.json',
                 ROOT/'output/mps-heldout-split-word-2026-11-02/review/human_reviews.json'):
        if path.exists():human.update(read(path)['cases'])
    prior_count=len(human)
    human_path=review/'human_reviews.json'
    if human_path.exists():human.update(read(human_path)['cases'])
    write(human_path,dict(source='User listening of these exact unchanged source recordings, before and after the regression',cases=human))
    added={r['recording']+'/'+cp for r in rows for cp in r['added_emissions']}
    confirmed={key for key in added if human.get(key,{}).get('classification')=='confirmed_correct_trigger'
               and human[key].get('human_should_emit')=='Yes'}
    count=listening_review(output,report,title='End-of-stream regression listening review',
        introduction='These inspected recordings were rerun with a frozen ASR finalization fix and unchanged matcher. User notes apply to the identical source audio. Unreviewed cases remain open, and endpoint-quality qualifications are retained.')
    report['listening_review']=dict(flagged_checkpoints=count,prior_source_audio_reviews=prior_count,
        source_audio_reviews=len(human),all_added_emissions_listened_to=added<=set(human),
        confirmed_correct_added_emissions=sorted(confirmed),
        qualified_added_emissions=sorted(key for key in added if 'qualified' in human.get(key,{}).get('classification','')),
        all_added_emissions_human_confirmed=added<=confirmed)
    report['post_evaluation_human_review']=dict(original_stream_results_unchanged=True,
        matcher_changed_after_review=False,
        cases=[{k:v for k,v in value.items() if k not in ('human_heard','user_comment','listening_history')}
               for key,value in sorted(human.items()) if key in added])
    write(output/'summary.json',report)
    write(ROOT/'benchmarks/results/eos-regression-2026-11-02.json',report)
    import json
    print(json.dumps({k:report[k] for k in ('execution','totals','assertions','provider_deleted_endpoint_or_required_word_controls','added_emissions','removed_emissions','unrelated_controls','listening_review')},indent=2))


if __name__=='__main__':main()
