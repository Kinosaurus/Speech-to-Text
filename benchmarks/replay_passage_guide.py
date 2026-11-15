"""Experimental passage-conditioned NeMo replay, with the original matcher."""
import argparse
from difflib import SequenceMatcher
import json
from pathlib import Path
import time
import wave

import numpy as np

from books_to_life.matching.checkpoint_matcher import normalize_text
from books_to_life.matching.timely_matcher import TimelyEvidenceMatcher
from books_to_life.runtime.nemo_parakeet import NemoParakeetSession, load_model
from books_to_life.runtime.streaming_utterances import SilenceBoundedSession

class PassageGuide:
    """Move the decoder's phrase tree using observed word matches, independent of cues."""
    def __init__(self, book, width, phrase_lengths, cue_phrases):
        self.book = book
        self.words = normalize_text(" ".join(page["text"] for page in book["pages"])).split()
        self.width = width
        self.phrase_lengths = phrase_lengths
        self.position = 0
        self.refresh_position = None
        self.cue_phrases = cue_phrases

    def update(self, segments):
        heard = normalize_text(' '.join(s['text'] for s in segments)).split()[-24:]
        start = max(0, self.position - 10)
        nearby = self.words[start:min(len(self.words), self.position + 38)]
        matches = SequenceMatcher(None, heard, nearby, autojunk=False).get_matching_blocks()
        for block in matches:
            if block.size >= 3 and len(heard) - block.a - block.size <= 6:
                self.position = max(self.position, start + block.b + block.size)
        if self.refresh_position is not None and self.position < self.refresh_position + 4:
            return None
        self.refresh_position = self.position
        start = max(0, self.position - 3)
        stop = min(len(self.words), self.position + self.width)
        cues = []
        if self.cue_phrases:
            for cue in self.book['checkpoints']:
                first, end = cue['word_start'], cue['word_end']
                if self.position - 4 <= end and self.position + self.width >= first:
                    cues.extend(' '.join(self.words[a:b]) for a, b in (
                        (first, end), (first, first+4), (end-3, end), (end-6, end)))
        return ', '.join(list(dict.fromkeys(cues + [
            ' '.join(self.words[i:i+length])
            for length in self.phrase_lengths
            for i in range(start, stop-length+1)
        ]))[:32])


def replay(model, audio, manifest, boost=5.0, width=13, lengths=(1, 2), cue_phrases=False, paced=False):
    matcher = TimelyEvidenceMatcher.from_file(manifest, stability=2)
    guide = PassageGuide(json.loads(manifest.read_text(encoding='utf-8')), width, lengths, cue_phrases)
    session = SilenceBoundedSession(lambda: NemoParakeetSession(model, boost=boost), 8960)
    cues, suppressions, refreshes = [], [], []
    callback_count = 0
    segment_text = []
    last_hints = guide.update([])
    session.set_hints(last_hints)
    origin = time.monotonic()

    def receive(segments, final=False):
        nonlocal callback_count, segment_text
        callback_count += 1
        segment_text = segments
        position = segments[-1]['end']
        text = ' '.join(s['text'] for s in segments)
        update = matcher.process(text, segments)
        if update.triggered:
            cues.append(dict(id=update.checkpoint_id, audio_seconds=round(position, 3)))
        if update.effect_suppressed:
            suppressions.append(dict(id=update.checkpoint_id, audio_seconds=round(position, 3),
                                     reason=update.effect_suppression_reason))
        if not final:
            hints = guide.update(segments)
            if hints is not None:
                session.set_hints(hints)
                refreshes.append(dict(audio_seconds=round(position, 3), book_word=guide.position))

    try:
        for start in range(0, len(audio), 4096):
            packet = audio[start:start+4096]
            if paced:
                time.sleep(max(0, origin+(start+len(packet))/16000-time.monotonic()))
            for segments in session.feed(packet):
                receive(segments)
        receive(session.finish(), final=True)
    finally:
        session.close()
    return dict(boost=boost, width=width, lengths=lengths, cue_phrases=cue_phrases, paced=paced,
                elapsed_seconds=round(time.monotonic()-origin, 3), cue_count=len(cues),
                expected=[c['id'] for c in matcher.checkpoints], cues=cues, suppressed=suppressions,
                updates=callback_count, guide_updates=refreshes,
                transcript=' '.join(s['text'] for s in segment_text))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model-path', type=Path, required=True)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--wav', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--paced', action='store_true', help='Feed audio at 1×.')
    args = parser.parse_args()
    model = load_model(args.model_path)
    with wave.open(str(args.wav)) as wav:
        if (wav.getnchannels(), wav.getsampwidth(), wav.getframerate()) != (1, 2, 16000):
            parser.error('Use a mono 16-bit 16 kHz WAV.')
        audio = np.frombuffer(wav.readframes(wav.getnframes()), dtype='<i2').astype(np.float32) / 32768
    result = replay(model, audio, args.manifest, paced=args.paced)
    args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(f"{result['cue_count']}/{len(result['expected'])} cues")


if __name__ == '__main__':
    main()
