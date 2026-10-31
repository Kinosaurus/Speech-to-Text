"""Check source coverage, pairing, exact copies and rebased passage assets."""
import hashlib
import json
from pathlib import Path
import re
import sys

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from books_to_life.matching.alignment_matcher import AlignmentMatcher

BASE = ROOT/'recordings/library'


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda: source.read(4*1024*1024), b''):
            h.update(block)
    return h.hexdigest()


def main():
    inv = json.loads((BASE/'inventory.json').read_text())
    assert len(inv['source_audio']) == inv['source_audio_count']
    for source, item in inv['source_audio'].items():
        if (ROOT/source).exists():
            assert digest(ROOT/source) == item.get('original_sha256',item['sha256']), f'Source changed: {source}'
        target = BASE/item['library_path']
        assert digest(target) == item['sha256'], f'Copy changed: {target}'
        if target.name == 'audio.wav':
            assert (target.parent/'transcript.txt').exists()
            assert ((target.parent/'checkpoints.json').exists()
                    or (target.parent/'checkpoint_status.json').exists())
        else:
            assert target.with_suffix('.transcript.txt').exists(), target
            assert (target.with_suffix('.checkpoints.json').exists()
                    or target.with_suffix('.checkpoint_status.json').exists()), target
    imported = 0
    for entry in inv.get('imports', {}).values():
        report = json.loads((BASE/entry['report']).read_text(encoding='utf-8'))
        assert len(report['recordings']) == entry['recordings']
        for recording in report['recordings']:
            folder = (BASE/recording['path']).resolve()
            assert folder.is_relative_to(BASE.resolve()), folder
            assert digest(folder/'audio.wav') == recording['audio_sha256'], folder
            assert all((folder/name).is_file() for name in
                       ['passage.txt','transcript.txt','checkpoints.json','source.json']), folder
            imported += 1
    manifests = 0
    for path in BASE.rglob('*.json'):
        data = json.loads(path.read_text(encoding='utf-8'))
        if isinstance(data, dict) and 'pages' in data and 'checkpoints' in data:
            AlignmentMatcher(data)
            manifests += 1
    derived = 0
    for row in inv['stories']:
        folder = BASE/row['path']
        if row['coverage'] != 'passage excerpt':
            continue
        info = json.loads((folder/'source.json').read_text())
        source = ROOT/info['source_audio']
        rate = sf.info(source).samplerate
        a, b = round(info['parent_start_seconds']*rate), round(info['parent_end_seconds']*rate)
        expected, sr = sf.read(source, start=a, stop=b, dtype='int16')
        actual, ar = sf.read(folder/'audio.wav', dtype='int16')
        assert sr == ar and np.array_equal(expected, actual), folder
        duration = len(actual)/ar
        annotations = json.loads((folder/'expected.json').read_text())
        assert all(0 < t <= duration+.002 for t in annotations['expected'].values())
        derived += 1
    broken = []
    for path in BASE.rglob('*.md'):
        text = path.read_text(encoding='utf-8')
        for target in re.findall(r'\]\(([^)]+)\)', text):
            if '://' in target or target.startswith('#'):
                continue
            if not (path.parent/target.split('#')[0]).exists():
                broken.append((str(path.relative_to(BASE)), target))
    assert not broken, broken
    migration=json.loads((BASE/'migration.json').read_text())
    for old,item in migration['paths'].items():
        target=ROOT/item['destination']
        assert target.is_file(), (old,target)
        if item['equivalence']=='exact_bytes':
            assert digest(target)==item['original_sha256'], old
    assert not any((ROOT/'recordings'/name).exists() for name in ['cache','transcripts','ocsc_more','ocsc_batch2'])
    result = dict(source_audio_accounted_for=inv['source_audio_count'],
        canonical_hashes_and_preserved_legacy_metadata_verified=True, audio_transcript_checkpoint_pairing_verified=True,
        valid_manifests=manifests, exact_pcm_passage_excerpts_verified=derived,
        story_groups=len({r['story'] for r in inv.get('catalogue',inv['stories'])}),
        story_reader_folders=sum(r.get('audio') is not None for r in inv.get('catalogue',inv['stories'])),
        imported_recordings_verified=imported,
        demo_entries=sum(r.get('audio') is None for r in inv.get('catalogue',[])),
        broken_markdown_links=broken, archives_created=0)
    (BASE/'verification.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
