import json
import threading
import time
import uuid

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
        options = {'uid': uid, 'model': 'nemotron', 'chunk_ms': args.chunk_ms, 'language': 'en', 'task': 'transcribe'}
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
        import hashlib
        expected_hash = hashlib.sha256((hotwords or '').encode()).hexdigest()
        if (reply.get('backend') != 'nemotron' or reply.get('chunk_ms') != args.chunk_ms
                or reply.get('boost') != 1.0 or reply.get('applied_hotwords_sha256') != expected_hash):
            raise RuntimeError('Nemotron did not acknowledge the frozen configuration')
        configuration = dict(reply)
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
        return {'backend': 'Nemotron WebSocket', 'acknowledged_configuration': configuration, 'device': 'WSL CUDA (existing server)',
                'precision': 'existing server configuration', 'ready_seconds': ready_seconds,
                'load_seconds': None, 'load_scope': 'already resident server; no model reload',
                'buffering': (f'{reply["chunk_ms"]} ms chunk / {reply["right_ms"]} ms right context'
                              if 'chunk_ms' in reply and 'right_ms' in reply
                              else f'Nemotron native {args.chunk_ms} ms; context {configuration["att_context"]}'),
                'server_url': args.nemo_url, 'includes_loopback_transport': True, **boost_ack}
    finally:
        done.set()
        ws.close()
        if thread:
            thread.join(timeout=5)

