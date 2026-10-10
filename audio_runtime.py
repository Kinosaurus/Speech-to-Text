"""Microphone selection and bounded startup for the pod client."""

import time


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
