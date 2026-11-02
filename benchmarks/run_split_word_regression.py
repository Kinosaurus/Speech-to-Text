"""Fresh regression streams for general ASR split-word permission.

Reuses the 24 inspected MPS recordings, three earlier reviewed cases and four
unrelated recordings. These are regression data, not a new held-out study.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import wave

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from benchmarks.run_mps_heldout import read, write, digest, check_frozen, old_tracker, audit_and_score

HELDOUT = ROOT / 'output/mps-heldout-2026-11-02'
REVIEWED = ROOT / 'output/listening-review-2026-11-02'
DEST = ROOT / 'output/split-word-regression-v2-2026-11-02'


def prepare(output):
    original = read(HELDOUT / 'protocol.json')
    prior = read(HELDOUT / 'downloaded-jobs.json')
    earlier = read(REVIEWED / 'regression/phonetic-after-fix/protocol.json')['jobs']
    metadata_path = REVIEWED / 'source/data.json'
    assert digest(metadata_path) == original['metadata_sha256']
    metadata = {r['audioID']:r for r in read(metadata_path)}
    jobs = {r['id']:dict(r, group='24-recording regression') for r in prior}
    legacy_targets = {
        '4a35g_EN-OL-RC-426_2': ('hibernate', False),
        '5b2b_EN-OL-RC-538_2': ('escape_enemies', False),
        '5b2b_EN-OL-RC-538_1': ('small_scales', True),
    }
    for row in earlier:
        meta=metadata[row['id']]['metaData']
        with wave.open(row['audio']) as wav: duration=wav.getnframes()/wav.getframerate()
        jobs[row['id']]=dict(row,group='previously human-reviewed controls',speaker=meta['speakerID'],
            grade=meta['grade'],gender=meta['gender'],audio_seconds=duration)
    targets = dict(legacy_targets)
    targets['3a8b_EN-OL-RC-234_1']=('riverside',True)
    targets['4c15g_EN-OL-RC-426_2']=('hibernate',False)
    order=list(targets)+[j['id'] for j in prior if j['id'] not in targets]
    assert len(order)==27 and len(set(order))==27
    output.mkdir(parents=True,exist_ok=False)
    ordered=[]
    for ident in order:
        row=jobs[ident]
        source=Path(row['manifest'])
        folder=output/'inputs'/ident
        folder.mkdir(parents=True)
        target=folder/'checkpoints.json'
        target.write_bytes(source.read_bytes())
        row['manifest']=str(target)
        assert digest(target)==row['manifest_sha256']
        assert digest(Path(row['audio']))==row['audio_sha256']
        if ident in targets:row['asserted_checkpoint'],row['expected_emission']=targets[ident]
        ordered.append(row)
    write(output/'selected.json',[metadata[j['id']] for j in ordered])
    write(output/'jobs.json',ordered)
    write(output/'downloaded-jobs.json',ordered)
    baseline=HELDOUT/'source-snapshot/books_to_life/matching'
    checks={}
    for name in ('effect_permission.py','timely_matcher.py'):
        target=output/'baseline-snapshot'/name
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes((baseline/name).read_bytes());checks[name]=digest(target)
    for path in baseline.glob('*.py'):
        if path.name not in checks:assert path.read_bytes()==(ROOT/'books_to_life/matching'/path.name).read_bytes()
    files=list((ROOT/'books_to_life').rglob('*.py'))+[Path(__file__).resolve(),
        ROOT/'benchmarks/run_mps_heldout.py',ROOT/'benchmarks/live_tracker_probe.py',
        ROOT/'benchmarks/prepare_mps_expansion.py',ROOT/'benchmarks/import_mps_samples.py',
        ROOT/'benchmarks/observer_manifests.py',ROOT/'benchmarks/pilot_effect_policy.json',
        *list((ROOT/'requirements').glob('*.txt'))]
    hashes={}
    for path in files:
        name=path.relative_to(ROOT).as_posix();content=path.read_bytes()
        target=output/'source-snapshot'/name
        target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(content)
        hashes[name]=hashlib.sha256(content).hexdigest()
    protocol=dict(date='2026-11-02',kind='Inspected-data split-word regression, not a held-out evaluation',
        configuration=original['configuration'],model=original['model'],lexicon=original['lexicon'],
        metadata_sha256=original['metadata_sha256'],source_sha256=hashes,baseline_sha256=checks,
        ordered_recordings=order,matched_streams=27,unrelated_streams=4,configured_matched_checkpoints=81,
        baseline='Frozen pre-split-word phonetic guard from the completed MPS evaluation',
        plan='Five asserted cases first, then all remaining MPS recordings in their original preselected order. One fresh stream each, no overwrite, no sample-dependent matcher changes.',
        changes_to_existing_manifests=False,raw_audio_reused_without_editing=True)
    write(output/'protocol.json',protocol)
    check_frozen(output,model_hash=True)
    print('FROZEN',len(order),'matched streams plus 4 unrelated streams.',flush=True)


def controls(output):
    jobs=read(output/'jobs.json');unique={}
    for job in jobs:
        manifest=read(Path(job['manifest']))
        key=tuple(p['text'] for p in manifest['pages'])
        unique.setdefault(key,job['manifest'])
    assert len(unique)==6
    manifests={f'passage-{i}':p for i,p in enumerate(unique.values(),1)}
    dest=output/'controls';dest.mkdir(exist_ok=False)
    rows=[]
    for name in ('dog','dragon','nickel','recording_2'):
        check_frozen(output)
        audio=ROOT/f'recordings/library/stories/{name}/readers/{name}/audio.wav'
        with wave.open(str(audio)) as wav:duration=wav.getnframes()/16000
        stem=dest/name
        command=[sys.executable,'-X','utf8','-u','benchmarks/live_tracker_probe.py',
            '--model','parakeet-nemo','--server','127.0.0.1','--port','9097',
            '--matching_mode','split','--no_book_context','--files',str(audio),
            '--mute_audio_playback','--transcript_file',str(stem.with_suffix('.srt'))]
        print('START unrelated',name,flush=True)
        with stem.with_suffix('.log').open('w',encoding='utf-8') as log:
            subprocess.run(command,cwd=ROOT,env=dict(os.environ,PYTHONUTF8='1',
                TRACKER_COMPARE_MANIFESTS=json.dumps(manifests)),stdout=log,stderr=subprocess.STDOUT,
                timeout=math.ceil(duration*1.5)+180,check=True)
        events=[json.loads(s) for s in stem.with_suffix('.events.jsonl').read_text(encoding='utf-8').splitlines()]
        packets=[e for e in events if e['kind']=='audio'];count=0
        for packet in packets:assert packet['sample_start']==count;count+=packet['sample_count']
        with wave.open(str(audio)) as wav:assert count==wav.getnframes()
        seg=[e for e in events if e['kind']=='segments']
        assert seg and seg[0]['wall']<packets[-1]['wall']
        assert seg[-1]['segments'][-1]['completed']
        assert abs(seg[-1]['segments'][-1]['end']-duration)<.001
        assert any(e['kind']=='status' and e.get('message')=='STREAM_DONE' for e in events)
        assert not any(e['kind']=='status' and e.get('status')=='ERROR' for e in events)
        current=[e for e in events if e['kind']=='tracker' and e['mode']=='timely']
        assert {e['book'] for e in current}==set(manifests)
        row=dict(recording=name,comparisons=len(manifests),
            emitted=sum(e['triggered'] for e in current),suppressed=sum(bool(e.get('suppressed')) for e in current),
            audio_sha256=digest(audio),samples_delivered=count,delivery_audited=True,partial_before_eof=True,stream_done=True)
        rows.append(row);write(output/'controls-results.json',rows)
        assert row['emitted']==0 and row['suppressed']==0
        print('DONE unrelated',name,'zero effects across',len(manifests),'passages',flush=True)


def run(output):
    check_frozen(output,model_hash=True)
    jobs=read(output/'downloaded-jobs.json');Old=old_tracker(output)
    streams=output/'streams';streams.mkdir(exist_ok=False)
    results=[]
    for index,job in enumerate(jobs,1):
        check_frozen(output);assert digest(Path(job['audio']))==job['audio_sha256']
        stem=streams/job['id']
        command=[sys.executable,'-X','utf8','-u','benchmarks/live_tracker_probe.py',
            '--model','parakeet-nemo','--server','127.0.0.1','--port','9097',
            '--matching_mode','split','--no_book_context','--files',job['audio'],
            '--mute_audio_playback','--checkpoints',job['manifest'],'--transcript_file',str(stem.with_suffix('.srt'))]
        print('START',index,'/',len(jobs),job['id'],flush=True)
        with stem.with_suffix('.log').open('w',encoding='utf-8') as log:
            subprocess.run(command,cwd=ROOT,env=dict(os.environ,PYTHONUTF8='1'),stdout=log,stderr=subprocess.STDOUT,
                timeout=math.ceil(job['audio_seconds']*1.5)+180,check=True)
        check_frozen(output)
        row=audit_and_score(output,job,Old);row['group']=job['group']
        if 'asserted_checkpoint' in job:
            actual=job['asserted_checkpoint'] in row['after']['emitted']
            row['assertion']=dict(checkpoint=job['asserted_checkpoint'],expected_emission=job['expected_emission'],
                actual_emission=actual,passed=actual==job['expected_emission'])
        results.append(row);write(output/'results.json',dict(recordings=results))
        print('DONE',index,'before/after',len(row['before']['emitted']),len(row['after']['emitted']),
            'added',row['added_emissions'],'removed',row['removed_emissions'],flush=True)
        if row.get('assertion'):assert row['assertion']['passed'],row['assertion']
    controls(output)
    check_frozen(output,model_hash=True)
    write(output/'completed.json',dict(matched_streams=27,unrelated_streams=4,source_unchanged=True,
        model_unchanged=True,manifests_unchanged=True,all_trials_retained=True))
    print('COMPLETE all 31 fresh streams; frozen sources unchanged.',flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage',choices=('prepare','run'),required=True)
    parser.add_argument('--output',type=Path,default=DEST)
    args=parser.parse_args();output=args.output.resolve()
    if not output.is_relative_to(ROOT/'output'):parser.error('Raw data must remain under ignored output/.')
    if args.stage=='prepare':prepare(output)
    else:run(output)


if __name__=='__main__':
    main()
