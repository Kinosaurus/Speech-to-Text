"""Prepare local ASR-assisted word drafts; never certify them as ground truth."""
import argparse
import json
import os
from pathlib import Path
import re
import wave

from benchmarks.asr_only import atomic_json, enforce_no_tracker, sha256
from benchmarks.metrics import words


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--cache', type=Path, required=True)
    args = parser.parse_args()
    enforce_no_tracker()
    args.output.mkdir(parents=True, exist_ok=True)
    if any(args.output.glob('*.annotation.json')):
        raise ValueError('Use a fresh annotation directory; existing review work is never overwritten.')
    paths = sorted({p.parent for p in (args.cache / 'cuda-runtime').rglob('*.dll')})
    os.environ['PATH'] = os.pathsep.join(map(str, paths)) + os.pathsep + os.environ.get('PATH', '')
    handles = [os.add_dll_directory(str(p)) for p in paths]
    from huggingface_hub import snapshot_download
    from faster_whisper import WhisperModel
    import numpy as np
    # A separate model assists reference preparation. It is not one of the six
    # evaluated configurations, and its output is still explicitly unverified.
    model_path = Path(snapshot_download('Systran/faster-whisper-small.en',
                                       cache_dir=str(args.cache / 'reference-models'),
                                       allow_patterns=['config.json', 'model.bin', 'tokenizer.json', 'vocabulary.txt']))
    model = WhisperModel(str(model_path), device='cuda', compute_type='float16', local_files_only=True)
    dataset = json.loads((args.run / 'dataset.json').read_text(encoding='utf-8'))
    metadata = {'run': str(args.run.resolve()), 'cases': [], 'audio_uploaded': False,
                'source': 'local faster-whisper small.en, offline word-timestamp draft; no passage prompt or hints',
                'model_snapshot': str(model_path), 'model_sha256': sha256(model_path / 'model.bin'),
                'human_verified': False, 'warning': 'ASR output and alignment proposals are not independent ground truth.'}
    historical = Path(__file__).resolve().parents[2] / 'benchmarks'
    for case in dataset['cases']:
        print('DRAFT ' + case['id'], flush=True)
        if sha256(case['audio']) != case['audio_sha256']:
            raise ValueError('Frozen audio changed: ' + case['id'])
        segments, info = model.transcribe(case['audio'], language='en', task='transcribe',
                                         initial_prompt=None, hotwords=None, condition_on_previous_text=False,
                                         vad_filter=False, word_timestamps=True, beam_size=5)
        rows, raw_segments = [], []
        for segment in segments:
            raw_segments.append({'start': segment.start, 'end': segment.end, 'text': segment.text,
                                 'avg_logprob': segment.avg_logprob, 'no_speech_prob': segment.no_speech_prob})
            for word in segment.words or []:
                rows.append({'id': f'w{len(rows)+1:04}', 'text': word.word.strip(),
                             'start': word.start, 'end': word.end, 'probability': word.probability,
                             'text_reviewed': False, 'timing_reviewed': False, 'notes': ''})
        alternate_path = historical / ({'tea': 'tea-streaming/timing-reference-streaming-estimated.json',
                                         'fat_cat': 'fat-cat-streaming/timing-reference-streaming-estimated.json',
                                         'little_mermaid': 'little-mermaid/timing-reference-parakeet.json'}[case['id']])
        alternate = None
        if alternate_path.exists():
            candidate = json.loads(alternate_path.read_text(encoding='utf-8'))
            if candidate.get('audio_sha256') == case['audio_sha256']:
                alternate = {'text': candidate['text'], 'words': candidate.get('words', []),
                             'source': candidate['source'], 'human_verified': False}
        alternate_words = set(words(alternate['text'])) if alternate else set()
        for row in rows:
            row['flags'] = []
            if row['probability'] < .65:
                row['flags'].append('low ASR probability')
            if row['end'] <= row['start']:
                row['flags'].append('zero/reversed duration')
            if alternate and any(token not in alternate_words for token in words(row['text'])):
                row['flags'].append('word absent from alternate ASR draft')
        annotation = {'schema': 'asr-reference-review-v1', 'case': case['id'], 'audio': case['audio'],
                      'audio_sha256': case['audio_sha256'], 'duration_seconds': case['duration_seconds'],
                      'draft_source': metadata['source'], 'draft_model_sha256': metadata['model_sha256'],
                      'words': rows, 'alternate': alternate, 'review': {},
                      'scope': 'all intelligible spoken words, including repetitions, errors, fillers and other speakers',
                      'status': 'automatic_draft_not_verified'}
        atomic_json(args.output / f'{case["id"]}.annotation.json', annotation)
        atomic_json(args.output / f'{case["id"]}.original-draft.json',
                    {'annotation': annotation, 'segments': raw_segments})
        with wave.open(case['audio']) as wav:
            samples = np.frombuffer(wav.readframes(wav.getnframes()), dtype='<i2').astype(np.int32)
        step = 80  # 5 ms envelope; not an assertion of annotation precision.
        padded = np.pad(samples, (0, (-len(samples)) % step))
        peaks = np.max(np.abs(padded.reshape(-1, step)), axis=1) / 32768
        atomic_json(args.output / f'{case["id"]}.waveform.json',
                    {'step_seconds': .005, 'peaks': np.round(peaks, 4).tolist()})
        (args.output / f'{case["id"]}.draft.txt').write_text(' '.join(row['text'] for row in rows) + '\n', encoding='utf-8')
        metadata['cases'].append(case['id'])
        atomic_json(args.output / 'project.json', metadata)
        print(f'SAVED {case["id"]}: {len(rows)} proposed words, all unverified', flush=True)


if __name__ == '__main__':
    main()
