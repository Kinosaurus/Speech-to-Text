"""Compare saved local trials on common recordings and exact word occurrences."""
import argparse
import json
from pathlib import Path
import statistics

from benchmarks.asr_only import atomic_json
from benchmarks.asr_reference import percentile95, word_arrivals
from benchmarks.compare_book_asr import cue_replay, lexical_text
from benchmarks.metrics import edit_alignment


LABELS = {
    'keen-book': 'KeenASR Web · full-book reading graph',
    'nemo-full-book': 'NeMo CUDA · full-book phrase boosting',
    'nemo-hints': 'NeMo CUDA · checkpoint phrase hints',
    'nemo-cuda': 'NeMo CUDA · no hints',
    'parakeet-vulkan': 'Native Parakeet Vulkan · no hints',
    'whisper-tiny-cuda': 'Whisper Tiny CUDA · no hints',
    'whisper-base-cuda': 'Whisper Base CUDA · no hints',
    'moonshine-vulkan': 'Moonshine Vulkan · no hints',
    'moonshine-cpu': 'Official Moonshine CPU · no hints',
    'whisper-tiny-cpu': 'Whisper Tiny CPU · no hints',
    'whisper-base-cpu': 'Whisper Base CPU · no hints',
}


def build(book_run, queued_run, cpu_run, sweep_run=None):
    dataset = json.loads((book_run / 'dataset.json').read_text(encoding='utf-8'))
    cases = {case['id']: case for case in dataset['cases']}
    references = {case: json.loads((book_run / f'{case}.reference.json').read_text(encoding='utf-8'))
                  for case in cases}
    labels = dict(LABELS)
    sources = {profile: book_run if profile in ('keen-book', 'nemo-full-book', 'nemo-hints')
               else cpu_run if profile in ('whisper-tiny-cpu', 'whisper-base-cpu') else queued_run
               for profile in labels}
    if sweep_run:
        from benchmarks.sweep_nemo_boost import profile_name
        from benchmarks.asr_reference import digest
        sweep = json.loads((sweep_run / 'dataset.json').read_text(encoding='utf-8'))
        for ident in cases:
            frozen = json.loads((sweep_run / f'{ident}.reference.json').read_text(encoding='utf-8'))
            if digest(frozen, timing=True) != digest(references[ident], timing=True):
                raise ValueError('Sweep uses different frozen reference: ' + ident)
        for level in sweep['boosts']:
            profile = profile_name(level)
            labels[profile] = f'NeMo CUDA · full text, boost {level:g} (sweep)'
            sources[profile] = sweep_run
    scores = {}
    for profile, directory in sources.items():
        scores[profile] = {}
        for case, data in cases.items():
            path = directory / f'{profile}--{case}.json'
            trial = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
            row = {'status': trial.get('status', 'not run'), 'error': trial.get('error')}
            scores[profile][case] = row
            if row['status'] != 'ok':
                continue
            if trial['audio_sha256'] != data['audio_sha256'] or references[case]['audio_sha256'] != data['audio_sha256']:
                raise ValueError('Mismatched recording: ' + str(path))
            events = [json.loads(line) for line in path.with_suffix('.events.jsonl').read_text(encoding='utf-8').splitlines()]
            updates = [event for event in events if event['kind'] == 'transcript']
            text = trial.get('final_text', trial.get('metrics', {}).get('final_text'))
            if not updates or not updates[-1]['final'] or updates[-1]['text'] != text:
                raise ValueError('Missing final transcript: ' + str(path))
            if any(a['wall_seconds'] > b['wall_seconds'] for a, b in zip(updates, updates[1:])):
                raise ValueError('Nonmonotonic transcript callbacks: ' + str(path))
            updates = [{**event, 'text': lexical_text(event['text'])} for event in updates]
            reference = references[case]
            score, _ = edit_alignment(' '.join(word['text'] for word in reference['words']), lexical_text(text))
            usable = {word['id'] for word in reference['words'] if word['end'] > word['start']}
            ledger = word_arrivals(updates, reference)
            delays = {word['id']: word['stable_delay_seconds'] for word in ledger
                      if word['id'] in usable and word['stable_delay_seconds'] is not None}
            triggers, duplicates = cue_replay(updates, data['cue_manifest'])
            row.update(score=score, delays=delays, triggers=triggers, duplicate_cues=duplicates,
                       configured_cues=len(data['cue_manifest']['checkpoints']))
    # Profiles with no complete file remain visible, with no invented score.
    eligible = [profile for profile in labels if any(row['status'] == 'ok' for row in scores[profile].values())]
    shared = [case for case in cases if all(scores[p][case]['status'] == 'ok' for p in eligible)]
    if not shared:
        raise ValueError('No common complete recording across measured profiles.')
    common = set.intersection(*({(case, word) for case in shared for word in scores[p][case]['delays']}
                                for p in eligible))
    rows = []
    for profile in labels:
        own = scores[profile]
        complete = [case for case in cases if own[case]['status'] == 'ok']
        scoped = [own[case] for case in shared] if profile in eligible else []
        tokens = sum(row['score']['reference_words'] for row in scoped)
        errors = sum(row['score'][key] for row in scoped for key in ('substitutions', 'deletions', 'insertions'))
        delays = [own[case]['delays'][word] for case, word in common] if profile in eligible else []
        all_tokens = sum(own[case]['score']['reference_words'] for case in complete)
        all_errors = sum(own[case]['score'][key] for case in complete for key in ('substitutions', 'deletions', 'insertions'))
        rows.append({'profile': profile, 'label': labels[profile], 'source_run': str(sources[profile].resolve()),
                     'delivery': 'inline' if sources[profile] == cpu_run else 'queued' if sources[profile] == queued_run else 'book trial',
                     'complete_files': len(complete), 'configured_files': len(cases),
                     'shared_wer_percent': 100 * errors / tokens if tokens else None,
                     'same_word_median_seconds': statistics.median(delays) if delays else None,
                     'same_word_p95_seconds': percentile95(delays), 'same_words': len(delays),
                     'cues_fired': sum(len(row['triggers']) for row in scoped) if scoped else None,
                     'configured_cues': sum(row['configured_cues'] for row in scoped) if scoped else None,
                     'all_three_wer_percent': 100 * all_errors / all_tokens if len(complete) == len(cases) else None,
                     'all_three_cues_fired': sum(len(own[case]['triggers']) for case in complete) if len(complete) == len(cases) else None,
                     'all_three_configured_cues': sum(own[case]['configured_cues'] for case in complete) if len(complete) == len(cases) else None})
    return {'estimated': True, 'human_verified': False, 'shared_recordings': shared,
            'common_words': len(common), 'scored_profiles': len(eligible), 'rows': rows, 'case_scores': scores,
            'scope': 'Shared scores use identical recordings and exact word occurrences for every scored configuration. No complete file means unavailable.',
            'conditions': 'Text support and audio-delivery mode differ as labelled. CPU Whisper trials use earlier inline delivery; others use queued delivery or the Keen browser audio clock. These are configuration comparisons, not isolated model-only effects.',
            'reference': 'Frozen unverified Whisper Small transcripts and automatic word endings; estimates may favor Whisper-family output.',
            'cues': 'Saved callbacks replayed through the same TimelyEvidenceMatcher, stability 2. No runtime tracker guided recognition. No audio, microphone, OSC or projection output.'}


def export(directory, result):
    atomic_json(directory / 'all-models.json', result)
    import csv
    with (directory / 'all-models.csv').open('w', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(file, fieldnames=list(result['rows'][0]))
        writer.writeheader()
        writer.writerows(result['rows'])
    def fmt(value, suffix=''):
        return '—' if value is None else f'{value:.2f}{suffix}'
    lines = ['# ESTIMATED comparison of all tested ASR configurations', '', result['reference'], '',
             'Shared recordings: ' + ', '.join(result['shared_recordings']) + f'. Same {result["common_words"]} timed words.', '',
             result['conditions'], '',
             '| Configuration | Complete files | Shared WER ↓ | Same-word median ↓ | P95 | Shared cues fired / configured | All-three WER | All-three cues fired / configured |',
             '|---|---:|---:|---:|---:|---:|---:|---:|']
    for row in result['rows']:
        cues = '—' if row['cues_fired'] is None else f'{row["cues_fired"]}/{row["configured_cues"]}'
        lines.append(f'| {row["label"]} | {row["complete_files"]}/{row["configured_files"]} | '
                     f'{fmt(row["shared_wer_percent"], "%")} | {fmt(row["same_word_median_seconds"], " s")} | '
                     f'{fmt(row["same_word_p95_seconds"], " s")} | {cues} | {fmt(row["all_three_wer_percent"], "%")} | '
                     + ('—' if row['all_three_cues_fired'] is None else f'{row["all_three_cues_fired"]}/{row["all_three_configured_cues"]}') + ' |')
    lines += ['', result['scope'], result['cues'],
              'One Fat Cat checkpoint was reportedly skipped. Fired/configured is not cue accuracy. '
              'Cue times exclude hardware, projection and sound. No recordings were uploaded.', '']
    (directory / 'all-models.md').write_text('\n'.join(lines), encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--book-run', type=Path, required=True)
    parser.add_argument('--queued-run', type=Path, required=True)
    parser.add_argument('--cpu-run', type=Path, required=True)
    parser.add_argument('--sweep-run', type=Path)
    args = parser.parse_args()
    result = build(args.book_run, args.queued_run, args.cpu_run, args.sweep_run)
    export(args.book_run, result)
    print(json.dumps({key: result[key] for key in ('shared_recordings', 'common_words', 'scored_profiles', 'rows')}), flush=True)


if __name__ == '__main__':
    main()
