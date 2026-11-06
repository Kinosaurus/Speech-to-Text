"""Summarize frozen resumption streams without relabelling historical trials."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import hashlib
import wave
import cmudict

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from benchmarks.run_resumption_regression import DEST,PRIOR,PHASE,NEGATIVES,verify
from benchmarks.run_mps_heldout import read,write,digest
from benchmarks.run_pending_regression import replay
from benchmarks.run_shared_policy_regression import signature
from books_to_life.matching.timely_matcher import TimelyEvidenceMatcher
from books_to_life.matching.checkpoint_matcher import normalize_text


def unreviewed_clip(output,jobs):
    path=output/'review/unconfirmed-lost-sheep.json'
    if path.exists():return read(path)
    job=jobs['shared-3a8b_EN-OL-RC-234_1-coaching_before_reading'];source=Path(job['audio'])
    path.parent.mkdir(exist_ok=True)
    with wave.open(str(source),'rb') as wav:
        rate=wav.getframerate();end=wav.getnframes();start=max(0,end-12*rate)
        wav.setpos(start);data=wav.readframes(end-start)
        channels,width=wav.getnchannels(),wav.getsampwidth()
    clip=path.with_suffix('.wav')
    with wave.open(str(clip),'wb') as wav:
        wav.setnchannels(channels);wav.setsampwidth(width);wav.setframerate(rate);wav.writeframes(data)
    row=dict(id=job['id'],checkpoint='lost_sheep',reference='One sheep was lost. The shepherd was sad.',
        source_audio=str(source),source_audio_sha256=digest(source),source_start=start/rate,source_end=end/rate,
        clip_sha256=digest(clip),processing='Exact PCM crop only.',old_emitted=True,new_emitted=False,
        human_heard=None,human_should_emit=None,
        diagnosis='ASR changes lost to locked in this coached variant; acceptance of this reference phrase has not been independently confirmed.')
    write(path,row);return row


def main(output):
    protocol=verify(output,model_hash=True,audio=True)
    rows=read(output/'results.json')['cases'];jobs={j['id']:j for j in read(output/'jobs.json')}
    assert len(rows)==read(output/'completed.json')['fresh_streams']==81
    assert hashlib.sha256(cmudict.dict_string().encode('utf-8')).hexdigest()==protocol['lexicon']['data_sha256']
    fixtures=[]
    for row in rows:
        job=jobs[row['id']];events=output/'streams'/(row['id']+'.events.jsonl')
        fixtures.append(dict(id=row['id'],group=row['group'],manifest=job['manifest'],
            manifest_sha256=job['manifest_sha256'],events=str(events),events_sha256=digest(events)))
    fixture_path=output/'fresh-replay-jobs.json'
    if fixture_path.exists():assert read(fixture_path)==fixtures
    else:write(fixture_path,fixtures)
    for label,old in [('before',True),('after',False)]:
        if not (output/f'fresh-{label}.json').exists():
            cmd=[sys.executable,'-X','utf8','-u','benchmarks/replay_policy_batch.py','--jobs',str(fixture_path),
                 '--output',str(output/f'fresh-{label}.json')]
            if old:cmd+=['--snapshot',str(output/'baseline-snapshot')]
            subprocess.run(cmd,cwd=ROOT,check=True)
    paired={label:{r['id']:r['outcomes'] for r in read(output/f'fresh-{label}.json')['cases']} for label in ('before','after')}
    originals={r['id']:r['outcomes'] for r in read(PRIOR/'results.json')['cases']}
    originals.update({'phase-'+r['id']:r['outcomes'] for r in read(PHASE/'results.json')['cases']})
    saved_after={r['id']:r['outcomes'] for r in read(PRIOR/'saved-after.json')['cases']}
    originals.update({j['id']:saved_after[j['id']] for j in jobs.values() if j['group']=='synthetic_challenge'})
    listening=read(ROOT/'benchmarks/results/pause-interruption-listening-2026-11-03.json')
    labels={c['id']:c for c in listening['cases']}
    portable=[];local=[];recoveries=[];offbook=[]
    for row in rows:
        ident=row['id'];job=jobs[ident]
        assert row['outcomes']==paired['after'][ident]
        events_path=output/'streams'/(ident+'.events.jsonl')
        events=[json.loads(s) for s in events_path.read_text(encoding='utf-8').splitlines()]
        original_events=[json.loads(s) for s in Path(job['baseline_events']).read_text(encoding='utf-8').splitlines()]
        original_final=next(e for e in reversed(original_events) if e['kind']=='segments')
        original_text=' '.join(s['text'] for s in original_final['segments'])
        if row['group']=='unrelated':
            for manifest in read(output/'offbook-manifests.json'):
                ledger=replay(TimelyEvidenceMatcher,read(Path(manifest)),events)
                assert not ledger['emitted'];offbook.append(dict(id=ident,manifest=Path(manifest).name,outcomes=ledger))
        item={k:v for k,v in row.items() if k not in ('final_asr','target_before_legitimate_reading','emissions_before_child_reading')}
        item.update(original=originals[ident],old_matcher_on_new_asr=paired['before'][ident],new=paired['after'][ident],
            added_vs_original=sorted(set(row['outcomes']['emitted'])-set(originals[ident]['emitted'])),
            removed_vs_original=sorted(set(originals[ident]['emitted'])-set(row['outcomes']['emitted'])),
            asr_normalized_text_matches_original=normalize_text(row['final_asr'])==normalize_text(original_text),
            asr_timeline_matches_original=signature(events_path)==signature(Path(job['baseline_events'])))
        if row['group'] in ('controlled_synthetic_roles','synthetic_challenge'):item['final_asr']=row['final_asr']
        if ident in labels:
            assert labels[ident]['source_audio_sha256']==row['audio_sha256']
            item['user_listening_assessment']=labels[ident]
            item['target_expectation_basis']='Original frozen per-job goal; the listening label applies to its explicit reviewed_checkpoint_id, which may differ from the job target.'
        portable.append(item);local.append(dict(item,final_asr=row['final_asr']))
        if job.get('asserted_checkpoint'):
            cp=job['asserted_checkpoint'];assert cp in row['outcomes']['emitted']
            recoveries.append(dict(id=ident,checkpoint=cp,original_emitted=cp in originals[ident]['emitted'],
                old_matcher_on_new_asr=cp in paired['before'][ident]['emitted'],new_emitted=True,
                effect_callback_audio_end=next(d['audio_end'] for d in row['decisions'] if d['id']==cp)))
    assert len(offbook)==24
    write(output/'fresh-unrelated-replays.json',dict(comparisons=offbook))
    phases=[r for r in portable if r['id'].startswith('phase-')]
    mps=[r for r in portable if r['group']=='reviewed_mps']
    challenges=[r for r in portable if r['group']=='synthetic_challenge']
    negatives=[r for r in challenges if r['category'] in NEGATIVES]
    positives=[r for r in challenges if r['category'] not in NEGATIVES]
    assert all(r['target_emitted'] for r in phases)
    assert all(r['target_expectation_met'] for r in mps+challenges)
    totals=lambda values:{k:sum(len(r[k]) for r in values) for k in ('emitted','suppressed','skipped','unreached')}
    report=dict(date='2026-11-03',scope='General digital-silence resumption and interrupted-reading regression',
        implementation=dict(silence='A full existing encoder right-context of exact zero PCM completes an utterance. Surplus digital quiet keeps its original clock; later nonzero audio uses a fresh decoder. No amplitude/VAD threshold or fixed padding is added.',
            reading='Retain a unique observed leading prefix of the already-acquired next anchor. Only after its source utterance completes with an off-book run can later utterances supply a continuation. Normal scores, coverage, required words, ambiguity and independent confirmations still apply.',
            bounds='Twelve real-audio seconds and twelve supported reading updates; unrelated updates do not consume reading evidence. Revised source words, negation, ambiguity, expiry or changed checkpoint abandon it.',
            no_word_exceptions=True,same_model_and_numeric_thresholds=True),
        configuration=protocol['configuration'],model=protocol['model'],lexicon=protocol['lexicon'],
        server_environment=read(output/'server-environment.json'),
        execution=dict(fresh_streams=81,original_regression_inputs=32,synthetic_challenges=45,phase_inputs=4,
            audio_seconds=sum(r['audio_seconds'] for r in rows),saved_comparisons=246,fresh_paired_comparisons=81,
            all_delivery_eof_app_observer_replay_audits_pass=True,one_trial_per_selected_input=True,all_trials_retained=True),
        requested_recoveries=recoveries,
        user_listening_assessment=listening,
        pronunciation_review='benchmarks/results/pronunciation-acceptance-review-2026-11-03.json',
        saved_comparisons=read(output/'preflight.json'),
        saved_provider_deletion_controls=dict(cases=len(protocol['provider_deletion_controls']),all_non_emitting=True),
        fresh_phases=dict(cases=4,targets_emitted=sum(r['target_emitted'] for r in phases)),
        fresh_mps=dict(cases=9,all_nine_target_assertions_pass=True,
            natural_omission_cases=[r['id'] for r in mps if not r['expected_target_emit']],
            omission_effects=sum(r['target_emitted'] for r in mps if not r['expected_target_emit'])),
        fresh_challenges=dict(cases=45,accepted_positive_cases=len(positives),positive_emissions=sum(r['target_emitted'] for r in positives),
            negative_cases=len(negatives),negative_target_emissions=sum(r['target_emitted'] for r in negatives),
            omitted_cases=sum(r['category']=='omitted' for r in challenges),omitted_target_emissions=sum(r['target_emitted'] for r in challenges if r['category']=='omitted'),
            basis='Current shared-reading policy and the five user-reviewed close pronunciation variants; original strict-literal measurements are preserved separately.'),
        unrelated=dict(fresh_streams=4,policy_replay_comparisons=24,effects=0),
        fresh_totals=dict(original=totals(originals.values()),old_matcher_on_new_asr=totals(paired['before'].values()),new=totals(paired['after'].values())),
        changes_vs_original=[dict(id=r['id'],added=r['added_vs_original'],removed=r['removed_vs_original']) for r in portable if r['added_vs_original'] or r['removed_vs_original']],
        unreviewed_changed_effects=[unreviewed_clip(output,jobs)],
        installed_nemo_unit_test=read(output/'nemo-unit-test-reference.json'),
        unit_tests=dict(run=204,passed=203,skipped=1,skip='Existing NeMo-only test requires WSL; separate installed-NeMo decoder test is run there.'),
        preliminary_aborted_batches=[read(ROOT/'output'/name/'ABORTED.json') for name in
            ('resumption-regression-2026-11-03','resumption-regression-v2-2026-11-03')],
        development_diagnostics='Three unpaced silence-segment probes with the stock model were retained under the preliminary output, separate from final streaming counts.',
        integrity=dict(model_weights_hash_verified=True,numeric_thresholds_unchanged=True,source_manifest_audio_hashes_verified=True,
            cmudict_data_hash_verified=True,changed_runtime_files=protocol['changed_runtime_files'],
            source_sha256=protocol['source_sha256'],baseline_sha256=protocol['baseline_sha256']),
        limits=protocol['limits'],cases=portable,artifacts=output.relative_to(ROOT).as_posix())
    write(output/'local-cases.json',dict(cases=local))
    write(output/'summary.json',report);write(ROOT/'benchmarks/results/resumption-regression-2026-11-03.json',report)
    print(json.dumps({k:report[k] for k in ('execution','requested_recoveries','fresh_phases','fresh_mps','fresh_challenges','unrelated','changes_vs_original')},indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,default=DEST)
    main(p.parse_args().output.resolve())
