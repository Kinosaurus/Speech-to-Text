import json
import os
from pathlib import Path
import sys

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
sys.path.insert(0, str(OUT / 'support'))
from benchmarks.asr_only import enforce_no_tracker, atomic_json
from benchmarks.metrics import edit_alignment, words
enforce_no_tracker()


def main():
    cache = ROOT / 'model-cache/asr-benchmark'
    paths = sorted({p.parent for p in (cache / 'cuda-runtime').rglob('*.dll')})
    os.environ['PATH'] = os.pathsep.join(map(str, paths)) + os.pathsep + os.environ.get('PATH', '')
    handles = [os.add_dll_directory(str(path)) for path in paths]
    from faster_whisper import WhisperModel
    snapshots = cache / 'reference-models/models--Systran--faster-whisper-small.en/snapshots'
    model_path = next(path for path in snapshots.iterdir() if (path / 'model.bin').is_file())
    model = WhisperModel(str(model_path), device='cuda', compute_type='float16', cpu_threads=2, local_files_only=True)
    data = json.loads((OUT / 'dataset.json').read_text(encoding='utf-8'))
    for index, case in enumerate(data['cases'], 1):
        target = OUT / f'timing--{case["id"]}.json'
        if target.exists():
            continue
        segments, _ = model.transcribe(case['audio'], language='en', beam_size=5, word_timestamps=True,
                                      initial_prompt=None, hotwords=None, condition_on_previous_text=False,
                                      vad_filter=False)
        timed = [dict(word=word.word, start=word.start, end=word.end)
                 for segment in segments for word in segment.words or []]
        tokens = [dict(token=token, start=word['start'], end=word['end'])
                  for word in timed for token in words(word['word'])]
        reference = words(case['reference'])
        _, matches = edit_alignment(case['reference'], ' '.join(word['token'] for word in tokens))
        cues = []
        for cue in case['cues']:
            phrase = words(cue['phrase'])
            occurrences = [start for start in range(len(reference) - len(phrase) + 1)
                           if reference[start:start + len(phrase)] == phrase]
            row = dict(**cue, eligible=len(occurrences) == 1, endpoint=None)
            if len(occurrences) == 1:
                end = occurrences[0] + len(phrase) - 1
                if end in matches:
                    endpoint = tokens[matches[end]]
                    row['endpoint'] = endpoint['end']
            cues.append(row)
        atomic_json(target, dict(case=case['id'], audio_sha256=case['audio_sha256'], words=timed, cues=cues,
                                 source='Separate unhinted Whisper small.en, aligned to saved reference',
                                 human_verified=False))
        print('TIMING', index, '/', len(data['cases']), case['id'],
              sum(c['endpoint'] is not None for c in cues), flush=True)


if __name__ == '__main__':
    main()
