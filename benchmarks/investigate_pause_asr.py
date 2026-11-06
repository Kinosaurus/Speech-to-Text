"""Fixed 2x2 pause/ASR-chunk-phase diagnostic; runtime stays unchanged."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import wave

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from benchmarks.run_mps_heldout import read,write,digest
from benchmarks.run_prefix_confirmation_regression import verify as verify_reference
from benchmarks.run_shared_reading import audit

REFERENCE=ROOT/'output/prefix-confirmation-regression-v2-2026-11-03'
DEST=ROOT/'output/pause-asr-diagnostic-2026-11-03'


def verify(output):
    reference=verify_reference(REFERENCE)
    protocol=read(output/'protocol.json')
    assert protocol['reference_source_sha256']==reference['source_sha256']
    assert digest(Path(__file__))==protocol['diagnostic_script_sha256']
    assert digest(output/'jobs.json')==protocol['jobs_sha256']
    for row in read(output/'audio-inventory.json'):
        assert digest(Path(row['audio']))==row['audio_sha256']
    for job in read(output/'jobs.json'):
        assert digest(Path(job['manifest']))==job['manifest_sha256']
    return protocol


def prepare(output):
    reference=verify_reference(REFERENCE,model_hash=True,audio=True)
    old={j['id']:j for j in read(REFERENCE/'jobs.json')}
    source=Path(old['shared-handoff_and_back']['audio'])
    with wave.open(str(source),'rb') as wav:
        assert (wav.getnchannels(),wav.getsampwidth(),wav.getframerate())==(1,2,16000)
        original=wav.readframes(wav.getnframes())
    target_start=61520  # Predeclared composition boundary: 3.845 s.
    # Short/long gaps crossed with both observed 560-ms chunk phases.
    plans=[('short_phase_a',0),('long_phase_b',246400),
           ('short_phase_b',4480),('long_phase_a',250880)]
    output.mkdir(parents=True,exist_ok=False)
    jobs=[];inventory=[]
    original_long=Path(old['shared-long_pause']['audio'])
    for ident,inserted_samples in plans:
        folder=output/'inputs'/ident;folder.mkdir(parents=True)
        manifest=folder/'checkpoints.json'
        shutil.copyfile(old['shared-handoff_and_back']['manifest'],manifest)
        data=original[:target_start*2]+bytes(inserted_samples*2)+original[target_start*2:]
        audio=folder/'audio.wav'
        with wave.open(str(audio),'wb') as wav:
            wav.setnchannels(1);wav.setsampwidth(2);wav.setframerate(16000);wav.writeframes(data)
        if ident=='long_phase_b':
            with wave.open(str(original_long),'rb') as wav:
                assert data==wav.readframes(wav.getnframes())
        start=(target_start+inserted_samples)/16000
        jobs.append(dict(id=ident,group='controlled_synthetic_roles',category='pause_phase_diagnostic',
            audio=str(audio),manifest=str(manifest),manifest_sha256=digest(manifest),
            target='target',expected_target_emit=True,expected_emitted=['start','target','finish'],
            inserted_silence_seconds=inserted_samples/16000,target_start_seconds=start,
            target_chunk_phase_samples=(target_start+inserted_samples)%8960))
        inventory.append(dict(id=ident,audio=str(audio),audio_sha256=digest(audio),
            samples=len(data)//2,audio_seconds=len(data)/32000,
            spans=[dict(label='david_target',start=start,end=start+3.65)]))
    write(output/'jobs.json',jobs);write(output/'audio-inventory.json',inventory)
    write(output/'protocol.json',dict(date='2026-11-03',scope=__doc__,
        reference_source_sha256=reference['source_sha256'],configuration=reference['configuration'],
        model=reference['model'],lexicon=reference['lexicon'],
        diagnostic_script_sha256=digest(Path(__file__)),jobs_sha256=digest(output/'jobs.json'),
        original_pcm_sha256=digest(source),ordered_recordings=[j['id'] for j in jobs],
        trials_per_input=1,all_trials_retained=True,selected_before_new_asr=True,
        runtime_asr_matcher_thresholds_unchanged=True,
        limits=['Inspected synthetic adult sentence; not new child accuracy.',
            'Four single trials distinguish this fixed grid only; no population or universal causal claim.',
            'No silence reset, hints, model parameters, matcher thresholds or words are modified.']))
    verify(output)
    print('FROZEN four real-paced streams; identical speech, two gap lengths and two chunk phases.',flush=True)


def run(output):
    verify(output);verify_reference(REFERENCE,model_hash=True,audio=True)
    (output/'streams').mkdir(exist_ok=False);rows=[]
    infos={r['id']:r for r in read(output/'audio-inventory.json')}
    for job in read(output/'jobs.json'):
        verify(output);stem=output/'streams'/job['id']
        command=[sys.executable,'-X','utf8','-u','benchmarks/live_tracker_probe.py',
            '--model','parakeet-nemo','--server','127.0.0.1','--port','9097',
            '--matching_mode','split','--no_book_context','--files',job['audio'],
            '--mute_audio_playback','--checkpoints',job['manifest'],
            '--transcript_file',str(stem.with_suffix('.srt'))]
        env=dict(os.environ,PYTHONUTF8='1');env.pop('TRACKER_COMPARE_MANIFESTS',None)
        print('START',job['id'],flush=True)
        with stem.with_suffix('.log').open('w',encoding='utf-8') as log:
            subprocess.run(command,cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=180,check=True)
        row=audit(output,job,infos[job['id']]);verify(output)
        row.update(inserted_silence_seconds=job['inserted_silence_seconds'],
            target_start_seconds=job['target_start_seconds'],target_chunk_phase_samples=job['target_chunk_phase_samples'])
        rows.append(row);write(output/'results.json',dict(cases=rows))
        print('DONE',job['id'],row['outcomes'],row['final_asr'],flush=True)
    write(output/'completed.json',dict(fresh_streams=4,all_trials_retained=True))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage',choices=('prepare','run'),required=True)
    parser.add_argument('--output',type=Path,default=DEST)
    args=parser.parse_args();globals()[args.stage](args.output.resolve())
