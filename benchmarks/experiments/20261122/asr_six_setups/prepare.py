import hashlib
import json
from pathlib import Path
import shutil
import sys
import wave

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
SOURCE = ROOT / 'output/reading-pod-first-pipeline'
sys.path.insert(0, str(SOURCE))
from benchmarks.metrics import words


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def sha(path):
    return hashlib.file_digest(path.open('rb'), 'sha256').hexdigest()


def main():
    cases = []
    mps = ROOT / 'output/mps-heldout-phonetic-2026-11-02'
    event_labels = {'SIL', 'BR', 'ON', 'FP', 'IR', 'MB', 'WH'}
    transcripts = {row['audioID']: ' '.join(token for token in row['manualTranscript'].split()
                                           if token not in event_labels)
                   for row in read(mps / 'selected.json')}
    for job in read(mps / 'downloaded-jobs.json'):
        folder = mps / 'inputs' / job['id']
        cases.append(dict(id=job['id'], audio=str(folder / 'audio.wav'),
                          manifest=str(folder / 'checkpoints.json'), reference=transcripts[job['id']],
                          reference_kind='provider_manual_transcript', reader=job['speaker']))
    library = ROOT / 'output/data/books-to-life-recordings-20261113/recordings/library/stories'
    for story, reader in [('fat_cat', 'fat_cat'), ('horse', 'horse'), ('little_mermaid', 'little_mermaid'),
                          ('tea', 'tea'), ('billy-visits-grandpa', '6027'), ('making-kites', '7028'),
                          ('tom-s-secret-study', '7015')]:
        folder = library / story / 'readers' / reader
        reference = folder / 'reference.txt'
        cases.append(dict(id=story, audio=str(folder / 'audio.wav'), manifest=str(folder / 'checkpoints.json'),
                          reference=reference.read_text(encoding='utf-8-sig'),
                          reference_kind='supplied_passage' if story in ('fat_cat', 'horse', 'little_mermaid', 'tea')
                          else 'saved_corpus_spoken_reference', reader=reader))
    for case in cases:
        audio, manifest = Path(case['audio']), Path(case['manifest'])
        config = read(manifest)
        case['manifest_sha256'] = sha(manifest)
        case['audio_sha256'] = sha(audio)
        case['keen_book_text'] = '\n'.join(page['text'] for page in config['pages'])
        case['cues'] = [dict(id=cue['id'], phrase=cue.get('effect_cue') or cue['checkpoint_text'])
                       for cue in config['checkpoints']]
        case['fixed_hints'] = list(dict.fromkeys(cue['phrase'].replace(',', ' ') for cue in case['cues']))
        assert len(case['fixed_hints']) <= 32 and all(len(p) <= 200 for p in case['fixed_hints'])
        case['passage_key'] = hashlib.sha256(' '.join(words(case['keen_book_text'])).encode()).hexdigest()
        with wave.open(str(audio)) as wav:
            assert (wav.getframerate(), wav.getnchannels(), wav.getsampwidth()) == (16000, 1, 2)
            case['samples'] = wav.getnframes()
            case['duration_seconds'] = wav.getnframes() / 16000
    assert len(cases) == 31 and len({case['passage_key'] for case in cases}) == 13
    payload = dict(protocol='asr-only-six-setups-20261122', tracker=False, packet_samples=4096,
                   tail_seconds=1.5, cases=cases,
                   selection='All 24 prior MPS heldout recordings plus seven available independent supplied/published passages.',
                   profiles=['parakeet-fixed-hints', 'keen-book', 'whisper-tiny-cpu', 'moonshine-cpu',
                             'nemotron-160-fixed-hints', 'nemotron-320-fixed-hints'],
                   hint_policy='Fixed authored cue list for NeMo engines, full independent passage for Keen, no hints for Whisper/Moonshine.',
                   latency='ASR phrase availability minus independent automatic acoustic endpoint. Replay estimates, unreviewed.',
                   clocks='GPU trials simulate 1x packet arrivals with measured synchronous processing. CPU and Keen trials use paced wall-clock replay. Cold model and graph loading is excluded.',
                   reference_normalization='Remove provider SIL/BR/ON/FP/IR/MB/WH annotation labels. Preserve spoken words and original non-Latin spellings.')
    target = OUT / 'dataset.json'
    if target.exists():
        assert read(target) == payload
    else:
        target.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    for filename in ['asr_only.py', 'asr_only_worker.py', 'metrics.py', 'capture_keen_book.py', 'keen_book_replay.mjs']:
        destination = OUT / 'support/benchmarks' / filename
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.exists():
            shutil.copyfile(SOURCE / 'benchmarks' / filename, destination)
    (OUT / 'support/benchmarks/__init__.py').touch()
    source = ROOT / 'tmp/nemotron-asr-comparison'
    shutil.copyfile(source / 'benchmarks/nemotron_streaming.py', OUT / 'support/nemotron_streaming.py')
    parakeet = (source / 'books_to_life/runtime/nemo_parakeet.py').read_text(encoding='utf-8')
    parakeet = parakeet.replace('from books_to_life.context.book_context import MAX_CONTEXT_CHARS', 'MAX_CONTEXT_CHARS = 65536')
    (OUT / 'support/nemo_parakeet.py').write_text(parakeet, encoding='utf-8')
    print(len(cases), 'recordings', len({c['passage_key'] for c in cases}), 'passages',
          round(sum(c['duration_seconds'] for c in cases) / 60, 1), 'minutes', flush=True)


if __name__ == '__main__':
    main()
