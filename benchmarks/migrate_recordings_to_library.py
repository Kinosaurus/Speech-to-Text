"""Verify preserved data before retiring legacy recording copies.

Default is a preflight. --apply removes only verified duplicates in this
checkout, preserving unique metadata under library/provenance. No uploads.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT/'recordings/library'
sys.path.insert(0, str(ROOT))
from recording_library import sample_audio


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(4*1024*1024),b''):
            h.update(chunk)
    return h.hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2)+'\n', encoding='utf-8')


def safe(path):
    path = path.resolve()
    if not path.is_relative_to(ROOT) or path in (ROOT, LIB, ROOT/'recordings'):
        raise ValueError(f'Unsafe cleanup target: {path}')
    return path


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    args=parser.parse_args()
    inventory=json.loads((LIB/'inventory.json').read_text())
    if inventory.get('version') == 2:
        raise RuntimeError('Migration already completed. Use the library verifier.')
    initial=inventory['source_audio']
    replacements={}
    retired=[]
    pcm_duplicates=[]
    review_old=LIB/'other_audio/output/ocsc/batch2-live-2026-10-29/audio-review'
    review_new=LIB/'reviews/timestamp_check'
    for old,entry in initial.items():
        path=LIB/entry['library_path']
        assert path.is_file() and sha(path)==entry['sha256'], path
        if '/cache/previous-resamples/' in old:
            name=Path(old).stem.removesuffix('_resampled')
            target=LIB/f'reading_sessions/{name}/audio.wav' if name.isdigit() else sample_audio(name)
            left,lr=sf.read(path,dtype='int16',always_2d=True)
            right,rr=sf.read(target,dtype='int16',always_2d=True)
            assert lr==rr and np.array_equal(left,right), path
            replacements[path]=target
            pcm_duplicates.append(path)
        elif path.is_relative_to(review_old):
            replacements[path]=review_new/path.relative_to(review_old)
    # Three whole-task story copies refer to the one canonical reading WAV.
    for ident,story in [('6008','grandmas-house'),('7057','grandmas-house'),('4006','peanuts')]:
        old=LIB/f'stories/{story}/readers/{ident}/audio.wav'
        target=LIB/f'reading_sessions/{ident}/audio.wav'
        assert sha(old)==sha(target)
        replacements[old]=target
        retired.append(old)

    legacy_dirs=[ROOT/f'recordings/{name}' for name in ('cache','transcripts','ocsc_more','ocsc_batch2')]
    legacy_files=[p for p in (ROOT/'recordings').iterdir() if p.is_file() and p.name not in ('README.md','OCSC_LOCAL_SETUP.md')]
    for folder in legacy_dirs:
        legacy_files += [p for p in folder.rglob('*') if p.is_file()]
    # The original review audio also has a verified copy in the library.
    legacy_files += [ROOT/p for p in initial if p.startswith('output/')]
    for path in legacy_dirs+legacy_files+retired:
        safe(path)
    by_hash={}
    for path in LIB.rglob('*'):
        if path.is_file() and not path.is_relative_to(review_old) and not path.is_relative_to(LIB/'other_audio/recordings/cache') and path not in retired:
            by_hash.setdefault(sha(path),path)
    paths={}
    pending=[]
    supplied={'tea':'tea_passage.txt','fat_cat':'fat_cat_passage.txt',
              'horse':'horse.txt','little_mermaid':'little_mermaid_passage.txt'}
    for name,filename in supplied.items():
        source=ROOT/'examples'/filename
        target=LIB/f'stories/{name}/readers/{name}/passage.txt'
        pending.append((source,target))
        by_hash[sha(source)]=target
    demo=LIB/'stories/sample/readers/demo'
    for name,target in [('sample_story.json','checkpoints.json'),('sample_passage.txt','passage.txt')]:
        source=ROOT/'examples'/name
        pending.append((source,demo/target))
        by_hash[sha(source)]=demo/target
    legacy_dirs.append(ROOT/'examples')
    legacy_files += [p for p in (ROOT/'examples').rglob('*') if p.is_file()]
    for source in legacy_files:
        key=source.relative_to(ROOT).as_posix()
        original_hash=sha(source)
        if key in initial:
            assert original_hash==initial[key]['sha256'], f'Source changed since library copy: {source}'
            old=LIB/initial[key]['library_path']
            target=replacements.get(old,old)
            kind='identical_pcm' if old in pcm_duplicates and original_hash!=sha(target) else 'exact_bytes'
        else:
            target=by_hash.get(original_hash)
            if target is None:
                target=LIB/'provenance/legacy_files'/source.relative_to(ROOT)
                if source.suffix=='.md':
                    target=target.with_suffix('.md.txt')
                pending.append((source,target))
            kind='exact_bytes'
        paths[key]=dict(destination=target.relative_to(ROOT).as_posix(),original_sha256=original_hash,equivalence=kind)
    # Capture all original mappings, not just files selected for deletion.
    for old,entry in initial.items():
        if old not in paths:
            target=LIB/entry['library_path']
            target=replacements.get(target,target)
            paths[old]=dict(destination=target.relative_to(ROOT).as_posix(),original_sha256=entry['sha256'],equivalence='exact_bytes')
    print(f'Preflight: {len(legacy_files)} legacy files; {len(pending)} unique metadata files to preserve; 13 redundant library WAVs.',flush=True)
    if not args.apply:
        return
    assert not review_new.exists()
    review_new.parent.mkdir(parents=True,exist_ok=True)
    shutil.move(str(safe(review_old)),str(review_new))
    for source,target in pending:
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(source,target)
        assert sha(source)==sha(target)
    # Record old metadata/paths before changing any live configuration.
    save(LIB/'provenance/initial_inventory.json',inventory)
    save(LIB/'migration.json',dict(version=1,paths=paths,note='Historical source paths; canonical data live in this library. PCM aliases can have different WAV headers.'))
    for folder in (LIB/'stories').glob('*/readers/*'):
        if (folder/'passage.txt').exists():
            save(folder/'text_status.json',dict(kind='supplied_passage',file='passage.txt',note='Original supplied reading text; transcript.txt remains separate.'))
        elif (folder/'reference.txt').exists():
            save(folder/'text_status.json',dict(kind='printed_reference' if folder.parent.parent.name=='grandmas-house' else 'transcript_derived_reference',
                file='reference.txt',note='Original printed text unavailable for transcript-derived corpus references.'))
        else:
            save(folder/'text_status.json',dict(kind='not_available',note='No independent supplied passage text exists for this recording.'))
    save(demo/'recording_status.json',dict(status='not_recorded',note='Supplied demo text and checkpoints; no matching audio or spoken transcript exists.'))
    (demo/'README.md').write_text('# Sample microphone demo\n\npassage.txt is the original supplied text; checkpoints.json is its matching manifest. No matching recording or spoken transcript exists.\n',encoding='utf-8')

    def mapped(value):
        if isinstance(value,dict): return {k:mapped(v) for k,v in value.items()}
        if isinstance(value,list): return [mapped(v) for v in value]
        if isinstance(value,str):
            entry=paths.get(value.replace('\\','/'))
            return entry['destination'] if entry else value
        return value

    for folder in ('reading_sessions','full_sessions','stories'):
        for p in (LIB/folder).rglob('source.json'):
            save(p,mapped(json.loads(p.read_text())))
    # Central jobs and subset definitions for current benchmark entry points.
    for batch in ('ocsc_more','ocsc_batch2'):
        source=ROOT/f'recordings/{batch}/checkpoints/jobs.json'
        save(LIB/f'jobs/{batch}.json',mapped(json.loads(source.read_text())))
    for name,oldname in [('standard','subset'),('early','subset-early')]:
        data=json.loads((ROOT/f'output/ocsc/{oldname}.json').read_text())
        data=mapped(data)
        data['manifest']='recordings/library/reading_sessions/6008/'+('checkpoints_early.json' if name=='early' else 'checkpoints.json')
        save(LIB/f'evaluation/ocsc_subsets/{name}.json',data)
    for old,new in replacements.items():
        if old in retired:
            relative=new.relative_to(LIB).as_posix()
            save(old.with_name('audio.json'),dict(library_path=relative,sha256=sha(new),note='Alias to the canonical complete reading-task audio.'))
            readme=old.parent/'README.md'
            text=readme.read_text(encoding='utf-8')
            text+='\n[Play audio](../../../../'+relative+') — shared canonical file; no extra WAV copy.\n'
            readme.write_text(text,encoding='utf-8')
    # Rebase relocated review links in the current library documents.
    for p in LIB.rglob('*.md'):
        text=p.read_text(encoding='utf-8')
        text=text.replace('../../other_audio/output/ocsc/batch2-live-2026-10-29/audio-review/REVIEW.md','../../reviews/timestamp_check/REVIEW.md')
        p.write_text(text,encoding='utf-8')
    # All deletion targets are confined to this checkout and verified first.
    for source in legacy_files:
        entry=paths[source.relative_to(ROOT).as_posix()]
        target=ROOT/entry['destination']
        assert target.is_file(),target
        assert sha(source)==entry['original_sha256'], f'Source changed during migration: {source}'
        if entry['equivalence']=='exact_bytes': assert sha(target)==entry['original_sha256'],target
    cache_dir=LIB/'other_audio/recordings/cache'
    safe(cache_dir)
    for path in legacy_files+retired:
        safe(path).unlink()
    # Empty old directories only, after the per-file preservation checks above.
    for folder in legacy_dirs:
        for path in sorted(folder.rglob('*'),key=lambda p:len(p.parts),reverse=True):
            if path.is_dir(): safe(path).rmdir()
        safe(folder).rmdir()
    shutil.rmtree(cache_dir)
    # Review ASR/preparation scratch scripts depended on the retired layout.
    for name in ('prepare_more_samples.py','prepare_batch2.py','build_more_checkpoints.py','build_batch2_checkpoints.py','validate_batch2.py','update_local_catalog.py'):
        source=ROOT/'output/ocsc'/name
        if source.exists():
            target=LIB/'provenance/retired_scripts'/(name+'.txt')
            target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(source,target)
            assert sha(source)==sha(target)
            safe(source).unlink()
    # Final source-audio registry points only at canonical live files.
    for old,entry in initial.items():
        destination=ROOT/paths[old]['destination']
        entry['library_path']=destination.relative_to(LIB).as_posix()
        entry['original_sha256']=paths[old]['original_sha256']
        entry['sha256']=sha(destination)
        entry['bytes']=destination.stat().st_size
        entry['equivalence']=paths[old]['equivalence']
    inventory.update(version=2,source_audio=initial,note='Canonical library after verified duplicate cleanup. Original path/byte metadata retained in migration.json and provenance/.')
    save(LIB/'inventory.json',inventory)
    print('Migration complete: legacy recording folders removed; canonical source files and unique metadata verified.',flush=True)


if __name__=='__main__': main()
