"""Compare saved streaming trigger times with explicitly provisional ASR word times.

This does not run recognition or write manual ground truth. It reports every
profile, retains missing endpoints, and keeps estimates outside verified reports.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from benchmarks.metrics import words
from benchmarks.run import PROFILES, load_manual_timing


def unique_endpoint(timed, suffix):
    query = words(suffix)
    if not query:
        raise ValueError('An endpoint requires a nonempty phrase.')
    tokens = [item['word'].lower() for item in timed]
    occurrences = [i for i in range(len(tokens) - len(query) + 1)
                   if tokens[i:i + len(query)] == query]
    if len(occurrences) != 1:
        return None
    start = occurrences[0]
    end = start + len(query)
    return {'start_word_index': start, 'end_word_index_exclusive': end,
            'endpoint_seconds': timed[end - 1]['end'],
            'recognized_context': ' '.join(item['word'] for item in timed[max(0, start - 5):end]),
            'matched_suffix': suffix}


def manual_report(root):
    output = root / 'output/benchmarks'
    report = {'timing_kind': 'user-supplied listening marks, whole seconds',
              'definition': 'saved confirming ASR update arrival minus user-supplied phrase ending',
              'precision': 'whole-second listening marks; subsecond endpoint accuracy not established',
              'scope': 'streaming only; excludes matcher computation, microphone, transport and physical playback',
              'datasets': {}}
    lines = ['# Checkpoint delays using your listening marks', '',
             'Endpoints were supplied by the user after listening to the recordings. They are whole-second marks;',
             'subsecond endpoint accuracy has not been established. No recognition was rerun to produce this report.', '',
             'Delay = saved trigger arrival time − supplied phrase ending. Negative values mean the trigger',
             'preceded that mark. No event means the checkpoint never emitted during the saved replay.',
             'Activations on skipped phrases have no phrase-end delay and are listed separately.',
             'They may represent scene catch-up; they are not direct detections of a spoken checkpoint phrase.', '',
             'These times exclude microphone, network, matcher computation and physical effect playback.', '']
    for key, folder in [('tea', 'tea-streaming'), ('fat_cat', 'fat-cat-streaming')]:
        result = json.loads((output / folder / 'results.json').read_text(encoding='utf-8'))
        audio_path, manifest_path = Path(result['audio']), Path(result['manifest'])
        endpoints, skipped, metadata = load_manual_timing(audio_path, manifest_path, output / folder)
        if not endpoints and not skipped:
            raise ValueError('No manual listening annotations found: ' + folder)
        if result['anchor_times'] != endpoints or set(result['manually_reported_skipped_anchors']) != skipped:
            raise ValueError('Run --summarize-only to refresh the saved manual results first.')
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        checkpoints = manifest['checkpoints']
        dataset = {'audio': str(audio_path), 'manifest': str(manifest_path),
                   'endpoints': endpoints, 'skipped_checkpoint_ids': sorted(skipped),
                   'annotation_metadata': metadata, 'profiles': {}, 'rows': result['rows']}
        lines += ['## ' + audio_path.name, '', '| Checkpoint | User listening mark |', '|---|---:|']
        for cp in checkpoints:
            mark = 'skipped' if cp['id'] in skipped else str(endpoints.get(cp['id'], 'not supplied')) + ' s'
            lines.append(f"| {cp['checkpoint_text']} | {mark} |")
        lines += ['', '| Profile | ' + ' | '.join(cp['id'] for cp in checkpoints) + ' |',
                  '|---|' + '---:|' * len(checkpoints)]
        for profile, profile_result in result['profiles'].items():
            if (profile_result['audio_sha256'] != metadata.get('audio_sha256')
                    or profile_result['manifest_sha256'] != metadata.get('manifest_sha256')):
                raise ValueError('Saved profile input differs from the listening annotations: ' + profile)
            triggers = {e['id']: e for e in profile_result['checkpoint_delays']}
            dataset['profiles'][profile] = profile_result['checkpoint_delays']
            values = []
            for cp in checkpoints:
                trigger = triggers.get(cp['id'])
                if cp['id'] in skipped:
                    values.append(f"skipped; activated at {trigger['trigger_wall_seconds']:.1f} s" if trigger else 'skipped; no activation')
                elif trigger and trigger['delay_seconds'] is not None:
                    values.append(f"{trigger['delay_seconds']:+.1f} s")
                else:
                    values.append('no event' if not trigger else 'endpoint unavailable')
            lines.append('| ' + profile + ' | ' + ' | '.join(values) + ' |')
        report['datasets'][key] = dataset
        lines += ['']
    (output / 'checkpoint-delays-manual.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    (output / 'checkpoint-delays-manual.md').write_text('\n'.join(lines), encoding='utf-8')
    print(output / 'checkpoint-delays-manual.md')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manual', action='store_true', help='Use already summarized user listening marks instead of ASR estimates.')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    if args.manual:
        manual_report(root)
        return
    output = root / 'output/benchmarks'
    cases = [
        ('tea', 'tea-streaming', '4YearOldTea_resampled.wav', 'examples/tea_story.json', {
            'make_a_pot_of_tea': ('I will make us a pot of tea', 'Full checkpoint phrase recognized.'),
            'teapot_on_stove': ('on the stove', 'Only the ending is matched; teapot is misrecognized in the reference stream.'),
            'little_house_ready': ('house', 'Single unique ending word; preceding words are misrecognized. Requires listening verification.'),
        }),
        ('fat_cat', 'fat-cat-streaming', '5YearOldFatCat_resampled.wav', 'examples/fat_cat_story.json', {
            'fat_cat_on_mat': ('A fat cat sat on a mat', 'Exact checkpoint phrase is absent from the ASR timing reference. A later similar sentence cannot verify this endpoint.'),
            'animals_in_hat': ('rat on a bat on a cat in a hat', 'Checkpoint recognized except its leading article.'),
        }),
    ]
    report = {
        'timing_kind': 'ASR-estimated, not independently listened to or verified',
        'definition': 'saved confirming ASR update arrival minus estimated spoken phrase ending',
        'scope': 'streaming only; excludes matcher computation, microphone, transport and physical playback',
        'no_new_model_downloads': True,
        'warning': 'Negative values suggest early firing. Model alignment errors can affect either sign. Do not present these as verified delays.',
        'datasets': {},
    }
    lines = ['# Provisional checkpoint delays', '',
             '**ASR estimates, not verified by listening.** Both timing references were produced by real-paced',
             'streaming Parakeet Unified F16 with no book hints. No whole-file recognition or warmup was used.', '',
             'Delay = saved trigger arrival time − estimated spoken phrase ending.',
             'A negative value suggests an early effect. No emission is labelled “no event”.',
             'Microphone, network, matcher computation and physical effect playback are outside this measurement.', '']
    for key, folder_name, audio_name, manifest_name, suffixes in cases:
        folder = output / folder_name
        audio_path = root / audio_name
        manifest_path = root / manifest_name
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        timing = json.loads((folder / 'timing-reference-streaming-estimated.json').read_text(encoding='utf-8'))
        audio_hash = hashlib.sha256(audio_path.read_bytes()).hexdigest()
        manifest_hash = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
        if timing['audio_sha256'] != audio_hash or timing['whole_file_inference']:
            raise ValueError('Timing reference does not match the required streaming audio.')
        checkpoints = []
        for cp in manifest['checkpoints']:
            suffix, note = suffixes[cp['id']]
            endpoint = unique_endpoint(timing['words'], suffix)
            occurrences = [unique_endpoint(s['words'], suffix) for s in timing['snapshots']]
            occurrences = [item['endpoint_seconds'] for item in occurrences if item]
            checkpoints.append({'id': cp['id'], 'phrase': cp['checkpoint_text'],
                                'status': 'ASR-estimated' if endpoint else 'endpoint unavailable',
                                'endpoint_seconds': endpoint['endpoint_seconds'] if endpoint else None,
                                'word_evidence': endpoint, 'note': note,
                                'matching_snapshots': len(occurrences),
                                'snapshot_endpoint_values': sorted(set(occurrences))})
        profiles = {}
        for profile in PROFILES:
            path = folder / (profile + '.json')
            if not path.exists():
                continue
            result = json.loads(path.read_text(encoding='utf-8'))
            if (result['audio_sha256'] != audio_hash or result['manifest_sha256'] != manifest_hash
                    or result['benchmark_mode'] != 'streaming-only-v1'):
                raise ValueError('Benchmark result has mismatched input or protocol: ' + profile)
            triggers = {e['checkpoint_id']: e for e in result['stream']['events'] if e['triggered']}
            profiles[profile] = []
            for cp in checkpoints:
                trigger = triggers.get(cp['id'])
                endpoint = cp['endpoint_seconds']
                delay = trigger['wall_seconds'] - endpoint if trigger and endpoint is not None else None
                profiles[profile].append({'id': cp['id'], 'emitted': trigger is not None,
                                         'trigger_wall_seconds': trigger['wall_seconds'] if trigger else None,
                                         'estimated_endpoint_seconds': endpoint,
                                         'estimated_delay_seconds': delay,
                                         'suspected_early': delay < -0.25 if delay is not None else None,
                                         'skipped_by_matcher': cp['id'] in result['stream']['skipped_ids']})
        report['datasets'][key] = {'audio': str(audio_path), 'audio_sha256': audio_hash,
                                   'manifest_sha256': manifest_hash,
                                   'timing_source': timing['source'], 'checkpoints': checkpoints,
                                   'profiles': profiles}
        lines += ['## ' + audio_name, '', '| Checkpoint | Estimated ending | Evidence |',
                  '|---|---:|---|']
        for cp in checkpoints:
            end = f"{cp['endpoint_seconds']:.2f} s" if cp['endpoint_seconds'] is not None else 'unavailable'
            lines.append(f"| {cp['phrase']} | {end} | {cp['note']} |")
        lines += ['', '| Profile | ' + ' | '.join(cp['id'] for cp in checkpoints) + ' |',
                  '|---|' + '---:|' * len(checkpoints)]
        for profile, delays in profiles.items():
            values = [('no event' if not d['emitted'] else 'emitted; endpoint unavailable')
                      if d['estimated_delay_seconds'] is None
                      else f"{d['estimated_delay_seconds']:+.2f} s" for d in delays]
            lines.append('| ' + profile + ' | ' + ' | '.join(values) + ' |')
        lines += ['', 'These are provisional signed delays, not counts of correctly timed effects.', '']
    (output / 'checkpoint-delay-estimates.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    (output / 'checkpoint-delay-estimates.md').write_text('\n'.join(lines), encoding='utf-8')
    print(output / 'checkpoint-delay-estimates.md')


if __name__ == '__main__':
    main()
