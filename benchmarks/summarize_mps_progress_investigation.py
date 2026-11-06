"""Report recognition/progress diagnostics without changing the frozen tracker."""
import argparse
from collections import Counter
from copy import deepcopy
import html
import json
import math
from pathlib import Path
import re
import sys
import wave

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from benchmarks.investigate_mps_progress import (DEST, FROZEN, read, write, digest, verify,
    TimelyEvidenceMatcher, EffectPermission, ordered_support, normalize_text, provider_anchor_evidence)
from books_to_life.matching.alignment_matcher import align_words
from books_to_life.matching.phonetic_endpoint import phonetic_endpoint_match


def ledger(matcher, events):
    result = dict(emitted=[], suppressed=[], skipped=[])
    updates = []
    for e in events:
        if e['kind'] != 'segments':
            continue
        seg = e['segments']
        u = matcher.process(' '.join(s['text'] for s in seg), seg)
        if u.triggered:
            result['emitted'].append(u.checkpoint_id)
        if u.effect_suppressed:
            result['suppressed'].append(u.checkpoint_id)
        result['suppressed'].extend(u.additional_suppressed_checkpoint_ids)
        result['skipped'].extend(u.skipped_checkpoint_ids)
        updates.append(dict(audio_end=seg[-1]['end'], position=matcher.tracked_word_position,
            checkpoint=u.checkpoint_id, triggered=u.triggered, confirmations=u.confirmations))
    result['skipped'] = sorted(set(result['skipped']))
    result['unreached'] = sorted({c['id'] for c in matcher.checkpoints} - set(result['emitted'])
        - set(result['suppressed']) - set(result['skipped']))
    return dict(outcomes=result, updates=updates)


def user_text_probe(output, jobs):
    review = read(ROOT / 'benchmarks/results/mps-listening-review-2026-11-06.json')
    item = next(c for c in review['cases'] if c['checkpoint'] == 'lost_sheep')
    job = next(j for j in jobs if j['id'] == item['recording'])
    cfg = read(job['manifest']); cp = next(c for c in cfg['checkpoints'] if c['id'] == item['checkpoint'])
    events = [json.loads(s) for s in Path(job['events']).read_text(encoding='utf-8').splitlines()]
    final = next(e for e in reversed(events) if e['kind'] == 'segments')['segments']
    assert len(final) == 1
    actual = normalize_text(final[0]['text']).split()
    reference = normalize_text(cp['checkpoint_text']).split()
    heard = normalize_text(item['human_heard']).split()
    assert len(reference) == len(heard)
    prefix = actual[:-len(heard)]; substitutions = []
    counterfactual = deepcopy(events)
    for e in counterfactual:
        if e['kind'] != 'segments' or len(e['segments']) != 1:
            continue
        s = e['segments'][0]; words = normalize_text(s['text']).split()
        count = len(words) - len(prefix)
        if words[:len(prefix)] == prefix and 0 < count <= len(heard):
            replacement = prefix + heard[:count]
            if replacement != words:
                substitutions.append(dict(audio_end=s['end'], observed_tail=words[len(prefix):],
                    oracle_tail=heard[:count]))
                s['text'] = ' '.join(replacement)
    normal = ledger(TimelyEvidenceMatcher(cfg), events)
    oracle = ledger(TimelyEvidenceMatcher(cfg), counterfactual)
    guard = EffectPermission(cp, cfg['min_coverage'], [])
    tail = actual[-len(reference):]
    endpoint_only = tail[:-1] + reference[-1:]
    result = dict(kind='Counterfactual recognized-text replay only; no ASR inference, audio edit, timing gold, or accuracy trial.',
        id=job['id'], checkpoint=cp['id'], human_transcription=item['human_heard'],
        input_events_sha256=digest(job['events']),
        substitution_rule='Only hypotheses sharing the final ASR prefix receive the equal-length prefix of the user transcription. Existing callback/segment times and all earlier recognition remain unchanged.',
        changed_hypotheses=substitutions, original=normal, oracle_recognition=oracle,
        permission=dict(required_support=math.ceil(len(reference) * guard.coverage),
            actual_spelling_support=len(ordered_support(reference, tail)),
            user_spelling_support=len(ordered_support(reference, heard)),
            actual_with_all_existing_local_aids=guard.permits(tail, allow_phonetic_endpoint=True,
                allow_word_boundaries=True, allow_phonetic_internal=True)[0],
            user_ordinary_permission=guard.permits(heard)[0],
            endpoint_restored_only_with_existing_local_aids=guard.permits(endpoint_only,
                allow_phonetic_endpoint=True, allow_word_boundaries=True, allow_phonetic_internal=True)[0]),
        standalone_alignment=dict(minimum_words=5,
            actual_anchor_candidate_count=len(align_words(tail, reference, cp['word_start'], 5, cfg['min_coverage'])),
            endpoint_restored_candidate_count=len(align_words(endpoint_only, reference, cp['word_start'], 5, cfg['min_coverage'])),
            first_sentence_word_count=len(normalize_text(re.split(r'[.!?]', cp['checkpoint_text'])[0]).split()),
            first_sentence_candidate_count=len(align_words(normalize_text(re.split(r'[.!?]', cp['checkpoint_text'])[0]).split(), reference,
                cp['word_start'], 5, cfg['min_coverage']))),
        caution='The user transcription is oracle evidence for diagnosis. This does not establish that unchanged ASR can produce it reliably.')
    assert normal['outcomes'] == job['expected']
    write(output / 'user-text-probe.json', result)
    return result


def summarize(output):
    protocol = verify(output, audio=True)
    assert read(output / 'completed.json')['fresh_streams'] == 7
    saved = read(output / 'saved-results.json')['cases']
    fresh = read(output / 'fresh-results.json')['cases']
    jobs = read(output / 'jobs.json'); indexed = {j['id']: j for j in jobs}
    metadata = {r['audioID']: r for r in read(ROOT / 'output/listening-review-2026-11-02/source/data.json')}
    assert len(saved) == 147 and len(fresh) == 7
    assert all(r['outcomes'] == r['previous_outcomes'] for r in fresh)
    rows = []; focus = []; deletion_controls = []
    for row in saved:
        cfg = read(indexed[row['id']]['manifest'])
        points = []
        for cp, point in zip(cfg['checkpoints'], row['checkpoints']):
            evidence = provider_anchor_evidence(metadata[row['id']], cp['word_start'], cp['word_end'])
            words = evidence.get('words', [])
            endpoint_deleted = bool(words and words[-1]['label'].lower() == 'd')
            essential_deleted = any(w['prompt'] in cp.get('required_words', []) and w['label'].lower() == 'd' for w in words)
            point = dict(point, provider_counts={k: evidence.get(k) for k in ('correct', 'substitutions', 'deletions')},
                provider_endpoint_or_required_deleted=endpoint_deleted or essential_deleted)
            points.append(point)
            if endpoint_deleted or essential_deleted:
                deletion_controls.append(dict(id=row['id'], checkpoint=cp['id'], outcome=point['outcome']))
            if cp['id'] == 'lost_sheep':
                first_length = point['first_clause_words']
                focus.append(dict(**{k: v for k, v in point.items() if k != 'id'},
                    id=row['id'], checkpoint=point['id'], group=row['group'],
                    provider_first_clause_all_correct=bool(words and all(w['label'].lower() == 'c' for w in words[:first_length])),
                    provider_following_clause_deletions=sum(w['label'].lower() == 'd' for w in words[first_length:]),
                    final_position=row['final_position']))
        rows.append(dict(id=row['id'], group=row['group'], outcomes=row['outcomes'], checkpoints=points))
    assert len(focus) == 24
    probe = user_text_probe(output, jobs)
    write(output / 'provider-enriched-results.json', rows)
    nonemitting = [r for r in focus if r['outcome'] != 'emitted']
    trace = read(ROOT / next(r['trace'] for r in saved if r['id'] == probe['id']))
    # Retain every callback near the final anchor, including rejected updates.
    target_cfg = read(indexed[probe['id']]['manifest'])
    target_cp = next(c for c in target_cfg['checkpoints'] if c['id'] == 'lost_sheep')
    target_trace = [r for r in trace if r['before']['position'] >= target_cp['word_start'] - 2
        and r['audio_end'] >= indexed[probe['id']]['audio_seconds'] - 5]
    write(output / 'reported-case-final-callbacks.json', target_trace)
    report = dict(date='2026-11-06', scope='Unchanged ASR/matcher investigation of lost-sheep recognition and progress across similar MPS cases',
        execution=dict(saved_recordings=147, saved_speakers=len({r['id'].split('_')[0] for r in saved}),
            saved_checkpoints=sum(len(r['checkpoints']) for r in saved), focus_readings=24,
            saved_callbacks=sum(r['callbacks'] for r in saved),
            fresh_diagnostic_streams=7, fresh_audio_seconds=sum(r['audio_seconds'] for r in fresh),
            fresh_callbacks=sum(r['callbacks'] for r in fresh),
            all_fresh_checkpoint_outcomes_match_saved=True,
            new_holdout_accuracy_claim=False, every_instrumented_update_agrees_with_vanilla=True),
        integrity=dict(runtime_model_lexicon_thresholds_hints_manifests_and_original_audio_unchanged=True,
            saved_original_ledgers_reproduced=147, all_fresh_delivery_eof_pacing_app_replay_audits_pass=True,
            protocol_sha256=digest(output / 'protocol.json'), diagnostic_helper_sha256=protocol['diagnostic_helper_sha256'],
            frozen_sources=protocol['frozen_sources']),
        saved_all_checkpoint_stages=dict(Counter(p['observed_stage'] for r in rows for p in r['checkpoints'])),
        saved_focus=dict(outcomes=dict(Counter(r['outcome'] for r in focus)),
            nonemission_stages=dict(Counter(r['observed_stage'] for r in nonemitting)),
            nonemitting_with_exact_first_clause=sum(r['exact_first_clause_observed'] for r in nonemitting),
            nonemitting_with_provider_correct_first_clause=sum(r['provider_first_clause_all_correct'] for r in nonemitting),
            nonemitting_with_ordinary_permission=sum(r['ever_permission_ordinary'] for r in nonemitting),
            nonemitting_with_local_aided_permission=sum(r['ever_permission_with_local_aids'] for r in nonemitting),
            rows=focus),
        fresh_comparisons=[dict(id=r['id'], previous_outcomes=r['previous_outcomes'], outcomes=r['outcomes'],
            asr_callback_sequence_identical=r['asr_callback_sequence_identical'],
            target=next(c for c in r['checkpoints'] if c['id'] == 'lost_sheep'),
            all_streaming_audits_pass=r['all_streaming_audits_pass']) for r in fresh],
        omission_controls=dict(kind='Provider-deleted endpoint/essential words in the 147 saved callback replays; not new human listening verdicts.',
            configured=len(deletion_controls), emitted=sum(r['outcome'] == 'emitted' for r in deletion_controls), cases=deletion_controls),
        reported_case=dict(id=probe['id'], reference_start=target_cp['word_start'], reference_end=target_cp['word_end'],
            final_position=next(r['final_position'] for r in saved if r['id'] == probe['id']),
            ordinary_required_support=probe['permission']['required_support'],
            actual_spelling_support=probe['permission']['actual_spelling_support'],
            user_spelling_support=probe['permission']['user_spelling_support'],
            oracle_text_replay_target_emitted='lost_sheep' in probe['oracle_recognition']['outcomes']['emitted'],
            oracle_is_not_audio_accuracy=True),
        findings=[
            'The reported reading never acquires the final anchor. Damaged ASR leaves only six spelling-supported words where seven are required; the standalone final phrase produces no ordinary alignment candidate.',
            'The user transcription supplies seven supported words and passes ordinary effect permission. A separate oracle-text replay tests the actual prior progress/confirmation state without changing production behavior.',
            'The current internal pronunciation aid is permission-only, requires local acquisition and an exact endpoint. It cannot bootstrap acquisition or combine arbitrary uncertain words.',
            'The four-word first sentence cannot independently meet the five-word alignment minimum; usable book context is required. The checkpoint also demands support for the following sentence.',
            'Historical non-emissions span score filtering, candidate selection and confirmation. Many would still fail permission even if progress alone were forced.',
            'Some comparable missing words are actual provider-annotated omissions. Preserve them as controls rather than assuming all incomplete ASR is a decoder failure.',
        ],
        limitations=['Historical saved ASR spans earlier streaming implementations; report it separately from seven unchanged-current-stack reruns.',
            'Most similar recordings have no new independent listening verdict. Provider labels do not prove what was acoustically spoken.',
            'These are inspected diagnostic/regression cases, not new-speaker holdout accuracy or microphone/room testing.',
            'No ASR, matcher, phonetic rule, threshold, checkpoint definition or audio fix is implemented.'],
        next_options=[
            'Review additional representative misses before declaring them required positives.',
            'For future checkpoint authoring, distinguish the event-bearing cue from following descriptive text and explicitly declare essential words; reconcile any changed authoring policy with existing omission controls.',
            'Investigate a general contextual acquisition path that can reuse already-existing pronunciation evidence without weakening unrelated/cold-start matches. It must pass the same word-presence and omission controls.',
            'Evaluate recognition robustness on varied phrases if acceptable spoken words are repeatedly transcribed incorrectly; do not add sample-specific transcript replacements.',
        ], local_artifacts=output.relative_to(ROOT).as_posix())
    write(output / 'summary.json', report)
    write(ROOT / 'benchmarks/results/mps-progress-investigation-2026-11-06.json', report)
    review = output / 'review'; review.mkdir(exist_ok=True)
    cards = []
    # Fixed diagnostic cases: clips are exact PCM and labels remain unassigned.
    for n, job in enumerate(read(output / 'reruns.json'), 1):
        original = Path(job['audio']); clip = review / (f'{n:02d}_' + job['id'] + '.wav')
        with wave.open(str(original)) as src:
            rate = src.getframerate(); begin = max(0, src.getnframes() - 18 * rate)
            frames = src.getnframes() - begin; src.setpos(begin); data = src.readframes(frames)
            with wave.open(str(clip), 'wb') as dst:
                dst.setparams(src.getparams()); dst.writeframes(data)
        esc = lambda text: html.escape(str(text))
        cards.append(f'<article><h2>{n}. {esc(job["id"])}</h2><p>One sheep was lost. The shepherd was sad.</p>'
            f'<audio controls preload="none" src="{esc(clip.name)}"></audio>'
            f'<p>Original audio from {begin/rate:.2f}s to the end. Exact PCM crop, without gain or filtering. '
            f'<a href="{esc(os_path(original, review))}">Full original recording</a>.</p>'
            '<p>Record what you hear and whether the effect should count; listening labels remain unassigned.</p>'
            f'<details><summary>Diagnostic reason — open after listening</summary><p>{esc(job["selection_reason"])}</p></details></article>')
    (review / 'index.html').write_text('<!doctype html><html lang="en"><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1"><title>MPS progress diagnosis</title>'
        '<style>body{max-width:850px;margin:32px auto;padding:0 20px;font:17px/1.6 system-ui}article{border-top:1px solid #bbb;padding:18px 0}audio{width:100%}</style>'
        '<h1>MPS progress diagnosis</h1><p>Seven outcome-informed diagnostic comparisons; no new holdout claim. '
        'The phrase can span two sentences. An omitted sentence and a recognition error need separate judgments.</p>'
        + ''.join(cards) + '</html>', encoding='utf-8')
    print(json.dumps(dict(execution=report['execution'], saved_focus={k:v for k,v in report['saved_focus'].items() if k!='rows'},
        reported_case=report['reported_case'], omission_controls=report['omission_controls']), indent=2), flush=True)


def os_path(path, relative_to):
    import os
    return Path(os.path.relpath(path, relative_to)).as_posix()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=DEST)
    args = parser.parse_args(); summarize(args.output.resolve())
