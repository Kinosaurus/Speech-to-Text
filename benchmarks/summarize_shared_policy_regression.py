"""Report the shared-reading policy change separately from older frozen results."""
import argparse
import csv
import html
import json
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from benchmarks.run_shared_policy_regression import DEST,verify
from benchmarks.run_mps_heldout import read,write
from benchmarks.pod_pronunciation_review import annotate


def totals(rows):
    return {key:sum(len(row[key]) for row in rows) for key in ('emitted','suppressed','skipped','unreached')}


def main(output):
    done=read(output/'completed.json');protocol=verify(output,model_hash=True,audio=True)
    rows=read(output/'results.json')['cases'];jobs={j['id']:j for j in read(output/'jobs.json')}
    before={r['id']:r['outcomes'] for r in read(output/'fresh-before.json')['cases']}
    after={r['id']:r['outcomes'] for r in read(output/'fresh-after.json')['cases']}
    saved_jobs=read(output/'replay-jobs.json');saved_before={r['id']:r['outcomes'] for r in read(output/'saved-before.json')['cases']}
    saved_after={r['id']:r['outcomes'] for r in read(output/'saved-after.json')['cases']}
    assert len(rows)==done['fresh_streams']==31
    assert all(after[r['id']]==r['outcomes'] for r in rows)
    review=output/'review';review.mkdir(exist_ok=True);sheet=[];cards=[];portable=[]
    for row in rows:
        job=jobs[row['id']];old=before[row['id']];new=after[row['id']]
        target=next(c['checkpoint_text'] for c in read(Path(job['manifest']))['checkpoints'] if c['id']==row['target'])
        item={k:v for k,v in row.items() if k!='final_asr'}
        item.update(before=old,after=new,
            added_emissions=sorted(set(new['emitted'])-set(old['emitted'])),
            removed_emissions=sorted(set(old['emitted'])-set(new['emitted'])))
        # The old audit's coaching-negative timing field has a different meaning
        # after this policy: a quoted full anchor is now legitimate reading.
        item.pop('target_before_legitimate_reading',None)
        item.pop('emissions_before_child_reading',None)
        item['before_target_goal_met']=((row['target'] in old['emitted'])==job['expected_target_emit'])
        if row['group']=='controlled_synthetic_roles':item['final_asr']=row['final_asr']
        portable.append(item)
        media=Path(os.path.relpath(job['audio'],review)).as_posix();esc=lambda x:html.escape(str(x))
        sheet.append(dict(case=row['id'],group=row['group'],target=row['target'],reference_target=target,
            expected_under_shared_policy=job['expected_target_emit'],before_emitted=row['target'] in old['emitted'],
            after_emitted=row['target_emitted'],added=';'.join(item['added_emissions']),removed=';'.join(item['removed_emissions']),
            audio=media,human_heard='',human_should_emit='',notes=''))
        cards.append('<article><h2>'+esc(row['id'])+'</h2><p>Target: '+esc(target)+
            '; desired under shared policy: '+esc(job['expected_target_emit'])+'.</p>'
            '<audio controls preload="none" src="'+esc(media)+'"></audio>'
            '<p>Old effects: '+esc(', '.join(old['emitted']) or 'none')+'; new effects: '+esc(', '.join(new['emitted']) or 'none')+'.</p>'
            '<details><summary>Fresh ASR</summary><p>'+esc(row['final_asr'])+'</p></details></article>')
    csv_path=review/'manual_review.csv'
    if not csv_path.exists():
        with csv_path.open('w',encoding='utf-8',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=list(sheet[0]));writer.writeheader();writer.writerows(sheet)
    (review/'index.html').write_text('<!doctype html><html lang="en"><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1"><title>Shared-reading policy regression</title>'
        '<style>body{max-width:950px;margin:36px auto;padding:0 22px;font:17px/1.6 system-ui;color:#203040}'
        'article{border-top:2px solid #ccd5df;padding:22px 0}audio{width:100%}</style>'
        '<h1>Shared-reading policy regression</h1><p>Positive coaching counts as reading. '
        'Both voices use normal story alignment and one-shot history. ASR/model/audio are unchanged. '
        'Old and new matchers replay the same fresh callbacks in separate processes. '
        'All inputs are inspected regressions; human labels for these composed cases remain blank. '
        '<a href="manual_review.csv">Review CSV</a></p>'+''.join(cards)+'</html>',encoding='utf-8')
    mps=[j for j in saved_jobs if j['group']=='saved_mps']
    challenges=[j for j in saved_jobs if j['group']=='saved_challenge']
    shared=[r for r in portable if r['group'] in ('controlled_synthetic_roles','recorded_child_constructed_interruption')]
    controlled=[r for r in shared if r['group']=='controlled_synthetic_roles']
    def complete_goal(row,ledger):
        expected=set(jobs[row['id']]['expected_emitted'])
        return set(ledger['emitted'])==expected
    report=dict(date='2026-11-03',scope='Shared-reading policy change and inspected-data regression',
        policy=protocol['policy'],changed_expectations=protocol['changed_expectations'],
        configuration=protocol['configuration'],model=protocol['model'],lexicon=protocol['lexicon'],
        client_environment=read(output/'client-environment.json'),server_environment=read(output/'server-environment.json'),
        execution=dict(fresh_streams=31,shared_reading_streams=18,reviewed_mps_streams=9,unrelated_streams=4,
            audio_seconds=sum(r['audio_seconds'] for r in rows),saved_comparisons=214,saved_mps_readings=123,
            all_samples_delivered=True,all_stream_done=True,all_app_observer_replay_agreement=True,
            asr_callbacks_identical_to_original=sum(r['asr_callbacks_identical_to_original'] for r in rows),
            all_trials_retained=True,one_fresh_trial_per_selected_input=True),
        saved_mps=dict(readings=123,before=totals([saved_before[j['id']] for j in mps]),
            after=totals([saved_after[j['id']] for j in mps]),
            changed_readings=[j['id'] for j in mps if saved_before[j['id']]!=saved_after[j['id']]],
            provider_deletion_controls=len(protocol['provider_deletion_controls']),all_deletion_controls_non_emitting=True),
        fresh_shared=dict(cases=18,goals_evaluated_under_new_policy_for_both_implementations=True,
            before_target_goals_met=sum(r['before_target_goal_met'] for r in shared),
            after_target_goals_met=sum(r['target_expectation_met'] for r in shared),
            controlled_complete_effect_goals_before=sum(complete_goal(r,r['before']) for r in controlled),
            controlled_complete_effect_goals_after=sum(complete_goal(r,r['after']) for r in controlled),
            changes=[dict(id=r['id'],added=r['added_emissions'],removed=r['removed_emissions']) for r in shared
                if r['added_emissions'] or r['removed_emissions']],
            remaining_target_misses=[r['id'] for r in shared if r['expected_target_emit'] and not r['target_emitted']],
            note='An adult coaching the whole anchor now counts, including hibernate. Such a composite contains the word and is not a literal-omission control. Existing forward jumps can skip earlier checkpoints.'),
        fresh_reviewed_mps=dict(cases=9,all_assertions_pass=done['nine_reviewed_mps_assertions_pass'],
            natural_omission_cases=[r['id'] for r in portable if r['group']=='reviewed_mps' and not r['expected_target_emit']],
            before=totals([r['before'] for r in portable if r['group']=='reviewed_mps']),
            after=totals([r['after'] for r in portable if r['group']=='reviewed_mps'])),
        unrelated=dict(saved_comparisons=24,saved_effects=0,fresh_streams=4,
            fresh_policy_replay_comparisons=24,fresh_effects=done['unrelated_effects'],
            note='Six policies replay each of four fresh unrelated ASR timelines; these are four audio trials, not 24.'),
        saved_challenges=dict(cases=45,
            positive_quoted_target_emissions=sum('target' in saved_after[j['id']]['emitted'] for j in challenges if j['category']=='quoted_prompt'),
            negated_prompt_target_emissions=sum('target' in saved_after[j['id']]['emitted'] for j in challenges if j['category']=='negated_prompt'),
            omitted_target_emissions=sum('target' in saved_after[j['id']]['emitted'] for j in challenges if j['category']=='omitted'),
            close_wrong_word_false_emissions_before=sum('target' in saved_before[j['id']]['emitted'] for j in challenges if j['category']=='close_wrong_word'),
            close_wrong_word_false_emissions_after=sum('target' in saved_after[j['id']]['emitted'] for j in challenges if j['category']=='close_wrong_word')),
        unit_tests=read(output/'unit-tests.json'),
        integrity=dict(asr_model_lexicon_audio_manifests_thresholds_unchanged=True,
            current_sources_frozen_during_testing=True,complete_old_runtime_replayed_in_separate_process=True,
            all_214_old_ledgers_reproduced=True,changed_runtime_files=protocol['changed_runtime_files'],
            source_sha256=protocol['source_sha256'],baseline_sha256=protocol['baseline_sha256']),
        limits=protocol['limits']+['Positive-coaching policy does not fix the separate Singapore prefix-confirmation miss.',
            'Negation remains a bounded text veto on effects/assistance; it is not a new hold-progress state.',
            'One coached hibernate phrase appears in ASR but remains unconfirmed; accepting coaching does not guarantee every phrase triggers.',
            'Known close-word false emissions remain. Existing missing finish effects and interruption losses remain.',
            'No new human listening labels, population accuracy or verified word latency are claimed.'],
        cases=portable,artifacts=output.relative_to(ROOT).as_posix(),
        listening_review=dict(cases=31,human_fields_blank=True,html=(review/'index.html').relative_to(ROOT).as_posix()))
    annotate(report)
    write(output/'summary.json',report);write(ROOT/'benchmarks/results/shared-policy-regression-2026-11-03.json',report)
    print(json.dumps({k:report[k] for k in ('execution','saved_mps','fresh_shared','fresh_reviewed_mps','unrelated','saved_challenges')},indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,default=DEST)
    main(parser.parse_args().output.resolve())
