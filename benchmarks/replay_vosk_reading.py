"""Compare Vosk dictation and passage grammars using the original pod matcher."""
import argparse
import json
from pathlib import Path
import re
import time
import wave

from vosk import KaldiRecognizer, Model, SetLogLevel

from books_to_life.matching.checkpoint_matcher import normalize_text
from books_to_life.matching.timely_matcher import TimelyEvidenceMatcher

def replay(model, audio, manifest, expected, grammar):
    matcher = TimelyEvidenceMatcher.from_file(manifest, stability=2)
    args = (json.dumps(grammar),) if grammar else ()
    recognizer = KaldiRecognizer(model, 16000, *args)
    recognizer.SetWords(True)
    recognizer.SetPartialWords(True)
    committed = []
    cues, suppressions = [], []
    segment_start = 0.0
    previous = None
    updates = 0
    start = time.perf_counter()

    def receive(result, completed, position):
        nonlocal previous, updates, segment_start
        text = result.get('text' if completed else 'partial', '')
        if not text:
            return
        if (text, completed) == previous:
            return
        previous = text, completed
        timed_words = result.get('result' if completed else 'partial_result', [])
        end = timed_words[-1]['end'] if timed_words else position
        segment = dict(start=segment_start, end=max(segment_start, end), text=text, completed=completed)
        segments = committed + [segment]
        if completed:
            committed.append(segment)
            segment_start = max(segment_start, end)
        updates += 1
        update = matcher.process(' '.join(s['text'] for s in segments), segments)
        if update.triggered:
            cues.append(dict(id=update.checkpoint_id, audio_seconds=round(position, 3)))
        if update.effect_suppressed:
            suppressions.append(update.checkpoint_id)

    packet_bytes = 8192
    for offset in range(0, len(audio), packet_bytes):
        packet = audio[offset:offset + packet_bytes]
        position = (offset+len(packet))/32000
        done = recognizer.AcceptWaveform(packet)
        receive(json.loads(recognizer.Result() if done else recognizer.PartialResult()), done, position)
    receive(json.loads(recognizer.FinalResult()), True, len(audio)/32000)
    fired = [cue['id'] for cue in cues]
    return dict(expected=expected,cues=cues,missing=[i for i in expected if i not in fired],
                unexpected=[i for i in fired if i not in expected],duplicates=len(fired)-len(set(fired)),
                suppressions=suppressions,updates=updates,audio_seconds=len(audio)/32000,
                compute_seconds=round(time.perf_counter()-start,3),
                transcript=' '.join(s['text'] for s in committed))


def pcm(file):
    with wave.open(file) as wav:
        assert (wav.getnchannels(), wav.getsampwidth(), wav.getframerate()) == (1, 2, 16000)
        return wav.readframes(wav.getnframes())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model-path', type=Path, required=True)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--wav', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--control', action='store_true', help='Expect no cues.')
    args = parser.parse_args()
    with args.wav.open('rb') as source:
        audio = pcm(source)
    book = json.loads(args.manifest.read_text(encoding='utf-8'))
    expected = [] if args.control else [cue['id'] for cue in book['checkpoints']]
    passage = ' '.join(page['text'] for page in book['pages'])
    grammar = [normalize_text(sentence) for sentence in re.split(r'[.!?]+', passage)
               if normalize_text(sentence)]
    grammar.append('[unk]')
    SetLogLevel(-1)
    model = Model(str(args.model_path))
    rows = []
    for mode, phrases in [('dictation', None), ('passage-grammar', grammar)]:
        row = replay(model, audio, args.manifest, expected, phrases)
        row['mode'] = mode
        rows.append(row)
        print(f"{mode}: {len(expected) - len(row['missing'])}/{len(expected)} expected cues, "
              f"{len(row['unexpected'])} unexpected")
    args.output.write_text(json.dumps(rows, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
