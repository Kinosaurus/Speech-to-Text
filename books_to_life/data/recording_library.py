"""Canonical local recording paths and optional historical-path resolution."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LIBRARY = ROOT / 'recordings/library'


def sample_audio(name, root=ROOT):
    return Path(root) / f'recordings/library/stories/{name}/readers/{name}/audio.wav'


def sample_checkpoints(name, root=ROOT):
    return sample_audio(name, root).with_name('checkpoints.json')


def reading_audio(reader, root=ROOT):
    return Path(root) / f'recordings/library/reading_sessions/{reader}/audio.wav'


def resolve_recording_path(path, root=ROOT):
    """Resolve old saved-job paths without rewriting historical result files."""
    root = Path(root).resolve()
    path = Path(str(path).replace('\\', '/'))
    candidate = path if path.is_absolute() else root / path
    if candidate.exists():
        if candidate.name == 'audio.json':
            target=(root/'recordings/library'/json.loads(candidate.read_text())['library_path']).resolve()
            if not target.is_relative_to(root/'recordings/library'):
                raise ValueError('Audio alias points outside library.')
            return target
        return candidate
    try:
        key = candidate.resolve().relative_to(root).as_posix()
    except ValueError:
        return candidate
    # Known historical layouts remain usable on another PC without requiring
    # this machine's migration inventory to be copied there.
    match=re.fullmatch(r'recordings/(?:ocsc_more/|ocsc_batch2/)?(\d{4})_(reading|full)\.(wav|txt|srt|cha)',key)
    target=None
    if match:
        reader,kind,ext=match.groups()
        category='reading_sessions' if kind=='reading' else 'full_sessions'
        filename='audio.wav' if ext=='wav' else 'transcript.'+ext
        target=root/f'recordings/library/{category}/{reader}/{filename}'
    match=re.fullmatch(r'recordings/(dog|dragon|fat_cat|horse|little_mermaid|nickel|recording_2|tea)\.(wav|txt|srt)',key)
    if match:
        name,ext=match.groups()
        target=sample_audio(name,root).with_name('audio.wav' if ext=='wav' else 'transcript.'+ext)
    match=re.fullmatch(r'examples/(dog|dragon|fat_cat|horse|little_mermaid|nickel|recording_2|tea)_story\.json',key)
    if match:
        target=sample_checkpoints(match[1],root)
    if target is not None and target.exists():
        return target
    migration = root / 'recordings/library/migration.json'
    if migration.exists():
        item = json.loads(migration.read_text(encoding='utf-8')).get('paths', {}).get(key)
        if item:
            target = (root / item['destination']).resolve()
            if not target.is_relative_to(root / 'recordings/library'):
                raise ValueError('Recording migration points outside the library.')
            return target
    return candidate


def session_outputs(files, session, root=ROOT):
    """Keep new captures/runs together without recreating the legacy folders."""
    library = Path(root).resolve() / 'recordings/library'
    capture = library / 'captures' / session
    if files and len(files) == 1:
        source = resolve_recording_path(files[0], root).resolve()
        if source.is_relative_to(library):
            return capture/'audio.wav', source.parent/'asr'/f'live-{session}.srt'
    if files:
        return capture/'audio.wav', library/'runs'/session/'transcript.srt'
    return capture/'audio.wav', capture/'transcript.srt'
