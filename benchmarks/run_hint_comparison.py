"""Fresh nine-recording trials with moving and fixed whole-passage hints."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import wave

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from checkpoint_matcher import normalize_text
from book_context import BookContext
from timely_matcher import TimelyEvidenceMatcher

LIB=ROOT/'recordings/library'
OUT=ROOT/'output/hint-comparison-2026-10-30'

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def write(path,data):path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

def whole_phrases(text):
    # Cover every normalized passage word in order, within NeMo's 32/200 bounds.
    # Pack adjacent short sentences, splitting long ones at 16 words.
    phrases=[]
    pending=[]
    for sentence in re.split(r'[.!?]+',text):
        words=normalize_text(sentence).split()
        while words:
            take=words[:16]
            words=words[16:]
            if pending and len(pending)+len(take)>16:
                phrases.append(' '.join(pending));pending=[]
            pending+=take
    if pending:phrases.append(' '.join(pending))
    assert ' '.join(phrases).split()==normalize_text(text).split()
    assert len(phrases)<=32 and all(len(p)<=200 for p in phrases)
    return phrases

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--resume',action='store_true')
    args=parser.parse_args()
    OUT.mkdir(exist_ok=True)
    jobs=[]
    sets=[(LIB/'acquisition/mps/import_report.json',LIB/'evaluation/live-2026-10-29-verified',
           LIB/'evaluation/live-2026-10-29-verified/estimated_delays.json'),
          (ROOT/'output/published-passages-2026-10-30/jobs.json',LIB/'evaluation/published-passages-live-2026-10-30',
           LIB/'evaluation/published-passages-live-2026-10-30/estimated_delays.json')]
    for index,base,timing in sets:
        baseline=json.loads((base/'comparison.json').read_text(encoding='utf-8'))
        byid={r['audio_id']:r for r in baseline['recordings']}
        for item in json.loads(index.read_text(encoding='utf-8'))['recordings']:
            folder=LIB/item['path']
            manifest=folder/'checkpoints.json'
            reference=folder/('full_story.txt' if (folder/'full_story.txt').exists() else 'passage.txt')
            assert digest(folder/'audio.wav')==byid[item['audio_id']]['audio_sha256']
            assert digest(manifest)==byid[item['audio_id']]['manifest_sha256']
            jobs.append(dict(id=item['audio_id'],path=item['path'],audio_sha256=digest(folder/'audio.wav'),
                manifest_sha256=digest(manifest),baseline_folder=base.relative_to(LIB).as_posix(),
                timing=timing.relative_to(LIB).as_posix(),whole_text=reference.relative_to(LIB).as_posix(),
                whole_text_sha256=digest(reference)))
    write(OUT/'protocol.json',dict(model='Parakeet Unified NeMo 0.6B CUDA bf16',boost=1.0,chunk_ms=560,right_ms=560,
        threshold=82,stability=2,min_coverage=.8,current_matcher='timely via split CLI',
        moving_policy='Existing BookContext defaults: next checkpoint plus 2 lookahead; prompt field ignored by NeMo',
        whole_policy='Fixed phrases covering full_story.txt for MPS; passage.txt for Kites/Billy/Tom; pack adjacent short sentences to <=16 words; <=32 phrases, <=200 chars each',
        baseline='Saved verified no-hints streams, one run per recording; no fresh no-hints replication',
        timing='Frozen previously estimated acoustic endpoints; not manually verified',jobs=jobs))
    for condition in ['moving','whole']:
        for job in jobs:
            folder=LIB/job['path']
            destination=OUT/condition/job['id']
            destination.mkdir(parents=True,exist_ok=True)
            if args.resume and (destination/'result.json').exists():
                old=json.loads((destination/'result.json').read_text(encoding='utf-8'))
                assert old['audio_sha256']==digest(folder/'audio.wav') and old['manifest_sha256']==digest(folder/'checkpoints.json')
                print('VERIFIED EXISTING',condition,job['id'],flush=True)
                continue
            frozen=destination/'checkpoints.json'
            frozen.write_bytes((folder/'checkpoints.json').read_bytes())
            config=json.loads(frozen.read_text(encoding='utf-8'))
            if condition=='moving':
                hints=BookContext(TimelyEvidenceMatcher(config)).hints
                hint_config=dict(initial_hotwords=hints.hotwords,lookahead=2,prompt_words=64)
                flags=[]
            else:
                text=(LIB/job['whole_text']).read_text(encoding='utf-8')
                phrases=whole_phrases(text)
                (destination/'hotwords.txt').write_text(', '.join(phrases),encoding='utf-8')
                hint_config=dict(phrases=phrases,text_source=job['whole_text'],full_passage_coverage=True)
                flags=['--no_book_context','--hotwords_file',str(destination/'hotwords.txt')]
            write(destination/'hints.json',hint_config)
            command=[sys.executable,'-u',str(ROOT/'benchmarks/live_tracker_probe.py'),
                '--model','parakeet-nemo','--server','127.0.0.1','--port','9097','--matching_mode','split',
                '--files',str(folder/'audio.wav'),'--mute_audio_playback','--checkpoints',str(frozen),
                '--transcript_file',str(destination/'transcript.srt'),*flags]
            command[1:1]=['-X','utf8']
            with wave.open(str(folder/'audio.wav')) as wav:frames,rate=wav.getnframes(),wav.getframerate()
            event_path=destination/'transcript.events.jsonl'
            recovered=False
            if args.resume and event_path.exists() and (destination/'client.log').exists():
                prior=[json.loads(s) for s in event_path.read_text(encoding='utf-8').splitlines()]
                recovered=any(e['kind']=='status' and e.get('message')=='STREAM_DONE' for e in prior)
            if recovered:
                print('AUDIT COMPLETED STREAM',condition,job['id'],flush=True)
            else:
                print('START',condition,job['id'],flush=True)
                with (destination/'client.log').open('w',encoding='utf-8') as log:
                    process=subprocess.run(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,timeout=frames/rate+180)
                assert process.returncode==0,(condition,job['id'],process.returncode)
            events=[json.loads(s) for s in (destination/'transcript.events.jsonl').read_text(encoding='utf-8').splitlines()]
            packets=[e for e in events if e['kind']=='audio']
            segments=[e for e in events if e['kind']=='segments']
            assert sum(p['sample_count'] for p in packets)==frames
            assert segments and segments[0]['wall']<packets[-1]['wall']
            assert any(e['kind']=='status' and e.get('message')=='STREAM_DONE' for e in events)
            assert not any(e['kind']=='status' and e.get('status')=='ERROR' for e in events)
            assert segments[-1]['segments'][-1]['completed']
            assert abs(segments[-1]['segments'][-1]['end']-frames/rate)<.001
            origin=packets[0]['wall']
            ids=[c['id'] for c in config['checkpoints']]
            triggers=[dict(checkpoint=e['scene'],arrival_seconds=e['wall']-origin,skipped=e['skipped'])
                for e in events if e['kind']=='tracker' and e['mode']=='timely' and e['triggered']]
            seen=[t['checkpoint'] for t in triggers]
            try:log_text=(destination/'client.log').read_text(encoding='utf-8')
            except UnicodeDecodeError:
                log_text=(destination/'client.log').read_text(encoding='cp1252')
                (destination/'client.log').write_text(log_text,encoding='utf-8')
            app=re.findall(r'^\[TRIGGER\] (\S+):',log_text,re.M)
            assert app==seen,(app,seen)
            sent=[e for e in events if e['kind']=='book_context_sent']
            acks=[e for e in events if e['kind']=='book_context_control' and e['data']['type']=='book_context_ack']
            if condition=='moving':assert sent and acks
            else:assert not sent
            result=dict(condition=condition,id=job['id'],path=job['path'],audio_sha256=digest(folder/'audio.wav'),
                manifest_sha256=digest(frozen),seconds=frames/rate,triggers=triggers,missing=[i for i in ids if i not in seen],
                unexpected=[i for i in seen if i not in ids],duplicates=len(seen)-len(set(seen)),
                live_before_eof=True,stream_done=True,samples_sent=frames,initial_hint_config=hint_config,
                hint_updates_sent=len(sent),hint_updates_acked=len(acks),
                final_asr=' '.join(s['text'] for s in segments[-1]['segments']))
            assert result['audio_sha256']==job['audio_sha256'] and result['manifest_sha256']==job['manifest_sha256']
            write(destination/'result.json',result)
            print('DONE',condition,job['id'],json.dumps(dict(triggered=seen,missing=result['missing'],updates=len(sent))),flush=True)
    print('ALL 18 HINT STREAMS COMPLETE',flush=True)

if __name__=='__main__':main()
