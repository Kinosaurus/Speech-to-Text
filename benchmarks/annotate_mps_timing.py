"""Estimate MPS checkpoint ends acoustically and score a frozen live run.

Needs no-prompt small.en/medium.en word-timing JSONs in output/mps/acoustic-
timing-2026-10-29. Same-family model agreement is not manual verification.
"""
import hashlib
import json
from pathlib import Path
import shutil
import statistics
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from checkpoint_matcher import normalize_text, fuzz
import soundfile as sf

LIB=ROOT/'recordings/library'
ACOUSTIC=ROOT/'output/mps/acoustic-timing-2026-10-29'
RUN=LIB/'evaluation/live-2026-10-29-verified'
REVIEW=LIB/'reviews/mps_timestamps'
METHOD='No-prompt faster-whisper small.en and medium.en CUDA float16 word estimates; median endpoint. Automatic, not manually verified.'

def write(path,data):
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

def locate(checkpoint,words):
    tokens=[]
    indices=[]
    for i,word in enumerate(words):
        parts=normalize_text(word['word']).split()
        tokens.extend(parts)
        indices.extend([i]*len(parts))
    anchor=normalize_text(checkpoint['checkpoint_text']).split()
    choices=[]
    for size in range(max(3,len(anchor)-2),len(anchor)+3):
        for start in range(len(tokens)-size+1):
            end=start+size
            # Constrain to a supported endpoint, not merely a similar prefix.
            if fuzz.ratio(tokens[end-1],anchor[-1])<75:
                continue
            score=fuzz.ratio(' '.join(tokens[start:end]),' '.join(anchor))
            choices.append((score,start,end))
    choices.sort(reverse=True)
    assert choices and choices[0][0]>=80,(checkpoint['id'],choices[:3])
    score,start,end=choices[0]
    first,last=indices[start],indices[end-1]
    return dict(start=words[first]['start'],end=words[last]['end'],match_score=score,
                recognized_phrase=' '.join(tokens[start:end]),endpoint_word=words[last],
                exact_endpoint=normalize_text(words[last]['word'])==anchor[-1],
                endpoint_index=last)

def boundary_wall(packets,seconds,rate):
    sample=seconds*rate
    for packet in packets:
        if packet['sample_start']<=sample<=packet['sample_start']+packet['sample_count']:
            return packet['wall']+(sample-packet['sample_start'])/rate
    raise ValueError(f'Endpoint outside sent audio: {seconds}')

def main():
    REVIEW.mkdir(parents=True,exist_ok=True)
    comparison=json.loads((RUN/'comparison.json').read_text(encoding='utf-8'))
    imports=json.loads((LIB/'acquisition/mps/import_report.json').read_text(encoding='utf-8'))
    byid={r['audio_id']:r for r in imports['recordings']}
    scored=[]
    clip_lines=['# MPS checkpoint listening clips', '',
                'Each clip surrounds an automatically estimated checkpoint endpoint. Relative clip offsets are recorded in annotations.json. Listen to decide whether the endpoint and spoken-word interpretation need correction. None is manually verified.', '',
                '| Recording | Checkpoint | Audio excerpt | Estimated end in original |', '| --- | --- | --- | ---: |']
    for row in comparison['recordings']:
        folder=LIB/byid[row['audio_id']]['path']
        audio,rate=sf.read(folder/'audio.wav',dtype='int16')
        assert hashlib.sha256((folder/'audio.wav').read_bytes()).hexdigest()==row['audio_sha256']
        manifest=json.loads((folder/'checkpoints.json').read_text(encoding='utf-8'))
        assert hashlib.sha256((folder/'checkpoints.json').read_bytes()).hexdigest()==row['manifest_sha256']
        estimates={}
        for model in ['small.en','medium.en']:
            source=ACOUSTIC/(row['audio_id']+'.'+model+'.json')
            data=json.loads(source.read_text(encoding='utf-8'))
            assert data['audio_sha256']==row['audio_sha256'] and data['initial_prompt'] is None and data['hotwords'] is None
            shutil.copyfile(source,folder/('word_timestamps.'+model+'.json'))
            estimates[model]=data
        events=[json.loads(s) for s in (RUN/(row['audio_id']+'.events.jsonl')).read_text(encoding='utf-8').splitlines()]
        packets=[e for e in events if e['kind']=='audio']
        assert sum(e['sample_count'] for e in packets)==len(audio)
        triggered={e['scene']:e for e in events if e['kind']=='tracker' and e['mode']=='timely' and e['triggered']}
        checkpoints=[]
        for cp in manifest['checkpoints']:
            matches={name:locate(cp,data['words']) for name,data in estimates.items()}
            ends=[m['end'] for m in matches.values()]
            end=statistics.median(ends)
            assert 0<end<len(audio)/rate
            spread=max(ends)-min(ends)
            flags=[]
            if spread>.35:flags.append('model endpoint disagreement over 350 ms')
            if any(not m['exact_endpoint'] for m in matches.values()):flags.append('endpoint word differs between recognition and passage')
            if any(m['endpoint_word']['probability']<.6 for m in matches.values()):flags.append('at least one endpoint probability below 0.6')
            wall=boundary_wall(packets,end,rate)
            trigger=triggered.get(cp['id'])
            delay=trigger['wall']-wall if trigger else None
            interval=([trigger['wall']-boundary_wall(packets,max(ends),rate),
                       trigger['wall']-boundary_wall(packets,min(ends),rate)] if trigger else None)
            clip_start=max(0,min(m['start'] for m in matches.values())-1)
            clip_end=min(len(audio)/rate,end+1.5)
            clip=REVIEW/(row['audio_id']+'.'+cp['id']+'.wav')
            sf.write(clip,audio[round(clip_start*rate):round(clip_end*rate)],rate,subtype='PCM_16')
            detail=dict(id=cp['id'],checkpoint_text=cp['checkpoint_text'],estimated_end_seconds=end,
                model_endpoint_range_seconds=[min(ends),max(ends)],model_spread_seconds=spread,
                model_matches=matches,manual_verification=False,review_flags=flags,
                review_clip=clip.relative_to(LIB).as_posix(),clip_start_seconds=clip_start,
                estimated_endpoint_in_clip_seconds=end-clip_start,
                triggered=trigger is not None,estimated_delay_seconds=delay,
                delay_range_from_model_endpoints_seconds=interval,
                delay_range_note='Model sensitivity only, not a statistical confidence interval or bound on true error.',
                trigger_arrival_seconds=trigger['wall']-packets[0]['wall'] if trigger else None)
            checkpoints.append(detail)
            scored.append(dict(audio_id=row['audio_id'],**detail))
            clip_lines.append(f'| {row["audio_id"]} | {cp["id"]} | [Listen]({clip.name}) | {end:.3f}s |')
        assert [c['estimated_end_seconds'] for c in checkpoints]==sorted(c['estimated_end_seconds'] for c in checkpoints)
        annotations=dict(method=METHOD,audio_sha256=row['audio_sha256'],manual_verification=False,
            warning='Both recognizers are Whisper models and can share timing/recognition biases. Agreement does not establish accuracy. Do not use as verified gold.',checkpoints=checkpoints)
        write(folder/'checkpoint_timestamps.json',annotations)
        write(folder/'expected.json',dict(expected={c['id']:c['estimated_end_seconds'] for c in checkpoints},
            unread=[],timing=METHOD,verified=False,annotations='checkpoint_timestamps.json'))
        write(folder/'timing_status.json',dict(status='automatic_acoustic_estimates_available',
            expected_timestamps='expected.json',annotations='checkpoint_timestamps.json',manual_verification=False,
            provider_timestamps_available=False,method=METHOD))
        marker='\n<!-- mps-acoustic-timing -->'
        original=(folder/'README.md').read_text(encoding='utf-8').split(marker)[0]
        original=original.replace('No expected trigger times are provided.',
            'Automatic endpoint estimates are available below; no manually verified word times are provided.')
        (folder/'README.md').write_text(original.rstrip()+marker+'\n\n[Automatic checkpoint timestamps and estimated delays](checkpoint_timestamps.json), [expected endpoint estimates](expected.json), and [listening review clips](../../../../reviews/mps_timestamps/README.md). Small/medium Whisper word timings were estimated from the WAV without passage prompts. **Not manually verified gold.**\n',encoding='utf-8')
    write(REVIEW/'annotations.json',dict(method=METHOD,checkpoints=scored))
    (REVIEW/'README.md').write_text('\n'.join(clip_lines)+'\n',encoding='utf-8')
    write(RUN/'estimated_delays.json',dict(method=METHOD,current_matcher='timely',checkpoints=scored))
    lines=['# MPS provisional checkpoint delays', '',
        '**Automatic estimates, not listening-verified timestamps.** Actual WAVs were independently transcribed with cached small.en and medium.en Whisper models, no initial prompt or hotwords. The median of the two word-end estimates is the provisional reference. Both models share a family and can share errors. Their range is sensitivity to model choice, not a confidence interval.', '',
        'Delay = recorded live trigger wall time minus the estimated word endpoint mapped onto the original packet-send clock. This removes sender pacing drift. Word positions and the ASR snapshot end time were not used as speech endpoints. No audio rerun, model/threshold tuning, or changes to frozen checkpoints.', '',
        '| Recording | Checkpoint | Estimated spoken end | Model spread | Estimated delay |',
        '| --- | --- | ---: | ---: | ---: |']
    for r in scored:
        delay='Missed' if r['estimated_delay_seconds'] is None else f'{r["estimated_delay_seconds"]:+.3f}s'
        lines.append(f'| {r["audio_id"]} | {r["id"]} | {r["estimated_end_seconds"]:.3f}s | {r["model_spread_seconds"]:.3f}s | {delay} |')
    flagged=[r for r in scored if r['review_flags']]
    lines+=['', '## Flagged endpoints', '']
    for r in flagged:
        lines.append(f'- {r["audio_id"]}, {r["id"]}: '+ '; '.join(r['review_flags'])+'. The small model reads the endpoint as bus; the medium model reads bush. The comparable acoustic span is used provisionally, not taken as proof of correct pronunciation.')
    delays=[r['estimated_delay_seconds'] for r in scored if r['estimated_delay_seconds'] is not None]
    lines+=['',f'18/18 detected. Estimated median delay {statistics.median(delays):.3f}s; minimum {min(delays):.3f}s; maximum {max(delays):.3f}s.', '',
        '[All listening clips](../../reviews/mps_timestamps/README.md) and [full model outputs, matches and calculations](estimated_delays.json). Negative estimates indicate a trigger before the estimated full anchor ending; they are preserved rather than clamped to zero.', '',
        'These values help identify candidates for early/late-trigger review. Human listening is still required before treating any boundary or exact delay as verified.']
    (RUN/'TIMING.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    for path in [RUN/'README.md',LIB/'README.md']:
        marker='\n<!-- mps-delay-estimates -->'
        original=path.read_text(encoding='utf-8').split(marker)[0]
        target='TIMING.md' if path.parent==RUN else 'evaluation/live-2026-10-29-verified/TIMING.md'
        path.write_text(original.rstrip()+marker+f'\n\n[Provisional audio-derived checkpoint delays]({target}). Automatic small/medium Whisper word timing, not manually verified.\n',encoding='utf-8')
    print(json.dumps(dict(checkpoints=len(scored),median_delay=statistics.median(delays),minimum_delay=min(delays),maximum_delay=max(delays),max_model_endpoint_spread=max(r['model_spread_seconds'] for r in scored),flagged=[(r['audio_id'],r['id'],r['review_flags']) for r in scored if r['review_flags']]),indent=2))

if __name__=='__main__':main()
