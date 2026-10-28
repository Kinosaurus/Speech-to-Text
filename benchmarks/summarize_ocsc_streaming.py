"""Score the locally annotated OCSC streaming run without changing trackers."""
import json
import argparse
import re
from pathlib import Path

BASE = Path(__file__).resolve().parents[1] / 'output/ocsc'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--results', type=Path, default=BASE / 'results')
    args = parser.parse_args()
    results = json.loads((args.results / 'comparison.json').read_text())
    scored = []
    for row in results:
        events = [json.loads(line) for line in
                  (args.results / f"{row['id']}.events.jsonl").read_text().splitlines()]
        packets = [e for e in events if e['kind'] == 'audio']
        segments = [e for e in events if e['kind'] == 'segments']
        assert segments[-1]['segments'][-1]['completed']
        assert abs(segments[-1]['segments'][-1]['end'] - row['audio_seconds']) < .001
        log = (args.results / f"{row['id']}.log").read_text()
        app_triggers = re.findall(r'^\[TRIGGER\] (\S+):', log, flags=re.M)
        available = {e.get('mode') for e in events if e['kind'] == 'tracker'}
        app_mode = next(m for m in ('timely','boundary','split') if m in available)
        assert app_triggers == [t['scene'] for t in row['triggers'] if t['mode'] == app_mode]
        assert 'connection closed: 1000' in log.lower()
        for mode in ('original', 'split', 'boundary', 'timely'):
            if mode not in available:
                continue
            triggers = [t for t in row['triggers'] if t['mode'] == mode]
            seen = {t['scene'] for t in triggers}
            detail = []
            for trigger in triggers:
                scene = trigger['scene']
                if scene not in row['expected']:
                    continue
                expected = row['expected'][scene]
                sample = expected * 16000
                packet = next(e for e in packets
                              if e['sample_start'] + e['sample_count'] >= sample)
                # Map the approximate source boundary to the sender's actual
                # clock, interpolating within its <=256 ms packet. This removes
                # accumulated sleep/scheduling drift, not recognizer latency.
                boundary_wall = packet['wall'] + (sample-packet['sample_start'])/16000
                delay = packets[0]['wall'] + trigger['arrival_seconds'] - boundary_wall
                detail.append(dict(scene=scene, source_boundary_seconds=expected,
                                   arrival_seconds=trigger['arrival_seconds'],
                                   delay_from_streamed_boundary_seconds=delay,
                                   delay_from_nominal_source_seconds=trigger['arrival_seconds']-expected))
            scored.append(dict(id=row['id'], mode=mode, reached=len(row['expected']),
                               caught=len(seen & row['expected'].keys()),
                               missed=sorted(row['expected'].keys()-seen),
                               unexpected=sorted(seen-row['expected'].keys()),
                               duplicates=len(triggers)-len(seen), timing=detail))
    (args.results / 'scored.json').write_text(json.dumps(scored, indent=2))
    print(json.dumps(scored, indent=2))


if __name__ == '__main__':
    main()
