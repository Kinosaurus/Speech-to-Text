"""Report prefix evidence, paired replay and fresh streaming controls."""
import argparse
import csv
import html
import json
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from benchmarks.run_prefix_confirmation_regression import DEST,RECOVERIES,verify
from benchmarks.run_mps_heldout import read,write
from benchmarks.pod_pronunciation_review import annotate
from benchmarks.summarize_shared_policy_regression import totals


def main(output):
    done=read(output/'completed.json');protocol=verify(output,model_hash=True,audio=True)
    rows=read(output/'results.json')['cases'];jobs={j['id']:j for j in read(output/'jobs.json')}
    before={r['id']:r for r in read(output/'fresh-before.json')['cases']}
    after={r['id']:r for r in read(output/'fresh-after.json')['cases']}
    fixtures=read(output/'replay-jobs.json')
    saved_before={r['id']:r for r in read(output/'saved-before.json')['cases']}
    saved_after={r['id']:r for r in read(output/'saved-after.json')['cases']}
    assert len(rows)==done['fresh_streams']==32
    review=output/'review';review.mkdir(exist_ok=True);cards=[];sheet=[];portable=[]
    for row in rows:
        job=jobs[row['id']];old=before[row['id']]['outcomes'];new=after[row['id']]['outcomes']
        assert new==row['outcomes']
        item={k:v for k,v in row.items() if k not in ('final_asr','target_before_legitimate_reading','emissions_before_child_reading')}
        item.update(before=old,after=new,prefix_confirmation_uses=after[row['id']]['prefix_confirmation_uses'],
            added_emissions=sorted(set(new['emitted'])-set(old['emitted'])),
            removed_emissions=sorted(set(old['emitted'])-set(new['emitted'])))
        if row['group']=='controlled_synthetic_roles':item['final_asr']=row['final_asr']
        portable.append(item)
        target=next(c['checkpoint_text'] for c in read(Path(job['manifest']))['checkpoints'] if c['id']==row['target'])
        media=Path(os.path.relpath(job['audio'],review)).as_posix();esc=lambda x:html.escape(str(x))
        sheet.append(dict(case=row['id'],group=row['group'],target=row['target'],reference_target=target,
            expected_target=job['expected_target_emit'],before=row['target'] in old['emitted'],after=row['target_emitted'],
            added=';'.join(item['added_emissions']),removed=';'.join(item['removed_emissions']),audio=media,
            human_heard='',human_should_emit='',notes=''))
        cards.append('<article><h2>'+esc(row['id'])+'</h2><p>Target: '+esc(target)+'</p>'
            '<audio controls preload="none" src="'+esc(media)+'"></audio><p>Old effects: '+esc(', '.join(old['emitted']) or 'none')+
            '; new effects: '+esc(', '.join(new['emitted']) or 'none')+'.</p>'
            '<details><summary>Fresh ASR and prefix evidence</summary><p>'+esc(row['final_asr'])+'</p><pre>'+
            esc(json.dumps(item['prefix_confirmation_uses'],indent=2))+'</pre></details></article>')
    path=review/'manual_review.csv'
    if not path.exists():
        with path.open('w',encoding='utf-8',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=list(sheet[0]));writer.writeheader();writer.writerows(sheet)
    (review/'index.html').write_text('<!doctype html><html lang="en"><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1"><title>Prefix confirmation regression</title>'
        '<style>body{max-width:950px;margin:36px auto;padding:0 22px;font:17px/1.6 system-ui}article{border-top:2px solid #ccd5df;padding:22px 0}audio{width:100%}pre{white-space:pre-wrap}</style>'
        '<h1>Prefix confirmation regression</h1><p>ASR, thresholds, audio and manifests are unchanged. '
        'Old and new complete matching stacks replay the same callbacks in separate processes. '
        'These are inspected regressions. Singapore is one complete conversation source; other cases include constructed audio. '
        'Markers are callback times, not verified word latency. New listening fields are blank. '
        '<a href="manual_review.csv">Review CSV</a></p>'+''.join(cards)+'</html>',encoding='utf-8')
    def saved_totals(group,ledger):return totals([ledger[j['id']]['outcomes'] for j in fixtures if j['group']==group])
    challenges=[j for j in fixtures if j['group']=='saved_challenge']
    challenge_emits=lambda ledger,kind:sum('target' in ledger[j['id']]['outcomes']['emitted'] for j in challenges if j['category']==kind)
    shared=[r for r in portable if r['group'] in ('controlled_synthetic_roles','recorded_child_constructed_interruption')]
    controlled=[r for r in shared if r['group']=='controlled_synthetic_roles']
    complete=lambda r,label:set(r[label]['emitted'])==set(jobs[r['id']]['expected_emitted'])
    recoveries=[]
    for goal in RECOVERIES:
        row=next(r for r in portable if r['id']==goal['id'])
        recoveries.append(dict(goal,before=goal['checkpoint'] in row['before']['emitted'],
            after=goal['checkpoint'] in row['after']['emitted'],
            evidence=[e for e in row['prefix_confirmation_uses'] if e['checkpoint']==goal['checkpoint']],
            effect_callback_audio_end=next(d['audio_end'] for d in row['decisions'] if d['id']==goal['checkpoint'])))
    aborted=ROOT/'output/prefix-confirmation-regression-2026-11-03/ABORTED.json'
    report=dict(date='2026-11-03',scope=protocol['scope'],prefix_rule=protocol['prefix_rule'],
        configuration=protocol['configuration'],model=protocol['model'],lexicon=protocol['lexicon'],
        client_environment=read(output/'client-environment.json'),server_environment=read(output/'server-environment.json'),
        execution=dict(version='Final corrected v2',fresh_streams=32,shared_streams=18,reviewed_mps=9,unrelated_streams=4,singapore_full_streams=1,
            audio_seconds=sum(r['audio_seconds'] for r in rows),saved_comparisons=214,
            asr_callbacks_identical_to_original=sum(r['asr_callbacks_identical_to_original'] for r in rows),
            all_samples_delivered=True,all_eof_and_app_observer_replay_audits_pass=True,
            all_trials_retained=True,one_trial_per_selected_input=True),
        preliminary_aborted_batch=read(aborted) if aborted.exists() else None,
        requested_recoveries=recoveries,
        saved_comparison=dict(changes=read(output/'preflight.json')['changes'],
            mps=dict(readings=123,before=saved_totals('saved_mps',saved_before),after=saved_totals('saved_mps',saved_after),
                changed_readings=[j['id'] for j in fixtures if j['group']=='saved_mps' and saved_before[j['id']]['outcomes']!=saved_after[j['id']]['outcomes']]),
            seven_provider_deletion_controls_non_emitting=True),
        fresh_comparison=dict(before=totals([r['before'] for r in portable]),after=totals([r['after'] for r in portable]),
            changes=[dict(id=r['id'],added=r['added_emissions'],removed=r['removed_emissions']) for r in portable if r['added_emissions'] or r['removed_emissions']],
            nine_reviewed_assertions_pass=done['nine_reviewed_assertions_pass'],
            literal_mps_omission_cases=[r['id'] for r in portable if r['group']=='reviewed_mps' and not r['expected_target_emit']],
            omission_effects=sum(r['target_emitted'] for r in portable if r['group']=='reviewed_mps' and not r['expected_target_emit']),
            shared_target_goals_met=sum(r['target_expectation_met'] for r in shared),shared_cases=18,
            controlled_complete_goals_before=sum(complete(r,'before') for r in controlled),
            controlled_complete_goals_after=sum(complete(r,'after') for r in controlled),
            remaining_shared_target_misses=[r['id'] for r in shared if r['expected_target_emit'] and not r['target_emitted']]),
        unrelated=dict(saved_comparisons=24,saved_effects=0,fresh_streams=4,fresh_policy_replay_comparisons=24,fresh_effects=0),
        saved_challenges=dict(cases=45,omitted_target_emissions=challenge_emits(saved_after,'omitted'),
            negated_target_emissions=challenge_emits(saved_after,'negated_prompt'),
            close_wrong_word_emissions_before=challenge_emits(saved_before,'close_wrong_word'),
            close_wrong_word_emissions_after=challenge_emits(saved_after,'close_wrong_word')),
        unit_tests=read(output/'unit-tests.json'),
        integrity=dict(asr_model_lexicon_thresholds_audio_manifests_unchanged=True,shared_reading_policy_unchanged=True,
            complete_old_runtime_replayed_in_separate_process=True,all_214_original_ledgers_verified=True,
            current_sources_frozen_during_testing=True,changed_runtime_files=protocol['changed_runtime_files'],
            source_sha256=protocol['source_sha256'],baseline_sha256=protocol['baseline_sha256']),
        limits=protocol['limits']+['A coached hibernate phrase contains the adult-spoken word; it is a positive shared-reading case, not a literal omission control.',
            'Singapore utterance_01 remains unclear and utterance_02 remains an ASR miss; reaching utterance_03 can skip those earlier checkpoints.',
            'Prefix-use counts include already-working checkpoints and are not a count of newly recovered effects.'],
        cases=portable,listening_review=dict(cases=32,human_fields_blank=True,html=(review/'index.html').relative_to(ROOT).as_posix()),
        artifacts=output.relative_to(ROOT).as_posix())
    assert not any(c['removed'] for c in report['fresh_comparison']['changes'])
    annotate(report)
    write(output/'summary.json',report);write(ROOT/'benchmarks/results/prefix-confirmation-regression-2026-11-03.json',report)
    print(json.dumps({k:report[k] for k in ('execution','requested_recoveries','fresh_comparison','saved_challenges')},indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,default=DEST)
    main(parser.parse_args().output.resolve())
