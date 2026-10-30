"""Stream imported MPS WAVs through real ASR and frozen checkpoint observers.

Requires a running local Parakeet NeMo server on port 9097. This measures
checkpoint detection, not latency against unavailable word-level gold times.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import wave

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT/'recordings/library'

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--results',type=Path,required=True)
    parser.add_argument('--jobs',type=Path,help='Optional library recording jobs with the same path/hash schema.')
    args=parser.parse_args()
    args.results.mkdir(parents=True,exist_ok=False)
    imports=json.loads((args.jobs or LIB/'acquisition/mps/import_report.json').read_text(encoding='utf-8'))
    results=[]
    for item in imports['recordings']:
        folder=LIB/item['path']
        audio=folder/'audio.wav'
        assert digest(audio)==item['audio_sha256']
        stem=args.results/item['audio_id']
        frozen=stem.with_suffix('.checkpoints.json')
        frozen.write_bytes((folder/'checkpoints.json').read_bytes())
        manifest=json.loads(frozen.read_text(encoding='utf-8'))
        ids=[cp['id'] for cp in manifest['checkpoints']]
        with wave.open(str(audio)) as wav:
            frames,rate=wav.getnframes(),wav.getframerate()
        command=[sys.executable,'-u',str(ROOT/'benchmarks/live_tracker_probe.py'),
                 '--model','parakeet-nemo','--server','127.0.0.1','--port','9097',
                 '--matching_mode','split','--files',str(audio),'--mute_audio_playback',
                 '--no_book_context','--checkpoints',str(frozen),
                 '--transcript_file',str(stem.with_suffix('.srt'))]
        print('START',item['audio_id'],flush=True)
        with stem.with_suffix('.log').open('w',encoding='utf-8') as log:
            process=subprocess.run(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,timeout=frames/rate+180)
        if process.returncode:
            raise RuntimeError(f'{item["audio_id"]} failed; inspect {stem}.log')
        events=[json.loads(line) for line in stem.with_suffix('.events.jsonl').read_text(encoding='utf-8').splitlines()]
        packets=[e for e in events if e['kind']=='audio']
        segments=[e for e in events if e['kind']=='segments']
        statuses=[e for e in events if e['kind']=='status']
        assert sum(e['sample_count'] for e in packets)==frames
        assert segments and any(e['kind']=='end_of_audio' for e in events)
        assert any(e.get('message')=='STREAM_DONE' for e in statuses),statuses
        assert not any(e.get('status')=='ERROR' for e in statuses),statuses
        origin=packets[0]['wall']
        observers={}
        for mode in ['original','split','boundary','timely']:
            triggers=[dict(checkpoint=e['scene'],arrival_seconds=e['wall']-origin,
                           asr_audio_end=e['audio_end'],skipped=e['skipped'])
                      for e in events if e['kind']=='tracker' and e['mode']==mode and e['triggered']]
            seen=[e['checkpoint'] for e in triggers]
            observers[mode]=dict(triggered=seen,missing=[name for name in ids if name not in seen],
                unexpected=[name for name in seen if name not in ids],duplicate_triggers=len(seen)!=len(set(seen)),events=triggers)
        result=dict(audio_id=item['audio_id'],reader=folder.name,grade=item.get('grade',3 if args.jobs is None else None),age_years=item.get('age_years'),
            audio_seconds=frames/rate,audio_sha256=digest(audio),manifest_sha256=digest(frozen),
            samples_sent=sum(e['sample_count'] for e in packets),sample_rate=rate,
            delivery_seconds=packets[-1]['wall']-origin+packets[-1]['sample_count']/rate,
            first_asr_seconds=segments[0]['wall']-origin,
            partial_before_eof=segments[0]['wall']<packets[-1]['wall'],
            stream_done=True,expected_checkpoint_ids=ids,observers=observers,
            final_asr=' '.join(s['text'] for s in segments[-1]['segments']),
            delay_accuracy='Not evaluated during streaming; see subsequent acoustic timing analysis')
        results.append(result)
        save=dict(configuration=dict(model='parakeet-unified-en-0.6b',chunk_ms=560,right_ms=560,
             book_context=False,current_matcher='timely (run_client split mode)',runs_per_recording=1,
             wait_for_stream_done=True,
             threshold=82,stability=2,min_coverage=0.8),recordings=results)
        (args.results/'comparison.json').write_text(json.dumps(save,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
        print('DONE',item['audio_id'],json.dumps({k:v['triggered'] for k,v in observers.items()}),flush=True)
    print('ALL',len(results),'COMPLETE',flush=True)

if __name__=='__main__':
    main()
