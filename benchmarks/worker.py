"""Run one isolated profile. Use run.py for the complete five-model comparison."""
import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from benchmarks.common import MemorySampler, Recorder, audio, gpu_memory_mib, paced_chunks
from benchmarks.metrics import latest_text


def whisper(args, pcm, manifest, reference):
    from whisper_live.backend.faster_whisper_backend import ServeClientFasterWhisper
    from whisper_live.transcriber.transcriber_faster_whisper import WhisperModel
    from books_to_life.context.book_context import install_context_updates

    recorder = Recorder(manifest, args.hints)
    details = {'runtime': 'WhisperLive/faster-whisper', 'device': 'cuda', 'precision': 'float16',
               'faster_whisper_version': importlib.metadata.version('faster-whisper'),
               'ctranslate2_version': importlib.metadata.version('ctranslate2'),
               'vad': {'threshold': 0.5, 'min_silence_duration_ms': 160, 'speech_pad_ms': 120},
               'same_output_threshold': 3, 'beam_size': 5}
    class Socket:
        backend = None
        revision = 0
        audio_end = 0
        def send(self, message):
            value = json.loads(message)
            if value.get('status') == 'ERROR':
                raise RuntimeError(value)
            if 'segments' not in value:
                return
            segments = value['segments']
            hints = recorder.receive(latest_text(segments), segments, self.audio_end)
            if hints and self.backend:
                self.revision += 1
                self.backend.book_context_state.queue(self.revision, hints)
        def close(self):
            pass
    socket = Socket()
    class Backend(ServeClientFasterWhisper):
        def create_model(self, device):
            started = time.perf_counter()
            self.transcriber = WhisperModel(self.model_size_or_path, device='cuda', compute_type='float16',
                                            cpu_threads=2, local_files_only=True)
            details['load_seconds'] = time.perf_counter() - started
    hints = recorder.context.hints if recorder.context else None
    backend = Backend(socket, client_uid='benchmark', model=args.model, language='en',
                      initial_prompt=hints.initial_prompt if hints else None,
                      hotwords=hints.hotwords if hints else None, use_vad=True,
                      vad_parameters=details['vad'], same_output_threshold=3,
                      single_model=False, send_last_n_segments=100)
    socket.backend = backend
    if args.hints:
        install_context_updates(backend)
    details['gpu_memory_loaded_mib'] = gpu_memory_mib()
    lags = []
    recorder.begin()
    try:
        for chunk, end, lag in paced_chunks(pcm):
            socket.audio_end = end
            backend.add_frames(chunk)
            lags.append(lag)
        # The real app's backend needs repeated updates to settle its final segment.
        time.sleep(2)
    finally:
        backend.cleanup()
        backend.trans_thread.join(timeout=20)
        if backend.trans_thread.is_alive():
            raise RuntimeError('Whisper worker failed to stop; refusing to start another benchmark.')
    details['stream'] = recorder.summary(reference)
    details['stream']['max_feed_lateness_seconds'] = max(lags)
    details['gpu_memory_after_stream_mib'] = gpu_memory_mib()
    return details


def cpp(args, pcm, manifest, reference):
    native = args.cache / 'transcribe-native-windows-x86_64-cpu-vulkan'
    os.environ['TRANSCRIBE_LIBRARY'] = str(native / 'transcribe.dll')
    dll_directory = os.add_dll_directory(str(native))
    sys.path.insert(0, str(args.cache / 'api'))
    import transcribe_cpp
    device = next(d for d in transcribe_cpp.backends() if d.kind == 'vulkan' and 'RTX 4060' in d.description)
    filename = ('parakeet-unified-en-0.6b-F16.gguf' if args.model == 'parakeet'
                else 'moonshine-streaming-medium-F16.gguf')
    details = {'runtime': 'transcribe.cpp 0.4.0', 'device': repr(device), 'precision': 'F16',
               'hints_supported': False, 'cpu_threads': 2, 'model_file': filename}
    started = time.perf_counter()
    with transcribe_cpp.Model(args.cache / filename, device=device) as model:
        details['load_seconds'] = time.perf_counter() - started
        assert model.device.kind == 'vulkan' and 'RTX 4060' in model.device.description
        details['selected_device'] = repr(model.device)
        with model.session(n_threads=2) as session:
            if args.model == 'parakeet':
                family = transcribe_cpp.ParakeetBufferedStreamOptions(
                    left_ms=5600, chunk_ms=args.chunk_ms, right_ms=args.chunk_ms)
                details['stream_geometry_ms'] = {'left': 5600, 'chunk': args.chunk_ms, 'right': args.chunk_ms}
                details['audio_buffer_ms'] = args.chunk_ms * 2
            else:
                family = (transcribe_cpp.MoonshineStreamingOptions(min_decode_interval_ms=args.moonshine_decode_ms)
                          if args.moonshine_decode_ms is not None else None)
                details['min_decode_interval_ms'] = args.moonshine_decode_ms
            recorder = Recorder(manifest)
            lags = []
            with session.stream(language='en', family=family) as stream:
                recorder.begin()
                for chunk, end, lag in paced_chunks(pcm):
                    update = stream.feed(chunk)
                    if update.result_changed:
                        text = stream.text().full
                        recorder.receive(text, [{'start': 0, 'end': end, 'text': text, 'completed': False}], end)
                    lags.append(lag)
                stream.finalize()
                text = stream.text().full
                recorder.receive(text, [{'start': 0, 'end': len(pcm) / 16000, 'text': text, 'completed': True}],
                                 len(pcm) / 16000, final=True)
            details['stream'] = recorder.summary(reference)
            details['stream']['max_feed_lateness_seconds'] = max(lags)
            details['gpu_memory_after_stream_mib'] = gpu_memory_mib()
    return details


def moonshine(args, pcm, manifest, reference):
    if args.ort_single_thread:
        os.environ['MOONSHINE_ORT_SINGLE_THREAD'] = '1'
    else:
        os.environ.pop('MOONSHINE_ORT_SINGLE_THREAD', None)
    sys.path.insert(0, str(args.cache / 'moonshine-python'))
    from moonshine_voice import ModelArch, Transcriber
    model_path = Path((args.cache / 'moonshine-model-path.txt').read_text().strip())
    recorder = Recorder(manifest, args.hints)
    details = {'runtime': 'moonshine-voice 0.1.5 (official)', 'device': 'CPU',
               'precision': 'published quantized ORT assets', 'hints_supported': True,
               'update_interval_seconds': 0.5, 'model_path': str(model_path),
               'vad': 'official runtime default',
               'cpu_threads': 1 if args.ort_single_thread else 'official runtime default'}
    options = {'identify_speakers': 'false'}
    if recorder.context:
        hints = recorder.context.hints
        options.update(context=hints.initial_prompt, keyterms=hints.hotwords)
    started = time.perf_counter()
    transcriber = Transcriber(model_path, ModelArch.MEDIUM_STREAMING, update_interval=0.5, options=options)
    details['load_seconds'] = time.perf_counter() - started
    # The official API retains stable line IDs. Replace changed lines by ID instead of appending text.
    lines = {}
    audio_end = 0
    def listener(event):
        if hasattr(event, 'error'):
            raise RuntimeError(str(event.error))
        line = event.line
        lines[line.line_id] = {'start': line.start_time, 'end': line.start_time + line.duration,
                               'text': line.text, 'completed': line.is_complete}
        snapshot = sorted(lines.values(), key=lambda item: item['start'])
        hints = recorder.receive(latest_text(snapshot), snapshot, audio_end)
        if hints:
            transcriber.set_context(hints.initial_prompt or '')
            transcriber.set_keyterms((hints.hotwords or '').split(', '))
    stream = transcriber.create_stream(update_interval=0.5)
    stream.add_listener(listener)
    stream.start()
    recorder.begin()
    lags = []
    try:
        for chunk, end, lag in paced_chunks(pcm):
            audio_end = end
            stream.add_audio(chunk.tolist(), sample_rate=16000)
            lags.append(lag)
        final = stream.stop()
        if final is None:
            raise RuntimeError('Moonshine did not return a final transcript.')
        snapshot = [{'start': line.start_time, 'end': line.start_time + line.duration,
                     'text': line.text, 'completed': line.is_complete} for line in final.lines]
        recorder.receive(latest_text(snapshot), snapshot, audio_end, final=True)
        details['stream'] = recorder.summary(reference)
        details['stream']['max_feed_lateness_seconds'] = max(lags)
        details['gpu_memory_after_stream_mib'] = gpu_memory_mib()
    finally:
        stream.close()
        transcriber.close()
    return details


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backend', choices=('whisper', 'cpp', 'moonshine'), required=True)
    parser.add_argument('--model', required=True)
    parser.add_argument('--hints', action='store_true')
    parser.add_argument('--chunk-ms', type=int, default=160)
    parser.add_argument('--audio', type=Path, required=True)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--cache', type=Path, default=Path('model-cache/asr-benchmark'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--ort-single-thread', action='store_true')
    parser.add_argument('--moonshine-decode-ms', type=int)
    args = parser.parse_args()
    if args.hints and args.backend == 'cpp':
        parser.error('These C++ model profiles do not implement book hints.')
    if args.backend == 'cpp' and args.model not in ('parakeet', 'moonshine'):
        parser.error('The C++ model must be parakeet or moonshine.')
    if args.moonshine_decode_ms is not None and (
        args.backend != 'cpp' or args.model != 'moonshine' or args.moonshine_decode_ms < 1
    ):
        parser.error('--moonshine-decode-ms requires the C++ Moonshine profile and a positive interval.')
    args.cache = args.cache.resolve()
    manifest = json.loads(args.manifest.read_text(encoding='utf-8'))
    reference = ' '.join(page['text'] for page in sorted(manifest['pages'], key=lambda p: p['page']))
    pcm = audio(args.audio)
    metadata = {'model': args.model, 'backend': args.backend, 'hints': args.hints,
                'audio': str(args.audio), 'audio_seconds': len(pcm) / 16000,
                'reference': reference, 'reference_status': 'supplied passage; child audio not manually transcribed',
                'benchmark_mode': 'streaming-only-v1', 'stream_repetitions': 1,
                'warmup': 'none; audio replayed only once after model loading',
                'platform': platform.platform(), 'python': sys.version,
                'checkpoint_matcher': 'unchanged AlignmentMatcher',
                'latency_scope': 'arrival of the transcript update that confirmed a checkpoint; '
                                 'matcher execution, microphone, WebSocket and physical effects excluded'}
    metadata['audio_sha256'] = hashlib.sha256(args.audio.read_bytes()).hexdigest()
    metadata['manifest_sha256'] = hashlib.sha256(args.manifest.read_bytes()).hexdigest()
    metadata['chunk_ms'] = args.chunk_ms
    metadata['ort_single_thread'] = args.ort_single_thread
    metadata['moonshine_decode_ms'] = args.moonshine_decode_ms
    with MemorySampler() as memory:
        details = globals()[args.backend](args, pcm, manifest, reference)
    result = {**metadata, **details, 'sampled_peak_process_rss_bytes': memory.peak or None}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps({'output': str(args.output),
                      'stream_reference_wer': details['stream']['reference_score']['wer'],
                      'triggered': details['stream']['triggered_ids']}, indent=2), flush=True)


if __name__ == '__main__':
    main()
