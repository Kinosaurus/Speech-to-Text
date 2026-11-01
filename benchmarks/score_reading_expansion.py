"""Audit fresh reading streams and create a local acoustic-review report.

Acoustic estimates are optional and never labelled human-verified timestamps.
Raw passages/transcripts/review clips remain in ignored local directories.
"""
import argparse
import csv
import hashlib
import html
import json
import os
from pathlib import Path
import re
import statistics
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from benchmarks.annotate_mps_timing import boundary_wall, locate
import soundfile as sf

LIB = ROOT / 'recordings/library'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def link(path, base):
    return os.path.relpath(path, base).replace('\\', '/')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--batch', type=Path, default=ROOT / 'output/mps-expansion-2026-11-02')
    args = parser.parse_args()
    batch = args.batch.resolve()
    if not batch.is_relative_to(ROOT / 'output'):
        parser.error('Keep corpus reports within ignored output/.')
    evaluation = batch / 'evaluation'
    protocol = read(evaluation / 'protocol.json')
    for name, digest in protocol['source_sha256'].items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest, name
    jobs = read(batch / 'jobs.json')['recordings']
    by_id = {r['audio_id']: r for r in jobs}
    live = read(evaluation / 'live/comparison.json')['recordings']
    assert {r['audio_id'] for r in live} == by_id.keys()
    review = batch / 'review'
    review.mkdir(exist_ok=True)
    cards = []
    scored = []
    review_rows = []
    index = ['# Additional child readings: local audio, passages and tests', '',
        '**Country: India, not Southeast Asia.** Six new reader IDs; individual ages unknown. '
        'Each WAV is a real provider recording. Original passage and child transcript are separate.', '',
        '[Open the listening and checkpoint review](review/index.html). '
        'Automatic endpoints are provisional, not human gold.', '',
        '| Reader / recording | Grade | Audio | Original passage | Checkpoints | Activated / configured |',
        '| --- | ---: | --- | --- | --- | ---: |']
    for row in live:
        job = by_id[row['audio_id']]
        folder = LIB / job['path']
        stem = evaluation / 'live' / row['audio_id']
        assert row['audio_sha256'] == job['audio_sha256']
        assert row['manifest_sha256'] == job['manifest_sha256']
        assert hashlib.sha256((folder / 'audio.wav').read_bytes()).hexdigest() == job['audio_sha256']
        manifest = read(stem.with_suffix('.checkpoints.json'))
        evidence = read(folder / 'checkpoint_evidence.json')
        events = [json.loads(line) for line in stem.with_suffix('.events.jsonl').read_text(encoding='utf-8').splitlines()]
        packets = [e for e in events if e['kind'] == 'audio']
        frame = 0
        for packet in packets:
            assert packet['sample_start'] == frame
            frame += packet['sample_count']
        audio, rate = sf.read(folder / 'audio.wav', dtype='int16')
        assert frame == len(audio) == row['samples_sent']
        assert row['stream_done'] and row['partial_before_eof']
        actual = row['observers']['timely']
        triggers = [e for e in events if e['kind'] == 'tracker' and e['mode'] == 'timely' and e['triggered']]
        printed = re.findall(r'^\[TRIGGER\] (\S+):', stem.with_suffix('.log').read_text(encoding='utf-8', errors='replace'), flags=re.M)
        assert printed == actual['triggered'] == [t['scene'] for t in triggers]
        models = {}
        for model in ('small.en', 'medium.en'):
            path = batch / 'acoustic' / f'{row["audio_id"]}.{model}.json'
            if path.exists():
                data = read(path)
                assert data['audio_sha256'] == row['audio_sha256']
                assert data['initial_prompt'] is None and data['hotwords'] is None
                models[model] = data
        details = []
        previous = {}
        checkpoint_cards = []
        for cp in manifest['checkpoints']:
            matches = {}
            flags = []
            for name, data in models.items():
                try:
                    found = locate(cp, data['words'])
                    if found['end'] <= previous.get(name, -1):
                        flags.append(name + ': non-increasing endpoint; excluded')
                        continue
                    previous[name] = found['end']
                    matches[name] = found
                except AssertionError:
                    flags.append(name + ': anchor could not be located')
            support = evidence[cp['id']]
            if support.get('substitutions', 0) or support.get('deletions', 0):
                flags.append('Provider reports a reading substitution/deletion in this anchor')
            trigger = next((t for t in triggers if t['scene'] == cp['id']), None)
            endpoint = None
            delay = None
            if len(matches) == 2:
                ends = [m['end'] for m in matches.values()]
                assert all(0 < e <= len(audio) / rate for e in ends)
                endpoint = statistics.median(ends)
                if max(ends) - min(ends) > .35:
                    flags.append('Model endpoint disagreement over 350 ms')
                if any(not m['exact_endpoint'] for m in matches.values()):
                    flags.append('Recognized endpoint differs from printed endpoint')
                if any(m['match_score'] < 90 for m in matches.values()):
                    flags.append('At least one acoustic anchor score below 90')
                if any(m['endpoint_word'].get('probability', 0) < .6 for m in matches.values()):
                    flags.append('Low endpoint recognition probability')
                if trigger:
                    delay = trigger['wall'] - boundary_wall(packets, endpoint, rate)
                    if delay < -.2:
                        flags.append('Activation precedes estimated endpoint by over 200 ms')
            else:
                flags.append('No two-model endpoint; latency unscored')
            item = dict(id=cp['id'], triggered=trigger is not None,
                estimated_endpoint_seconds=endpoint, estimated_delay_seconds=delay,
                manual_verification=False, review_flags=flags,
                provider_counts={k: support.get(k) for k in ('correct', 'substitutions', 'deletions')},
                model_matches=matches)
            if matches:
                start = max(0, min(m['start'] for m in matches.values()) - 1.5)
                end = min(len(audio) / rate, max(m['end'] for m in matches.values()) + 2)
                clip = review / f'{row["audio_id"]}.{cp["id"]}.wav'
                sf.write(clip, audio[round(start * rate):round(end * rate)], rate, subtype='PCM_16')
                item.update(review_clip=clip.name, clip_start_seconds=start,
                            endpoint_in_clip_seconds=endpoint - start if endpoint is not None else None)
                player = f'<audio controls preload="none" src="{html.escape(clip.name)}"></audio>'
            else:
                player = '<p>Use the full recording; no endpoint clip can be justified.</p>'
            checkpoint_cards.append('<section><h3>' + html.escape(cp['id']) + '</h3><p>' +
                html.escape(cp['checkpoint_text']) + '</p><p>Activated: ' + str(item['triggered']) +
                '; estimated endpoint: ' + (f'{endpoint:.3f}s' if endpoint is not None else 'unscored') +
                '; estimated delay: ' + (f'{delay:.3f}s' if delay is not None else 'unscored') +
                '</p>' + player + '<p>' + html.escape('; '.join(flags) or 'No extra automatic flags; still not manually verified.') + '</p></section>')
            details.append(item)
            review_rows.append(dict(audio_id=row['audio_id'], checkpoint=cp['id'],
                clip=item.get('review_clip', ''), clip_start_seconds=item.get('clip_start_seconds', ''),
                estimated_endpoint_seconds=endpoint if endpoint is not None else '',
                automatic_flags='; '.join(flags),
                human_endpoint_seconds='', spoken_anchor_status='', expected_effect='',
                reviewer='', review_date='', notes=''))
        write(folder / 'expansion_checkpoint_review.json', dict(manual_verification=False,
            method='Independent no-prompt small.en and medium.en acoustic estimates; not temporal gold', checkpoints=details))
        public_points = [{k: v for k, v in item.items() if k not in ('model_matches', 'review_clip')} for item in details]
        scored.append(dict(audio_id=row['audio_id'], reader=job['reader'], grade=job['grade'],
            gender=job['gender'], age_years=None, country='India', audio_seconds=row['audio_seconds'],
            audio_sha256=row['audio_sha256'], manifest_sha256=row['manifest_sha256'],
            configured=len(manifest['checkpoints']), triggered=len(actual['triggered']),
            missing=actual['missing'], unexpected=actual['unexpected'], duplicates=actual['duplicate_triggers'],
            first_asr_seconds=row['first_asr_seconds'], application_agreement=True,
            all_samples_delivered=True, partial_before_eof=True, stream_done=True,
            observer_counts={name: len(data['triggered']) for name, data in row['observers'].items()}, checkpoints=public_points))
        index.append(f'| {row["audio_id"]} | {job["grade"]} | [Play]({link(folder / "audio.wav", batch)}) | '
            f'[Passage]({link(folder / "passage.txt", batch)}) | [Manifest]({link(folder / "checkpoints.json", batch)}) | '
            f'{len(actual["triggered"])}/{len(manifest["checkpoints"])} |')
        cards.append('<article><h2>' + html.escape(row['audio_id']) + '</h2><p>India; Grade ' + str(job['grade']) +
            '; age unknown. Provider transcript is not the printed passage.</p><audio controls preload="none" src="' +
            html.escape(link(folder / 'audio.wav', review)) + '"></audio><details><summary>Original written passage</summary><p>' +
            html.escape((folder / 'passage.txt').read_text(encoding='utf-8')) +
            '</p></details><details><summary>Provider spoken transcript</summary><p>' +
            html.escape((folder / 'transcript.txt').read_text(encoding='utf-8')) + '</p></details>' + ''.join(checkpoint_cards) + '</article>')
    controls = read(evaluation / 'controls/results.json')
    points = [p for r in scored for p in r['checkpoints']]
    delays = [p['estimated_delay_seconds'] for p in points if p['estimated_delay_seconds'] is not None]
    result = dict(date='2026-11-02', country='India', regional_status='South Asian fallback; not Singapore/SEA validation',
        configuration=protocol['configuration'], selection=protocol['selection'],
        source_sha256=protocol['source_sha256'], analysis_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        manual_timing_verification=False, recordings=scored,
        aggregate=dict(readers=len({r['reader'] for r in scored}), recordings=len(scored),
            audio_seconds=sum(r['audio_seconds'] for r in scored), configured=len(points),
            triggered=sum(r['triggered'] for r in scored), unexpected=sum(len(r['unexpected']) for r in scored),
            duplicate_recordings=sum(r['duplicates'] for r in scored),
            estimated_latency_count=len(delays), median_estimated_delay_seconds=statistics.median(delays) if delays else None,
            min_estimated_delay_seconds=min(delays) if delays else None, max_estimated_delay_seconds=max(delays) if delays else None,
            checkpoints_needing_review=sum(bool(p['review_flags']) for p in points),
            provider_deviating_anchors=sum(bool(p['provider_counts']['substitutions'] or p['provider_counts']['deletions']) for p in points)),
        controls=dict(recordings=len(controls), manifest_comparisons=sum(len(r['manifests']) for r in controls),
            current_triggers=sum(t['mode'] == 'timely' for r in controls for t in r['triggers']),
            all_observer_triggers=sum(len(r['triggers']) for r in controls)))
    write(batch / 'summary.json', result)
    with (review / 'manual_review.csv').open('w', encoding='utf-8', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=list(review_rows[0]))
        writer.writeheader()
        writer.writerows(review_rows)
    (batch / 'INDEX.md').write_text('\n'.join(index) + '\n', encoding='utf-8')
    (review / 'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Child reading review</title>'
        '<style>body{max-width:950px;margin:35px auto;padding:0 20px;font:17px/1.6 system-ui;color:#17212d}'
        'article{border-top:2px solid #ccc;margin-top:40px}section{padding:12px 20px;background:#f3f5f7;margin:12px 0}'
        'audio{width:100%}summary{cursor:pointer}h3{margin:0}</style>'
        '<h1>Additional child-reading tests</h1><p><b>India, not Singapore or Southeast Asia.</b> '
        'Real child audio, original provider passages, fixed checkpoints. Automatic endpoints require listening review; '
        'none is manually verified. No ASR tuning was performed after testing.</p>' + ''.join(cards), encoding='utf-8')
    print(json.dumps(result['aggregate'], indent=2))
    print(json.dumps(result['controls'], indent=2))


if __name__ == '__main__':
    main()
