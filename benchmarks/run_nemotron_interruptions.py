"""Controlled interruption checks through the real Nemotron WebSocket server.

Prepare/synthesize/assemble before run. Audio is sent without real-time sleeps;
an acknowledged context message fences each 80 ms packet. This tests recognition
and tracker decisions on the audio clock, not wall-clock effect latency. Physical
input/output is never opened. Raw inputs and callbacks stay in ignored output/.
"""
import argparse
from collections import Counter
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import sys
import time
import wave
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from books_to_life.context.book_context import BookContext
from books_to_life.matching.checkpoint_matcher import MATCHING_ENGINE
from books_to_life.matching.timely_matcher import TimelyEvidenceMatcher

RATE = 16000
PACKET = 1280
SAMPLE = ROOT / 'recordings/library/stories/sample/readers/demo/checkpoints.json'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pcm(path):
    with wave.open(str(path)) as wav:
        assert (wav.getframerate(), wav.getnchannels(), wav.getsampwidth()) == (RATE, 1, 2)
        return wav.readframes(wav.getnframes())


def wav_write(path, data):
    with wave.open(str(path), 'wb') as wav:
        wav.setparams((1, 2, RATE, 0, 'NONE', 'not compressed'))
        wav.writeframes(data)


def prepare(out):
    out.mkdir(parents=True, exist_ok=False)
    fragments = out / 'fragments'
    fragments.mkdir()
    manifest = read(SAMPLE)
    write(out / 'manifest.json', manifest)
    page1, page2, page3, _ = [p['text'] for p in manifest['pages']]
    head1, tail1 = 'Mila found a tiny silver', 'seed beside the old gate'
    head2, tail2 = 'Soft green grass curled across', 'the floor like a ribbon'
    after1 = 'She carried it carefully into the quiet garden and pressed it into the warm soil.'
    after2 = 'Mila followed it as it wound between the stones and climbed towards the hill.'
    prompt = 'Take your time. What does that word say?'
    aside = 'I need a drink of water. The glass is on the table next to your bag.'
    long_aside = ('We can take a little break and look outside at the trees. '
                  'Your lunch is in the kitchen and your shoes are beside the door. '
                  'When we finish we can go to the playground and meet our friends.')
    cases = []

    def add(name, turns, expected, target=None, resume=None):
        cases.append(dict(id=name, kind='synthetic', turns=turns, expected=expected,
                          target=target, resume_turn=resume))

    first_ids = ['seed_found', 'grass_grows', 'clouds_arrive']
    for name, pause, interruption in [
        ('clean', .25, None), ('pause_2s', 2, None), ('pause_15s', 15, None),
        ('pause_90s', 90, None), ('parent_question', 1, prompt),
        ('off_book_aside', 1, aside), ('long_conversation', 1, long_aside),
    ]:
        turns = [head1, pause]
        if interruption:
            turns += [interruption, 1.0]
        resume = len(turns)
        turns += [tail1, after1, page2, page3]
        add('opening_' + name, turns, first_ids, 'seed_found', resume)

    for name, pause, interruption in [
        ('clean', .25, None), ('pause_15s', 15, None),
        ('parent_question', 1, prompt), ('off_book_aside', 1, aside),
        ('long_conversation', 1, long_aside),
    ]:
        turns = [page1, head2, pause]
        if interruption:
            turns += [interruption, 1.0]
        resume = len(turns)
        turns += [tail2, after2, page3]
        add('acquired_' + name, turns, first_ids, 'grass_grows', resume)

    add('restart_and_reread', [page1, head2, prompt, head2, tail2, after2, page2, page3],
        first_ids, 'grass_grows', 4)
    negative_ids = ['seed_found', 'clouds_arrive']
    for name, middle in [
        ('endpoint_only', [head2, aside, 'ribbon']),
        ('missing_endpoint', ['Soft green grass curled across the floor like a', aside]),
        ('wrong_endpoint', ['Soft green grass curled across the floor like a river', aside]),
        ('negated_prompt', ['Do not say soft green grass curled across the floor like a ribbon.', aside]),
        ('quoted_prompt', ['Can you say soft green grass curled across the floor like a ribbon?', aside]),
        ('skipped_checkpoint', [aside]),
    ]:
        add(name, [page1, *middle, page3], negative_ids)

    jobs, texts = [], {}
    for case in cases:
        for turn in case['turns']:
            if not isinstance(turn, str) or turn in texts:
                continue
            ident = f'part-{len(texts):03d}'
            texts[turn] = ident
            ssml = fragments / (ident + '.ssml')
            ssml.write_text('<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" '
                            'xml:lang="en-US">' + escape(turn) + '</speak>', encoding='utf-8')
            jobs.append(dict(id=ident, ssml=str(ssml), audio=str(fragments / (ident + '.wav'))))
    write(out / 'jobs.json', jobs)
    write(out / 'plan.json', dict(cases=cases, texts=texts, voice='Microsoft Zira Desktop',
                                threshold=82, stability=2, coverage=.8))
    print(f'Prepared {len(cases)} synthetic cases and {len(jobs)} speech fragments', flush=True)


def assemble(out):
    plan = read(out / 'plan.json')
    rows = []
    for case in plan['cases']:
        data, turns = bytearray(), []
        for i, turn in enumerate(case['turns']):
            start = len(data) / 2 / RATE
            fragment = (pcm(out / 'fragments' / (plan['texts'][turn] + '.wav'))
                        if isinstance(turn, str) else bytes(round(turn * RATE) * 2))
            data.extend(fragment)
            turns.append(dict(index=i, start=start, end=len(data) / 2 / RATE, content=turn))
        data.extend(bytes(RATE * 2))  # Identical one-second EOF settling silence.
        path = out / (case['id'] + '.wav')
        assert not path.exists(), path
        wav_write(path, data)
        rows.append({**case, 'turns': turns, 'audio': path.name, 'manifest': 'manifest.json',
                     'audio_sha256': sha(path), 'samples': len(data) // 2})
    for story in ('horse', 'tea', 'little_mermaid'):
        directory = ROOT / f'recordings/library/stories/{story}/readers/{story}'
        data = pcm(directory / 'audio.wav')
        manifest = read(directory / 'checkpoints.json')
        write(out / (story + '-manifest.json'), manifest)
        for interrupted in (False, True):
            # Preserve every original speech sample; insert 15 seconds of silence
            # at the fixed midpoint. This is not a word-aligned interruption.
            split = (len(data) // 4) * 2
            audio = data[:split] + bytes(15 * RATE * 2) + data[split:] if interrupted else data
            audio += bytes(RATE * 2)
            ident = story + ('-midpoint-pause' if interrupted else '-original')
            path = out / (ident + '.wav')
            assert not path.exists(), path
            wav_write(path, audio)
            rows.append(dict(id=ident, kind='original_pause' if interrupted else 'original',
                expected=[str(c['id']) for c in manifest['checkpoints']],
                audio=path.name, manifest=story + '-manifest.json',
                audio_sha256=sha(path), source_audio_sha256=sha(directory / 'audio.wav'),
                samples=len(audio)//2, insertion_seconds=split/2/RATE if interrupted else None))
    sources = [Path(__file__), ROOT / 'books_to_life/runtime/nemotron.py',
               ROOT / 'books_to_life/cli/run_nemo_server.py',
               ROOT / 'books_to_life/context/book_context.py',
               *sorted((ROOT / 'books_to_life/matching').glob('*.py'))]
    write(out / 'protocol.json', dict(cases=rows, packet_samples=PACKET,
        backend='nemotron', chunk_ms=160, attention_context=[70, 1],
        matcher='TimelyEvidenceMatcher (panel split mode)', hints='Low: next checkpoint only',
        threshold=82, stability=2, min_coverage=.8, real_time=False,
        input_output='saved WAVs; no microphone, speaker, or projector',
        synthetic_voice=plan['voice'],
        source_sha256={p.relative_to(ROOT).as_posix(): sha(p) for p in sources},
        model_sha256=sha(ROOT / 'model-cache/nemotron-nemo/nemotron-speech-streaming-en-0.6b.nemo'),
        manifest_sha256={p.name: sha(p) for p in out.glob('*manifest.json')}))
    print(f'Assembled {len(rows)} cases', flush=True)


def run_case(out, row, url, hints_enabled):
    import numpy as np
    from websockets.sync.client import connect
    manifest = read(out / row['manifest'])
    matcher = TimelyEvidenceMatcher(manifest, threshold=82, stability=2)
    matcher.explain_matches = True
    context = BookContext(matcher, lookahead=0, phrase_only=True)
    hotwords = context.hints.hotwords if hints_enabled else None
    audio = out / row['audio']
    assert sha(audio) == row['audio_sha256']
    data = np.frombuffer(pcm(audio), dtype='<i2').astype(np.float32) / 32768
    events, triggers, changes = [], [], []
    started = time.perf_counter()
    revision, acks = 0, 0
    with connect(url, open_timeout=20, max_size=8*1024*1024) as socket:
        socket.send(json.dumps(dict(uid=row['id'], model='nemotron', language='en',
                                    task='transcribe', hotwords=hotwords)))
        ready = None

        def receive():
            nonlocal hotwords
            message = json.loads(socket.recv(timeout=120))
            if message.get('status') in ('ERROR', 'WARNING'):
                raise RuntimeError(message)
            for segment in message.get('segments', []):
                update = matcher.process(segment['text'], [segment])
                event = dict(audio_end=segment['end'], text=segment['text'], final=segment['completed'],
                             update=asdict(update))
                events.append(event)
                if update.triggered:
                    triggers.append(dict(id=update.checkpoint_id, audio_end=segment['end']))
                refreshed = context.refresh()
                if hints_enabled and refreshed and refreshed.hotwords != hotwords:
                    hotwords = refreshed.hotwords
                    changes.append(dict(audio_end=segment['end'], hotwords=hotwords))
            return message

        while ready is None:
            message = receive()
            if message.get('message') == 'SERVER_READY':
                ready = message
        assert ready['backend'] == 'nemotron' and ready['chunk_ms'] == 160 and ready['att_context'] == [70, 1], ready
        for offset in range(0, len(data), PACKET):
            socket.send(data[offset:offset+PACKET].astype('<f4').tobytes())
            revision += 1
            socket.send(json.dumps(dict(type='book_context', revision=revision, hotwords=hotwords)))
            while True:
                message = receive()
                if message.get('type') == 'book_context_ack' and message['revision'] == revision:
                    acks += 1
                    break
        socket.send(b'END_OF_AUDIO')
        while receive().get('message') != 'STREAM_DONE':
            pass
    assert events and events[-1]['final'] and events[-1]['audio_end'] == len(data)/RATE
    assert acks == (len(data)+PACKET-1)//PACKET
    counts = Counter(t['id'] for t in triggers)
    expected = set(row['expected'])
    resume = row.get('resume_turn')
    earliest = row['turns'][resume]['start'] if resume is not None else None
    premature = [t for t in triggers if t['id'] == row.get('target') and t['audio_end'] < earliest] if earliest is not None else []
    summary = dict(id=row['id'], kind=row['kind'], expected=row['expected'], hits=list(counts),
        missed=sorted(expected-set(counts)), unexpected=sorted(set(counts)-expected),
        duplicates={k:v for k,v in counts.items() if v>1}, premature=premature,
        target_resume_start=earliest, suppressed=sorted(matcher.suppressed_checkpoint_ids),
        skipped=sorted(matcher.skipped_checkpoint_ids), final_position=matcher.tracked_word_position,
        duration_seconds=len(data)/RATE, samples_delivered=len(data), packet_acks=acks,
        stream_done=True, hints_enabled=hints_enabled, wall_seconds=time.perf_counter()-started)
    summary['passed'] = not any(summary[k] for k in ('missed','unexpected','duplicates','premature'))
    return dict(summary=summary, ready=ready, hint_changes=changes, triggers=triggers, events=events)


def run(out, url, hints_enabled):
    protocol = read(out / 'protocol.json')
    assert MATCHING_ENGINE == 'rapidfuzz', MATCHING_ENGINE
    for path, digest in protocol['source_sha256'].items():
        assert sha(ROOT / path) == digest, path
    for path, digest in protocol['manifest_sha256'].items():
        assert sha(out / path) == digest, path
    results = out / ('hints-low' if hints_enabled else 'hints-off')
    results.mkdir(exist_ok=False)
    summaries = []
    for row in protocol['cases']:
        print('START', row['id'], flush=True)
        try:
            result = run_case(out, row, url, hints_enabled)
        except Exception as error:
            write(results / (row['id'] + '-FAILED.json'), dict(error=repr(error)))
            raise
        write(results / (row['id'] + '.json'), result)
        summaries.append(result['summary'])
        write(results / 'summary.json', summaries)
        print('RESULT', json.dumps(result['summary']), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=('prepare','assemble','run'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--url', default='ws://127.0.0.1:9097')
    parser.add_argument('--hints-off', action='store_true')
    args = parser.parse_args()
    out = args.output.resolve()
    assert out.is_relative_to(ROOT / 'output')
    if args.stage == 'prepare':
        prepare(out)
    elif args.stage == 'assemble':
        assemble(out)
    else:
        run(out, args.url, not args.hints_off)


if __name__ == '__main__':
    main()
