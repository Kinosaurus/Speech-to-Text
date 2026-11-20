"""Silent, sequential, real-time full-text NeMo boost sweep over frozen recordings."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import statistics
import time
import wave

from benchmarks.asr_only import ASRRecorder, atomic_json, sha256
from benchmarks.asr_only_worker import nemo
from benchmarks.asr_reference import percentile95, word_arrivals
from benchmarks.compare_book_asr import full_book_hints, cue_replay, MARK_IDS
from benchmarks.metrics import edit_alignment
from benchmarks.nemo_boost_server import validate_boost


def profile_name(boost):
    return 'nemo-full-boost-' + format(boost, 'g').replace('.', 'p')


def capture(args, dataset):
    import numpy as np
    levels = dataset['boosts']
    # Rotate order between recordings to reduce a simple warmup/order confound.
    for index, case in enumerate(dataset['cases']):
        order = levels[index:] + levels[:index]
        with wave.open(case['audio'], 'rb') as wav:
            if wav.getnchannels() != 1 or wav.getframerate() != 16000 or wav.getsampwidth() != 2:
                raise ValueError('Expected frozen 16 kHz mono PCM16 source.')
            pcm = np.frombuffer(wav.readframes(wav.getnframes()), dtype='<i2').astype(np.float32) / 32768
        if sha256(case['audio']) != case['audio_sha256']:
            raise ValueError('Recording changed: ' + case['id'])
        hotwords = full_book_hints(case['keen_book_text'])
        for boost in order:
            profile = profile_name(boost)
            path = args.output / f'{profile}--{case["id"]}.json'
            if path.exists():
                raise ValueError('Preserve existing trial before rerunning: ' + str(path))
            result = dict(profile=profile, case=case['id'], boost=boost, audio_sha256=case['audio_sha256'],
                          full_book_text=case['keen_book_text'], book_hints=hotwords,
                          gpu_before=__import__('benchmarks.asr_only_worker', fromlist=['gpu_snapshot']).gpu_snapshot())
            print(f'START {case["id"]} boost={boost}', flush=True)
            recorder = ASRRecorder(path.with_suffix('.events.jsonl'), delivery='queued')
            try:
                result['runtime'] = nemo(args, pcm, recorder, dataset, hotwords=hotwords, boost=boost)
                expected = len(pcm) + round(dataset['tail_seconds'] * 16000)
                final = [event for event in recorder.events if event['kind'] == 'transcript' and event['final']]
                if len(final) != 1 or not final[0]['text'].strip() or recorder.sent_samples != expected:
                    raise ValueError('Missing full delivery or final transcript.')
                from benchmarks.verify_asr_only import verify_queue
                result['delivery'] = verify_queue(recorder.events, expected, complete=True)
                result.update(status='ok', final_text=final[0]['text'])
            except Exception as error:
                result.update(status='failed', error=repr(error))
            finally:
                recorder.close()
                atomic_json(path, result)
            print(f'{result["status"].upper()} {case["id"]} boost={boost} {result.get("error", "")}', flush=True)
            atomic_json(args.output / 'progress.json', {'case': case['id'], 'boost': boost,
                        'completed': len(list(args.output.glob('nemo-full-boost-*--*.json'))), 'total': len(levels)*len(dataset['cases'])})
            if result['status'] != 'ok':
                raise RuntimeError('Sweep stopped after failed trial; evidence retained.')


def summarise(directory, dataset):
    cases = {case['id']: case for case in dataset['cases']}
    profiles = [profile_name(level) for level in dataset['boosts']]
    scores = {profile: {} for profile in profiles}
    for profile in profiles:
        for ident, case in cases.items():
            path = directory / f'{profile}--{ident}.json'
            trial = json.loads(path.read_text(encoding='utf-8'))
            if trial['status'] != 'ok' or trial['audio_sha256'] != case['audio_sha256']:
                raise ValueError('Incomplete or mismatched sweep: ' + str(path))
            if trial['runtime']['benchmark_boost'] != trial['boost']:
                raise ValueError('Unacknowledged boost.')
            annotation = json.loads((directory / f'{ident}.reference.json').read_text(encoding='utf-8'))
            if annotation['audio_sha256'] != case['audio_sha256']:
                raise ValueError('Mismatched frozen reference.')
            events = [json.loads(line) for line in path.with_suffix('.events.jsonl').read_text(encoding='utf-8').splitlines()]
            updates = [event for event in events if event['kind'] == 'transcript']
            if not updates[-1]['final'] or updates[-1]['text'] != trial['final_text']:
                raise ValueError('Missing final callback.')
            reference = ' '.join(word['text'] for word in annotation['words'])
            score, _ = edit_alignment(reference, trial['final_text'])
            usable = {word['id'] for word in annotation['words'] if word['end'] > word['start']}
            delays = {word['id']: word['stable_delay_seconds'] for word in word_arrivals(updates, annotation)
                      if word['id'] in usable and word['stable_delay_seconds'] is not None}
            triggers, duplicates = cue_replay(updates, case['cue_manifest'])
            scores[profile][ident] = {'score': score, 'delays': delays, 'triggers': triggers, 'duplicate_cues': duplicates}
    common = set.intersection(*({(case, word) for case in cases for word in scores[p][case]['delays']} for p in profiles))
    rows = []
    for level, profile in zip(dataset['boosts'], profiles):
        entries = scores[profile]
        total = sum(entry['score']['reference_words'] for entry in entries.values())
        edits = sum(entry['score'][key] for entry in entries.values() for key in ('substitutions', 'deletions', 'insertions'))
        delays = [entries[case]['delays'][word] for case, word in common]
        rows.append({'profile': profile, 'boost': level, 'complete_files': len(cases), 'wer_percent': 100*edits/total,
                     'errors': edits, 'reference_tokens': total, 'same_words': len(delays),
                     'word_median_seconds': statistics.median(delays) if delays else None,
                     'word_p95_seconds': percentile95(delays),
                     'cues_fired': sum(len(entry['triggers']) for entry in entries.values()),
                     'configured_cues': sum(len(case['cue_manifest']['checkpoints']) for case in cases.values()),
                     'duplicate_cues': sum(entry['duplicate_cues'] for entry in entries.values())})
    marks = {(ident, MARK_IDS[mark['id']]): mark for ident, case in cases.items()
             for mark in case.get('timing_marks', []) if mark['id'] in MARK_IDS}
    flags = []
    for profile, level in zip(profiles, dataset['boosts']):
        for ident in cases:
            for key, trigger in scores[profile][ident]['triggers'].items():
                mark = marks.get((ident, key))
                if mark and trigger['callback_seconds'] < mark['end_seconds']-mark.get('precision_seconds',1):
                    flags.append({'case':ident,'checkpoint':key,'boost':level,'callback_seconds':trigger['callback_seconds'],
                                  'coarse_end_seconds':mark['end_seconds'],'mark_precision_seconds':mark.get('precision_seconds',1)})
    result = {'estimated': True, 'human_verified': False, 'rows': rows, 'case_scores': scores,
              'coarse_timing_flags': flags,
              'cues': [{'case': ident, 'id': str(checkpoint['id']),
                        'coarse_end_seconds':marks.get((ident,str(checkpoint['id'])),{}).get('end_seconds'),
                        'reportedly_skipped': ident == 'fat_cat' and str(checkpoint['id']) == 'fat_cat_on_mat',
                        **{profile: scores[profile][ident]['triggers'].get(str(checkpoint['id'])) for profile in profiles}}
                       for ident, case in cases.items() for checkpoint in case['cue_manifest']['checkpoints']],
              'shared_recordings': list(cases), 'common_words': len(common),
              'conditions': 'Same full supplied printed text, 1x queued replay, resident CUDA NeMo, 560 ms chunk + 560 ms right context. Boost acknowledged by server before replay. Same matcher, stability 2, offline cue scoring.',
              'reference': 'Frozen Whisper Small drafts and automatic word endings, not listening verified. One Fat Cat anchor reportedly skipped. Fired/configured is not cue accuracy.',
              'recommendation': 'Development sweep on these three recordings, not a held-out validation. No production boost was changed.'}
    atomic_json(directory / 'boost-comparison.json', result)
    import csv
    with (directory / 'boost-comparison.csv').open('w', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    lines = ['# ESTIMATED NeMo full-text boost sweep', '', result['conditions'], '', result['reference'], '',
             f'Timing compares the same {len(common)} exact word occurrences across all boost settings.', '',
             '| Boost | Complete files | Est. WER ↓ | Median word delay ↓ | P95 | Checkpoints fired / configured | Duplicates |',
             '|---:|---:|---:|---:|---:|---:|---:|']
    for row in rows:
        lines.append(f'| {row["boost"]:g} | {row["complete_files"]}/3 | {row["wer_percent"]:.1f}% | '
                     f'{row["word_median_seconds"]:.2f} s | {row["word_p95_seconds"]:.2f} s | '
                     f'{row["cues_fired"]}/{row["configured_cues"]} | {row["duplicate_cues"]} |')
    lines += ['', '## Cue timing checks', '',
              'Coarse listening marks have whole-second precision. Earlier callbacks may reflect useful prediction or a timing problem; they are not confirmed false activations.']
    for flag in flags:
        lines.append(f'- Boost {flag["boost"]:g}, {flag["case"]}/{flag["checkpoint"]}: callback {flag["callback_seconds"]:.2f} s '
                     f'versus coarse spoken-end mark {flag["coarse_end_seconds"]:g} s, precision ±{flag["mark_precision_seconds"]:g} s. Review before choosing a production boost.')
    if not flags:lines.append('No trigger preceded an available coarse mark by more than its stated precision. This does not verify unmarked cues.')
    (directory / 'boost-comparison.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
    print(json.dumps({'rows': rows, 'common_words': len(common)}), flush=True)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('setup', 'run', 'report'))
    parser.add_argument('--source', type=Path, default=Path('output/asr-only/20261119-nemo-full-book'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--boosts', type=float, nargs='+', default=[0, .5, 1, 2, 3, 5])
    parser.add_argument('--nemo-url', default='ws://127.0.0.1:9098')
    args = parser.parse_args()
    if args.action == 'setup':
        args.output.mkdir(exist_ok=False, parents=True)
        dataset = json.loads((args.source / 'dataset.json').read_text(encoding='utf-8'))
        dataset['boosts'] = [validate_boost(level) for level in args.boosts]
        if len(set(dataset['boosts'])) != len(dataset['boosts']):
            raise ValueError('Duplicate boost levels.')
        for case in dataset['cases']:
            full_book_hints(case['keen_book_text'])
            (args.output / f'{case["id"]}.reference.json').write_bytes((args.source / f'{case["id"]}.reference.json').read_bytes())
        dataset['sweep_source'] = str(args.source.resolve())
        atomic_json(args.output / 'dataset.json', dataset)
        return
    dataset = json.loads((args.output / 'dataset.json').read_text(encoding='utf-8'))
    if args.action == 'run':
        capture(args, dataset)
    summarise(args.output, dataset)


if __name__ == '__main__':
    main()
