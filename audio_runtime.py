"""Microphone selection and bounded startup for the pod client."""

import time
import hashlib
from pathlib import Path
import wave


def prepare_stream_audio(source):
    """Reuse ready PCM files; cache conversions without root-level duplicates."""
    source = Path(source).resolve()
    try:
        with wave.open(str(source), 'rb') as audio:
            if (audio.getnchannels(), audio.getsampwidth(), audio.getframerate(),
                    audio.getcomptype()) == (1, 2, 16000, 'NONE'):
                return str(source)
    except (wave.Error, EOFError):
        pass
    import av
    digest = hashlib.sha256()
    with source.open('rb') as data:
        for block in iter(lambda: data.read(1024 * 1024), b''):
            digest.update(block)
    cache = Path(__file__).resolve().parent / 'recordings/cache'
    cache.mkdir(parents=True, exist_ok=True)
    target = cache / f'{source.stem}-{digest.hexdigest()[:16]}-16k.wav'
    if target.is_file():
        return str(target)
    partial = target.with_suffix('.partial.wav')
    # An explicit Python file handle ensures Windows releases the converted
    # file before the atomic rename, even if PyAV stream objects remain alive.
    with partial.open('wb') as binary, av.open(str(source)) as incoming, \
            av.open(binary, mode='w', format='wav') as outgoing:
        stream = outgoing.add_stream('pcm_s16le', rate=16000)
        stream.layout = 'mono'
        resampler = av.AudioResampler(format='s16', layout='mono', rate=16000)
        for frame in incoming.decode(audio=0):
            frame.pts = None
            for converted in resampler.resample(frame):
                for packet in stream.encode(converted):
                    outgoing.mux(packet)
        for converted in resampler.resample(None):
            for packet in stream.encode(converted):
                outgoing.mux(packet)
        for packet in stream.encode(None):
            outgoing.mux(packet)
    partial.replace(target)
    return str(target)


def input_devices(audio):
    return [audio.get_device_info_by_index(index)
            for index in range(audio.get_device_count())
            if audio.get_device_info_by_index(index).get('maxInputChannels', 0) > 0]


def select_input_device(audio, selection=None):
    if selection is None or str(selection).casefold() == 'default':
        return audio.get_default_input_device_info()
    devices = input_devices(audio)
    if str(selection).isdigit():
        matches = [device for device in devices if device['index'] == int(selection)]
    else:
        matches = [device for device in devices
                   if str(selection).casefold() in device['name'].casefold()]
    if not matches:
        raise ValueError(f'No input microphone matches {selection!r}. Use --list_input_devices.')
    if len(matches) > 1:
        raise ValueError(f'Multiple microphones match {selection!r}. Use a device index from --list_input_devices.')
    return matches[0]


def configure_microphone(client, selection=None, chunk=4096):
    device = select_input_device(client.p, selection)
    # WhisperLive opens the default microphone during construction. Reopen only
    # when a different device/buffer was requested or the initial open failed.
    if selection is not None or chunk != client.chunk or client.stream is None:
        if client.stream is not None:
            client.stream.stop_stream()
            client.stream.close()
            client.stream = None
        client.chunk = chunk
        client.stream = client.p.open(
            format=client.format, channels=client.channels, rate=client.rate,
            input=True, input_device_index=int(device['index']),
            frames_per_buffer=chunk,
        )
    return device


def wait_for_server(client, timeout=180):
    """Wait without WhisperLive's busy spin, including model loading time."""
    deadline = time.monotonic() + timeout
    while not all(connection.recording for connection in client.clients):
        for connection in client.clients:
            if connection.server_error or connection.waiting:
                raise ConnectionError('Recognition server rejected the session. Check the server logs.')
        if time.monotonic() >= deadline:
            raise TimeoutError(f'Recognition server was not ready after {timeout:g}s. Check its address and logs.')
        time.sleep(0.05)
