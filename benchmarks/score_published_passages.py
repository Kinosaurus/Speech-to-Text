"""Pair fresh published-passage streaming results with acoustic estimates."""
import hashlib
import json
from pathlib import Path
import shutil
import statistics
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from benchmarks.annotate_mps_timing import locate, boundary_wall
from books_to_life.matching.checkpoint_matcher import normalize_text
import soundfile as sf

LIB=ROOT/'recordings/library'
OUT=ROOT/'output/published-passages-2026-10-30'
DEST=LIB/'evaluation/published-passages-live-2026-10-30'
REVIEW=LIB/'reviews/published-passages-timestamps-2026-10-30'

def write(path,data):
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

def endpoint(cp,words):
    try:
        found=locate(cp,words)
        found['review_note']=None
        return found
    except AssertionError:
        # The two independent models render the last attempted word as cheat/
        # cheap. Locate that audible attempt using its long preceding context;
        # do not change the runtime anchor or claim the child said chess.
        if cp['id']!='cookies_and_chess':raise
        parts=normalize_text(cp['checkpoint_text']).split()
        assert parts[-1]=='chess'
        options=[]
        for substitute in ['cheat','cheap']:
            alternative=dict(cp,checkpoint_text=' '.join(parts[:-1]+[substitute]))
            try: options.append(locate(alternative,words))
            except AssertionError:pass
        assert options
        found=max(options,key=lambda m:m['match_score'])
        assert found['match_score']>=90 and found['end']>=words[-1]['end']-.5
        found['exact_endpoint']=False
        found['review_note']='End of acoustically recognized final-word attempt (cheat/cheap), not verification that chess was correctly spoken.'
        return found

def main():
    data=json.loads((OUT/'live/comparison.json').read_text(encoding='utf-8'))
    assert len(data['recordings'])==3
    jobs=json.loads((OUT/'jobs.json').read_text(encoding='utf-8'))['recordings']
    byid={r['audio_id']:r for r in jobs}
    DEST.mkdir(parents=True,exist_ok=True)
    REVIEW.mkdir(parents=True,exist_ok=True)
    shutil.copytree(OUT/'live',DEST,dirs_exist_ok=True)
    write(DEST/'jobs.json',dict(recordings=jobs))
    scored=[]
    clip_index=['# Published-passage checkpoint review clips', '',
        'Automatic timing estimates, not human listening verification. Clip endpoints are at the offsets in checkpoint_timestamps.json. All source and spoken transcripts remain separate.', '',
        '| Recording | Checkpoint | Clip | Original endpoint estimate |', '| --- | --- | --- | ---: |']
    for row in data['recordings']:
        job=byid[row['audio_id']]
        folder=LIB/job['path']
        assert hashlib.sha256((folder/'audio.wav').read_bytes()).hexdigest()==row['audio_sha256']
        assert hashlib.sha256((folder/'checkpoints.json').read_bytes()).hexdigest()==row['manifest_sha256']
        audio,rate=sf.read(folder/'audio.wav',dtype='int16')
        manifest=json.loads((folder/'checkpoints.json').read_text(encoding='utf-8'))
        models={}
        for name in ['small.en','medium.en']:
            path=OUT/'acoustic'/(row['audio_id']+'.'+name+'.json')
            models[name]=json.loads(path.read_text(encoding='utf-8'))
            assert models[name]['audio_sha256']==row['audio_sha256']
            shutil.copyfile(path,folder/('word_timestamps.'+name+'.json'))
        events=[json.loads(s) for s in (DEST/(row['audio_id']+'.events.jsonl')).read_text(encoding='utf-8').splitlines()]
        packets=[e for e in events if e['kind']=='audio']
        assert sum(e['sample_count'] for e in packets)==len(audio)
        triggers=[e for e in events if e['kind']=='tracker' and e['mode']=='timely' and e['triggered']]
        assert len({e['scene'] for e in triggers})==len(triggers)
        observations=[]
        for cp in manifest['checkpoints']:
            matches={name:endpoint(cp,m['words']) for name,m in models.items()}
            ends=[m['end'] for m in matches.values()]
            estimate=statistics.median(ends)
            assert 0<estimate<=len(audio)/rate
            flags=[]
            if max(ends)-min(ends)>.35:flags.append('Model endpoints differ by more than 350 ms')
            if any(not m['exact_endpoint'] for m in matches.values()):flags.append('Final-word attempt differs from printed endpoint; lexical verification needed')
            if any(m['endpoint_word']['probability']<.6 for m in matches.values()):flags.append('Endpoint recognition probability below 0.6 in at least one model')
            if any(m['match_score']<90 for m in matches.values()):flags.append('Anchor recognition differs materially from print; review context')
            trig=next((e for e in triggers if e['scene']==cp['id']),None)
            delays=[trig['wall']-boundary_wall(packets,e,rate) for e in ends] if trig else []
            start=max(0,min(m['start'] for m in matches.values())-1)
            stop=min(len(audio)/rate,estimate+1.5)
            clip=REVIEW/(row['audio_id']+'.'+cp['id']+'.wav')
            sf.write(clip,audio[round(start*rate):round(stop*rate)],rate,subtype='PCM_16')
            observation=dict(audio_id=row['audio_id'],id=cp['id'],checkpoint_text=cp['checkpoint_text'],
                estimated_end_seconds=estimate,model_endpoint_range_seconds=[min(ends),max(ends)],
                model_spread_seconds=max(ends)-min(ends),model_matches=matches,review_flags=flags,
                manual_verification=False,triggered=trig is not None,
                estimated_delay_seconds=trig['wall']-boundary_wall(packets,estimate,rate) if trig else None,
                delay_range_from_model_endpoints_seconds=[min(delays),max(delays)] if delays else None,
                review_clip=clip.relative_to(LIB).as_posix(),clip_start_seconds=start,
                estimated_endpoint_in_clip_seconds=estimate-start)
            observations.append(observation)
            scored.append(observation)
            clip_index.append(f'| {row["audio_id"]} | {cp["id"]} | [Listen]({clip.name}) | {estimate:.3f}s |')
        assert [o['estimated_end_seconds'] for o in observations]==sorted(o['estimated_end_seconds'] for o in observations)
        write(folder/'checkpoint_timestamps.json',dict(method='No-prompt small.en/medium.en Whisper word estimates; median endpoint; not human gold',checkpoints=observations))
        write(folder/'expected.json',dict(expected={o['id']:o['estimated_end_seconds'] for o in observations},unread=[],verified=False,
            timing='Automatic acoustic end-of-anchor/attempt estimates; published wording is not proof of spoken correctness',annotations='checkpoint_timestamps.json'))
        write(folder/'timing_status.json',dict(status='automatic_acoustic_estimates_available',manually_verified=False,
            expected_timestamps='expected.json',annotations='checkpoint_timestamps.json'))
        write(folder/'live_pipeline_test.json',dict(configuration=data['configuration'],result=row,timing=observations))
        previous=(folder/'history/before-published-rebuild-2026-10-30/README.original.txt').read_text(encoding='utf-8')
        (folder/'README.md').write_text(previous.rstrip()+'\n\n## Published-passage rebuild and fresh audio test (30 October 2026)\n\nCurrent [passage](passage.txt) and [checkpoints](checkpoints.json) use independently published text. The exact OCSC card edition remains unverified. `reference.txt` retains the earlier transcript-derived reference. [Previous manifest and timestamps](history/before-published-rebuild-2026-10-30/checkpoints.json) are preserved.\n\n[Actual-audio pipeline results](live_pipeline_test.json), [automatic endpoint and delay estimates](checkpoint_timestamps.json), and [review clips](../../../../reviews/published-passages-timestamps-2026-10-30/README.md). No human listening verification claimed.\n',encoding='utf-8')
        reader_readme=folder/'README.md'
        reader_readme.write_text(reader_readme.read_text(encoding='utf-8').replace('[Reading text](reference.txt)','[Published reading text](passage.txt)'),encoding='utf-8')
        story_readme=folder.parents[1]/'README.md'
        old_target=f'readers/{folder.name}/reference.txt'
        if story_readme.exists():
            story_readme.write_text(story_readme.read_text(encoding='utf-8').replace(f'[Reference (see text_status.json)]({old_target})',f'[Published passage](readers/{folder.name}/passage.txt)'),encoding='utf-8')
        catalogue=LIB/'README.md'
        old_target=job['path']+'/reference.txt'
        catalogue.write_text(catalogue.read_text(encoding='utf-8').replace(f'[Reference (see text_status.json)]({old_target})',f'[Published passage]({job["path"]}/passage.txt)'),encoding='utf-8')
    (REVIEW/'README.md').write_text('\n'.join(clip_index)+'\n',encoding='utf-8')
    write(DEST/'estimated_delays.json',dict(method='Actual WAV, two no-prompt Whisper model sizes; mapped to live packet sender clock',manual_verification=False,checkpoints=scored))
    lines=['# Kites, Billy and Tom: published-passage audio retest', '',
        '30 October 2026. Three fresh real-time WAV streams through Parakeet Unified NeMo, 560 ms chunk/right context, no hints, current split/TimelyEvidenceMatcher. Threshold 82, stability 2, minimum coverage 0.8. All three manifests rebuilt from independently published passages; IDs/settings retained, word ranges recomputed. Exact OCSC stimulus-card editions are still unverified.', '',
        '| Recording | Checkpoint | Triggered | Estimated spoken endpoint | Model spread | Estimated delay |',
        '| --- | --- | --- | ---: | ---: | ---: |']
    for r in scored:
        delay='N/A' if r['estimated_delay_seconds'] is None else f'{r["estimated_delay_seconds"]:+.3f}s'
        lines.append(f'| {r["audio_id"]} | {r["id"]} | {r["triggered"]} | {r["estimated_end_seconds"]:.3f}s | {r["model_spread_seconds"]:.3f}s | {delay} |')
    lines+=['','## Timing limits and reading differences','',
        'All timestamps are automatic acoustic estimates from small.en and medium.en Whisper, without passage prompts. Both models share a family and can share biases. Median endpoint used; model spread is sensitivity, not a statistical confidence interval. No manual listening was performed. Delay is live trigger wall time minus endpoint mapped onto actual packet-send timing; it removes cumulative sender drift. Snapshot-end times and character/word positions were not treated as speech endpoints.', '',
        '- Billy: the independent ASR detects a garbled attempt at the wrong-day/Tuesday paragraph missing from the old reference. It does not establish that every printed word was spoken. The final chess attempt is recognized as cheat/cheap by the independent models; its acoustic attempt end is used provisionally and explicitly flagged, rather than declaring the word correct.',
        '- Billy cookies_and_chess did not trigger in this fresh run. The final Parakeet snapshot ends at teach you to play and never supplies chess. Independent recognition hears a final cheat/cheap attempt. No delay is assigned to a missing trigger, and no runtime alias or threshold change was introduced to force it.',
        '- Tom: both independent ASR outputs end at Mother knew better though. The published Mother/Clean ending remains in the reference but has no configured checkpoint. This is not a missed checkpoint or proof that the exact recording card contained that ending.',
        '- Kites: runtime dinosaur checkpoint is now the printed Joe cut a dinosaur kite. The child/ASR includes out; that is left as spoken, not inserted into the printed passage.', '',
        '## Review flags','']
    lines += [f'- {r["audio_id"]}, {r["id"]}: '+ '; '.join(r['review_flags']) for r in scored if r['review_flags']]
    totals={mode:sum(len(r['observers'][mode]['triggered']) for r in data['recordings']) for mode in ['original','split','boundary','timely']}
    delays=[r['estimated_delay_seconds'] for r in scored if r['estimated_delay_seconds'] is not None]
    lines += ['',f'Current detector: {totals["timely"]}/9 checkpoints. Estimated median delay {statistics.median(delays):.3f}s; range {min(delays):.3f}–{max(delays):.3f}s.', '',
        'All audio samples delivered, live recognition before EOF, final STREAM_DONE received. Source hashes and frozen manifests retained. Logs, SRT, event JSONL, comparison.json and frozen manifests are beside this report.', '',
        '[Listen to all nine endpoint clips](../../reviews/published-passages-timestamps-2026-10-30/README.md). [Full timing calculations](estimated_delays.json).','',
        '## Comparison observers','', '| Observer | Triggered / 9 |','| --- | ---: |']
    lines += [f'| {m} | {v} |' for m,v in totals.items()]
    lines+=['','## Final ASR snapshots','']
    for r in data['recordings']:lines += [f'### {r["audio_id"]}','',r['final_asr'],'']
    (DEST/'README.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    path=LIB/'README.md'
    marker='\n<!-- published-passage-retest -->'
    text=path.read_text(encoding='utf-8').split(marker)[0]
    path.write_text(text.rstrip()+marker+'\n\n[Kites, Billy and Tom: rebuilt published passages and actual-audio results](evaluation/published-passages-live-2026-10-30/README.md). Automatic acoustic timing, not manually verified.\n',encoding='utf-8')
    print(json.dumps(dict(current=totals['timely'],configured=9,median=statistics.median(delays),minimum=min(delays),maximum=max(delays),observers=totals),indent=2))

if __name__=='__main__':main()
