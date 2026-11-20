"""Play the first Sky Garden cue from a Books to Life trigger stream."""

import argparse
from functools import partial
import json
import os
from pathlib import Path
import shutil
import socket
import struct
import subprocess
import sys
from threading import Timer


DEMO_DIR = Path(__file__).resolve().parent
REPO = DEMO_DIR.parents[1]
PROJECT = DEMO_DIR / 'Sky Garden.mmp'
VIDEO_PROJECT = DEMO_DIR / 'Sky Garden - Spoken Cue.mmp'
VIDEO_FILE = 'Sky Garden - Silver Seed.mp4'
GARDEN_SOURCE = 2
CUE_PREFIX = '[TRIGGER] seed_found: '
# Hold the final moment before the six-second clip can loop.
VIDEO_HOLD_SECONDS = 5.85


def osc_string(value):
    data = value.encode('utf-8') + b'\0'
    return data + b'\0' * (-len(data) % 4)


def send_source(port, command, value=None):
    packet = osc_string(f'/mapmap/source/{command}')
    if value is None:
        packet += osc_string(',i') + struct.pack('>i', GARDEN_SOURCE)
    else:
        packet += osc_string(',if') + struct.pack('>if', GARDEN_SOURCE, value)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sender:
        sender.sendto(packet, ('127.0.0.1', port))


def audio_player():
    sound = DEMO_DIR / 'silver-seed.wav'
    if not sound.is_file():
        raise FileNotFoundError(sound)
    if sys.platform == 'win32':
        import winsound

        return lambda: winsound.PlaySound(str(sound), winsound.SND_FILENAME)

    for name in ('pw-play', 'paplay', 'aplay'):
        executable = shutil.which(name)
        if executable:
            return lambda: subprocess.run([executable, str(sound)], check=True)
    raise RuntimeError('Install a WAV player such as aplay (alsa-utils) on the Jetson host.')


def play_cue(port, play_sound):
    send_source(port, 'opacity', 1.0)
    print('[SKY GARDEN] Sent visual cue. Starting chime.', flush=True)
    play_sound()


def hold_video(port):
    send_source(port, 'volume', 0.0)
    send_source(port, 'pause')


def reset_video(port):
    send_source(port, 'opacity', 0.0)
    hold_video(port)
    send_source(port, 'rewind')


def play_video(port):
    send_source(port, 'rewind')
    send_source(port, 'volume', 1.0)
    send_source(port, 'opacity', 1.0)
    send_source(port, 'play')
    Timer(VIDEO_HOLD_SECONDS, hold_video, args=(port,)).start()
    print('[SKY GARDEN] Started the Silver Seed video and its chime.', flush=True)


def listen(stream, fire_cue):
    played = False
    for line in stream:
        print(line, end='', flush=True)
        if not played and line.startswith(CUE_PREFIX):
            fire_cue()
            played = True


def read_with_parakeet(fire_cue):
    command = [
        sys.executable, '-u', '-m', 'books_to_life.cli.run_client',
        '--model', 'parakeet-nemo', '--server', '127.0.0.1', '--port', '9097',
        '--matching_mode', 'split', '--no_book_context', '--checkpoint_stability', '1',
        '--checkpoints', 'recordings/library/stories/sample/readers/demo/checkpoints.json',
    ]
    print('[SKY GARDEN] Connecting the microphone client to Parakeet on port 9097.', flush=True)
    with subprocess.Popen(
        command, cwd=REPO, env={**os.environ, 'PYTHONIOENCODING': 'utf-8'},
        stdout=subprocess.PIPE, encoding='utf-8', errors='replace',
    ) as client:
        try:
            listen(client.stdout, fire_cue)
            return client.wait()
        finally:
            if client.poll() is None:
                client.terminate()


def relink_project(video):
    project_path = VIDEO_PROJECT if video else PROJECT
    project = json.loads(project_path.read_text(encoding='utf-8'))
    media = {1: 'wall-calibration.png', GARDEN_SOURCE: VIDEO_FILE if video else 'sky-garden.png'}
    for source in project['sources']:
        source['uri'] = (DEMO_DIR / media[source['id']]).as_posix()
    project_path.write_text(json.dumps(project, indent=2) + '\n', encoding='utf-8')
    print(project_path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--listen', action='store_true', help='Read the speech client output from stdin.')
    mode.add_argument('--read', action='store_true', help='Start the microphone client for the local Parakeet demo.')
    mode.add_argument('--reset', action='store_true', help='Return MapMap to its calibration grid.')
    mode.add_argument('--relink', action='store_true', help='Update the demo project media paths after moving it.')
    parser.add_argument('--video', action='store_true', help='Use the spoken-cue MapMap project and its MP4 soundtrack.')
    parser.add_argument('--port', type=int, default=12345, help='MapMap local OSC port (default: 12345).')
    args = parser.parse_args()
    try:
        if args.relink:
            relink_project(args.video)
        elif args.reset:
            if args.video:
                reset_video(args.port)
            else:
                send_source(args.port, 'opacity', 0.0)
        else:
            if args.video:
                reset_video(args.port)
                if args.read or args.listen:
                    print('[SKY GARDEN] Video armed. Waiting for the silver-seed checkpoint.', flush=True)
                fire_cue = partial(play_video, args.port)
            else:
                play_sound = audio_player()
                fire_cue = partial(play_cue, args.port, play_sound)

            if args.read:
                return read_with_parakeet(fire_cue)
            elif args.listen:
                listen(sys.stdin, fire_cue)
            else:
                fire_cue()
    except KeyboardInterrupt:
        return 130
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as error:
        parser.exit(1, f'[SKY GARDEN] {error}\n')


if __name__ == '__main__':
    sys.exit(main())
