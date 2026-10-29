"""Refresh the canonical recording catalogue without rebuilding legacy folders."""
import hashlib
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / 'recordings/library'


def audio_for(folder):
    direct = folder/'audio.wav'
    if direct.exists():
        return direct
    alias = folder/'audio.json'
    if alias.exists():
        target = (LIB/json.loads(alias.read_text())['library_path']).resolve()
        if not target.is_relative_to(LIB.resolve()):
            raise ValueError('Audio alias outside library')
        return target
    return None


def link(path, base):
    return Path(os.path.relpath(path, base)).as_posix()


def main():
    inventory = json.loads((LIB/'inventory.json').read_text())
    if inventory.get('version') != 2:
        raise RuntimeError('Complete the verified library migration first.')
    lines = ['# Recording library', '', 'Canonical recordings, reading text, spoken transcripts and checkpoints. Old recording folders have been retired. Downloaded corpus data remain local and Git-ignored.', '', '| Story / passage | Reader | Reading text | Spoken transcript | Recording | Checkpoints |', '| --- | --- | --- | --- | --- | --- |']
    rows = []
    for story in sorted((LIB/'stories').iterdir()):
        if not story.is_dir():
            continue
        story_lines = [f'# {story.name}', '', 'Different readers of the same passage are grouped here. Their spoken transcripts can differ. Water-park and Tess-and-Ty installments are separate.', '', '| Reader | Text | Transcript | Audio | Checkpoints |', '| --- | --- | --- | --- | --- |']
        for folder in sorted((story/'readers').iterdir()):
            if not folder.is_dir():
                continue
            audio = audio_for(folder)
            supplied = folder/'passage.txt'
            reference = folder/'reference.txt'
            text = supplied if supplied.exists() else reference if reference.exists() else None
            spoken = folder/'transcript.txt'
            checkpoint = folder/'checkpoints.json'
            def cell(path, base, label, missing):
                return f'[{label}]({link(path,base)})' if path and path.exists() else missing
            def cells(base):
                return [cell(text,base,'Supplied text' if supplied.exists() else 'Reference (see text_status.json)','Unavailable'), cell(spoken,base,'Transcript','Not recorded'), cell(audio,base,'Play audio','Not recorded'),cell(checkpoint,base,'Checkpoints','Not configured')]
            lines.append(f'| [{story.name}]({link(story/"README.md",LIB)}) | {folder.name} | '+' | '.join(cells(LIB))+' |')
            story_lines.append(f'| [{folder.name}](readers/{folder.name}/README.md) | '+' | '.join(cells(story))+' |')
            readme=folder/'README.md'
            old=readme.read_text(encoding='utf-8').split('<!-- library-files -->')[0] if readme.exists() else f'# {story.name}: {folder.name}\n'
            extra=['', '<!-- library-files -->', '## Files', '']
            for label,path in [('Reading text',text),('Spoken transcript',spoken),('Recording',audio),('Checkpoints',checkpoint)]:
                if path and path.exists():extra.append(f'- [{label}]({link(path,folder)})')
            extra+=['', 'passage.txt is the original supplied text when present. reference.txt can be a transcript-derived corpus reference; text_status.json records its status. transcript.txt describes recorded speech and can include reading mistakes, adult prompts or ASR errors.', '']
            readme.write_text(old.rstrip()+'\n'+'\n'.join(extra),encoding='utf-8')
            rows.append(dict(story=story.name,reader=folder.name,path=folder.relative_to(LIB).as_posix(),audio=audio.relative_to(LIB).as_posix() if audio else None))
        (story/'README.md').write_text('\n'.join(story_lines)+'\n',encoding='utf-8')
    lines += ['', '## Complete sessions', '', '| Reader | Full source session | Complete reading task |', '| --- | --- | --- |']
    for folder in sorted((LIB/'full_sessions').iterdir()):
        if folder.is_dir():lines.append(f'| {folder.name} | [Full session](full_sessions/{folder.name}/README.md) | [Reading task](reading_sessions/{folder.name}/README.md) |')
    lines+=['', '## Notes', '', '- Supplied story text and spoken transcripts are separate. Some corpus references are transcript-derived, not original printed text. Missing material is explicitly marked.', '- Story excerpts have rebased checkpoint ranges and provisional timing. Previous live results cover complete reading tasks, not freshly tested excerpt playback.', '- Only the reading interval in a full session has configured checkpoints; other tasks are not annotated as story reading.', '- Shared whole-task audio uses audio.json aliases instead of duplicate WAVs. Cached resamples with identical audio have been removed.', '- transcript_history/ preserves earlier ASR versions; reviews/timestamp_check/ contains the two audio reviews.', '- evaluation/ holds reports; jobs/ holds current benchmark definitions; migration.json resolves historical paths. provenance/ preserves unique legacy metadata.', '- New microphone captures use captures/<session>/audio.wav and transcript.srt; file-run subtitles use the recording folder asr/ directory. Temporary conversions use .cache/.', '- Original eight public recordings and the supplied sample demo are tracked in Git. OCSC audio/transcripts remain ignored; follow TalkBank reuse rules and cite Wagner et al. (2025), The Ohio Child Speech Corpus.', '']
    (LIB/'README.md').write_text('\n'.join(lines),encoding='utf-8')
    inventory['catalogue']=rows
    (LIB/'inventory.json').write_text(json.dumps(inventory,indent=2)+'\n',encoding='utf-8')
    print(f'Refreshed {len(rows)} reader/demo entries; {len({r["story"] for r in rows})} story groups.')


if __name__ == '__main__':
    main()
