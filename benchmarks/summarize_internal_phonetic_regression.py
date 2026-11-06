"""Report internal pronunciation support without rewriting recognition text."""
import argparse
import json
import math
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from benchmarks.run_internal_phonetic_regression import DEST,PRIOR,TARGET,NEGATIVES,verify
from benchmarks.run_mps_heldout import read,write,digest
from benchmarks.run_pending_regression import replay
from books_to_life.matching.timely_matcher import TimelyEvidenceMatcher
from books_to_life.matching.phonetic_endpoint import phonetic_endpoint_match


def primary_trace(job,events):
    matcher=TimelyEvidenceMatcher(read(Path(job['manifest'])));traces=[]
    for ident,permission in matcher._effect_permissions.items():
        original=permission._internal_phonetic_support
        def observed(window,pairs,permission=permission,original=original,ident=ident):
            result=original(window,pairs)
            if result:
                matched=dict(pairs+[(len(permission.anchor)-1,len(window)-1)])
                substitutions=[]
                for i in range(1,len(permission.anchor)-1):
                    if i in matched or permission.anchor[i] in permission.required:continue
                    left,right=matched.get(i-1),matched.get(i+1)
                    if left is not None and right==left+2 and permission.anchor[i-1]==window[left] and permission.anchor[i+1]==window[right] and phonetic_endpoint_match(permission.anchor[i],window[left+1]):
                        substitutions.append(dict(reference=permission.anchor[i],asr=window[left+1]))
                traces.append(dict(checkpoint=ident,audio_end=matcher._audio_time,asr_window=window,
                    spelling_support=len(pairs)+1,phonetic_credit=1,
                    required_support=math.ceil(len(permission.anchor)*permission.coverage),
                    anchor_words=len(permission.anchor),substitutions=substitutions))
            return result
        permission._internal_phonetic_support=observed
    for e in events:
        if e['kind']=='segments':matcher.process(' '.join(s['text'] for s in e['segments']),e['segments'])
    return traces


def main(output):
    protocol=verify(output,model_hash=True,audio=True)
    rows=read(output/'results.json')['cases'];assert len(rows)==read(output/'completed.json')['fresh_streams']==25
    jobs={j['id']:j for j in read(output/'jobs.json')}
    fixtures=[dict(id=j['id'],group=j['group'],manifest=j['manifest'],manifest_sha256=j['manifest_sha256'],
        events=str(output/'streams'/(j['id']+'.events.jsonl')),events_sha256=digest(output/'streams'/(j['id']+'.events.jsonl')))
        for j in jobs.values()]
    path=output/'fresh-replay-jobs.json'
    if path.exists():assert read(path)==fixtures
    else:write(path,fixtures)
    for label,old in [('before',True),('after',False)]:
        if not (output/f'fresh-{label}.json').exists():
            cmd=[sys.executable,'-X','utf8','-u','benchmarks/replay_policy_batch.py','--jobs',str(path),'--output',str(output/f'fresh-{label}.json')]
            if old:cmd+=['--snapshot',str(output/'baseline-snapshot')]
            subprocess.run(cmd,cwd=ROOT,check=True)
    before={r['id']:r['outcomes'] for r in read(output/'fresh-before.json')['cases']}
    after={r['id']:r['outcomes'] for r in read(output/'fresh-after.json')['cases']}
    portable=[];unrelated=[];trace=[]
    for row in rows:
        ident=row['id'];j=jobs[ident]
        assert row['outcomes']==after[ident] and row['asr_callbacks_identical_to_previous']
        assert set(before[ident]['emitted']).issubset(after[ident]['emitted'])
        item={k:v for k,v in row.items() if k not in ('final_asr','target_before_legitimate_reading','emissions_before_child_reading')}
        item.update(before=before[ident],after=after[ident],
            added=sorted(set(after[ident]['emitted'])-set(before[ident]['emitted'])))
        if row['group'] in ('controlled_synthetic_roles','synthetic_challenge'):item['final_asr']=row['final_asr']
        portable.append(item)
        events=[json.loads(s) for s in (output/'streams'/(ident+'.events.jsonl')).read_text(encoding='utf-8').splitlines()]
        if ident==TARGET:trace=primary_trace(j,events)
        if row['group']=='unrelated':
            for p in read(output/'offbook-manifests.json'):
                ledger=replay(TimelyEvidenceMatcher,read(Path(p)),events);assert not ledger['emitted']
                unrelated.append(dict(id=ident,manifest=str(p),outcomes=ledger))
    assert len(unrelated)==24
    write(output/'unrelated-policy-replays.json',dict(comparisons=unrelated))
    word_omissions=[r for r in rows if r['group']=='synthetic_challenge' or (r['group']=='reviewed_mps' and not r['expected_target_emit'])]
    assert len(word_omissions)==8 and not any(r['target_emitted'] for r in word_omissions)
    assert all(r['target_expectation_met'] for r in rows)
    primary=next(r for r in rows if r['id']==TARGET)
    assert 'lost_sheep' not in before[TARGET]['emitted'] and 'lost_sheep' in after[TARGET]['emitted']
    assert any(t['checkpoint']=='lost_sheep' and t['substitutions']==[dict(reference='sheep',asr='ship')]
               and t['spelling_support']==6 and t['required_support']==7 for t in trace)
    unit_reference=read(PRIOR/'nemo-unit-test-reference.json')
    for name,sha in unit_reference['files_unchanged_since_passing_check'].items():assert protocol['source_sha256'][name]==sha
    assert digest(ROOT/unit_reference['log'])==unit_reference['sha256']
    changes=read(output/'preflight.json')['changes']
    report=dict(date='2026-11-04',freeze_label_date=protocol['date'],scope='One guarded internal pronunciation match after ordinary acquisition',
        rule=protocol['rule'],configuration=protocol['configuration'],model=protocol['model'],lexicon=protocol['lexicon'],
        server_environment=read(PRIOR/'server-environment.json'),
        execution=dict(fresh_streams=25,audio_seconds=sum(r['audio_seconds'] for r in rows),saved_comparisons=327,
            fresh_paired_comparisons=25,all_asr_callback_sequences_identical_to_previous=True,
            all_delivery_eof_app_observer_replay_audits_pass=True,one_trial_per_selected_input=True,all_trials_retained=True),
        user_listening=read(output/'user-listening.json'),
        confirmed_recovery=dict(id=TARGET,checkpoint='lost_sheep',before=False,after=True,permission_trace=trace,
            asr_text_unchanged=True,explanation='Existing pronunciation comparison supports sheep/ship between exact one/was neighbours. Spelling supplies six of eight anchor words; one phonetic match reaches the existing seven-word requirement. Lost/locked remains unmatched; the ASR transcript is not rewritten.'),
        saved_comparisons=read(output/'preflight.json'),
        saved_additions=dict(changed_comparisons=len(changes),new_effect_events=sum(len(c['added']) for c in changes),
            effect_ids=sorted({e for c in changes for e in c['added']}),
            scope='Repeated conditions/timelines for the same underlying sheep recording, not new independent readers.'),
        fresh_comparison=dict(changes=[dict(id=r['id'],added=r['added']) for r in portable if r['added']],
            removed_effects=0,all_skips_unchanged=all(before[r['id']]['skipped']==after[r['id']]['skipped'] for r in rows)),
        omissions=dict(fresh_word_omission_controls=8,target_emissions=0,
            saved_provider_deletion_controls=len(protocol['provider_deletion_controls']),all_saved_controls_non_emitting=True),
        other_fresh_regressions=dict(reviewed_mps=9,all_target_assertions_pass=True,
            prior_long_pause_and_child_aside_recoveries_preserved=True,pause_phase_cases=4,all_phase_targets_emit=True),
        unrelated=dict(fresh_recordings=4,policy_replay_comparisons=24,effects=0),
        unit_tests=dict(run=211,passed=210,skipped=1,installed_nemo_test=unit_reference),
        integrity=dict(model_asr_lexicon_thresholds_audio_and_manifests_unchanged=True,asr_callbacks_unchanged=True,
            changed_runtime_files=protocol['changed_runtime_files'],source_sha256=protocol['source_sha256'],
            baseline_sha256=protocol['baseline_sha256']),
        limits=protocol['limits'],cases=portable,artifacts=output.relative_to(ROOT).as_posix())
    write(output/'summary.json',report);write(ROOT/'benchmarks/results/internal-phonetic-regression-2026-11-04.json',report)
    print(json.dumps({k:report[k] for k in ('execution','confirmed_recovery','saved_additions','fresh_comparison','omissions','unrelated')},indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,default=DEST)
    main(p.parse_args().output.resolve())
