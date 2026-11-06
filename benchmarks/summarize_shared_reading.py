"""Summarize frozen shared-reading stress tests without relabelling failures."""
import argparse
import csv
import hashlib
import html
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from benchmarks.run_shared_reading import DEST,verify
from benchmarks.run_mps_heldout import read,write
from books_to_life.matching.checkpoint_matcher import normalize_text


def main(output):
    done=read(output/'completed.json');protocol=verify(output,model_hash=True,audio=True)
    rows=read(output/'results.json')['cases'];jobs={j['id']:j for j in read(output/'jobs.json')}
    inventory={j['id']:j for j in read(output/'audio-inventory.json')}
    assert len(rows)==done['fresh_streams']==18 and [r['id'] for r in rows]==protocol['ordered_recordings']
    assert all(r['delivery_audit_pass'] and r['stream_done'] and r['app_observer_replay_agreement'] for r in rows)
    synthetic=[r for r in rows if r['group']=='controlled_synthetic_roles']
    child=[r for r in rows if r['group']=='recorded_child_constructed_interruption']
    baseline={r['source_id']:r for r in child if r['category']=='baseline'}
    review=output/'review';review.mkdir(exist_ok=True);cards=[];sheet=[];portable=[];diagnostics=[]
    for row in rows:
        job=jobs[row['id']];info=inventory[row['id']];cfg=read(Path(job['manifest']))
        anchor=next(c['checkpoint_text'] for c in cfg['checkpoints'] if c['id']==row['target'])
        events=[json.loads(s) for s in (output/'streams'/(row['id']+'.events.jsonl')).read_text(encoding='utf-8').splitlines()]
        callbacks=[e for e in events if e['kind']=='segments']
        phrase=' '+normalize_text(anchor)+' '
        matches=[e['segments'][-1]['end'] for e in callbacks
            if phrase in ' '+normalize_text(' '.join(s['text'] for s in e['segments']))+' ']
        item={k:v for k,v in row.items() if k!='final_asr'}
        item['exact_target_in_any_asr_callback']=bool(matches)
        item['first_exact_target_callback_audio_end']=matches[0] if matches else None
        item['exact_target_can_come_from_coaching']=row['category'] in ('coaching_only','coaching_then_reading','coaching_before_reading')
        item['final_asr_words']=len(normalize_text(row['final_asr']).split())
        item['final_asr_sha256']=hashlib.sha256(row['final_asr'].encode('utf-8')).hexdigest()
        if row['group']=='controlled_synthetic_roles':item['final_asr']=row['final_asr']
        if row.get('source_id'):
            comparison=baseline[row['source_id']]
            late_baseline=[d['id'] for d in comparison['decisions']
                if d['audio_end']>comparison['audio_seconds']/2]
            item['relative_to_fresh_child_baseline']=dict(
                added_emissions=sorted(set(row['outcomes']['emitted'])-set(comparison['outcomes']['emitted'])),
                lost_emissions=sorted(set(comparison['outcomes']['emitted'])-set(row['outcomes']['emitted'])),
                baseline_effect_callback_markers_after_midpoint=late_baseline,
                lost_effects_with_baseline_callbacks_after_midpoint=sorted(set(late_baseline)-set(row['outcomes']['emitted'])))
        diagnostics.append(dict(id=row['id'],reference_target=anchor,final_asr=row['final_asr'],
            composition_spans=info['spans'],exact_target_callback_ends=matches,
            note='Callback times and composition spans are not verified word endpoints. Exact target may be quoted coaching.'))
        portable.append(item)
        flags=[]
        if not row['target_expectation_met']:flags.append('target differs from declared goal')
        if row.get('missing_expected'):flags.append('missing expected effects: '+', '.join(row['missing_expected']))
        if row.get('unexpected_emitted'):flags.append('unexpected effects: '+', '.join(row['unexpected_emitted']))
        if row.get('target_before_legitimate_reading'):flags.append('target fired before legitimate reading')
        if row.get('emissions_before_child_reading'):flags.append('effects before child reading')
        if item.get('relative_to_fresh_child_baseline',{}).get('lost_emissions'):flags.append('lost effects relative to fresh child baseline')
        media='../inputs/'+row['id']+'/audio.wav';esc=lambda x:html.escape(str(x))
        cards.append('<article><h2>'+esc(row['id'])+'</h2><p>'+esc('; '.join(flags) or 'No declared target-goal failure flagged.')+
            '</p><audio controls preload="none" src="'+esc(media)+'"></audio>'
            '<p>Target: '+esc(anchor)+' Expected target effect: '+esc(row['expected_target_emit'])+
            '; emitted: '+esc(row['target_emitted'])+'.</p>'
            '<details><summary>Composition and ASR</summary><pre>'+esc(json.dumps(info['spans'],indent=2))+
            '</pre><p>ASR: '+esc(row['final_asr'])+'</p></details></article>')
        sheet.append(dict(case=row['id'],group=row['group'],category=row['category'],target=row['target'],
            reference_target=anchor,expected_target_emit=row['expected_target_emit'],target_emitted=row['target_emitted'],
            exact_target_in_asr=bool(matches),flags='; '.join(flags),audio=media,
            human_heard='',human_target_audible='',human_coaching_or_reading='',human_should_emit='',notes=''))
    path=review/'manual_review.csv'
    if not path.exists():
        with path.open('w',encoding='utf-8',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=list(sheet[0]));writer.writeheader();writer.writerows(sheet)
    (review/'index.html').write_text('<!doctype html><html lang="en"><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1"><title>Shared-reading stress tests</title>'
        '<style>body{max-width:950px;margin:36px auto;padding:0 22px;font:17px/1.6 system-ui;color:#203040}'
        'article{border-top:2px solid #ccd5df;padding:22px 0}audio{width:100%}pre{white-space:pre-wrap}</style>'
        '<h1>Offline shared-reading stress tests</h1><p>Ten controlled two-adult-TTS cases and eight variants of '
        'two previously inspected child recordings. Every selected input streamed once. ASR and matcher unchanged. '
        'These are constructed stress tests, not natural family reading or a microphone evaluation. '
        'Human labels are blank. Confirm target audibility, coaching versus reading, and whether effects should fire. '
        '<a href="manual_review.csv">Review CSV</a></p>'+''.join(cards)+'</html>',encoding='utf-8')
    write(output/'local-diagnostics.json',diagnostics)
    report=dict(date='2026-11-03',scope=protocol['scope'],
        sources=dict(controlled_synthetic_voices=protocol['synthetic_voices'],controlled_synthetic_streams=10,
            recorded_child_sources=2,child_composite_streams=8,previously_inspected=True,
            source_ids=sorted(baseline),human_listening_labels=0),
        configuration=protocol['configuration'],model=protocol['model'],lexicon=protocol['lexicon'],
        client_environment=read(output/'client-environment.json'),server_environment=read(output/'server-environment.json'),
        execution=dict(fresh_streams=18,total_audio_seconds=sum(r['audio_seconds'] for r in rows),
            one_trial_per_selected_input=True,all_trials_retained=True,all_samples_delivered=True,
            streams_with_interim_text=sum(r['partial_before_eof'] for r in rows),
            all_eof_and_app_observer_replay_audits_pass=True),
        controlled_synthetic=dict(cases=10,
            target_goals_met=sum(r['target_expectation_met'] for r in synthetic),
            complete_effect_goals_met=sum(not r['missing_expected'] and not r['unexpected_emitted'] and not r['target_before_legitimate_reading'] for r in synthetic),
            missed_target_goals=[r['id'] for r in synthetic if r['expected_target_emit'] and not r['target_emitted']],
            emissions_on_target_negative_cases=[r['id'] for r in synthetic if not r['expected_target_emit'] and r['target_emitted']],
            premature_targets=[r['id'] for r in synthetic if r['target_before_legitimate_reading']]),
        recorded_child=dict(cases=8,target_goals_met=sum(r['target_expectation_met'] for r in child),
            source_baseline_outcomes={ident:r['outcomes'] for ident,r in baseline.items()},
            comparisons=[dict(id=r['id'],**r['relative_to_fresh_child_baseline']) for r in portable if r.get('source_id')],
            omissions=dict(source_id='4a35g_EN-OL-RC-426_2',target='hibernate',
                cases=sum(r['source_id']=='4a35g_EN-OL-RC-426_2' for r in child),
                literal_absence_variants=3,quoted_coaching_variant=1,
                note='The child omits the word in all four. The coaching variant contains the word in an adult prompt, so only three variants preserve literal absence throughout the composite.',
                emitting_cases=[r['id'] for r in child if r['source_id']=='4a35g_EN-OL-RC-426_2' and r['target_emitted']])),
        interpretation='Counts compare outcomes with predeclared constructed goals, not independently confirmed correctness or population accuracy. Exact ASR anchor text can be coaching. Paired child baselines use the same common source attenuation. Preserving only effects whose baseline callbacks precede an interruption does not demonstrate recovery after it.',
        composition=protocol['composition'],limits=protocol['limits'],
        integrity=dict(asr_matcher_model_lexicon_unchanged=True,hints_disabled=True,
            selections_scripts_and_recipes_fixed_before_synthesis_and_recognition=True,
            original_child_files_unchanged=True,no_child_samples_removed=True,
            all_composed_audio_hashes_unchanged=True,source_sha256=protocol['source_sha256']),
        cases=portable,listening_review=dict(cases=18,human_fields_blank=True,
            html=(review/'index.html').relative_to(ROOT).as_posix()),artifacts=output.relative_to(ROOT).as_posix())
    write(output/'summary.json',report)
    write(ROOT/'benchmarks/results/shared-reading-2026-11-03.json',report)
    print(json.dumps({k:report[k] for k in ('execution','controlled_synthetic','recorded_child')},indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,default=DEST)
    main(parser.parse_args().output.resolve())
