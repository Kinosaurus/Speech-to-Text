"""Quiet file comparison of Keen's oral-reading graph and NeMo's book phrases."""

import argparse
from copy import deepcopy
import json
from pathlib import Path
import re
import statistics
import wave

from benchmarks.asr_only import ASRRecorder, atomic_json, sha256
from benchmarks.asr_only_worker import nemo
from benchmarks.asr_reference import percentile95, word_arrivals
from benchmarks.metrics import edit_alignment
from books_to_life.context.book_context import BookContext
from books_to_life.matching.timely_matcher import TimelyEvidenceMatcher


PROFILES = ('keen-book', 'nemo-hints')
ROOT = Path(__file__).resolve().parents[1]
MARK_IDS = {'tea': 'make_a_pot_of_tea', 'stove': 'teapot_on_stove',
            'house': 'little_house_ready', 'hat': 'animals_in_hat'}


def setup(args):
    args.output.mkdir(parents=True, exist_ok=False)
    dataset = json.loads(args.dataset.read_text(encoding='utf-8'))
    for case in dataset['cases']:
        audio = Path(case['audio'])
        if sha256(audio) != case['audio_sha256']:
            raise ValueError(f'Audio changed for {case["id"]}')
        manifest = audio.with_name('checkpoints.json')
        if not manifest.is_file():
            raise ValueError(f'No cue manifest for {case["id"]}')
        annotation = args.references / f'{case["id"]}.annotation.json'
        draft = json.loads(annotation.read_text(encoding='utf-8'))
        if draft['audio_sha256'] != case['audio_sha256']:
            raise ValueError(f'Draft reference does not match {case["id"]}')
        data = json.loads(manifest.read_text(encoding='utf-8'))
        hints = BookContext(TimelyEvidenceMatcher(data, stability=2)).hints.hotwords
        if not hints:
            raise ValueError(f'No book hints for {case["id"]}')
        case['nemo_hotwords'] = hints
        case['cue_manifest'] = data
        case['manifest_sha256'] = sha256(manifest)
        case['keen_book_text'] = '\n'.join(page['text'] for page in data['pages'])
        atomic_json(args.output / f'{case["id"]}.reference.json', draft)
        print(case['id'], f'{case["duration_seconds"]:.2f} s', f'{len(hints.split(","))} fixed NeMo hints', flush=True)
    dataset.pop('tracker', None)
    dataset.update(protocol='book-informed-asr-comparison-v1', hints=True, recognition_tracker=False,
                   cue_matcher='TimelyEvidenceMatcher (split), stability 2')
    atomic_json(args.output / 'dataset.json', dataset)


def capture_nemo(args, dataset):
    import numpy as np

    profile = getattr(args, 'nemo_profile', 'nemo-hints')
    for case in dataset['cases']:
        ident = case['id']
        result_path = args.output / f'{profile}--{ident}.json'
        if result_path.exists():
            if json.loads(result_path.read_text(encoding='utf-8'))['status'] == 'ok':
                continue
            raise ValueError(f'Preserve the failed attempt before replaying {ident}')
        if sha256(case['audio']) != case['audio_sha256']:
            raise ValueError(f'Audio changed for {ident}')
        with wave.open(case['audio'], 'rb') as wav:
            pcm = np.frombuffer(wav.readframes(wav.getnframes()), dtype='<i2').astype(np.float32) / 32768
        recorder = ASRRecorder(result_path.with_suffix('.events.jsonl'), delivery='queued')
        hotwords = (full_book_hints(case['keen_book_text']) if profile == 'nemo-full-book'
                    else case['nemo_hotwords'])
        result = {'case': ident, 'profile': profile, 'audio_sha256': case['audio_sha256'],
                  'book_hints': hotwords, 'full_book_text': case['keen_book_text'] if profile == 'nemo-full-book' else None}
        print('START NeMo', ident, flush=True)
        try:
            result['runtime'] = nemo(args, pcm, recorder, dataset, hotwords=hotwords)
            expected = len(pcm) + round(dataset['tail_seconds'] * 16000)
            final = [e for e in recorder.events if e['kind'] == 'transcript' and e['final']]
            if len(final) != 1 or not final[0]['text'].strip() or recorder.sent_samples != expected:
                raise ValueError('NeMo did not return a final transcript after full delivery')
            from benchmarks.verify_asr_only import verify_queue
            result['delivery'] = verify_queue(recorder.events, expected, complete=True)
            result.update(status='ok', final_text=final[0]['text'])
        except Exception as error:
            result.update(status='failed', error=repr(error))
        finally:
            recorder.close()
            atomic_json(result_path, result)
        print(result['status'].upper(), 'NeMo', ident, result.get('error', ''), flush=True)


def full_book_hints(text):
    """Supply every printed word as bounded phrases accepted by the NeMo server."""
    from books_to_life.runtime.nemo_parakeet import hint_phrases
    phrases = []
    for sentence in re.split(r'[.!?\n]+', text):
        current = ''
        for word in sentence.replace(',', ' ').split():
            candidate = (current + ' ' + word).strip()
            if len(candidate) > 200:
                if not current:
                    raise ValueError('Book has a word longer than the NeMo phrase limit.')
                phrases.append(current)
                current = word
            else:
                current = candidate
        if current:
            phrases.append(current)
    hotwords = ', '.join(phrases)
    hint_phrases(hotwords)  # Validate without truncating text to fit server limits.
    from benchmarks.metrics import words
    if not phrases or words(hotwords) != words(text):
        raise ValueError('Full-book hints must retain every printed word in order.')
    return hotwords


def lexical_text(text):
    # Keep rejected speech as one unmatched token and retain the underlying
    # spelling of Keen's marked incomplete words. The original is saved as well.
    text = re.sub(r'<SPOKEN_NOISE>', ' [unknownspeech] ', text, flags=re.IGNORECASE)
    return re.sub(r'#INC\b', '', text, flags=re.IGNORECASE)


def cue_replay(events, manifest):
    matcher = TimelyEvidenceMatcher(deepcopy(manifest), stability=2)
    triggers = {}
    repeats = 0
    for event in events:
        text = lexical_text(event['text'])
        end = event['delivered_audio_seconds']
        segment = {'start': 0, 'end': end, 'text': text, 'completed': event['final']}
        update = matcher.process(text, [segment])
        if update.triggered:
            ident = str(update.checkpoint_id)
            if ident in triggers:
                repeats += 1
            else:
                triggers[ident] = {'callback_seconds': event['wall_seconds'], 'final_callback': event['final']}
    return triggers, repeats


def summarise(args, dataset):
    profiles = tuple(dataset.get('profiles', PROFILES))
    rows, cue_rows = [], []
    for case in dataset['cases']:
        ident = case['id']
        annotation = json.loads((args.output / f'{ident}.reference.json').read_text(encoding='utf-8'))
        reference = ' '.join(word['text'] for word in annotation['words'])
        usable = {word['id'] for word in annotation['words'] if word['end'] > word['start']}
        scope = {profile: {} for profile in profiles}
        for profile in profiles:
            path = args.output / f'{profile}--{ident}.json'
            result = json.loads(path.read_text(encoding='utf-8'))
            entry = dict(case=ident, profile=profile, status=result['status'], error=result.get('error'))
            if result['status'] != 'ok':
                scope[profile] = entry
                continue
            if result['audio_sha256'] != case['audio_sha256']:
                raise ValueError(f'Mismatched audio in {path.name}')
            events = [json.loads(line) for line in path.with_suffix('.events.jsonl').read_text(encoding='utf-8').splitlines()]
            expected_samples = round((case['duration_seconds'] + dataset['tail_seconds']) * 16000)
            capture_ends = [event for event in events if event['kind'] == 'end_of_capture']
            if len(capture_ends) != 1 or capture_ends[0]['samples'] != expected_samples:
                raise ValueError(f'Missing full source capture in {path.name}')
            if capture_ends[0]['wall_seconds'] < expected_samples / 16000 - .025:
                raise ValueError(f'Source capture ran ahead of the file clock in {path.name}')
            updates = [event for event in events if event['kind'] == 'transcript']
            if not updates or not updates[-1]['final'] or updates[-1]['text'] != result['final_text']:
                raise ValueError(f'Missing final callback evidence in {path.name}')
            if any(a['wall_seconds'] > b['wall_seconds'] for a, b in zip(updates, updates[1:])):
                raise ValueError(f'Nonmonotonic transcript callbacks in {path.name}')
            eval_updates = [{**event, 'text': lexical_text(event['text'])} for event in updates]
            score, _ = edit_alignment(reference, eval_updates[-1]['text'])
            ledger = word_arrivals(eval_updates, annotation)
            delays = {word['id']: word['stable_delay_seconds'] for word in ledger
                      if word['id'] in usable and word['stable_delay_seconds'] is not None}
            triggers, repeats = cue_replay(updates, case['cue_manifest'])
            entry.update(score=score, delays=delays, usable_words=len(usable), triggers=triggers,
                         duplicate_cues=repeats, cue_count=len(case['cue_manifest']['checkpoints']))
            scope[profile] = entry
        common = set.intersection(*(set(scope[profile].get('delays', {})) for profile in profiles))
        for entry in scope.values():
            delays = [entry['delays'][word] for word in common]
            entry.update(common_word_delays=delays, common_words=len(common),
                         word_median_seconds=statistics.median(delays) if delays else None,
                         word_p95_seconds=percentile95(delays))
            rows.append(entry)
        marks = {MARK_IDS[mark['id']]: mark['end_seconds'] for mark in case['timing_marks']}
        for checkpoint in case['cue_manifest']['checkpoints']:
            key = str(checkpoint['id'])
            cue_rows.append({'case': ident, 'id': key, 'text': checkpoint['checkpoint_text'],
                             'approx_spoken_end_seconds': marks.get(key),
                             'reportedly_skipped': ident == 'fat_cat' and key == 'fat_cat_on_mat',
                             **{profile: scope[profile].get('triggers', {}).get(key) for profile in profiles}})
    shared = [case['id'] for case in dataset['cases']
              if all(row['status'] == 'ok' for row in rows if row['case'] == case['id'])]
    aggregate = []
    for profile in profiles:
        runs = [row for row in rows if row['profile'] == profile and row['case'] in shared]
        tokens = sum(row['score']['reference_words'] for row in runs)
        errors = sum(row['score'][key] for row in runs for key in ('substitutions', 'deletions', 'insertions'))
        delays = [delay for row in runs for delay in row['common_word_delays']]
        aggregate.append(dict(profile=profile, reference_tokens=tokens, errors=errors,
                              wer=errors / tokens if tokens else None, common_words=len(delays),
                              word_median_seconds=statistics.median(delays) if delays else None,
                              word_p95_seconds=percentile95(delays), cues_fired=sum(len(row['triggers']) for row in runs),
                              configured_cues=sum(row['cue_count'] for row in runs),
                              duplicate_cues=sum(row['duplicate_cues'] for row in runs)))
    nemo_profile = 'nemo-full-book' if 'nemo-full-book' in profiles else 'nemo-hints'
    cue_deltas = [row['keen-book']['callback_seconds'] - row[nemo_profile]['callback_seconds']
                  for row in cue_rows if row['keen-book'] and row[nemo_profile]]
    summary = {'estimated_word_metrics': True, 'shared_completed_recordings': shared, 'aggregate': aggregate,
               'rows': rows, 'cues': cue_rows, 'common_cues': len(cue_deltas),
               'median_keen_minus_nemo_cue_seconds': statistics.median(cue_deltas) if cue_deltas else None}
    atomic_json(args.output / 'comparison.json', summary)
    write_report(args.output / 'report.md', summary)


def write_report(path, summary):
    labels = {'keen-book': 'KeenASR Web / book graph', 'nemo-hints': 'Parakeet NeMo / checkpoint hints',
              'nemo-full-book': 'Parakeet NeMo / full-book phrase boosting'}
    profiles = tuple(row['profile'] for row in summary['aggregate'])
    nemo_profile = 'nemo-full-book' if 'nemo-full-book' in profiles else 'nemo-hints'
    names = {'tea': 'Tea', 'fat_cat': 'Fat Cat', 'little_mermaid': 'Little Mermaid'}
    rows, cue_rows = summary['rows'], summary['cues']
    lines = ['# KeenASR and NeMo on the same books', '',
             'The same stored recordings were replayed at real-time speed without audio output. '
             'Keen used the installed English Web SDK and a graph built from each printed book. '
             'NeMo used CUDA with the labelled phrase set and the server’s standard boost of 1.0. '
             'Full-book boosting includes every printed word as bounded phrases; checkpoint hints include only the anchor phrases. '
             'The graph constrains Keen more strongly than phrase boosting constrains NeMo.', '',
             'Shared complete recordings: ' + (', '.join(names[name] for name in summary['shared_completed_recordings']) or 'none') + '.', '',
             '| Configuration | Est. WER ↓ | Est. median word delay ↓ | Est. P95 | Identical timed words | Cues fired / configured |',
             '|---|---:|---:|---:|---:|---:|']

    def seconds(value):
        return '—' if value is None else f'{value:.2f} s'

    for row in summary['aggregate']:
        wer = '—' if row['wer'] is None else f'{100 * row["wer"]:.1f}%'
        lines.append(f'| {labels[row["profile"]]} | {wer} | {seconds(row["word_median_seconds"])} | '
                     f'{seconds(row["word_p95_seconds"])} | {row["common_words"]} | '
                     f'{row["cues_fired"]}/{row["configured_cues"]} |')
    lines += ['', '## Why more cues can coexist with higher word error', '',
              'WER scores every word in the final transcript, including extra words and repetitions. '
              'Cue firing depends on short checkpoint phrases in the live callbacks, using the same forgiving matcher. '
              'A system can preserve the checkpoint phrases while making more errors in the rest of the passage.', '',
              'Some apparent errors may be in the unverified reference itself; this is not listening-verified accuracy.', '',
              'Full-book graph constraints and checkpoint phrase boosting are different conditions. '
              'Book support guides recognition but does not guarantee verbatim speech. '
              'Fired/configured is not cue accuracy: one of the seven configured anchors was reportedly skipped.', '']
    lines += ['', '| Recording | Configuration | Est. WER ↓ | Est. median word delay ↓ | Est. P95 | Timed words / usable | Cues fired |',
              '|---|---|---:|---:|---:|---:|---:|']
    for row in rows:
        name = names[row['case']]
        label = labels[row['profile']]
        if row['status'] != 'ok':
            lines.append(f'| {name} | {label} (incomplete) | — | — | — | — | — |')
            continue
        wer = 100 * row['score']['wer']
        lines.append(f'| {name} | {label} | {wer:.1f}% | {seconds(row["word_median_seconds"])} '
                     f'| {seconds(row["word_p95_seconds"])} | {len(row["delays"])}/{row["usable_words"]} '
                     f'| {len(row["triggers"])}/{row["cue_count"]} |')
    lines += ['', 'Word error compares the final text with the same provisional Whisper Small transcript. '
              'Word delay is the stable correct-word callback minus the estimated word end, using the same exact word occurrences for both systems per file. '
              'P95 is shown with at least 20 matched words. Automated references and timings remain estimates. '
              'Keen’s incomplete-word suffix is stripped for lexical scoring, and its spoken-noise token counts as one unknown word.', '',
              '| Recording | Checkpoint | ' + ' | '.join(labels[p] + ' cue time' for p in profiles) + ' | Approx. spoken end | Keen − NeMo |',
              '|---|---|' + '---:|' * (len(profiles) + 2)]
    for row in cue_rows:
        times = [seconds(row[p]['callback_seconds']) if row[p] else '—' for p in profiles]
        anchor = 'Reportedly skipped' if row['reportedly_skipped'] else seconds(row['approx_spoken_end_seconds'])
        delta = (f'{row["keen-book"]["callback_seconds"] - row[nemo_profile]["callback_seconds"]:+.2f} s'
                 if row['keen-book'] and row[nemo_profile] else '—')
        lines.append(f'| {names[row["case"]]} | {row["text"]} | ' + ' | '.join(times) + f' | {anchor} | {delta} |')
    lines += ['', 'Cue times are from recording start. Both raw callback histories were replayed through the same shared split matcher with stability 2. '
              'Timing names the callback that lets the matcher fire. Cue hardware and sound are outside the measurement. '
              'Where a spoken end is available, subtract it from the cue time for an approximate response delay. The saved spoken-end marks have whole-second precision.', '',
              'Keen received a silent browser MediaStream on the WebAudio clock. NeMo received queued 256 ms packets over local WebSocket. '
              'The browser’s native audio worklet, buffering and end-of-session behavior are part of the Keen configuration. '
              'A cue that fires on the final callback depends on that backend’s finalization behavior.', '']
    if summary['common_cues']:
        lines.append(f'Across {summary["common_cues"]} shared cue triggers, median Keen minus NeMo time was '
                     f'{summary["median_keen_minus_nemo_cue_seconds"]:+.2f} seconds. Negative values mean Keen triggered earlier.')
    for row in rows:
        if row['status'] != 'ok':
            lines.append(f'- {row["case"]}, {row["profile"]}: {row["error"]}')
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(path, flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('setup', 'nemo', 'report'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--dataset', type=Path, default=ROOT / 'output/asr-only/20261119-queued-01/dataset.json')
    parser.add_argument('--references', type=Path, default=ROOT / 'output/asr-only-reference-review/20261119-01')
    parser.add_argument('--nemo-url', default='ws://127.0.0.1:9097')
    parser.add_argument('--nemo-profile', choices=('nemo-hints', 'nemo-full-book'), default='nemo-hints')
    args = parser.parse_args()
    if args.action == 'setup':
        setup(args)
        return
    dataset = json.loads((args.output / 'dataset.json').read_text(encoding='utf-8'))
    if args.action == 'nemo':
        capture_nemo(args, dataset)
    else:
        summarise(args, dataset)


if __name__ == '__main__':
    main()
