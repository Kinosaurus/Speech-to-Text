"""Actual NeMo + shared matcher + SoundPlayer replay with process-only WASAPI capture.

The physical render endpoint is muted only during the trial and restored in
finally. Audio capture includes this test PID only, never other apps or the mic.
The output stream is warmed before source delivery; no matcher rules are changed.
"""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from types import SimpleNamespace
import wave

import numpy as np
import pyaudio

from benchmarks.asr_only import ASRRecorder, sha256
from transport import nemo
from benchmarks.compare_book_asr import full_book_hints
from benchmarks.metrics import edit_alignment
from books_to_life.matching.timely_matcher import TimelyEvidenceMatcher
from books_to_life.runtime.sound_player import SoundPlayer


def run(args):
    args.output.mkdir(parents=True, exist_ok=False)
    manifest = json.loads(args.manifest.read_text(encoding='utf-8'))
    matcher = TimelyEvidenceMatcher(manifest, stability=2)
    original_backend = pyaudio
    audio = None; stream = None; player = None; recorder = None; capture = None
    endpoint = None; original_session_mute = None
    result = dict(status='failed', input_kind='local synthetic speech',
                  input_sha256=sha256(args.audio), manifest_sha256=sha256(args.manifest),
                  asr=f'Nemotron {args.chunk_ms} ms; same fixed full-excerpt hints; boost 1.0',
                  matcher=matcher.mode, stability=2, threshold=matcher.default_threshold,
                  min_coverage=matcher.default_min_coverage, output_stream_warmed=True,
                  output_capture='Windows process-only loopback, real PortAudio SoundPlayer output',
                  cue_events=[])
    tool = str(args.capture_tool.resolve())
    prefix = args.output.resolve() / 'windows-output'
    def command(*parts):
        return subprocess.run([tool, *map(str, parts)], capture_output=True, text=True,
                              check=True, timeout=15).stdout
    class Recorder(ASRRecorder):
        def receive(self, text, *, segments=None, final=False):
            if text == self.last_text and not final:
                return
            super().receive(text, segments=segments, final=final)
            match_started=time.perf_counter()
            update = matcher.process(text, segments=segments)
            self.emit('match_trace',processing_seconds=time.perf_counter()-match_started,
                      triggered=update.triggered,checkpoint_id=update.checkpoint_id,
                      tracked_word_position=update.tracked_word_position,
                      pending=getattr(update,'effect_pending_checkpoint_id',None),
                      suppressed=getattr(update,'effect_suppressed',False))
            if update.triggered:
                emitted = player.handle_update(update)
                event = dict(id=str(update.checkpoint_id), callback_seconds=time.perf_counter()-self.origin,
                             sound_scheduled=emitted, score=update.score,
                             skipped=list(getattr(update, 'skipped_checkpoint_ids', ())))
                result['cue_events'].append(event)
                self.emit('checkpoint', **event)
                print('CHECKPOINT', json.dumps(event), flush=True)
    try:
        if True:
            # Exclude one-time CUDA/kernel initialization equally for every
            # candidate. This separate silent session never runs the matcher.
            warm=ASRRecorder(args.output/'warmup.events.jsonl',delivery='queued')
            try:
                text='\n'.join(page['text'] for page in manifest['pages'])
                result['warmup_runtime']=nemo(args,np.zeros(32000,dtype=np.float32),warm,
                                             dict(packet_samples=1280,tail_seconds=0),hotwords=full_book_hints(text))
            finally:
                warm.close()
        output = command('endpoint', 'default', 'true')
        endpoint = dict(re.findall(r'^(ENDPOINT_ID|ORIGINAL_ENDPOINT_MUTE)=(.*)$', output, re.M))
        (args.output/'endpoint-original.json').write_text(json.dumps(endpoint), encoding='utf-8')
        audio = original_backend.PyAudio()
        stream = audio.open(format=original_backend.paInt16, channels=2, rate=44100,
                            output=True, frames_per_buffer=1024, start=False)
        output = command('mute', os.getpid(), 'false')
        original_session_mute = 'ORIGINAL_SESSION_MUTE=True' in output
        # Retain the actual native stream; only move its initialization before
        # source playback so muting cannot add a tool-launch delay to cue timing.
        class WarmAudio:
            def open(self, **kwargs):
                return stream
            def terminate(self):
                pass
        sys.modules['pyaudio'] = SimpleNamespace(paInt16=original_backend.paInt16, PyAudio=lambda: WarmAudio())
        player = SoundPlayer(manifest['checkpoints'], args.manifest, volume=.5)
        if player.error or len(player.sounds) != len(manifest['checkpoints']):
            raise RuntimeError('SoundPlayer did not preload every assigned cue')
        capture = subprocess.Popen([tool, 'capture', str(os.getpid()), str(prefix)],
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        ready = capture.stdout.readline()
        if 'CAPTURE_READY' not in ready:
            raise RuntimeError('No process-only loopback capture: '+ready)
        stream.start_stream()
        stream.write(np.zeros((1024, 2), dtype='<i2').tobytes())
        if args.latency_profile or args.calibrate_output:
            # Prove the quiet digital output path before starting the source
            # clock. A scheduled first cue alone is insufficient evidence.
            phase=np.arange(22050,dtype=np.float64)/44100
            tone=(np.sin(2*np.pi*997*phase)*1000).astype('<i2')
            stream.write(np.repeat(tone[:,None],2,axis=1).tobytes())
            stream.write(np.zeros((13230,2),dtype='<i2').tobytes())
            time.sleep(.2)
            raw=np.fromfile(prefix.with_suffix('.pcm'),dtype='<i2')
            if not len(raw) or np.max(np.abs(raw.astype(np.int32)))<100:
                raise RuntimeError('Quiet digital calibration tone absent; do not score recognition')
            result['pre_source_digital_tone_verified']=True
        recorder = Recorder(args.output/'recognition.events.jsonl', delivery='queued')
        with wave.open(str(args.audio)) as wav:
            if (wav.getframerate(),wav.getnchannels(),wav.getsampwidth()) != (16000,1,2):
                raise ValueError('Expected canonical 16 kHz mono PCM16 source')
            pcm = np.frombuffer(wav.readframes(wav.getnframes()), dtype='<i2').astype(np.float32)/32768
        text = '\n'.join(page['text'] for page in manifest['pages'])
        result['packet_samples']=args.packet_samples
        result['runtime'] = nemo(args, pcm, recorder, dict(packet_samples=args.packet_samples, tail_seconds=3),
                                 hotwords=full_book_hints(text))
        result['source_origin_qpc_seconds'] = recorder.origin
        result['source_seconds'] = len(pcm)/16000
        result['source_samples_sent'] = recorder.sent_samples
        # Let real scheduled effects finish, then close the production mixer.
        player.close(drain=True)
        if player.error:
            raise RuntimeError(str(player.error))
        finals = [e for e in recorder.events if e['kind']=='transcript' and e['final']]
        if len(finals)!=1 or recorder.sent_samples != len(pcm)+48000:
            raise RuntimeError('Incomplete source delivery or missing unique final transcript')
        result['final_transcript'] = finals[0]['text']
        reference=args.reference_text.read_text(encoding='utf-8') if args.reference_text else text
        score, _ = edit_alignment(reference, finals[0]['text'])
        result['wer_reference_sha256']=sha256(args.reference_text) if args.reference_text else sha256(args.manifest)
        result['estimated_synthetic_wer'] = score
        result['status']='ok'
        time.sleep(.3)
    except Exception as error:
        result['error'] = repr(error)
        raise
    finally:
        try:
            if player is not None:
                player.close()
            prefix.with_suffix('.stop').touch()
            if capture is not None:
                rest = capture.communicate(timeout=15)[0]
                (args.output/'capture-console.log').write_text(rest,encoding='utf-8')
                result['capture_exit_code']=capture.returncode
            if recorder is not None:
                recorder.close()
            if stream is not None:
                try:stream.stop_stream();stream.close()
                except OSError:pass
            if original_session_mute is not None:
                command('mute',os.getpid(),str(original_session_mute))
            if audio is not None:
                audio.terminate()
        finally:
            sys.modules['pyaudio']=original_backend
            if endpoint:
                command('endpoint',endpoint['ENDPOINT_ID'],endpoint['ORIGINAL_ENDPOINT_MUTE'])
                result['physical_endpoint_original_mute_restored']=True
            (args.output/'result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:result[k] for k in ('status','cue_events','physical_endpoint_original_mute_restored')}),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--manifest',type=Path,required=True)
    parser.add_argument('--audio',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--capture-tool',type=Path,required=True)
    parser.add_argument('--nemo-url',default='ws://127.0.0.1:9097')
    parser.add_argument('--packet-samples',type=int,default=4096)
    parser.add_argument('--latency-profile',choices=('baseline','short-chunk','balanced','fast'))
    parser.add_argument('--reference-text',type=Path)
    parser.add_argument('--calibrate-output',action='store_true')
    parser.add_argument('--chunk-ms',type=int,choices=(160,320),required=True)
    run(parser.parse_args())
