"""One pure ASR trial; never imports the application, tracker or hint logic."""
import argparse
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import threading
import time
import traceback
import uuid
import wave

from benchmarks.asr_only import ASRRecorder, PROFILES, PROTOCOL, atomic_json, enforce_no_tracker, score_updates, sha256


def gpu_snapshot():
    try:
        result = subprocess.run(['nvidia-smi', '--query-gpu=name,memory.used,utilization.gpu', '--format=csv,noheader'],
                                capture_output=True, text=True, timeout=8,
                                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        return result.stdout.strip() if result.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def nemo(args, pcm, recorder, dataset, *, hotwords=None, boost=None):
    import websocket
    uid = uuid.uuid4().hex
    start = time.perf_counter()
    ws = websocket.create_connection(args.nemo_url, timeout=30)
    done = threading.Event()
    barrier = threading.Event()
    barrier_revision = 0
    thread = None
    try:
        options = {'uid': uid, 'model': 'parakeet-nemo', 'language': 'en', 'task': 'transcribe'}
        if hotwords:
            options['hotwords'] = hotwords
        if boost is not None:
            options['benchmark_boost'] = boost
        latency_profile = getattr(args, 'latency_profile', None)
        if latency_profile:
            options['benchmark_latency_profile'] = latency_profile
        ws.send(json.dumps(options))
        while True:
            reply = json.loads(ws.recv())
            if reply.get('status') == 'ERROR':
                raise RuntimeError(reply.get('message'))
            if reply.get('uid') == uid and reply.get('message') == 'SERVER_READY':
                break
        boost_ack = {}
        if boost is not None:
            import hashlib
            expected_hash = hashlib.sha256((hotwords or '').encode()).hexdigest()
            if reply.get('benchmark_boost') != boost or reply.get('applied_hotwords_sha256') != expected_hash:
                raise RuntimeError('Benchmark server did not acknowledge the exact boost and supplied text.')
            boost_ack = {key: reply[key] for key in ('benchmark_boost', 'applied_hotwords_sha256', 'phrase_count')}
        ready_seconds = time.perf_counter() - start
        if latency_profile:
            from benchmarks.nemo_latency_server import PROFILES
            expected = PROFILES[latency_profile]
            import hashlib
            if (reply.get('benchmark_latency_profile') != latency_profile
                    or (reply.get('chunk_ms'), reply.get('right_ms')) != expected
                    or reply.get('boost') != 1.0
                    or reply.get('applied_hotwords_sha256') != hashlib.sha256((hotwords or '').encode()).hexdigest()):
                raise RuntimeError('Latency server did not acknowledge exact configuration and hints')
            boost_ack.update({k:reply[k] for k in ('benchmark_latency_profile','chunk_ms','right_ms','boost','applied_hotwords_sha256')})
        def receive():
            try:
                while not done.is_set():
                    reply = json.loads(ws.recv())
                    if reply.get('uid') != uid:
                        continue
                    if reply.get('status') == 'ERROR':
                        raise RuntimeError(reply.get('message'))
                    if reply.get('type')=='book_context_ack' and reply.get('revision')==barrier_revision:
                        barrier.set()
                    if 'segments' in reply:
                        if 'benchmark_server_timing' in reply:
                            recorder.emit('server_timing', **reply['benchmark_server_timing'])
                        segments = reply['segments']
                        recorder.receive(' '.join(s['text'] for s in segments).strip(), segments=segments,
                                         final=bool(segments) and all(s.get('completed') for s in segments))
                    if reply.get('message') == 'STREAM_DONE':
                        done.set()
            except Exception as error:
                if not done.is_set():
                    recorder.error = str(error)
                done.set()
        thread = threading.Thread(target=receive, daemon=True)
        thread.start()
        for packet_index,chunk in enumerate(recorder.chunks(pcm, dataset['packet_samples'], dataset['tail_seconds']),1):
            if done.is_set():
                raise RuntimeError(recorder.error or 'Server ended before all samples were sent.')
            ws.send_binary(chunk.astype('<f4', copy=False).tobytes())
            flow=getattr(args,'flow_control_packets',0)
            if flow and packet_index%flow==0:
                # Bound accelerated replay without changing phrase state.
                # This serial no-op ACK also keeps heartbeat frames reachable.
                barrier_revision+=1;barrier.clear()
                ws.send(json.dumps(dict(type='book_context',revision=barrier_revision,hotwords=hotwords)))
                deadline=time.monotonic()+30
                while not barrier.wait(.1):
                    if done.is_set():raise RuntimeError(recorder.error or 'Stream ended at flow barrier')
                    if time.monotonic()>deadline:raise TimeoutError('Quality replay flow barrier timed out')
                recorder.emit('quality_flow_barrier',revision=barrier_revision)
        ws.send_binary(b'END_OF_AUDIO')
        drain_timeout=getattr(args,'nemo_drain_timeout',60)
        if not done.wait(drain_timeout):
            raise TimeoutError(f'No STREAM_DONE within {drain_timeout} seconds.')
        if recorder.error:
            raise RuntimeError(recorder.error)
        return {'backend': 'NeMo WebSocket', 'device': 'WSL CUDA (existing server)',
                'precision': 'existing server configuration', 'ready_seconds': ready_seconds,
                'load_seconds': None, 'load_scope': 'already resident server; no model reload',
                'buffering': (f'{reply["chunk_ms"]} ms chunk / {reply["right_ms"]} ms right context'
                              if 'chunk_ms' in reply and 'right_ms' in reply
                              else 'legacy managed NeMo server; buffering not acknowledged'),
                'server_url': args.nemo_url, 'includes_loopback_transport': True, **boost_ack}
    finally:
        done.set()
        ws.close()
        if thread:
            thread.join(timeout=5)


def native(args, pcm, recorder, dataset):
    directory = args.cache / 'transcribe-native-windows-x86_64-cpu-vulkan'
    os.environ['TRANSCRIBE_LIBRARY'] = str(directory / 'transcribe.dll')
    handle = os.add_dll_directory(str(directory))
    sys.path.insert(0, str(args.cache / 'api'))
    import transcribe_cpp as tc
    devices = [d for d in tc.backends() if d.kind == 'vulkan']
    if not devices:
        raise RuntimeError('No Vulkan device available.')
    device = next((d for d in devices if 'NVIDIA' in d.description.upper() or 'RTX' in d.description.upper()), devices[0])
    parakeet = args.profile == 'parakeet-vulkan'
    path = args.cache / ('parakeet-unified-en-0.6b-F16.gguf' if parakeet else 'moonshine-streaming-medium-F16.gguf')
    start = time.perf_counter()
    compute = 0
    with tc.Model(path, device=device) as model:
        loaded = time.perf_counter() - start
        with model.session(n_threads=2) as session:
            family = tc.ParakeetBufferedStreamOptions(left_ms=5600, chunk_ms=560, right_ms=560) if parakeet else None
            with session.stream(language='en', family=family) as stream:
                for chunk in recorder.chunks(pcm, dataset['packet_samples'], dataset['tail_seconds']):
                    began = time.perf_counter()
                    update = stream.feed(chunk)
                    compute += time.perf_counter() - began
                    if update.result_changed:
                        recorder.receive(stream.text().full)
                began = time.perf_counter()
                stream.finalize()
                compute += time.perf_counter() - began
                recorder.receive(stream.text().full, final=True)
    return {'backend': 'transcribe.cpp', 'version': tc.__version__, 'device': repr(device), 'precision': 'F16',
            'load_seconds': loaded, 'model_sha256': sha256(path), 'model_file': str(path),
            'synchronous_feed_and_finalize_seconds': compute, 'threads': 2,
            'buffering': {'left_ms': 5600, 'chunk_ms': 560, 'right_ms': 560} if parakeet else 'runtime default',
            'includes_loopback_transport': False}


def moonshine(args, pcm, recorder, dataset):
    sys.path.insert(0, str(args.cache / 'moonshine-python'))
    from moonshine_voice import ModelArch, Transcriber
    path = Path((args.cache / 'moonshine-model-path.txt').read_text().strip())
    lines = {}
    def listener(event):
        if hasattr(event, 'error'):
            recorder.error = str(event.error)
            return
        line = event.line
        if line is None:
            return
        lines[line.line_id] = {'start': line.start_time, 'end': line.start_time + line.duration,
                               'text': line.text, 'completed': line.is_complete}
        snapshot = sorted(lines.values(), key=lambda x: x['start'])
        recorder.receive(' '.join(x['text'] for x in snapshot).strip(), segments=snapshot)
    start = time.perf_counter()
    transcriber = Transcriber(path, ModelArch.MEDIUM_STREAMING, update_interval=.5,
                              options={'identify_speakers': 'false'})
    loaded = time.perf_counter() - start
    stream = None
    try:
        stream = transcriber.create_stream(update_interval=.5)
        stream.add_listener(listener)
        stream.start()
        for chunk in recorder.chunks(pcm, dataset['packet_samples'], dataset['tail_seconds']):
            if recorder.error:
                raise RuntimeError(recorder.error)
            stream.add_audio(chunk.tolist(), sample_rate=16000)
        final = stream.stop()
        if final is None:
            raise RuntimeError('No final Moonshine transcript.')
        snapshot = [{'start': x.start_time, 'end': x.start_time + x.duration, 'text': x.text,
                     'completed': x.is_complete} for x in final.lines]
        recorder.receive(' '.join(x['text'] for x in snapshot).strip(), segments=snapshot, final=True)
        if recorder.error:
            raise RuntimeError(recorder.error)
    finally:
        if stream:
            stream.close()
        transcriber.close()
    return {'backend': 'moonshine-voice', 'version': '0.1.5', 'device': 'Windows CPU',
            'precision': 'published quantized ORT assets', 'load_seconds': loaded,
            'model_path': str(path), 'model_sha256': {str(p.relative_to(path)): sha256(p) for p in path.rglob('*') if p.is_file()},
            'update_interval_seconds': .5, 'threads': 'runtime default', 'includes_loopback_transport': False}


def whisper(args, pcm, recorder, dataset):
    dll_handles = []
    cuda_paths = sorted({p.parent for p in (args.cache / 'cuda-runtime').rglob('*.dll')})
    if args.profile.endswith('-cuda') and cuda_paths:
        os.environ['PATH'] = os.pathsep.join(map(str, cuda_paths)) + os.pathsep + os.environ.get('PATH', '')
        dll_handles = [os.add_dll_directory(str(p)) for p in cuda_paths]
    # This imports the recognizer backend only, not its microphone client,
    # application, context system or checkpoint matcher.
    from whisper_live.backend.faster_whisper_backend import ServeClientFasterWhisper
    from whisper_live.transcriber.transcriber_faster_whisper import WhisperModel
    model_name = 'tiny.en' if 'tiny' in args.profile else 'base.en'
    folder = Path.home() / '.cache/huggingface/hub' / ('models--Systran--faster-whisper-' + model_name) / 'snapshots'
    cached = sorted(p for p in folder.glob('*') if (p / 'model.bin').is_file())
    if not cached:
        raise FileNotFoundError('Whisper weights are not cached: ' + model_name)
    model_path = cached[-1]
    device = 'cuda' if args.profile.endswith('-cuda') else 'cpu'
    precision = 'float16' if device == 'cuda' else 'int8'
    details = {'backend': 'WhisperLive/faster-whisper', 'device': device, 'precision': precision,
               'model_file': str(model_path), 'model_sha256': sha256(model_path / 'model.bin'),
               'faster_whisper_version': importlib.metadata.version('faster-whisper'),
               'ctranslate2_version': importlib.metadata.version('ctranslate2'),
               'vad': {'threshold': .5, 'min_silence_duration_ms': 160, 'speech_pad_ms': 120},
               'same_output_threshold': 3, 'send_last_n_segments': 100, 'includes_loopback_transport': False}
    details['cuda_runtime_directories'] = [str(p) for p in cuda_paths] if device == 'cuda' else []
    details['buffer_trim_events'] = []
    class Socket:
        def send(self, message):
            value = json.loads(message)
            if value.get('status') == 'ERROR':
                recorder.error = value.get('message')
            if 'segments' in value:
                segments = value['segments']
                recorder.receive(' '.join(x['text'] for x in segments).strip(), segments=segments)
        def close(self):
            pass
    class Backend(ServeClientFasterWhisper):
        MAX_BUFFER_DURATION_S = max(45, len(pcm) / 16000 + dataset['tail_seconds'] + 1)
        decoded_through_seconds = 0.0

        def create_model(self, _autodetected_device):
            start = time.perf_counter()
            self.transcriber = WhisperModel(str(model_path), device=device, compute_type=precision,
                                            cpu_threads=2, local_files_only=True)
            if self.transcriber.model.device != device:
                raise RuntimeError('Whisper selected a different device than the requested profile.')
            details['actual_device'] = self.transcriber.model.device
            details['load_seconds'] = time.perf_counter() - start
        def transcribe_audio(self, input_sample):
            try:
                with self.lock:
                    start_seconds = self.timestamp_offset
                result = super().transcribe_audio(input_sample)
                self.decoded_through_seconds = max(self.decoded_through_seconds,
                                                   start_seconds + len(input_sample) / self.RATE)
                return result
            except Exception as error:
                # WhisperLive otherwise logs decoder failures and retries forever.
                recorder.error = repr(error)
                raise
        def add_frames(self, frame_np):
            with self.lock:
                previous_offset = self.frames_offset
                processed = self.timestamp_offset
            super().add_frames(frame_np)
            if self.frames_offset > previous_offset:
                discarded = max(0, self.frames_offset - processed)
                event = {'buffer_offset_seconds': self.frames_offset,
                         'processed_before_seconds': processed,
                         'discarded_unprocessed_seconds': discarded}
                details['buffer_trim_events'].append(event)
                recorder.emit('decoder_buffer_trim', **event)
                if discarded > .001:
                    raise RuntimeError('Whisper discarded unprocessed audio after falling behind real time.')
    previous_hook = threading.excepthook
    def failed_thread(args):
        recorder.error = repr(args.exc_value)
        previous_hook(args)
    threading.excepthook = failed_thread
    backend = None
    try:
        backend = Backend(Socket(), client_uid='asr-only', model=model_name, language='en',
                          initial_prompt=None, hotwords=None, use_vad=True, vad_parameters=details['vad'],
                          same_output_threshold=3, single_model=False, send_last_n_segments=100)
        if recorder.error or not hasattr(backend, 'trans_thread'):
            raise RuntimeError(recorder.error or 'Whisper backend did not start.')
        for chunk in recorder.chunks(pcm, dataset['packet_samples'], dataset['tail_seconds']):
            if recorder.error:
                raise RuntimeError(recorder.error)
            backend.add_frames(chunk)
        # Wait for the final hypothesis to stop revising, with a bounded drain.
        deadline = time.perf_counter() + 180
        while time.perf_counter() < deadline:
            if recorder.error:
                raise RuntimeError(recorder.error)
            updates = [e for e in recorder.events if e['kind'] == 'transcript']
            last = updates[-1]['wall_seconds'] if updates else 0
            if (backend.decoded_through_seconds >= len(pcm) / 16000
                    and time.perf_counter() - recorder.origin - last >= 2):
                break
            time.sleep(.1)
        else:
            raise TimeoutError('Whisper did not decode through the final source sample')
        details['decoded_through_seconds'] = backend.decoded_through_seconds
        details['source_audio_seconds'] = len(pcm) / 16000
        details['audio_buffer_limit_seconds'] = backend.MAX_BUFFER_DURATION_S
    finally:
        if backend and hasattr(backend, 'trans_thread'):
            backend.cleanup()
            backend.trans_thread.join(timeout=20)
            if backend.trans_thread.is_alive():
                raise RuntimeError('Whisper decoder failed to stop.')
        threading.excepthook = previous_hook
    if recorder.error:
        raise RuntimeError(recorder.error)
    recorder.receive(recorder.last_text or '', final=True)
    return details


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', choices=PROFILES, required=True)
    parser.add_argument('--dataset', type=Path, required=True)
    parser.add_argument('--case', required=True)
    parser.add_argument('--cache', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--nemo-url', default='ws://127.0.0.1:9097')
    parser.add_argument('--delivery', choices=('inline', 'queued'), default='inline')
    args = parser.parse_args()
    enforce_no_tracker()
    dataset = json.loads(args.dataset.read_text(encoding='utf-8'))
    case = next(x for x in dataset['cases'] if x['id'] == args.case)
    if dataset['protocol'] != PROTOCOL or dataset['hints'] is not False or dataset['tracker'] is not False:
        raise ValueError('Not an ASR-only baseline dataset.')
    if sha256(case['audio']) != case['audio_sha256']:
        raise ValueError('Audio differs from frozen dataset.')
    import numpy as np
    with wave.open(case['audio']) as wav:
        pcm = np.frombuffer(wav.readframes(wav.getnframes()), dtype='<i2').astype(np.float32) / 32768
    recorder = ASRRecorder(args.output.with_suffix('.events.jsonl'), delivery=args.delivery)
    result = {'protocol': PROTOCOL, 'profile': args.profile, 'case': case['id'],
              'audio_sha256': case['audio_sha256'], 'duration_seconds': case['duration_seconds'],
              'platform': platform.platform(), 'python': sys.version,
              'tracker': False, 'hints': False, 'packet_samples': dataset['packet_samples'],
              'tail_seconds': dataset['tail_seconds'], 'audio_delivery_mode': args.delivery,
              'gpu_before': gpu_snapshot()}
    try:
        backend = nemo if args.profile == 'nemo-cuda' else (
            whisper if args.profile.startswith('whisper-') else
            moonshine if args.profile == 'moonshine-cpu' else native)
        start = time.perf_counter()
        result['runtime'] = backend(args, pcm, recorder, dataset)
        result['trial_wall_seconds_including_load'] = time.perf_counter() - start
        events = recorder.events
        audio = [e for e in events if e['kind'] == 'audio']
        eof = next(e for e in events if e['kind'] == 'end_of_audio')
        expected = len(pcm) + round(dataset['tail_seconds'] * 16000)
        if sum(e['sample_count'] for e in audio) != expected:
            raise RuntimeError('Incomplete sample delivery.')
        if not any(e['kind'] == 'transcript' and words_nonempty(e['text']) for e in events):
            raise RuntimeError('No nonempty transcript returned.')
        result['delivery'] = {'samples_sent': expected, 'original_samples': len(pcm),
                              'max_feed_lateness_seconds': max(e['feed_lateness_seconds'] for e in audio),
                              'end_of_audio_seconds': eof['wall_seconds'],
                              'finalization_seconds': time.perf_counter() - recorder.origin - eof['wall_seconds']}
        if args.delivery == 'queued':
            captures = [e for e in events if e['kind'] == 'capture']
            capture_eof = next(e for e in events if e['kind'] == 'end_of_capture')
            if capture_eof['samples'] != expected:
                raise RuntimeError('Incomplete capture.')
            result['delivery'].update(
                samples_captured=capture_eof['samples'],
                end_of_capture_seconds=capture_eof['wall_seconds'],
                max_capture_lateness_seconds=max(e['capture_lateness_seconds'] for e in captures),
                max_queued_audio_seconds=max(e['pending_audio_seconds'] for e in captures),
                max_queue_wait_seconds=max(e['queue_wait_seconds'] for e in audio),
            )
        result['metrics'] = score_updates(events, case)
        result['status'] = 'ok'
        args.output.with_suffix('.transcript.txt').write_text(result['metrics']['final_text'], encoding='utf-8')
    except Exception as error:
        result.update(status='failed', error=repr(error), traceback=traceback.format_exc())
    finally:
        result['gpu_after'] = gpu_snapshot()
        result['no_tracker_modules_imported'] = not any(x.startswith(('books_to_life.matching', 'books_to_life.context')) for x in sys.modules)
        try:
            import psutil
            memory = psutil.Process().memory_info()
            result['worker_rss_at_end_bytes'] = memory.rss
            result['worker_peak_working_set_bytes'] = getattr(memory, 'peak_wset', None)
        except ImportError:
            result['worker_rss_at_end_bytes'] = None
        recorder.close()
        atomic_json(args.output, result)
    print(json.dumps({k: result.get(k) for k in ('profile', 'case', 'status', 'error')}), flush=True)
    if result['status'] != 'ok':
        raise SystemExit(1)


def words_nonempty(text):
    return bool(text.strip())


if __name__ == '__main__':
    main()
