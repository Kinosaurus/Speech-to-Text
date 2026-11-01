"""Audit guarded fresh streams without calling suppressed effects successes."""
import argparse
import csv
import hashlib
import html
import json
from pathlib import Path
import re
import statistics
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from benchmarks.annotate_mps_timing import boundary_wall
import soundfile as sf
LIB = ROOT / 'recordings/library'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def audit_stream(stem, audio):
    events = [json.loads(line) for line in stem.with_suffix('.events.jsonl').read_text(encoding='utf-8').splitlines()]
    packets = [e for e in events if e['kind'] == 'audio']
    frame = 0
    for packet in packets:
        assert packet['sample_start'] == frame
        frame += packet['sample_count']
    info = sf.info(audio)
    assert info.samplerate == 16000 and info.channels == 1 and frame == info.frames
    segments = [e for e in events if e['kind'] == 'segments']
    assert segments and segments[0]['wall'] < packets[-1]['wall']
    assert any(e['kind'] == 'end_of_audio' for e in events)
    assert any(e['kind'] == 'status' and e.get('message') == 'STREAM_DONE' for e in events)
    assert not any(e['kind'] == 'status' and e.get('status') == 'ERROR' for e in events)
    assert segments[-1]['segments'][-1]['completed']
    assert abs(float(segments[-1]['segments'][-1]['end']) - info.duration) < .001
    return events, packets, info


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    assert output.is_relative_to(ROOT / 'output')
    protocol = read(output / 'protocol.json')
    assert read(output / 'completed.json')['source_unchanged']
    for name, digest in protocol['source_sha256'].items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest, name
    endpoints = {}
    for folder in ('live-2026-10-29-verified', 'published-passages-live-2026-10-30'):
        for point in read(LIB / 'evaluation' / folder / 'estimated_delays.json')['checkpoints']:
            endpoints[point['audio_id'], point['id']] = point['estimated_end_seconds']
    for row in read(ROOT / 'output/mps-expansion-2026-11-02/summary.json')['recordings']:
        for point in row['checkpoints']:
            if point['estimated_endpoint_seconds'] is not None:
                endpoints[row['audio_id'], point['id']] = point['estimated_endpoint_seconds']
    rows = []
    review_cards = []
    review_rows = []
    review = output / 'review'
    review.mkdir(exist_ok=True)
    jobs = read(output / 'jobs.json')
    for job in jobs:
        stem = output / job['group'] / job['id']
        assert hashlib.sha256(Path(job['audio']).read_bytes()).hexdigest() == job['audio_sha256']
        assert hashlib.sha256(Path(job['manifest']).read_bytes()).hexdigest() == job['manifest_sha256']
        events, packets, info = audit_stream(stem, job['audio'])
        manifest = read(Path(job['manifest']))
        current = [e for e in events if e['kind'] == 'tracker' and e['mode'] == 'timely']
        emitted = [e for e in current if e['triggered']]
        suppressed = [e for e in current if e.get('suppressed')]
        ids = [str(cp['id']) for cp in manifest['checkpoints']]
        emitted_ids = [e['scene'] for e in emitted]
        suppressed_ids = [e['scene'] for e in suppressed]
        skipped_ids = {i for e in current for i in e['skipped']}
        assert set(emitted_ids).isdisjoint(suppressed_ids)
        assert len(set(emitted_ids)) == len(emitted_ids) and len(set(suppressed_ids)) == len(suppressed_ids)
        assert not (set(emitted_ids + suppressed_ids) - set(ids))
        log = stem.with_suffix('.log').read_text(encoding='utf-8')
        assert re.findall(r'^\[TRIGGER\] (\S+):', log, re.M) == emitted_ids
        assert re.findall(r'^\[SUPPRESSED\] (\S+):', log, re.M) == suppressed_ids
        baseline_stem = Path(job['baseline']) / job['id']
        old = [json.loads(s) for s in baseline_stem.with_suffix('.events.jsonl').read_text(encoding='utf-8').splitlines()]
        old_triggers = [e for e in old if e['kind'] == 'tracker' and e['mode'] == 'timely' and e['triggered']]
        old_packets = [e for e in old if e['kind'] == 'audio']
        details = []
        for cp in manifest['checkpoints']:
            ident = cp['id']
            emitted_event = next((e for e in emitted if e['scene'] == ident), None)
            suppressed_event = next((e for e in suppressed if e['scene'] == ident), None)
            old_event = next((e for e in old_triggers if e['scene'] == ident), None)
            endpoint = endpoints.get((job['id'], ident))
            new_delay = emitted_event['wall'] - boundary_wall(packets, endpoint, 16000) if emitted_event and endpoint is not None else None
            old_delay = old_event['wall'] - boundary_wall(old_packets, endpoint, 16000) if old_event and endpoint is not None else None
            details.append(dict(id=ident, effect_policy=cp['effect_policy'], required_words=cp.get('required_words', []),
                emitted=bool(emitted_event), suppressed=bool(suppressed_event), baseline_emitted=bool(old_event),
                suppression_reason=suppressed_event.get('suppression_reason') if suppressed_event else None,
                estimated_endpoint_seconds=endpoint, estimated_delay_seconds=new_delay,
                baseline_estimated_delay_seconds=old_delay,
                new_minus_baseline_seconds=new_delay-old_delay if new_delay is not None and old_delay is not None else None,
                manually_verified=False))
            if suppressed_event or (old_event and not emitted_event) or (job['id'] == '5a21k_EN-OL-RC-538_2' and ident == 'damaged_wing'):
                focus = suppressed_event or emitted_event
                if endpoint is not None:
                    start = max(0, endpoint-6)
                    end = min(info.duration, max(endpoint+3, (focus['audio_end']+2) if focus else endpoint+3))
                else:
                    end = min(info.duration, (focus['audio_end']+2) if focus else info.duration)
                    start = max(0, end-16)
                data, rate = sf.read(job['audio'], start=round(start*16000), stop=round(end*16000), dtype='int16')
                clip = review / f'{job["id"]}.{ident}.wav'
                sf.write(clip, data, rate, subtype='PCM_16')
                at = next((e for e in reversed(events) if e['kind']=='segments' and focus and e['wall'] <= focus['wall']), None)
                text = ' '.join(s['text'] for s in at['segments']) if at else ''
                disposition = 'suppressed' if suppressed_event else ('emitted' if emitted_event else 'unreached/skipped')
                review_rows.append(dict(recording=job['id'], checkpoint=ident, automated_status=disposition,
                    clip=clip.name, clip_start_seconds=start, human_spoken_anchor='', human_should_emit='',
                    human_word_end_seconds='', reviewer='', date='', notes=''))
                review_cards.append('<article><h2>'+html.escape(job['id']+' / '+ident)+'</h2><p>'+html.escape(cp['checkpoint_text'])+
                    '</p><p>Current: '+disposition+'; baseline emitted: '+str(bool(old_event))+
                    '; required words: '+html.escape(', '.join(cp.get('required_words', [])) or '(endpoint and phrase support)')+
                    '</p><audio controls preload="none" src="'+clip.name+'"></audio><p>Context window starts at '+
                    f'{start:.3f}s in the original WAV. Not a human word alignment.</p><details><summary>Current recognition at the decision</summary><p>'+
                    html.escape(text)+'</p></details></article>')
        rows.append(dict(id=job['id'], group=job['group'], configured=len(ids),
            audio_sha256=job['audio_sha256'], original_manifest_sha256=job['original_manifest_sha256'],
            policy_manifest_sha256=job['manifest_sha256'], emitted=emitted_ids, suppressed=suppressed_ids,
            unreached=sorted(set(ids)-set(emitted_ids+suppressed_ids)-skipped_ids),
            skipped=sorted(skipped_ids),
            baseline_emitted=[e['scene'] for e in old_triggers], checkpoints=details,
            samples_delivered=info.frames, audio_seconds=info.duration, delivery_audit_pass=True,
            app_observer_agreement=True, progress_completed='[CHECKPOINTS] All story checkpoints completed.' in log,
            first_asr_seconds=next(e['wall'] for e in events if e['kind']=='segments')-packets[0]['wall'],
            maximum_matcher_compute_ms=max(e['compute_seconds'] for e in current)*1000))
    controls = []
    for name in ('dog', 'dragon', 'nickel', 'recording_2'):
        stem = output / 'controls' / (name + '-control')
        audio = LIB / f'stories/{name}/readers/{name}/audio.wav'
        events, packets, info = audit_stream(stem, audio)
        tracker = [e for e in events if e['kind'] == 'tracker']
        current = [e for e in tracker if e['mode'] == 'timely']
        controls.append(dict(id=name, manifest_comparisons=len({e['book'] for e in current}),
            current_effects=sum(e['triggered'] for e in current),
            current_suppressions=sum(e.get('suppressed', False) for e in current),
            all_observer_effects=sum(e['triggered'] for e in tracker), delivery_audit_pass=True))
    groups = {}
    for group in ('original', 'expansion'):
        subset = [r for r in rows if r['group'] == group]
        delays = [p['estimated_delay_seconds'] for r in subset for p in r['checkpoints'] if p['estimated_delay_seconds'] is not None]
        groups[group] = dict(recordings=len(subset), configured=sum(r['configured'] for r in subset),
            emitted=sum(len(r['emitted']) for r in subset), suppressed=sum(len(r['suppressed']) for r in subset),
            skipped=sum(len(r['skipped']) for r in subset), unreached=sum(len(r['unreached']) for r in subset),
            baseline_emitted=sum(len(r['baseline_emitted']) for r in subset),
            estimated_delay_count=len(delays), median_estimated_delay_seconds=statistics.median(delays) if delays else None)
    result = dict(date='2026-11-02', configuration=protocol['configuration'], effect_policy=protocol['effect_policy'],
        source_sha256=protocol['source_sha256'], analysis_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        groups=groups, recordings=rows, controls=controls,
        control_totals=dict(streams=4, manifest_comparisons=sum(c['manifest_comparisons'] for c in controls),
            emitted=sum(c['current_effects'] for c in controls), suppressed=sum(c['current_suppressions'] for c in controls),
            all_observer_effects=sum(c['all_observer_effects'] for c in controls)),
        timing_status='Previously frozen automatic acoustic endpoints mapped to fresh packet clocks; not human gold.',
        comparison_limits='Fresh ASR may differ. Effect permission semantics and the authored hibernate requirement changed; raw activation counts are not accuracy.',
        country_limits='India and earlier non-Singapore development recordings; no Singapore microphone trial.')
    write = lambda p, d: p.write_text(json.dumps(d, indent=2) + '\n', encoding='utf-8')
    write(output / 'summary.json', result)
    if review_rows:
        with (review / 'manual_review.csv').open('w', encoding='utf-8', newline='') as file:
            writer = csv.DictWriter(file, fieldnames=list(review_rows[0]))
            writer.writeheader(); writer.writerows(review_rows)
        (review / 'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Guarded effect review</title>'
            '<style>body{max-width:950px;margin:35px auto;padding:0 20px;font:17px/1.6 system-ui}article{border-top:2px solid #ddd;margin-top:35px}audio{width:100%}</style>'
            '<h1>Guarded effects: listening handoff</h1><p>Actual source recordings and automated decisions. '
            'Human listening and word timings remain unverified. Suppressed effects are not counted as successes. '
            'Use manual_review.csv for independent listening decisions.</p>'+''.join(review_cards), encoding='utf-8')
    print(json.dumps(groups, indent=2))
    print(json.dumps(result['control_totals'], indent=2))


if __name__ == '__main__':
    main()
