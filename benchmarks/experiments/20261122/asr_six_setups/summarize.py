import json
from pathlib import Path
import re
from statistics import median
import sys

OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(OUT / 'support'))
from benchmarks.metrics import edit_alignment, words


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def clean(text):
    return re.sub(r'#INC\b', '', re.sub(r'<SPOKEN_NOISE>', 'unknownspeech', text, flags=re.I), flags=re.I)


def present(text, phrase):
    query, cue = words(clean(text)), words(phrase)
    return any(query[start:start + len(cue)] == cue for start in range(len(query) - len(cue) + 1))


def main():
    data = read(OUT / 'dataset.json')
    totals = []
    labels = ['Parakeet NeMo, fixed cue hints', 'KeenASR Web SDK, full-passage graph',
              'Whisper Tiny English, CPU', 'Moonshine Medium, CPU',
              'Nemotron 160 ms, fixed cue hints', 'Nemotron 320 ms, fixed cue hints (experimental)']
    for profile, label in zip(data['profiles'], labels):
        scored = []
        for case in data['cases']:
            target = OUT / f'{profile}--{case["id"]}.json'
            if profile == 'keen-book':
                target = OUT / f'keen-book--{case["id"]}.json'
            if not target.exists():
                continue
            result = read(target)
            assert result['status'] == 'ok', (profile, case['id'], result)
            assert result['audio_sha256'] == case['audio_sha256']
            text = result['final_text']
            stats, _ = edit_alignment(case['reference'], clean(text))
            timing = read(OUT / f'timing--{case["id"]}.json')
            events_path = target.with_suffix('.events.jsonl')
            events = result.get('events') or [json.loads(line) for line in events_path.read_text(encoding='utf-8').splitlines()]
            updates = [event for event in events if event['kind'] == 'transcript']
            assert updates and updates[-1]['final']
            marks = []
            for cue in timing['cues']:
                if not cue['eligible']:
                    continue
                caught = present(text, cue['phrase'])
                last_absent = max((index for index, event in enumerate(updates)
                                   if not present(event['text'], cue['phrase'])), default=-1)
                arrival = updates[last_absent + 1]['wall_seconds'] if caught else None
                delay = arrival - cue['endpoint'] if arrival is not None and cue['endpoint'] is not None else None
                marks.append(dict(id=cue['id'], caught=caught, endpoint=cue['endpoint'], arrival=arrival, delay=delay))
            scored.append(dict(case=case['id'], reference_kind=case['reference_kind'], **stats, cues=marks))
        if not scored:
            print(profile, 'pending')
            continue
        spoken = [row for row in scored if row['reference_kind'] != 'supplied_passage']
        errors = sum(sum(row[key] for key in ('substitutions', 'deletions', 'insertions')) for row in spoken)
        denominator = sum(row['reference_words'] for row in spoken)
        cues = [cue for row in spoken for cue in row['cues']]
        delays = [cue['delay'] for cue in cues if cue['delay'] is not None]
        row = dict(profile=profile, label=label, recordings=len(scored), scored_recordings=len(spoken), word_errors=errors,
                   reference_words=denominator, wer_percent=100 * errors / denominator,
                   exact_cues=sum(cue['caught'] for cue in cues), eligible_cues=len(cues),
                   median_estimated_delay=median(delays) if delays else None, timed_cues=len(delays),
                   early_estimates=sum(delay < -.25 for delay in delays), recordings_detail=scored)
        totals.append(row)
        print(label, f'{len(scored)}/{len(data["cases"])} files', round(row['wer_percent'], 2),
              f'{row["exact_cues"]}/{len(cues)} cues', round(median(delays), 3) if delays else None, 'early', row['early_estimates'])
    if len(totals) == len(data['profiles']) and all(row['recordings'] == len(data['cases']) for row in totals):
        timed = [{(recording['case'], cue['id']): cue['delay']
                  for recording in row['recordings_detail']
                  if recording['reference_kind'] != 'supplied_passage'
                  for cue in recording['cues'] if cue['delay'] is not None}
                 for row in totals]
        common = set.intersection(*(set(cues) for cues in timed))
        assert common
        for row, cues in zip(totals, timed):
            row['shared_cue_median_estimated_delay'] = median(cues[key] for key in common)
            row['shared_timed_cues'] = len(common)
        target = OUT / 'comparison.json'
        target.write_text(json.dumps(dict(recordings=len(data['cases']), passages=13,
                                         scored_recordings=27, scored_passage_sections=9,
                                         reference_note='Scores use 24 provider manual transcripts with noise labels removed and three saved corpus spoken references. Four supplied-text checks are retained separately.',
                                         latency_note=data['latency'], clock_policy=data['clocks'],
                                         shared_timed_cues=len(common),
                                         rows=totals), indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
