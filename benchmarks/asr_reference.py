"""Validated reference approvals and post-run ASR scoring, without a tracker."""
from bisect import bisect_right
from hashlib import sha256
import json
import math
from pathlib import Path
import statistics

from benchmarks.metrics import edit_alignment, words


def digest(annotation, timing=False):
    fields = ('id', 'text', 'start', 'end') if timing else ('id', 'text')
    payload = {'audio_sha256': annotation['audio_sha256'], 'scope': annotation['scope'],
               'words': [{k: row[k] for k in fields} for row in annotation['words']]}
    if timing:
        payload['uncertainty_seconds'] = annotation.get('review', {}).get('timing_uncertainty_seconds')
    return sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def validate(annotation, strict_text=False, strict_timing=False):
    rows = annotation['words']
    if not rows or len(rows) > 5000:
        raise ValueError('Use 1–5000 word rows.')
    previous = -1
    ids = set()
    for row in rows:
        if not isinstance(row.get('id'), str) or row['id'] in ids:
            raise ValueError('Word IDs must be unique strings.')
        ids.add(row['id'])
        text = row.get('text')
        if not isinstance(text, str) or not text.strip() or len(text) > 100:
            raise ValueError('Each word needs a short nonempty text value.')
        for key in ('start', 'end'):
            value = row.get(key)
            if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value):
                raise ValueError('Word times must be finite numbers.')
        if not 0 <= row['start'] <= row['end'] <= annotation['duration_seconds'] + .0001:
            raise ValueError('Word times must stay inside the recording.')
        if row['start'] < previous:
            raise ValueError('Order rows by word start time.')
        previous = row['start']
        if strict_text:
            if not words(text) or '[' in text or ']' in text:
                raise ValueError('Unresolved/unclear words cannot establish full-recording WER.')
            if len(text.split()) != 1:
                raise ValueError('Use one spoken word per row; put non-speech labels in notes.')
            if row.get('text_reviewed') is not True:
                raise ValueError('Review every word and check for omitted speech before approving text.')
        if strict_timing and (row.get('timing_reviewed') is not True or row['end'] <= row['start']):
            raise ValueError('Review every start/end boundary; zero-duration words are not verified.')


def approval_status(annotation):
    review = annotation.get('review', {})
    status = {'text_verified': False, 'timing_verified': False}
    try:
        validate(annotation, strict_text=True)
        approval = review.get('text_approval', {})
        status['text_verified'] = bool(approval.get('reviewer') and approval.get('at')
                                       and review.get('all_speech_checked') is True
                                       and approval.get('digest') == digest(annotation))
        uncertainty = review.get('timing_uncertainty_seconds')
        if not status['text_verified'] or isinstance(uncertainty, bool) or not isinstance(uncertainty, (float, int)):
            return status
        validate(annotation, strict_text=True, strict_timing=True)
        approval = review.get('timing_approval', {})
        status['timing_verified'] = bool(math.isfinite(uncertainty) and 0 < uncertainty <= 1
                                         and approval.get('reviewer') and approval.get('at')
                                         and approval.get('digest') == digest(annotation, timing=True))
    except (KeyError, TypeError, ValueError):
        pass
    return status


def unambiguous_matches(reference, hypothesis):
    """Only exact pairs shared by every minimum-edit global alignment.

    This is offline evaluation, with no book progress or cue permission state.
    Repeated-word ambiguity is retained instead of arbitrarily picking a match.
    """
    nr, nh = len(reference), len(hypothesis)
    dp = [[0] * (nh + 1) for _ in range(nr + 1)]
    for i in range(nr + 1):
        dp[i][0] = i
    for j in range(nh + 1):
        dp[0][j] = j
    for i in range(1, nr + 1):
        for j in range(1, nh + 1):
            dp[i][j] = min(dp[i-1][j] + 1, dp[i][j-1] + 1,
                           dp[i-1][j-1] + (reference[i-1] != hypothesis[j-1]))
    pending, seen, candidates, possibly_unmatched = [(nr, nh)], set(), {}, set()
    while pending:
        i, j = pending.pop()
        if (i, j) in seen:
            continue
        seen.add((i, j))
        if i and dp[i][j] == dp[i-1][j] + 1:
            possibly_unmatched.add(i-1)
            pending.append((i-1, j))
        if j and dp[i][j] == dp[i][j-1] + 1:
            pending.append((i, j-1))
        if i and j and dp[i][j] == dp[i-1][j-1] + (reference[i-1] != hypothesis[j-1]):
            if reference[i-1] == hypothesis[j-1]:
                candidates.setdefault(i-1, set()).add(j-1)
            else:
                possibly_unmatched.add(i-1)
            pending.append((i-1, j-1))
    return {i: next(iter(values)) for i, values in candidates.items()
            if len(values) == 1 and i not in possibly_unmatched}


def word_arrivals(events, annotation):
    rows = annotation['words']
    reference, groups, starts = [], [], []
    for row in rows:
        tokens = words(row['text'])
        groups.append(list(range(len(reference), len(reference) + len(tokens))))
        reference.extend(tokens)
        starts.extend([row['start']] * len(tokens))
    first, stable, previous = {}, {}, set()
    updates = [e for e in events if e['kind'] == 'transcript']
    for event in updates:
        # Never borrow words from audio not delivered to the recognizer. Using
        # word onsets permits early lexical predictions; signed delay is kept.
        delivered = event.get('delivered_audio_seconds', annotation['duration_seconds'])
        eligible = bisect_right(starts, min(delivered, annotation['duration_seconds']))
        pairs = unambiguous_matches(reference[:eligible], words(event['text']))
        current = set()
        for row, indices in zip(rows, groups):
            if indices and all(i in pairs for i in indices):
                positions = [pairs[i] for i in indices]
                if positions == list(range(positions[0], positions[0] + len(positions))):
                    current.add(row['id'])
        for ident in current:
            first.setdefault(ident, event['wall_seconds'])
            if ident not in previous:
                stable[ident] = event['wall_seconds']
        for ident in previous - current:
            stable.pop(ident, None)
        previous = current
    return [{'id': row['id'], 'text': row['text'], 'reference_end_seconds': row['end'],
             'first_correct_seconds': first.get(row['id']), 'stable_correct_seconds': stable.get(row['id']),
             'first_delay_seconds': first[row['id']] - row['end'] if row['id'] in first else None,
             'stable_delay_seconds': stable[row['id']] - row['end'] if row['id'] in stable else None}
            for row in rows]


def percentile95(values):
    if len(values) < 20:
        return None
    return sorted(values)[math.ceil(.95 * len(values)) - 1]


def comparison(run, annotations):
    config = json.loads((run / 'run.json').read_text(encoding='utf-8'))
    dataset = json.loads((run / 'dataset.json').read_text(encoding='utf-8'))
    cases = [case['id'] for case in dataset['cases']]
    trials = {(profile, case): json.loads((run / f'{profile}--{case}.json').read_text(encoding='utf-8'))
              for profile in config['profiles'] for case in cases}
    statuses = {case: approval_status(annotations[case]) for case in cases}
    shared = [case for case in cases if all(trials[profile, case]['status'] == 'ok' for profile in config['profiles'])]
    text_ready = bool(shared) and all(statuses[case]['text_verified'] for case in shared)
    timing_ready = text_ready and all(statuses[case]['timing_verified'] for case in shared)
    tables, ledgers, case_scores = [], {}, {}
    for profile in config['profiles']:
        case_scores[profile] = {}
        for case in cases:
            trial = trials[profile, case]
            if trial['status'] != 'ok':
                case_scores[profile][case] = {'status': 'recognition trial incomplete', 'error': trial.get('error')}
                continue
            if not statuses[case]['text_verified']:
                case_scores[profile][case] = {'status': 'reference review pending'}
                continue
            reference = ' '.join(w['text'] for w in annotations[case]['words'])
            score, _ = edit_alignment(reference, trial['metrics']['final_text'])
            case_scores[profile][case] = {'status': 'spoken text reviewed', 'score': score}
            if statuses[case]['timing_verified']:
                events = [json.loads(x) for x in (run / f'{profile}--{case}.events.jsonl').read_text(encoding='utf-8').splitlines()]
                ledgers[profile, case] = word_arrivals(events, annotations[case])
        scores = []
        if text_ready:
            for case in shared:
                scores.append(case_scores[profile][case]['score'])
        delays = [w['stable_delay_seconds'] for case in shared for w in ledgers.get((profile, case), [])
                  if timing_ready and w['stable_delay_seconds'] is not None]
        total = sum(s['reference_words'] for s in scores)
        edits = sum(s[k] for s in scores for k in ('substitutions', 'deletions', 'insertions'))
        full_scores = ([case_scores[profile][case]['score'] for case in cases]
                       if all(trials[profile, case]['status'] == 'ok' and statuses[case]['text_verified'] for case in cases) else [])
        full_tokens = sum(s['reference_words'] for s in full_scores)
        full_edits = sum(s[k] for s in full_scores for k in ('substitutions', 'deletions', 'insertions'))
        tables.append({'profile': profile, 'complete_streams': sum(trials[profile, case]['status'] == 'ok' for case in cases),
                       'attempted_streams': len(cases), 'shared_recordings': shared,
                       'verified_wer_percent': 100 * edits / total if total else None,
                       'full_corpus_verified_wer_percent': 100 * full_edits / full_tokens if full_tokens else None,
                       'substitutions': sum(s['substitutions'] for s in scores) if scores else None,
                       'deletions': sum(s['deletions'] for s in scores) if scores else None,
                       'insertions': sum(s['insertions'] for s in scores) if scores else None,
                       'reference_tokens': total or None,
                       'stable_word_delay_median_seconds': statistics.median(delays) if delays else None,
                       'stable_word_delay_p95_seconds': percentile95(delays),
                       'timed_correct_words': len(delays),
                       'eligible_reference_words': sum(len(annotations[c]['words']) for c in shared) if timing_ready else None,
                       'negative_delay_count': sum(d < 0 for d in delays),
                       'status': 'reviewed' if timing_ready else 'text reviewed; timing pending' if text_ready else 'reference review pending'})
    common = None
    if timing_ready:
        for profile in config['profiles']:
            ids = {(case, w['id']) for case in shared for w in ledgers[profile, case] if w['stable_delay_seconds'] is not None}
            common = ids if common is None else common & ids
    for table in tables:
        profile = table['profile']
        same_words = [w['stable_delay_seconds'] for case in shared for w in ledgers.get((profile, case), [])
                      if common and (case, w['id']) in common]
        table['common_correct_word_count'] = len(same_words) if timing_ready else None
        table['common_correct_word_delay_median_seconds'] = statistics.median(same_words) if same_words else None
    return {'method': 'asr-reviewed-reference-v1', 'reference_status': statuses, 'shared_recordings': shared,
            'selection_note': 'Shared completed subset is selected after observing completion; failures remain separately reported.',
            'rows': tables, 'case_scores': case_scores,
            'word_ledgers': {profile: {case: ledgers.get((profile, case), []) for case in cases}
                                            for profile in config['profiles']},
            'accuracy_formula': 'WER = (substitutions + deletions + insertions) / normalized spoken reference tokens',
            'latency_formula': 'ASR callback wall time relative to recording start minus reviewed acoustic word end',
            'latency_alignment': 'Exact token pairs shared by all optimal edit alignments to delivered reference prefix; ambiguous repeated words excluded. No fuzzy matching.',
            'uncertainty_seconds': {case: annotations[case].get('review', {}).get('timing_uncertainty_seconds') for case in shared}}


def estimated_comparison(run, annotations):
    """Score fixed ASR drafts without creating or bypassing human approvals."""
    config = json.loads((run / 'run.json').read_text(encoding='utf-8'))
    dataset = json.loads((run / 'dataset.json').read_text(encoding='utf-8'))
    cases = [case['id'] for case in dataset['cases']]
    for case in dataset['cases']:
        annotation = annotations[case['id']]
        if 'audio_sha256' in case and annotation['audio_sha256'] != case['audio_sha256']:
            raise ValueError('Provisional reference belongs to a different recording: ' + case['id'])
        validate(annotation)
    trials = {(profile, case): json.loads((run / f'{profile}--{case}.json').read_text(encoding='utf-8'))
              for profile in config['profiles'] for case in cases}
    shared = [case for case in cases if all(trials[profile, case]['status'] == 'ok' for profile in config['profiles'])]
    comparison_profiles = set(config['profiles'])
    common_recording_scope = 'all profiles'
    if not shared and config.get('delivery') == 'queued':
        # Prefer the recording with the most complete trials, in dataset order
        # for a tie. One failure need not hide the same-file results of others.
        counts = {case: sum(trials[p, case]['status'] == 'ok' for p in config['profiles']) for case in cases}
        best = max(counts, key=counts.get, default=None)
        if best is not None and counts[best]:
            shared = [best]
            comparison_profiles = {p for p in config['profiles'] if trials[p, best]['status'] == 'ok'}
            common_recording_scope = 'profiles completing the best-covered recording'
    usable = {case: {w['id'] for w in annotations[case]['words'] if w['end'] > w['start']}
              for case in cases}
    case_scores, ledgers, rows = {}, {}, []
    for profile in config['profiles']:
        case_scores[profile] = {}
        delivery_by_case = {}
        for case in cases:
            trial = trials[profile, case]
            event_path = run / f'{profile}--{case}.events.jsonl'
            events = []
            if trial['status'] == 'ok' or (config.get('delivery') == 'queued' and event_path.is_file()):
                events = [json.loads(line) for line in event_path.read_text(encoding='utf-8').splitlines()]
            if config.get('delivery') == 'queued':
                captures = [event for event in events if event['kind'] == 'capture']
                submissions = [event for event in events if event['kind'] == 'audio']
                delivery_by_case[case] = {
                    'max_capture_lateness_seconds': max((e['capture_lateness_seconds'] for e in captures), default=None),
                    'max_queued_audio_seconds': max((e['pending_audio_seconds'] for e in captures), default=None),
                    'max_queue_wait_seconds': max((e['queue_wait_seconds'] for e in submissions), default=None),
                    'capture_complete': any(e['kind'] == 'end_of_capture' for e in events),
                    'submission_complete': any(e['kind'] == 'end_of_audio' for e in events),
                }
            if trial['status'] != 'ok':
                case_scores[profile][case] = {'status': 'recognition trial incomplete', 'error': trial.get('error')}
                continue
            reference = ' '.join(w['text'] for w in annotations[case]['words'])
            score, _ = edit_alignment(reference, trial['metrics']['final_text'])
            case_scores[profile][case] = {'status': 'ESTIMATED from provisional ASR reference', 'score': score}
            ledger = word_arrivals(events, annotations[case])
            for word in ledger:
                word['estimated'] = True
                word['timing_usable'] = word['id'] in usable[case]
                if not word['timing_usable']:
                    word['first_delay_seconds'] = word['stable_delay_seconds'] = None
                    word['timing_exclusion'] = 'zero-duration automatic word timing'
            ledgers[profile, case] = ledger
            case_delays = [word['stable_delay_seconds'] for word in ledger if word['stable_delay_seconds'] is not None]
            case_scores[profile][case].update(
                estimated_stable_word_delay_median_seconds=statistics.median(case_delays) if case_delays else None,
                estimated_stable_word_delay_p95_seconds=percentile95(case_delays),
                timed_correct_words=len(case_delays), eligible_reference_words=len(usable[case]),
            )
        scores = [case_scores[profile][case]['score'] for case in shared if profile in comparison_profiles]
        total = sum(score['reference_words'] for score in scores)
        edits = sum(score[key] for score in scores for key in ('substitutions', 'deletions', 'insertions'))
        full_scores = ([case_scores[profile][case]['score'] for case in cases]
                       if all(trials[profile, case]['status'] == 'ok' for case in cases) else [])
        full_tokens = sum(score['reference_words'] for score in full_scores)
        full_edits = sum(score[key] for score in full_scores for key in ('substitutions', 'deletions', 'insertions'))
        delays = [word['stable_delay_seconds'] for case in shared for word in ledgers.get((profile, case), [])
                  if word['stable_delay_seconds'] is not None]
        first = [word['first_delay_seconds'] for case in shared for word in ledgers.get((profile, case), [])
                 if word['first_delay_seconds'] is not None]
        rows.append({'profile': profile, 'estimated': True, 'status': 'ESTIMATED — not listening verified',
                     'complete_streams': sum(trials[profile, case]['status'] == 'ok' for case in cases),
                     'attempted_streams': len(cases), 'estimated_wer_percent': 100 * edits / total if total else None,
                     'full_corpus_estimated_wer_percent': 100 * full_edits / full_tokens if full_tokens else None,
                     'substitutions': sum(s['substitutions'] for s in scores),
                     'deletions': sum(s['deletions'] for s in scores), 'insertions': sum(s['insertions'] for s in scores),
                     'reference_tokens': total,
                     'estimated_first_word_delay_median_seconds': statistics.median(first) if first else None,
                     'estimated_stable_word_delay_median_seconds': statistics.median(delays) if delays else None,
                     'estimated_stable_word_delay_p95_seconds': percentile95(delays),
                     'timed_correct_words': len(delays),
                     'eligible_reference_words': sum(len(usable[case]) for case in shared),
                     'reference_words_with_unusable_timing': sum(len(annotations[case]['words']) - len(usable[case]) for case in shared),
                     'negative_delay_count': sum(delay < 0 for delay in delays),
                     'delivery_by_case': delivery_by_case,
                     **{key: max((d[key] for d in delivery_by_case.values() if d[key] is not None), default=None)
                        for key in ('max_capture_lateness_seconds', 'max_queued_audio_seconds', 'max_queue_wait_seconds')}})
    common = None
    for profile in config['profiles']:
        if profile not in comparison_profiles:
            continue
        ids = {(case, word['id']) for case in shared for word in ledgers[profile, case]
               if word['stable_delay_seconds'] is not None}
        common = ids if common is None else common & ids
    for row in rows:
        delays = [word['stable_delay_seconds'] for case in shared for word in ledgers.get((row['profile'], case), [])
                  if (case, word['id']) in common]
        row['common_correct_word_count'] = len(delays)
        row['estimated_common_word_delay_median_seconds'] = statistics.median(delays) if delays else None
        row['estimated_common_word_delay_p95_seconds'] = percentile95(delays)
    return {'method': 'asr-provisional-reference-v1', 'estimated': True, 'human_verified': False,
            'delivery_mode': config.get('delivery', 'inline'), 'run': run.name,
            'label': 'ESTIMATED — provisional ASR transcripts and automatic word endings, not listening verified',
            'reference_selection': 'One fixed separate offline Whisper Small English draft per recording for every candidate; not selected to minimize candidate errors.',
            'reference_sources': {case: {'source': annotations[case].get('draft_source'),
                                        'model_sha256': annotations[case].get('draft_model_sha256'),
                                        'audio_sha256': annotations[case]['audio_sha256'],
                                        'text_digest': digest(annotations[case]),
                                        'timing_digest': digest(annotations[case], timing=True),
                                        'words': annotations[case]['words']} for case in cases},
            'shared_recordings': shared, 'comparison_profiles': [p for p in config['profiles'] if p in comparison_profiles],
            'common_recording_scope': common_recording_scope, 'rows': rows, 'case_scores': case_scores,
            'word_ledgers': {profile: {case: ledgers.get((profile, case), []) for case in cases} for profile in config['profiles']},
            'accuracy_formula': 'Estimated WER = (substitutions + deletions + insertions) / normalized provisional reference tokens',
            'latency_formula': 'ASR callback arrival relative to recording start minus automatic draft word ending',
            'latency_alignment': 'Exact pairs shared by all optimal edit alignments; ambiguous repeats excluded; stable words remain correct through final snapshot.',
            'limitations': ['ASR-generated references can omit or mishear speech; this is agreement with a draft, not verified accuracy.',
                            'The reference is a separate Small model but shares the Whisper family with Tiny and Base; correlated errors can bias the comparison.',
                            'Automatic word endings have unknown absolute accuracy; decimal display does not establish timing precision.',
                            'Main table uses the same completed recordings for all included scores. With no all-model recording, it uses the recording most profiles completed and leaves other cells unavailable.',
                            'Per-model timing medians cover different correctly aligned words; use common-word timing for the same-word comparison.',
                            'Signed delays are retained; negative values can reflect prediction or bad reference timing. No invented latency for unmatched words.',
                            'No runtime tracker, book hints, new recognition pass, microphone or physical cue playback.']}


def compare_delivery_runs(previous, current):
    """Compare the same recordings and matched draft word occurrences in both runs."""
    profiles = [row['profile'] for row in current['rows']]
    if set(profiles) != set(previous['word_ledgers']):
        raise ValueError('Delivery comparisons require the same model profiles.')
    shared = [case for case in current['shared_recordings'] if case in previous['shared_recordings']]
    if current['reference_sources'] != previous['reference_sources']:
        raise ValueError('Delivery comparisons require identical draft references.')
    same_words = None
    measurements = {}
    paired_profiles = [p for p in profiles if p in current['comparison_profiles'] and p in previous['comparison_profiles']]
    for run in (previous, current):
        for profile in paired_profiles:
            delays = {(case, word['id']): word['stable_delay_seconds']
                      for case in shared for word in run['word_ledgers'][profile][case]
                      if word['stable_delay_seconds'] is not None}
            measurements[run['run'], profile] = delays
            same_words = set(delays) if same_words is None else same_words & delays.keys()
    rows = []
    for profile in profiles:
        row = {'profile': profile}
        for label, run in [('before', previous), ('after', current)]:
            delays = measurements.get((run['run'], profile), {})
            scores = [run['case_scores'][profile][case]['score'] for case in shared if profile in paired_profiles]
            tokens = sum(score['reference_words'] for score in scores)
            edits = sum(score[k] for score in scores for k in ('substitutions', 'insertions', 'deletions'))
            row[f'{label}_wer_percent'] = 100 * edits / tokens if tokens else None
            row[f'{label}_median_seconds'] = (statistics.median(delays[key] for key in same_words)
                                              if same_words and delays else None)
        rows.append(row)
    return {'previous_run': previous['run'], 'current_run': current['run'],
            'shared_recordings': shared, 'profile_count': len(paired_profiles),
            'common_words': len(same_words or ()), 'rows': rows}
