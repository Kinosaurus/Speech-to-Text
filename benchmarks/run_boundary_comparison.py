"""Fresh paced audio comparison of original, split, boundary and timely trackers."""
import hashlib
import argparse
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import time
import wave

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from recording_library import resolve_recording_path
OUT = ROOT / 'output/timely-streaming-2026-10-28'
MODES = ('original', 'split', 'boundary', 'timely')


def main():
    global OUT
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--resume',action='store_true',help='Validate and retain completed live logs.')
    parser.add_argument('--output',type=Path,default=OUT)
    parser.add_argument('--jobs',type=Path,help='Optional explicit local jobs JSON for a separate condition.')
    args=parser.parse_args()
    OUT=args.output
    OUT.mkdir(parents=True, exist_ok=True)
    jobs = []
    subsets = [json.loads((ROOT/f'recordings/library/evaluation/ocsc_subsets/{name}.json').read_text())
               for name in ('standard', 'early')]
    for row in subsets[0]['jobs']:
        jobs.append(dict(id='ocsc-'+row['id'], audio=row['clip'], condition='no-hints',
                         manifests={name:s['manifest'] for name,s in zip(('ocsc-standard','ocsc-early'),subsets)},
                         expected={name:next(j for j in s['jobs'] if j['id']==row['id'])['expected']
                                   for name,s in zip(('ocsc-standard','ocsc-early'),subsets)}))
    hints = dict(horse='farm, family, horse, brown, run fast',
                 fat_cat='cat, mat, rat, fat cat, bat, hat',
                 tea='mouse, pot of tea, phone, teapot, stove, cups, little house, Toad',
                 little_mermaid='mermaid, legs, prince, deep blue eyes')
    for condition in ('no-hints','fixed-hints'):
        for name in hints:
            manifest = f'recordings/library/stories/{name}/readers/{name}/checkpoints.json'
            expected = {c['id']:None for c in json.loads((ROOT/manifest).read_text())['checkpoints']}
            jobs.append(dict(id=name+'-'+condition, audio=f'recordings/library/stories/{name}/readers/{name}/audio.wav',
                             condition=condition, hints=hints[name] if condition=='fixed-hints' else None,
                             manifests={name:manifest}, expected={name:expected}))
    allbooks = {name:f'recordings/library/stories/{name}/readers/{name}/checkpoints.json' for name in hints}
    for name in ('dog','dragon','nickel','recording_2'):
        jobs.append(dict(id=name+'-off-book', audio=f'recordings/library/stories/{name}/readers/{name}/audio.wav',
                         condition='off-book', manifests=allbooks, expected={name:{} for name in hints}))
    if args.jobs:
        jobs=json.loads(args.jobs.read_text())
    for job in jobs:
        job['audio'] = str(resolve_recording_path(job['audio']))
        job['manifests'] = {name:str(resolve_recording_path(path)) for name,path in job['manifests'].items()}
    (OUT/'protocol.json').write_text(json.dumps(dict(jobs=jobs, source_sha256={
        name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in
        ('alignment_matcher.py','evidence_matcher.py','split_matcher.py','boundary_matcher.py','timely_matcher.py',
         'benchmarks/live_tracker_probe.py','run_client.py')}),indent=2))
    # Only startup is retried; no automatic rerun of completed recognition.
    deadline = time.monotonic()+240
    while True:
        try:
            with socket.create_connection(('127.0.0.1',9097),timeout=1): break
        except OSError:
            if time.monotonic()>deadline: raise TimeoutError('Parakeet startup')
            time.sleep(1)
    results=[]
    for job in jobs:
        print('START',job['id'],flush=True)
        stem=OUT/job['id'];audio=ROOT/job['audio']
        command=[sys.executable,'-u',str(ROOT/'benchmarks/live_tracker_probe.py'),
                 '--model','parakeet-nemo','--server','127.0.0.1','--port','9097',
                 '--matching_mode','split','--files',str(audio),'--mute_audio_playback',
                 '--no_book_context','--transcript_file',str(stem.with_suffix('.srt'))]
        if job['condition']!='off-book':
            command+=['--checkpoints',str(ROOT/next(iter(job['manifests'].values())))]
        if job.get('hints'): command+=['--hotwords',job['hints']]
        if not (args.resume and stem.with_suffix('.events.jsonl').exists()):
            with stem.with_suffix('.log').open('w',encoding='utf-8') as log:
                result=subprocess.run(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,timeout=420,
                                      env=dict(os.environ,TRACKER_COMPARE_MANIFESTS=json.dumps(job['manifests'])))
            if result.returncode: raise RuntimeError(f"Client failed {job['id']}: {result.returncode}")
        events=[json.loads(line) for line in stem.with_suffix('.events.jsonl').read_text().splitlines()]
        packets=[e for e in events if e['kind']=='audio'];segments=[e for e in events if e['kind']=='segments']
        with wave.open(str(audio)) as w: samples,rate=w.getnframes(),w.getframerate()
        assert sum(e['sample_count'] for e in packets)==samples
        assert any(e['kind']=='end_of_audio' for e in events)
        # NativeStreamClient consumes STREAM_DONE before the base-client probe.
        # Verify final coverage plus its normal close instead of requiring that
        # intercepted protocol message to reach the observer.
        close_log=stem.with_suffix('.log').read_text().lower()
        # Upstream may close locally immediately after NativeConnection.finished
        # is set, yielding None rather than the peer's 1000 close callback.
        assert ('connection closed: 1000' in close_log or
                'connection closed: none: none' in close_log)
        assert not any(e['kind']=='status' and e.get('status')=='ERROR' for e in events)
        assert segments[-1]['segments'][-1]['completed']
        assert abs(segments[-1]['segments'][-1]['end']-samples/rate)<.001
        origin=packets[0]['wall'];callback=None;triggers=[]
        for e in events:
            if e['kind']=='segments': callback=e['wall']-origin
            if e['kind']=='tracker' and e['triggered']:
                item=dict(book=e['book'],mode=e['mode'],scene=e['scene'],
                          callback_seconds=callback,decision_seconds=e['wall']-origin,
                          audio_end=e['audio_end'],skipped=e['skipped'])
                endpoint=job['expected'].get(e['book'],{}).get(e['scene'])
                if endpoint is not None:
                    p=next(p for p in packets if p['sample_start']+p['sample_count']>=endpoint*rate)
                    mapped=p['wall']+(endpoint*rate-p['sample_start'])/rate
                    item['approx_delay_seconds']=origin+callback-mapped
                triggers.append(item)
        # The application is configured with the first manifest (or no effects
        # for off-book). Its fixed tracker must agree with the corresponding observer.
        app=re.findall(r'^\[TRIGGER\] (\S+):',stem.with_suffix('.log').read_text(),flags=re.M)
        if job['condition']!='off-book':
            assert app==[t['scene'] for t in triggers if t['mode']=='timely' and
                         t['book']==next(iter(job['manifests']))]
        row=dict(**job,audio_sha256=hashlib.sha256(audio.read_bytes()).hexdigest(),samples_sent=samples,
                 audio_seconds=samples/rate,delivery_seconds=packets[-1]['wall']-origin+packets[-1]['sample_count']/rate,
                 first_asr_seconds=segments[0]['wall']-origin,
                 partial_before_eof=segments[0]['wall']<packets[-1]['wall'],
                 final_completed_and_normal_close=True,app_agreement=True,triggers=triggers)
        results.append(row);(OUT/'results.json').write_text(json.dumps(results,indent=2))
        print('DONE',job['id'],{m:sum(t['mode']==m for t in triggers) for m in MODES},flush=True)
    print('COMPLETE',flush=True)


if __name__=='__main__':main()
