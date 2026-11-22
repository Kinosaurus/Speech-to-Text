import hashlib
import json
from pathlib import Path
import sys

OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(OUT / 'support'))
from benchmarks.metrics import words


def sha(path):
    with Path(path).open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest()


def main():
    data = json.loads((OUT / 'dataset.json').read_text(encoding='utf-8'))
    assert data['tracker'] is False
    assert len(data['cases']) == 31 and len({c['passage_key'] for c in data['cases']}) == 13
    checks = []
    for case in data['cases']:
        assert sha(case['audio']) == case['audio_sha256'], case['id']
        assert sha(case['manifest']) == case['manifest_sha256'], case['id']
        expected = case['samples'] + round(data['tail_seconds'] * 16000)
        for profile in data['profiles']:
            path = OUT / f'{profile}--{case["id"]}.json'
            if not path.exists():
                continue
            result = json.loads(path.read_text(encoding='utf-8'))
            assert result['status'] == 'ok', (path.name, result.get('error'))
            assert result['audio_sha256'] == case['audio_sha256']
            assert words(result['final_text'])
            if profile == 'keen-book':
                assert result['delivered_end']
            else:
                assert result['samples_delivered'] == expected
                assert result['no_tracker_modules_imported'] is True
                if profile == 'whisper-tiny-cpu':
                    assert result['runtime']['decoded_through_seconds'] >= case['duration_seconds']
                    assert not result['runtime']['buffer_trim_events']
            events_path = path.with_suffix('.events.jsonl')
            events = result.get('events') or [json.loads(line) for line in events_path.read_text(encoding='utf-8').splitlines()]
            updates = [event for event in events if event['kind'] == 'transcript']
            assert updates and updates[-1]['final']
            assert updates[-1]['text'] == result['final_text']
            assert all(a['wall_seconds'] <= b['wall_seconds'] for a, b in zip(updates, updates[1:]))
            assert not any(event['kind'] in ('tracker', 'trigger', 'book_context_sent') for event in events)
            checks.append(dict(case=case['id'], profile=profile, final=True, full_delivery=True, tracker=False))
    source_files = sorted([*OUT.rglob('*.py'), *OUT.rglob('*.mjs')])
    summary = dict(recordings=31, distinct_passage_sections=13, completed_trials=len(checks),
                   required_trials=31 * len(data['profiles']), all_complete=len(checks) == 186,
                   dataset_sha256=sha(OUT / 'dataset.json'),
                   source_sha256={str(path.relative_to(OUT)): sha(path) for path in source_files},
                   trials=checks)
    if summary['all_complete']:
        root = OUT.parents[1]
        cache = root / 'model-cache/asr-benchmark'
        tiny = Path.home() / '.cache/huggingface/hub/models--Systran--faster-whisper-tiny.en/snapshots'
        tiny_file = next(path / 'model.bin' for path in tiny.iterdir() if (path / 'model.bin').is_file())
        model_files = {
            'Nemotron': root / 'tmp/nemotron-asr-comparison/model-cache/nemotron-nemo/nemotron-speech-streaming-en-0.6b.nemo',
            'Parakeet': root / 'model-cache/parakeet-nemo/parakeet-unified-en-0.6b.nemo',
            'Whisper Tiny': tiny_file,
            'KeenASR': root / 'output/keen-corpus-21750e9/public/vendor/keenasr/models/keenAK3m-nnet3chain-en-us.tgz',
        }
        moonshine = Path((cache / 'moonshine-model-path.txt').read_text().strip())
        model_files.update({f'Moonshine/{path.name}': path for path in moonshine.iterdir() if path.is_file()})
        summary['model_sha256'] = {name: sha(path) for name, path in model_files.items()}
    (OUT / 'audit.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
    print(f'{len(checks)}/186 trials verified; audio, manifests, final transcripts, delivery and tracker absence checked.')


if __name__ == '__main__':
    main()
