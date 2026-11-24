"""Local digital-output scoring; never substitutes a successful send for sound.

Synthetic word endings are estimates from SAPI phoneme timing, checked against
the waveform. Clock interpolation uses native frame timestamps, not ADB timing.
"""
import argparse
import csv
import json
from pathlib import Path
import statistics
import wave

import av
import numpy as np
from scipy.signal import fftconvolve, find_peaks, resample_poly

from books_to_life.matching.checkpoint_matcher import normalize_text


def decode(path, rate=16000):
    resampler = av.AudioResampler(format='flt', layout='mono', rate=rate)
    chunks = []
    with av.open(str(path)) as source:
        for frame in source.decode(audio=0):
            chunks.extend(x.to_ndarray().flatten() for x in resampler.resample(frame))
        chunks.extend(x.to_ndarray().flatten() for x in resampler.resample(None))
    return np.concatenate(chunks).astype(np.float64)


def clock(events, kind):
    rows = [e for e in events if e['kind'] == kind and e.get('nano', 0) > 0]
    # The same native timestamp can be returned on consecutive polls.
    rows = list({e['frame']: e for e in rows}.values())
    rows.sort(key=lambda e: e['frame'])
    return np.array([e['frame'] for e in rows]), np.array([e['nano'] / 1e9 for e in rows])


def frame_time(frame, pair):
    frames, seconds = pair
    if frame < frames[0] or frame > frames[-1]:
        raise ValueError('Requested sample outside native clock evidence')
    return float(np.interp(frame, frames, seconds))


def timed_words(prefix):
    data = json.loads(prefix.with_suffix('.marks.json').read_text(encoding='utf-8-sig'))
    words = [e for e in data['Marks'] if e['Kind'] == 'word_start']
    phones = [e for e in data['Marks'] if e['Kind'] == 'phoneme' and e['Text'] != '\x07']
    with wave.open(str(prefix.with_suffix('.wav'))) as wav:
        signal = np.frombuffer(wav.readframes(wav.getnframes()), dtype='<i2')
        rate = wav.getframerate()
    result = []
    for i, word in enumerate(words):
        start = word['AudioSeconds']
        following = words[i + 1]['AudioSeconds'] if i + 1 < len(words) else len(signal) / rate
        ends = [p['AudioSeconds'] + p['DurationSeconds'] for p in phones
                if start - .001 <= p['AudioSeconds'] < following - .001]
        end = max(ends) if ends else following
        # Audit the final nontrivial waveform sample within this word's interval.
        lo, hi = round(start * rate), min(round(following * rate), len(signal))
        active = np.flatnonzero(np.abs(signal[lo:hi].astype(np.int32)) > 40)
        acoustic_end = (lo + int(active[-1]) + 1) / rate if len(active) else None
        result.append(dict(text=normalize_text(word['Text']), start=start, end=end,
                           acoustic_end_estimate=acoustic_end))
    return result


def anchor_interval(words, anchor):
    wanted = normalize_text(anchor).split()
    tokens = [w['text'] for w in words]
    matches = [i for i in range(len(tokens) - len(wanted) + 1)
               if tokens[i:i + len(wanted)] == wanted]
    if len(matches) != 1:
        raise ValueError(f'Anchor must occur once in synthetic reference: {anchor}')
    i = matches[0]
    return words[i]['start'], words[i + len(wanted) - 1]['end']


def template_matches(signal, template, threshold=.55):
    template = template - template.mean()
    n = len(template)
    correlation = fftconvolve(signal, template[::-1], mode='valid')
    energy = fftconvolve(signal * signal, np.ones(n), mode='valid')
    ncc = correlation / np.sqrt(np.maximum(energy, 1e-18) * np.sum(template * template))
    peaks, _ = find_peaks(ncc, height=threshold, distance=16000)
    # A signal must remain distinguishable from the next-highest occurrence.
    return sorted([(int(i), float(ncc[i])) for i in peaks], key=lambda x: x[1], reverse=True)


def audible_offset(signal, rate=16000):
    n = rate // 100
    blocks = signal[:len(signal) // n * n].reshape(-1, n)
    rms = np.sqrt(np.mean(blocks * blocks, axis=1))
    threshold = max(.0001, float(rms.max()) * .01)
    indices = np.flatnonzero((rms[:-1] > threshold) & (rms[1:] > threshold))
    if not len(indices):
        raise ValueError('Template has no audible digital signal')
    return int(indices[0]) * n / rate


def score_readmio(root, trial, prefix):
    events = [json.loads(line) for line in (trial / 'clocks.jsonl').read_text(encoding='utf-8').splitlines()]
    source_clock, output_clock = clock(events, 'source_clock'), clock(events, 'output_clock')
    first = next(e['first_frame'] for e in events if e['kind'] == 'source_start')
    last = next(e['last_frame'] for e in events if e['kind'] == 'source_eof')
    elapsed = frame_time(last, source_clock) - frame_time(first, source_clock)
    words = timed_words(prefix)
    output = np.fromfile(trial / 'output.pcm', dtype='<i2').reshape(-1, 2).mean(axis=1) / 32768
    output = resample_poly(output, 1, 3)
    cues = json.loads((root / 'readmio-predeclared-cues.json').read_text())['expected_events']
    rows = []
    for cue in cues:
        template = decode(cue['sound_file'])
        matches = template_matches(output, template)
        start, end = anchor_interval(words, cue['anchor'])
        phrase_start = frame_time(first + start * 48000, source_clock)
        phrase_end = frame_time(first + end * 48000, source_clock)
        candidates = []
        for position, similarity in matches:
            onset = frame_time((position / 16000 + audible_offset(template)) * 48000, output_clock)
            # Count only a corresponding response while/after the highlighted phrase.
            if phrase_start - .25 <= onset <= phrase_end + 5:
                candidates.append((position, similarity, onset))
        match = max(candidates, key=lambda item: item[1]) if candidates else None
        rows.append(dict(id=cue['id'], anchor=cue['anchor'], hit=match is not None,
                         similarity=match[1] if match else None,
                         source_phrase_start_seconds=start, source_phrase_end_seconds=end,
                         output_template_start_seconds=match[0] / 16000 if match else None,
                         effect_delay_seconds=match[2] - phrase_end if match else None,
                         detected_candidate_count=len(candidates)))
    hits = [r for r in rows if r['hit']]
    summary = dict(status='exploratory_calibration_not_frozen_holdout',
                   input_kind='local synthetic speech; Microsoft David Desktop',
                   metric='digital sound onset minus estimated highlighted phrase ending',
                   median_effect_delay_seconds=statistics.median(r['effect_delay_seconds'] for r in hits) if hits else None,
                   checkpoints_hit=len(hits), expected_checkpoints=len(rows),
                   ideal_input_seconds=(last - first) / 48000, measured_input_seconds=elapsed,
                   detector=dict(method='normalized correlation with official sound assets', threshold=.55),
                   negative_delay='sound began before the highlighted phrase finished', events=rows)
    (trial / 'score.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
    with (trial / 'events.csv').open('w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys()); writer.writeheader(); writer.writerows(rows)
    return summary


def score_pod(root, trial, prefix, manifest=None):
    from benchmarks.metrics import edit_alignment
    result = json.loads((trial / 'result.json').read_text(encoding='utf-8'))
    updates = [json.loads(l) for l in (trial / 'recognition.events.jsonl').read_text(encoding='utf-8').splitlines()]
    final = [e for e in updates if e['kind'] == 'transcript' and e['final']]
    eof = [e for e in updates if e['kind'] == 'end_of_audio']
    if len(final) != 1 or len(eof) != 1 or result['capture_exit_code'] != 0:
        raise ValueError('Incomplete recognition/capture; cannot score output')
    if eof[0]['samples'] != round((result['source_seconds'] + 3) * 16000):
        raise ValueError('Source sample count mismatch')
    stamps = [json.loads(l) for l in (trial / 'windows-output.jsonl').read_text(encoding='utf-8').splitlines()]
    packet_clock = (np.array([e['file_frame'] for e in stamps]),
                    np.array([e['qpc_100ns'] / 1e7 for e in stamps]))
    output = np.fromfile(trial / 'windows-output.pcm', dtype='<i2').reshape(-1, 2).mean(axis=1) / 32768
    output = resample_poly(output, 160, 441)
    if manifest is None:
        cues = json.loads((root / 'readmio-predeclared-cues.json').read_text())['expected_events']
        reference = Path('benchmarks/product_comparison/readmio_lion_excerpt.txt').read_text(encoding='utf-8')
    else:
        book = json.loads(manifest.read_text(encoding='utf-8'))
        cues = [dict(id=cp['id'],anchor=cp['checkpoint_text'],sound_file=cp['effect']['sound'])
                for cp in book['checkpoints']]
        reference = '\n'.join(page['text'] for page in book['pages'])
    words = timed_words(prefix)
    rows = []
    for cue in cues:
        template = decode(cue['sound_file'])
        start, end = anchor_interval(words, cue['anchor'])
        candidates = []
        for position, similarity in template_matches(output, template):
            frame = (position / 16000 + audible_offset(template)) * 44100
            onset = frame_time(frame, packet_clock) - result['source_origin_qpc_seconds']
            if start - .25 <= onset <= end + 5:
                candidates.append((position, similarity, onset))
        match = max(candidates, key=lambda x: x[1]) if candidates else None
        callbacks = [e for e in result['cue_events'] if e['id'] == cue['id']]
        rows.append(dict(id=cue['id'], anchor=cue['anchor'], hit=match is not None,
                         similarity=match[1] if match else None,
                         source_phrase_end_seconds=end,
                         effect_delay_seconds=match[2] - end if match else None,
                         matcher_callback_delay_seconds=callbacks[0]['callback_seconds'] - end if callbacks else None,
                         detected_candidate_count=len(candidates)))
    hits = [e for e in rows if e['hit']]
    wer, _ = edit_alignment(reference, final[0]['text'])
    summary = dict(status='captured_output_verified',
                   original_runner_status=result['status'],
                   report_recovered_after_error=result.get('error'),
                   checkpoints_hit=len(hits),expected_checkpoints=len(rows),
                   median_effect_delay_seconds=statistics.median(e['effect_delay_seconds'] for e in hits) if hits else None,
                   estimated_synthetic_wer=wer,events=rows,
                   output_capture='actual process-only Windows loopback',
                   physical_endpoint_original_mute_restored=result['physical_endpoint_original_mute_restored'])
    (trial / 'score.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
    with (trial / 'events.csv').open('w',newline='',encoding='utf-8-sig') as f:
        writer=csv.DictWriter(f,fieldnames=rows[0].keys());writer.writeheader();writer.writerows(rows)
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--trial', type=Path, required=True)
    parser.add_argument('--source-prefix', type=Path, required=True)
    parser.add_argument('--pod', action='store_true')
    parser.add_argument('--manifest', type=Path)
    args = parser.parse_args()
    score = (score_pod(args.root,args.trial,args.source_prefix,args.manifest) if args.pod
             else score_readmio(args.root,args.trial,args.source_prefix))
    print(json.dumps(score, indent=2))
