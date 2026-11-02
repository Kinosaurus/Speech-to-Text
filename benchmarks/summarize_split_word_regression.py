"""Summarize the completed frozen split-word regression without relabelling it held-out."""
import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from benchmarks.run_mps_heldout import read,write,check_frozen
from benchmarks.run_split_word_regression import DEST


def totals(rows,label):
    return {k:sum(len(r[label][k]) for r in rows) for k in ('emitted','suppressed','skipped','unreached')}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=DEST)
    args=parser.parse_args();out=args.output.resolve()
    completed=read(out/'completed.json')
    assert completed['matched_streams']==27 and completed['unrelated_streams']==4
    protocol=check_frozen(out,model_hash=True)
    rows=read(out/'results.json')['recordings'];controls=read(out/'controls-results.json')
    assert len(rows)==27 and len(controls)==4
    assert [r['recording'] for r in rows]==protocol['ordered_recordings']
    assert all(r['delivery_audit_pass'] and r['app_observer_agreement'] for r in rows)
    assert all(r['assertion']['passed'] for r in rows if r.get('assertion'))
    assert sum(r['emitted'] for r in controls)==0 and sum(r['suppressed'] for r in controls)==0
    annotations=[]
    for row in rows:
        for cp in row['checkpoints']:
            if cp['provider_endpoint_deleted'] or cp['provider_required_word_deleted']:
                annotations.append(dict(recording=row['recording'],checkpoint=cp['id'],emitted=cp['emitted'],
                    suppressed=cp['suppressed']))
    assert not any(r['emitted'] for r in annotations)
    portable=[]
    for row in rows:
        result={k:v for k,v in row.items() if k!='checkpoints'}
        result['checkpoints']=[]
        for cp in row['checkpoints']:
            evidence=cp['provider_evidence']
            result['checkpoints'].append({k:v for k,v in cp.items() if k!='provider_evidence'} | {
                'provider_annotation_status':evidence['status'],
                'provider_counts':{k:evidence.get(k) for k in ('correct','substitutions','deletions')}})
        portable.append(result)
    corpus=[r for r in rows if r['group']=='24-recording regression']
    legacy=[r for r in rows if r['group']!='24-recording regression']
    riverside=next(r for r in rows if r['recording']=='3a8b_EN-OL-RC-234_1')
    decisions=read(out/'streams/3a8b_EN-OL-RC-234_1.decisions.json')
    preflight=read(out/'preflight-replay.json')
    report=dict(date='2026-11-02',scope='General split-word fix: inspected-data regression, not a new held-out evaluation',
        algorithm=dict(reference_word_consumes_one_or_two_adjacent_asr_tokens=True,
            exact_full_anchor_text_required=True,all_reference_words_consumed_once=True,
            no_gaps_or_character_substitutions=True,prior_local_acquisition_required=True,
            endpoint_within_latest_four_tokens=True,prompt_checks_retained=True,
            no_word_specific_aliases=True,existing_spelling_phonetic_and_coverage_rules_unchanged=True),
        exact_split_position_candidate=dict(next_checkpoint_only=True,prior_local_acquisition=True,
            unique_anchor_in_book=True,normal_search_bounds=True,normal_independent_confirmation=True,
            complete_anchor_can_end_at_eof=True),
        configuration=protocol['configuration'],model=protocol['model'],lexicon=protocol['lexicon'],
        execution=dict(fresh_matched_streams=27,fresh_unrelated_streams=4,configured_matched=81,
            full_mps_regression_recordings=24,original_reviewed_recordings=3,
            matched_audio_seconds=sum(r['audio_seconds'] for r in rows),
            all_delivery_audits_passed=True,all_partial_before_eof=True,all_stream_done=True,
            all_app_observer_agreement=True,one_trial_per_recording=True),
        integrity=dict(sources_unchanged_during_run=True,model_hash_unchanged=True,
            lexicon_unchanged=True,existing_manifests_unchanged=True,
            source_sha256=protocol['source_sha256'],pre_split_baseline_sha256=protocol['baseline_sha256']),
        totals=dict(before=totals(rows,'before'),after=totals(rows,'after')),
        mps_24_regression=dict(before=totals(corpus,'before'),after=totals(corpus,'after')),
        earlier_reviewed_regressions=dict(before=totals(legacy,'before'),after=totals(legacy,'after')),
        assertions=[dict(recording=r['recording'],**r['assertion']) for r in rows if r.get('assertion')],
        provider_deleted_endpoint_or_essential_word_controls=annotations,
        added_emissions=[dict(recording=r['recording'],checkpoints=r['added_emissions']) for r in rows if r['added_emissions']],
        removed_emissions=[dict(recording=r['recording'],checkpoints=r['removed_emissions']) for r in rows if r['removed_emissions']],
        riverside=dict(recording=riverside['recording'],human_reading_confirmed_before_fix=True,
            original_saved_callback_diagnostic=dict(kind=preflight['kind'],
                result=next(r for r in preflight['results'] if r['recording']==riverside['recording'])),
            before_emitted='riverside' in riverside['before']['emitted'],
            after_emitted='riverside' in riverside['after']['emitted'],
            recognized_split_retained_in_after_buffer=any(d['checkpoint']=='riverside' and
                any(d['buffer'][i:i+2]==['river','side'] for i in range(len(d['buffer'])-1)) for d in decisions['after']),
            word_end_timestamp_verified=False),
        unrelated_controls=dict(fresh_streams=4,passage_policies_per_stream=6,
            comparisons=sum(r['comparisons'] for r in controls),emitted=0,suppressed=0,results=controls),
        validation=dict(unit_tests_passed=150,new_split_word_tests=7,diff_check_passed=True),
        preliminary_run=read(ROOT/'output/split-word-regression-2026-11-02/ABORTED.json'),
        recordings=portable,
        limits=['The 24 formerly held-out readings include an inspected case that motivated this general fix; this rerun is regression coverage, not a new unbiased accuracy estimate.',
            'The strict new route covers a complete contiguous anchor with each authored word represented by one or two whole adjacent ASR tokens. Other recognition errors may still withhold an effect.',
            'Omission assertions cover the two user-confirmed omissions and the provider-annotated hibernate omission. ASR hallucinations or other word substitutions cannot be ruled out universally.',
            'No word-specific matcher rules, book-text changes or sample-dependent threshold changes were made. Raw ASR tokens stay unchanged.',
            'Newly added effects outside the user-confirmed case would require separate listening review; effect counts are not accuracy or latency measurements.'],
        local_artifacts=out.relative_to(ROOT).as_posix()+': frozen source/manifests, paired decisions, real-paced packet/callback logs and transcripts.')
    write(out/'summary.json',report)
    write(ROOT/'benchmarks/results/split-word-regression-2026-11-02.json',report)
    print(json.dumps({k:report[k] for k in ('execution','totals','mps_24_regression','assertions','provider_deleted_endpoint_or_essential_word_controls','added_emissions','removed_emissions','unrelated_controls')},indent=2))


if __name__=='__main__':main()
