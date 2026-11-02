"""Report the frozen held-out-speaker sweep; provider labels are review evidence."""
import argparse
import csv
import hashlib
import html
import json
from pathlib import Path
import sys
import wave

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from benchmarks.run_mps_heldout import (ROOT, DEFAULT_OUTPUT, DEFAULT_METADATA, read, write, check_frozen,
    old_tracker, digest, TimelyEvidenceMatcher)


def totals(rows, label):
    return {status: sum(len(r[label][status]) for r in rows)
            for status in ('emitted', 'suppressed', 'skipped', 'unreached')}


def negative_replay(output, jobs, controls):
    unique = {}
    for job in jobs:
        manifest = read(Path(job['manifest']))
        key = tuple(p['text'] for p in manifest['pages'])
        unique.setdefault(key, job)
    Old = old_tracker(output)
    results = []
    for name in ('dog', 'dragon', 'nickel', 'recording_2'):
        path = controls / (name + '.events.jsonl')
        if not path.is_file():
            return dict(available=False, reason='Prior unrelated ASR timelines are absent.')
        segments = [event['segments'] for line in path.read_text(encoding='utf-8').splitlines()
                    if (event := json.loads(line))['kind']=='segments']
        for job in unique.values():
            row = dict(control=name, passage_representative=job['id'])
            for label, Tracker in [('before', Old), ('after', TimelyEvidenceMatcher)]:
                matcher = Tracker(read(Path(job['manifest'])))
                emitted, suppressed = [], []
                for seg in segments:
                    update = matcher.process(' '.join(s['text'] for s in seg), seg)
                    suppressed.extend(getattr(update, 'additional_suppressed_checkpoint_ids', ()))
                    if update.triggered: emitted.append(update.checkpoint_id)
                    if update.effect_suppressed: suppressed.append(update.checkpoint_id)
                row[label] = dict(emitted=emitted, suppressed=suppressed)
            results.append(row)
    return dict(available=True,
        kind='Saved ASR callbacks from four existing fresh unrelated-speech streams, replayed against six frozen passage manifests; not additional fresh audio trials.',
        source_streams=4, passage_policies=len(unique), comparisons=len(results),
        before_emitted=sum(len(r['before']['emitted']) for r in results),
        after_emitted=sum(len(r['after']['emitted']) for r in results), results=results)


def split_anchor_evidence(output, jobs, rows):
    """Record exact split support without claiming the permission route used it."""
    results = []
    indexed = {r['recording']:r for r in rows}
    for job in jobs:
        matcher = TimelyEvidenceMatcher(read(Path(job['manifest'])))
        decisions = read(output/'streams'/(job['id']+'.decisions.json'))['after']
        for decision in decisions:
            permission = matcher._effect_permissions[decision['checkpoint']]
            if (decision['emitted'] and hasattr(permission, 'supports_split_anchor')
                    and permission.supports_split_anchor(decision['buffer'])):
                results.append(dict(recording=job['id'], checkpoint=decision['checkpoint'],
                    before_emitted=decision['checkpoint'] in indexed[job['id']]['before']['emitted']))
    return dict(kind='Complete exact split-anchor support in emitted decision buffers; diagnostic evidence, not an instrumented permission-route trace.',
        emitted_checkpoints=len(results), results=results)


def pending_effect_evidence(output, rows):
    results=[]
    for row in rows:
        path=output/'streams'/(row['recording']+'.events.jsonl')
        events=[json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]
        pending={e['scene'] for e in events if e['kind']=='pending_effect' and e['mode']=='timely'}
        if pending:
            results.append(dict(recording=row['recording'],pending=sorted(pending),
                emitted=sorted(pending&set(row['after']['emitted'])),
                suppressed=sorted(pending&set(row['after']['suppressed']))))
    return dict(kind='Observed pending lifecycle events in the fresh app streams',
        pending_checkpoints=sum(len(r['pending']) for r in results),
        emitted=sum(len(r['emitted']) for r in results),
        suppressed=sum(len(r['suppressed']) for r in results),results=results)


def summarize(output, controls, metadata, reference_protocol=None):
    completed = read(output / 'completed.json')
    assert completed['streams']==24 and completed['source_unchanged']
    protocol = check_frozen(output, model_hash=True)
    identical_baseline = all(checksum==protocol['source_sha256']['books_to_life/matching/'+name]
                             for name,checksum in protocol['baseline_sha256'].items())
    rows = read(output / 'results.json')['recordings']
    jobs = read(output / 'downloaded-jobs.json')
    assert digest(metadata) == protocol['metadata_sha256']
    canonical = {r['audioID']:r for r in read(metadata)}
    selected = read(output / 'selected.json')
    assert [r['audioID'] for r in selected] == protocol['ordered_recordings']
    assert all(canonical[r['audioID']] == r for r in selected)
    prior_path = reference_protocol or ROOT/'output/listening-review-2026-11-02/regression/local-sweep/protocol.json'
    matches_previous = None
    if prior_path.is_file():
        prior = read(prior_path)
        previous = prior['source_sha256'] if 'source_sha256' in prior else prior['sources']
        runtime = {k:v for k,v in protocol['source_sha256'].items() if k.startswith('books_to_life/')}
        assert all(previous.get(k)==v for k,v in runtime.items())
        matches_previous = True
    assert len(rows)==24 and len({r['speaker'] for r in rows})==12
    assert len({r['audio_sha256'] for r in rows})==24
    assert {r['speaker'] for r in rows}.isdisjoint(protocol['excluded_speakers'])
    assert [r['recording'] for r in rows] == protocol['ordered_recordings']
    assert all(r['delivery_audit_pass'] and r['app_observer_agreement'] for r in rows)
    for job in jobs:
        assert digest(Path(job['audio'])) == job['audio_sha256']
    points = [(r, cp) for r in rows for cp in r['checkpoints']]
    human_path = output/'review/human_reviews.json'
    human = read(human_path).get('cases', {}) if human_path.is_file() else {}
    portable_human = [{k:v for k,v in item.items() if k not in ('human_heard','user_comment')}
                      for item in human.values()]
    provider_correct = [(r, cp) for r, cp in points if cp['provider_evidence'].get('words')
        and cp['provider_evidence'].get('substitutions')==0 and cp['provider_evidence'].get('deletions')==0]
    deleted = [(r, cp) for r, cp in points if cp['provider_endpoint_deleted'] or cp['provider_required_word_deleted']]
    suspects = [(r, cp) for r, cp in deleted if cp['emitted']]
    nonemit_correct = [(r, cp) for r, cp in provider_correct if not cp['emitted']]
    portable_rows = []
    for row in rows:
        portable = {k:v for k,v in row.items() if k!='checkpoints'}
        portable['checkpoints'] = []
        for cp in row['checkpoints']:
            evidence = cp['provider_evidence']
            portable['checkpoints'].append({k:v for k,v in cp.items() if k!='provider_evidence'} | {
                'provider_annotation_status':evidence['status'],
                'provider_counts':{k:evidence.get(k) for k in ('correct','substitutions','deletions')}})
        portable_rows.append(portable)
    grouped = {}
    for grade in ('3','4','5'):
        group = [r for r in rows if r['grade']==grade]
        grouped[grade] = dict(recordings=len(group), speakers=len({r['speaker'] for r in group}),
            configured=sum(r['configured'] for r in group), before=totals(group,'before'), after=totals(group,'after'))
    report = dict(date='2026-11-02', scope='Untuned speaker-disjoint MPS streaming evaluation',
        selection=dict(seed=protocol['seed'], provider_revision=protocol['provider_revision'],
            metadata_sha256=protocol['metadata_sha256'], speakers=protocol['speakers'],
            excluded_speakers=protocol['excluded_speakers'], strata=protocol['strata'],
            ordered_recordings=protocol['ordered_recordings'], rule=protocol['selection_rule'],
            frozen_before_audio_download=True, speaker_overlap=0),
        configuration=protocol['configuration'], model=protocol['model'], lexicon=protocol['lexicon'],
        server_environment=json.loads((output/'server-environment.json').read_text(encoding='utf-8-sig')),
        execution=dict(fresh_reading_streams=24, speakers=12, passage_texts=6, configured=72,
            audio_seconds=sum(r['audio_seconds'] for r in rows), runs_per_recording=1,
            warmup=protocol['warmup'], all_selected_trials_retained=True,
            all_samples_delivered=True, all_partial_before_eof=True, all_stream_done=True,
            unique_audio_files=24,
            all_app_observer_agreement=True, comparison_guard_is_paired_callback_replay=True,
            comparison_matcher_identical=identical_baseline,
            pre_audio_transport_failures=[read(path) for path in sorted((output/'startup-failures').glob('*.json'))]),
        integrity=dict(matcher_sources_unchanged=True, recognizer_sources_unchanged=True,
            checkpoint_manifests_unchanged=True, model_hash_unchanged=True, lexicon_unchanged=True,
            provider_metadata_hash_verified=True, selected_rows_match_original_provider=True,
            runtime_sources_match_reference_sweep=matches_previous,
            reference_protocol=prior_path.relative_to(ROOT).as_posix() if prior_path.is_relative_to(ROOT) else str(prior_path),
            no_sample_replacements=True, no_matcher_or_hint_tuning=True,
            source_sha256=protocol['source_sha256'],baseline_sha256=protocol['baseline_sha256']),
        totals=dict(before=totals(rows,'before'),after=totals(rows,'after')), by_grade=grouped,
        added_emissions=[dict(recording=r['recording'],checkpoints=r['added_emissions']) for r in rows if r['added_emissions']],
        removed_emissions=[dict(recording=r['recording'],checkpoints=r['removed_emissions']) for r in rows if r['removed_emissions']],
        phonetic_fallback=dict(kind='Instrumented helper calls, including exact/ordinary matches and repeated candidate/permission checks; not a count of effects that required phonetic fallback.',
            comparisons=sum(len(r['phonetic_calls']) for r in rows),
            matched_comparisons=sum(c['matched'] for r in rows for c in r['phonetic_calls']),
            recordings=[r['recording'] for r in rows if any(c['matched'] for c in r['phonetic_calls'])]),
        split_anchor_evidence=split_anchor_evidence(output,jobs,rows),
        pending_effect_evidence=pending_effect_evidence(output,rows),
        provider_annotation_review=dict(provider_correct_anchors=len(provider_correct),
            emitted_provider_correct=sum(cp['emitted'] for r,cp in provider_correct),
            provider_deleted_endpoints_or_essential_words=len(deleted),
            emissions_on_provider_deleted_endpoints_or_essential_words=[dict(recording=r['recording'],checkpoint=cp['id']) for r,cp in suspects],
            non_emissions_on_provider_correct_anchors=[dict(recording=r['recording'],checkpoint=cp['id']) for r,cp in nonemit_correct],
            human_listening_performed=bool(human), human_reviewed_checkpoints=len(human),
            complete_human_signoff=False,
            note='Provider annotations flag review candidates. Substitutions may be acceptable pronunciation attempts; these counts are not an effect-accuracy or latency score.'),
        post_evaluation_human_review=dict(cases=portable_human,
            confirmed_false_negatives=sum(r.get('classification')=='confirmed_false_negative' for r in human.values()),
            original_stream_results_unchanged=True, matcher_tuned_after_review=False,
            scope='Only listed cases have user listening confirmation. Phrase-location marks are not verified word endpoints.'),
        unrelated_speech_replay=negative_replay(output,jobs,controls), recordings=portable_rows,
        limits=['Held-out speaker IDs on the same six familiar Indian MPS paragraph texts; not held-out books or Singapore-accent validation.',
            ('Single fresh stream per recording. Both replay ledgers use the identical frozen matcher and ASR callbacks; their agreement is an audit, not an improvement comparison.'
             if identical_baseline else 'Single fresh stream per selected recording. Old/new guards share identical ASR callbacks; only current guard ran through the live app.'),
            'Human listening applies only to explicitly attached post-evaluation reviews; no exact word-end timestamps are verified.',
            'Effects emitted/withheld/unreached/skipped are operational outcomes, not pronunciation or checkpoint precision/recall.',
            'Raw recordings, provider transcripts and review clips remain local under ignored output/.'],
        artifacts=output.relative_to(ROOT).as_posix()+': preselection protocol, frozen source/manifests, original WAVs, packet/callback logs, SRTs, per-case decisions and blank listening review.')
    write(output/'summary.json', report)
    write(ROOT/'benchmarks/results'/(output.name+'.json'), report)
    return report


def listening_review(output, report, *, title='Held-out MPS listening review',
                     introduction='The batch was selected before audio download and evaluated with a frozen matcher.'):
    """Create context clips and blank labels; do not infer human decisions."""
    review = output / 'review'
    review.mkdir(exist_ok=True)
    originals = {r['recording']:r for r in read(output/'results.json')['recordings']}
    jobs = {j['id']:j for j in read(output/'downloaded-jobs.json')}
    human_path = review/'human_reviews.json'
    human = read(human_path).get('cases', {}) if human_path.is_file() else {}
    queue = []
    for row in report['recordings']:
        for cp in row['checkpoints']:
            needs_review = cp['review_flags'] or not cp['emitted'] or cp['id'] in row['added_emissions']
            if not needs_review:
                continue
            if cp['emitted'] and (cp['provider_endpoint_deleted'] or cp['provider_required_word_deleted']): priority=0
            elif cp['id'] in row['added_emissions']: priority=1
            elif not cp['emitted'] and cp['provider_counts'].get('substitutions')==0 and cp['provider_counts'].get('deletions')==0: priority=2
            elif not cp['emitted']: priority=3
            else: priority=4
            queue.append((priority,row,cp))
    queue.sort(key=lambda item:(item[0],item[1]['recording'],item[2]['id']))
    cards, sheet = [], []
    for number,(priority,row,cp) in enumerate(queue,1):
        job = jobs[row['recording']]
        decisions = read(output/'streams'/(row['recording']+'.decisions.json'))['after']
        focus = next((d for d in decisions if d['checkpoint']==cp['id']),None)
        if focus:
            start=max(0,focus['audio_end']-14);end=min(job['audio_seconds'],focus['audio_end']+3)
            basis='Decision-centred context, not a verified word alignment.'
        else:
            start,end=0,job['audio_seconds'];basis='Full recording because this checkpoint was unreached/skipped.'
        clip=review/f'{number:02d}_{row["recording"]}.{cp["id"]}.wav'
        with wave.open(job['audio']) as src,wave.open(str(clip),'wb') as dst:
            dst.setparams(src.getparams());src.setpos(round(start*16000));dst.writeframes(src.readframes(round((end-start)*16000)))
        with wave.open(str(clip)) as check: assert check.getnframes()>0
        manifest=read(Path(job['manifest']))
        anchor=next(c['checkpoint_text'] for c in manifest['checkpoints'] if c['id']==cp['id'])
        state='emitted' if cp['emitted'] else 'suppressed' if cp['suppressed'] else 'unreached/skipped'
        heard = human.get(row['recording']+'/'+cp['id'], {})
        sheet.append(dict(number=number,recording=row['recording'],speaker=row['speaker'],grade=row['grade'],
            checkpoint=cp['id'],automated_status=state,clip=clip.name,clip_start_seconds=start,
            human_heard=heard.get('human_heard',''),human_should_emit=heard.get('human_should_emit',''),
            human_word_end_seconds_original=heard.get('human_word_end_seconds_original') or '',
            reviewer=heard.get('reviewer',''),date=heard.get('date',''),notes=heard.get('diagnosis','')))
        esc=lambda value:html.escape(str(value))
        text=' '.join(focus['buffer']) if focus else '(No effect decision reached.)'
        note = ('<p><b>Recorded user review:</b> '+esc(heard['classification'])+'. Heard: '+
            esc(heard['human_heard'])+'. '+esc(heard['user_comment'])+'. '+esc(heard['time_meaning'])+
            ' Matcher remains unchanged.</p>') if heard else ''
        cards.append(f'<article><h2>{number}. {esc(row["recording"])} / {esc(cp["id"])}</h2>'
            f'<p><b>{esc(anchor)}</b></p><audio controls preload="none" src="{esc(clip.name)}"></audio>'
            f'<p>Original window {start:.2f}–{end:.2f}s. {esc(basis)} '
            f'<a href="../inputs/{esc(row["recording"])}/audio.wav">Full recording</a></p>'
            +note+
            '<p>Write what you heard, whether the effect should fire, and any uncertainty in the CSV.</p>'
            f'<details><summary>Automated decision and provider evidence — inspect after listening</summary>'
            f'<p>Status: {esc(state)}. Flags: {esc("; ".join(cp["review_flags"]))}</p>'
            f'<p>Provider counts: {esc(cp["provider_counts"])}. These are not word timings or a human effect-policy decision.</p>'
            f'<p>Recent recognition at the decision: {esc(text)}</p></details></article>')
    path=review/'manual_review.csv'
    if sheet and not path.exists():
        with path.open('w',encoding='utf-8',newline='') as handle:
            writer=csv.DictWriter(handle,fieldnames=list(sheet[0]));writer.writeheader();writer.writerows(sheet)
    (review/'index.html').write_text('<!doctype html><html lang="en"><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<title>{html.escape(title)}</title>'
        '<style>body{max-width:950px;margin:36px auto;padding:0 22px;font:17px/1.6 system-ui;color:#203040}article{border-top:2px solid #ccd5df;padding:22px 0}audio{width:100%}summary{cursor:pointer}a{color:#17638a}</style>'
        f'<h1>{html.escape(title)}</h1><p>{len(sheet)} flagged checkpoints; {len(human)} with recorded user listening notes.</p>'
        '<p>'+html.escape(introduction)+' '
        'Unreviewed human fields remain blank. Provider miscues and automated triggers do not determine the human answer. '
        '<a href="manual_review.csv">Open the review CSV</a>.</p>' + ''.join(cards)+'</html>',encoding='utf-8')
    return len(sheet)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=DEFAULT_OUTPUT)
    parser.add_argument('--metadata',type=Path,default=DEFAULT_METADATA)
    parser.add_argument('--controls',type=Path,default=ROOT/'output/listening-review-2026-11-02/regression/phonetic-controls')
    parser.add_argument('--reference-protocol',type=Path,
        help='Earlier completed regression whose runtime source hashes must match this batch.')
    args=parser.parse_args()
    report=summarize(args.output.resolve(),args.controls.resolve(),args.metadata.resolve(),
        args.reference_protocol.resolve() if args.reference_protocol else None)
    review_count=listening_review(args.output.resolve(),report)
    print(json.dumps({k:report[k] for k in ('execution','totals','by_grade','added_emissions','removed_emissions','phonetic_fallback','provider_annotation_review')},indent=2))
    print('Listening-review rows:',review_count)


if __name__=='__main__':
    main()
