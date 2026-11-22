"""Audit the paired tracker/sound replays and compare preserved Parakeet captures."""
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
import statistics

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
OLD = ROOT / 'output/reading-pod-first-pipeline'

def read(path):
    return json.loads(path.read_text(encoding='utf-8'))

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    freeze = read(OUT / 'provenance.json')
    for name, expected in freeze['files'].items():
        assert digest(Path(name)) == expected, 'Frozen input or implementation changed: ' + name
    audit = []
    rows = []
    details = []
    for case, title in [('moon','The Moon'), ('lion','The Lion and the Mouse')]:
        common = freeze['same_subset'][case]
        prior_root = OLD / 'output/latency-investigation-20261119'
        prior_paths = [prior_root / part / f'{case}-short-chunk-01' for part in ('short-chunk','confirmation')]
        prior_results = [read(p / 'result.json') for p in prior_paths]
        configs = [('Parakeet 160 ms chunk / 560 ms future context (saved)', prior_paths)]
        configs += [(f'Nemotron {ms} ms', [OUT / f'{case}-nemotron-{ms}-{r:02d}' for r in (1,2)]) for ms in (160,320)]
        for model, paths in configs:
            scores = [read(p / 'score.json') for p in paths]
            results = [read(p / 'result.json') for p in paths]
            events = [event for score in scores for event in score['events']]
            matched = [event for event in events if event['id'] in common]
            delays = [event['effect_delay_seconds'] for event in matched if event['hit']]
            all_delays = [event['effect_delay_seconds'] for event in events if event['hit']]
            callbacks = [event for result in results for event in result['cue_events']]
            duplicates = sum(sum(n-1 for n in Counter(e['id'] for e in result['cue_events']).values()) for result in results)
            median = statistics.median(delays) if delays else None
            row = dict(book=title, model=model, repetitions=2,
                       common_cue_median_seconds=median,
                       common_cues_hit=len(delays), common_cues_expected=len(matched),
                       all_configured_cues_hit=sum(s['checkpoints_hit'] for s in scores),
                       all_configured_cues_expected=len(events),
                       all_configured_median_seconds=statistics.median(all_delays) if all_delays else None,
                       duplicate_tracker_triggers=duplicates,
                       early_sound_events=sum(x < 0 for x in all_delays),
                       common_cue_min_seconds=min(delays) if delays else None,
                       common_cue_max_seconds=max(delays) if delays else None,
                       per_trial_common_medians=[statistics.median(e['effect_delay_seconds'] for e in s['events'] if e['hit'] and e['id'] in common) for s in scores])
            if model.startswith('Parakeet'):
                old_median = median
            else:
                row['reduction_vs_saved_parakeet_percent'] = 100 * (1 - median / old_median) if median is not None else None
            rows.append(row)
            for path, result, score in zip(paths, results, scores):
                assert result['status'] == 'ok' and result['capture_exit_code'] == 0
                assert result['physical_endpoint_original_mute_restored']
                assert result['pre_source_digital_tone_verified']
                assert result['input_sha256'] == prior_results[0]['input_sha256']
                assert result['manifest_sha256'] == prior_results[0]['manifest_sha256']
                assert result['threshold'] == 82 and result['stability'] == 2 and result['min_coverage'] == .8
                updates = [json.loads(line) for line in (path / 'recognition.events.jsonl').read_text(encoding='utf-8').splitlines()]
                assert sum(e['kind'] == 'transcript' and e['final'] for e in updates) == 1
                assert sum(e['kind'] == 'end_of_audio' for e in updates) == 1
                assert result['source_samples_sent'] == round((result['source_seconds'] + 3) * 16000)
                if model.startswith('Nemotron'):
                    cfg = result['runtime']['acknowledged_configuration']
                    assert cfg['backend'] == 'nemotron'
                    assert cfg['chunk_ms'] == int(model.split()[1])
                    assert cfg['att_context'] == [70,cfg['chunk_ms'] // 80 - 1]
                    assert cfg['applied_hotwords_sha256'] == prior_results[0]['runtime']['applied_hotwords_sha256']
                    assert result['packet_samples'] == 1280
                    assert cfg['boost'] == 1.0
                    final_timing = [e for e in updates if e['kind'] == 'server_timing'][-1]
                    assert final_timing['audio_samples'] == result['source_samples_sent']
                    assert final_timing['processed_frames'] > result['source_seconds'] * 100
                for event in score['events']:
                    if event['hit']:
                        scheduled = [e for e in result['cue_events'] if e['id'] == event['id'] and e['sound_scheduled']]
                        assert scheduled, 'Detected waveform without a matching scheduled cue'
                        assert event['similarity'] >= .55
                audit.append(dict(trial=str(path), model=model, case=case,
                                  source_sha256=result['input_sha256'], full_source_and_tail_delivered=True,
                                  output_captured_and_calibrated=True, speaker_mute_restored=True,
                                  max_packet_feed_lateness_seconds=max(e.get('feed_lateness_seconds',0) for e in updates),
                                  max_source_capture_lateness_seconds=max(e.get('capture_lateness_seconds',0) for e in updates),
                                  tracker_callback_count=len(result['cue_events']),
                                  sound_capture_bytes=(path / 'windows-output.pcm').stat().st_size,
                                  evidence_sha256={name:digest(path / name) for name in ('windows-output.pcm','windows-output.jsonl','recognition.events.jsonl','result.json','score.json')},
                                  model_sha256=result['runtime'].get('acknowledged_configuration',{}).get('model_sha256')))
                details.append(dict(trial=str(path), model=model, case=case, score=score,
                                    final_transcript=result['final_transcript'], cue_events=result['cue_events']))
    report = dict(status='complete', metric=freeze['metric'], rows=rows, trials=details,
                  common_cue_ids=freeze['same_subset'], settings=freeze['settings'],
                  caveats=['Two synthetic Microsoft David recordings, two replays per setting per story.',
                           'Digital application output; physical microphone, speaker acoustics and projection excluded.',
                           'Estimated cue endings reused unchanged from the original SAPI timing marks.',
                           'Full-excerpt fixed hints and exact original tracker; these are not ASR-only measurements.',
                           'Moon common-subset comparison uses opening/cat/mouse; dog is included in separate configured-cue counts.',
                           'Parakeet results are saved November 19 runs; Nemotron results are newly measured November 22.',
                           'Nemotron 320 ms uses experimental attention context [70,3], as in the previous ASR comparison.'])
    (OUT / 'comparison.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    (OUT / 'audit.json').write_text(json.dumps(dict(status='passed', trials=audit),indent=2),encoding='utf-8')
    with (OUT / 'comparison.csv').open('w',newline='',encoding='utf-8-sig') as stream:
        writer = csv.DictWriter(stream,fieldnames=list(dict.fromkeys(k for row in rows for k in row)))
        writer.writeheader()
        writer.writerows(rows)
    lines = ['# Tracker cue-to-sound replay comparison', '',
             'New Nemotron runs: 22 November 2026. Parakeet comparator: preserved 19 November runs.', '',
             'Median captured digital sound onset minus the same estimated synthetic cue endings. All rows use the same source WAVs, effect files, full-excerpt hints and original tracker (threshold 82, stability 2, coverage 0.8). Input is paced at 1x in 80 ms packets. Cold loading and a separate two-second silence warmup precede measurement.', '',
             '| Recording | Setup | Common-cue median | Common-cue range | Common cues | All configured cues | Duplicates | Early sounds |',
             '|---|---|---:|---:|---:|---:|---:|---:|']
    for row in rows:
        lines.append(f"| {row['book']} | {row['model']} | {row['common_cue_median_seconds']:.3f} s | {row['common_cue_min_seconds']:.3f}–{row['common_cue_max_seconds']:.3f} s | {row['common_cues_hit']}/{row['common_cues_expected']} | {row['all_configured_cues_hit']}/{row['all_configured_cues_expected']} | {row['duplicate_tracker_triggers']} | {row['early_sound_events']} |")
    lines += ['', 'Counts pool two replays per row. A faster hits-only median must be read alongside missed cues.', '',
              'The Moon uses opening, cat and mouse for the shared median, reproducing the slide’s original 1.18 s subset. Its dog cue remains in the separate all-configured count. The Lion and the Mouse uses all four original cues.', '',
              'Nemotron 160 ms uses [70,1]. The experimental 320 ms setting uses [70,3]. Their native chunk settings differ from Parakeet’s 160 ms updates with 560 ms future context.', '',
              'Source/capture hashes, server configuration acknowledgements, complete sample delivery, final transcript, tracker thresholds, actual waveform detection and restoration of the original speaker mute were audited. No live microphone was opened. Raw waveforms (.pcm), native clocks, recognition/matcher traces, cue events and per-cue scores remain in each trial folder.', '',
              'This small synthetic replay measures digital output latency. Physical cue-to-speaker latency needs a separate shared-clock acoustic recording.', '']
    (OUT / 'README.md').write_text('\n'.join(lines),encoding='utf-8')
    for row in rows:
        print(json.dumps(row),flush=True)


if __name__ == '__main__':
    main()
