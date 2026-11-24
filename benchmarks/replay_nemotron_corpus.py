"""Replay the 50 saved comparison recordings through Nemotron and today's tracker.

Packets arrive in order without real-time waits. Log audio-clock arrivals and a
simulated real-time clock using measured processing times. Neither is a fresh
measurement of live transport latency. Keep raw transcripts in ignored output.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
import time
import wave

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from benchmarks.nemotron_streaming import load_model, NemotronSession
from books_to_life.matching.timely_matcher import TimelyEvidenceMatcher

CORPUS = ROOT / 'output/parakeet-corpus'
MODEL = ROOT / 'model-cache/nemotron-nemo/nemotron-speech-streaming-en-0.6b.nemo'
PACKET = 4096
RATE = 16000
CHECKPOINT_BOOST = 1.0


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def sha(path):
    with path.open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest() if hasattr(hashlib, 'file_digest') else hashlib.sha256(source.read()).hexdigest()


def checkpoint_phrases(manifest):
    return list(dict.fromkeys(phrase for cue in manifest['checkpoints']
        if (phrase := ' '.join((cue.get('effect_cue') or cue['checkpoint_text']).split()))))


def make_protocol(checkpoint_hints=False, *, lookahead=None):
    cases = read(CORPUS / 'results/keen-corpus/summary.json')['results']
    refs = {row['name']:row for row in read(CORPUS / 'transcript-comparison.json')['recordings']}
    rows = []
    for case in cases:
        path = Path(case['archive_path'])
        audio = ROOT/path
        manifest = audio.with_name('checkpoints.json')
        assert sha(audio) == sha(CORPUS/'inputs'/path), path
        original_manifest = (CORPUS/'inputs'/path).with_name('checkpoints.json')
        assert [p['id'] for p in read(manifest)['checkpoints']] == case['expected'], path
        reference = refs[case['name']].get('reference_file')
        with wave.open(str(audio)) as wav:
            assert (wav.getframerate(), wav.getnchannels(), wav.getsampwidth()) == (RATE, 1, 2)
            assert wav.getnframes() == round(case['duration']*RATE)
        rows.append(dict(name=case['name'], audio=path.as_posix(), audio_sha256=sha(audio),
                         manifest_sha256=sha(manifest), prior_manifest_sha256=sha(original_manifest),
                         reference=reference, reference_sha256=sha(ROOT/reference) if reference else None,
                         group=refs[case['name']]['group'], expected=case['expected'], duration=case['duration']))
        if checkpoint_hints:
            rows[-1]['checkpoint_phrases'] = checkpoint_phrases(read(manifest))
            assert rows[-1]['checkpoint_phrases'], path
    files = [Path(__file__), ROOT/'benchmarks/nemotron_streaming.py', *sorted((ROOT/'books_to_life/matching').glob('*.py'))]
    protocol = dict(recordings=rows, source_sha256={p.relative_to(ROOT).as_posix():sha(p) for p in files},
                model_sha256=sha(MODEL), model='nvidia/nemotron-speech-streaming-en-0.6b',
                revision='ebe59e5a817142986528bbbee5dba8db7b38ed50', chunk_ms=160, attention_context=[70,1],
                packet_samples=PACKET, rate_hz=RATE, hints=checkpoint_hints, timed_realtime=False)
    if checkpoint_hints:
        protocol['hint_policy'] = dict(source='authored effect_cue or checkpoint_text in existing manifest',
            schedule='fixed once per recording, before the first packet', boost=CHECKPOINT_BOOST,
            context_score=1.0, depth_scaling=2.0)
        if lookahead is not None:
            protocol['hint_policy'].update(lookahead=lookahead,
                schedule='window starts at tracker current_index; refresh before next packet or flush after progress')
    return protocol


def replay(model, row, *, lookahead=None):
    import torch

    audio = ROOT/row['audio']
    manifest = audio.with_name('checkpoints.json')
    assert sha(audio)==row['audio_sha256'] and sha(manifest)==row['manifest_sha256']
    with wave.open(str(audio)) as wav:
        audio_samples = np.frombuffer(wav.readframes(wav.getnframes()), dtype='<i2').astype(np.float32)/32768
    matcher = TimelyEvidenceMatcher.from_file(manifest, stability=2)
    def window(index):
        return matcher.checkpoints[index:index + lookahead + 1]

    initial = (row.get('checkpoint_phrases', ()) if lookahead is None
               else checkpoint_phrases({'checkpoints':window(0)}))
    session = NemotronSession(model, phrases=initial, boost=CHECKPOINT_BOOST)
    events, triggers = [], []
    hint_updates = []
    hint_index = 0
    supplied_samples = 0
    clock, compute = 0., 0.
    start = time.perf_counter()

    if lookahead is not None:
        hint_updates.append(dict(audio_end=0., index=0, checkpoint_ids=[str(cue['id']) for cue in window(0)]))

    def refresh_hints():
        nonlocal hint_index
        if lookahead is None or hint_index==matcher.current_index:
            return
        assert hint_index < matcher.current_index
        hint_index = matcher.current_index
        selected = window(hint_index)
        session.set_hints(checkpoint_phrases({'checkpoints':selected}))
        hint_updates.append(dict(audio_end=supplied_samples/RATE, index=hint_index,
                                 checkpoint_ids=[str(cue['id']) for cue in selected]))

    def consume(text, audio_end, final=False):
        nonlocal clock
        before = time.perf_counter()
        update = matcher.process(text, [dict(start=0., end=audio_end, text=text, completed=final)])
        clock += time.perf_counter() - before
        events.append((audio_end, clock, text, final))
        if update.triggered:
            triggers.append(dict(id=update.checkpoint_id, audio_end=audio_end, simulated_decision=clock))

    try:
        with torch.inference_mode(), torch.autocast('cuda', dtype=torch.bfloat16):
            for offset in range(0,len(audio_samples),PACKET):
                part = audio_samples[offset:offset+PACKET]
                audio_end = (offset+len(part))/RATE
                start_packet = time.perf_counter()
                refresh_hints()
                updates = session.feed(part)
                supplied_samples = offset+len(part)
                torch.cuda.synchronize()
                elapsed = time.perf_counter()-start_packet
                compute += elapsed
                clock = max(clock, audio_end) + elapsed
                for text in updates:
                    consume(text, audio_end)
            started = time.perf_counter()
            refresh_hints()
            final = session.finish()
            torch.cuda.synchronize()
            elapsed = time.perf_counter()-started
        compute += elapsed
        clock += elapsed
        consume(final, len(audio_samples)/RATE, True)
    finally:
        session.close()
    counts = Counter(t['id'] for t in triggers)
    assert not (set(counts) - set(row['expected']))
    result = dict(name=row['name'], samples_delivered=supplied_samples, triggers=triggers,
                tracker_counts=dict(counts), final=final, events=events, compute_seconds=compute,
                run_seconds=time.perf_counter()-start)
    if lookahead is not None:
        result['hint_updates'] = hint_updates
    return result


def freeze(output, protocol):
    output.mkdir(exist_ok=True, parents=True)
    ledger = output/'protocol.json'
    if ledger.exists():
        assert read(ledger)==protocol, 'Inputs or sources changed; use a new output folder'
    else:
        write(ledger,protocol)
    return sorted(protocol['recordings'], key=lambda row:row['duration'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--checkpoint-hints', action='store_true',
                        help='Boost every authored cue in the recording’s manifest, with a fixed list per recording.')
    parser.add_argument('--rolling-lookahead', type=int, choices=(0,1), nargs='+',
                        help='Test next checkpoint only (0) and/or next plus one (1).')
    args = parser.parse_args()
    output = args.output.resolve()
    assert output.is_relative_to(ROOT/'output')
    if args.rolling_lookahead and args.checkpoint_hints:
        parser.error('Choose fixed checkpoint hints or rolling lookahead.')
    modes = list(dict.fromkeys(args.rolling_lookahead)) if args.rolling_lookahead else [None]
    enable_hints = args.checkpoint_hints or modes!=[None]
    configs = []
    for mode in modes:
        destination = output if mode is None else output/f'lookahead-{mode}'
        rows = freeze(destination,make_protocol(enable_hints,lookahead=mode))
        configs.append((mode,destination,rows))
    pending = [(mode,dest,row) for group in zip(*(rows for _,_,rows in configs))
               for (mode,dest,_),row in zip(configs,group) if not (dest/(row['name']+'.json')).is_file()]
    if not pending:
        return
    total = sum(len(rows) for _,_,rows in configs)
    print(f'LOAD; {len(pending)} of {total} remaining', flush=True)
    model = load_model(MODEL, chunk_ms=160, enable_hints=enable_hints)
    for index,(mode,dest,row) in enumerate(pending,total-len(pending)+1):
        print(f'START {index}/{total} lookahead={mode} {row["name"]} {row["duration"]:.1f}s', flush=True)
        result = replay(model,row,lookahead=mode)
        assert result['samples_delivered']==round(row['duration']*RATE)
        target = dest/(row['name']+'.json')
        staged = target.with_suffix('.tmp')
        write(staged,result)
        staged.replace(target)
        print(f'DONE {index}/{total} {len(result["tracker_counts"])}/{len(row["expected"])} cues in {result["run_seconds"]:.1f}s', flush=True)


if __name__ == '__main__':
    main()
