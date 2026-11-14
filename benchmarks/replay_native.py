"""Pace the original pod WAVs at 1x through the native server and score software cues."""

import argparse
import asyncio
from contextlib import suppress
import json
from pathlib import Path
from statistics import median
import time
import wave
import zipfile

import numpy as np
from websockets.asyncio.client import connect

from books_to_life.matching.checkpoint_matcher import MATCHING_ENGINE, normalize_text
from books_to_life.matching.timely_matcher import TimelyEvidenceMatcher


SAMPLE_RATE = 16000
PACKET_FRAMES = 4096
STORIES = {'little-mermaid': 'little_mermaid', 'tea': 'tea'}
ROOT = Path(__file__).resolve().parents[1]


async def replay(server, model, case, recording):
    story = STORIES[case['book']]
    manifest = ROOT / 'recordings/library/stories' / story / 'readers' / story / 'checkpoints.json'
    matcher = TimelyEvidenceMatcher.from_file(manifest, stability=2)
    endpoints = {str(cp['id']): normalize_text(cp.get('effect_cue', cp['checkpoint_text'])).split()[-1]
                 for cp in matcher.checkpoints}
    first_report = {}
    cues = []
    callback_lag = []
    previous_text = None
    final_text = ''
    origin = 0.0
    sent = 0
    last_packet_lag = 0.0
    expected = case['expected']
    with wave.open(recording) as audio:
        if (audio.getnchannels(), audio.getsampwidth(), audio.getframerate()) != (1, 2, SAMPLE_RATE):
            raise ValueError(f"{case['name']}: expected 16-bit mono WAV at 16 kHz")
        if case['samples'] != audio.getnframes():
            raise ValueError(f"{case['name']}: sample count differs from manifest")
        async with connect(server, ping_interval=None) as socket:
            await socket.send(json.dumps(dict(uid=case['name'], model=model, language='en', task='transcribe')))
            ready = json.loads(await asyncio.wait_for(socket.recv(), 30))
            if ready.get('message') != 'SERVER_READY':
                raise RuntimeError(f"Native server rejected {case['name']}: {ready}")

            async def receive():
                nonlocal final_text, previous_text
                async for raw in socket:
                    arrived = time.monotonic() - origin
                    event = json.loads(raw)
                    if event.get('status') == 'ERROR':
                        raise RuntimeError(event['message'])
                    if event.get('message') == 'STREAM_DONE':
                        return arrived
                    segments = event.get('segments')
                    if not segments:
                        continue
                    text = ' '.join(segment['text'] for segment in segments)
                    words = set(normalize_text(text).split())
                    for key, word in endpoints.items():
                        if word in words:
                            first_report.setdefault(key, arrived)
                    if text.strip() and text != previous_text and not segments[-1]['completed']:
                        callback_lag.append((arrived, arrived - float(segments[-1]['end'])))
                    previous_text = final_text = text
                    update = matcher.process(text, segments)
                    if update.triggered:
                        elapsed = time.monotonic() - origin
                        first = first_report.get(update.checkpoint_id)
                        cues.append(dict(id=update.checkpoint_id, seconds_from_audio_start=round(elapsed, 3),
                                         seconds_after_first_literal_endpoint=None if first is None
                                         else round(elapsed-first, 3)))
                raise RuntimeError('Server closed before STREAM_DONE')

            origin = time.monotonic()
            receiver = asyncio.create_task(receive())
            try:
                while pcm := audio.readframes(PACKET_FRAMES):
                    sent += len(pcm)//2
                    deadline = origin + sent/SAMPLE_RATE
                    await asyncio.sleep(max(0.0, deadline - time.monotonic()))
                    if receiver.done():
                        raise RuntimeError(f'Server ended early at {sent/SAMPLE_RATE:.2f}s: {receiver.result()}')
                    samples = np.frombuffer(pcm, dtype='<i2').astype('<f4') / 32768
                    await socket.send(samples.tobytes())
                    last_packet_lag = time.monotonic() - deadline
                await socket.send(b'END_OF_AUDIO')
                finished = await asyncio.wait_for(receiver, 120)
            finally:
                if not receiver.done():
                    receiver.cancel()
                    with suppress(asyncio.CancelledError):
                        await receiver

    duration = sent/SAMPLE_RATE
    ids = [cue['id'] for cue in cues]
    first_half = [seconds for at, seconds in callback_lag if at <= duration/2]
    second_half = [seconds for at, seconds in callback_lag if at > duration/2]
    return dict(clip=case['name'], duration_seconds=round(duration, 3), expected=expected,
                cues=cues, missing=[cue for cue in expected if cue not in ids],
                unexpected=[cue for cue in ids if cue not in expected],
                duplicate_cues=len(ids)-len(set(ids)), exact=ids == expected,
                first_half_callback_lag_seconds=round(median(first_half), 3) if first_half else None,
                second_half_callback_lag_seconds=round(median(second_half), 3) if second_half else None,
                final_drain_seconds=round(finished-duration-last_packet_lag, 3),
                sender_overrun_seconds=round(last_packet_lag, 3),
                final_transcript=final_text)


async def main(args):
    results = []
    with zipfile.ZipFile(args.archive) as archive:
        cases = json.loads(archive.read('cases.json'))
        if args.clip:
            cases = [case for case in cases if case['name'] == args.clip]
        if not cases:
            raise SystemExit('No clips matched.')
        for case in cases:
            print(f"Streaming {case['name']} at 1x", flush=True)
            with archive.open(case['audio']) as recording:
                row = await replay(args.server, args.model, case, recording)
            results.append(row)
            print(f"  Cues {len(row['cues'])}/{len(row['expected'])}; "
                  f"callback lag {row['first_half_callback_lag_seconds']} to "
                  f"{row['second_half_callback_lag_seconds']} s; "
                  f"final drain {row['final_drain_seconds']:.3f} s", flush=True)
            args.output.write_text(json.dumps(dict(playback_rate=1, model=args.model, matching_engine=MATCHING_ENGINE,
                                                  stability=2, results=results), indent=2)+'\n', encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path, help='ZIP with cases.json and the corresponding WAVs')
    parser.add_argument('--server', default='ws://127.0.0.1:9091')
    parser.add_argument('--model', choices=('parakeet', 'parakeet-nemo'), default='parakeet',
                        help='Select the model expected by the native or NeMo server.')
    parser.add_argument('--output', type=Path, default=Path('pi-parakeet-results-private.json'))
    parser.add_argument('--clip', help='Replay just one case by name')
    asyncio.run(main(parser.parse_args()))
