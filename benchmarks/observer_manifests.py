"""Resolve the exact book manifests used by live benchmark observers."""
from pathlib import Path
from recording_library import resolve_recording_path


def observer_manifest_paths(root, checkpoint_path=None):
    root = Path(root)
    if checkpoint_path is not None:
        path = resolve_recording_path(checkpoint_path, root)
        if not path.is_file():
            raise FileNotFoundError(path)
        name = path.parent.name if path.name == 'checkpoints.json' else path.stem.removesuffix('_story')
        return {name: path}
    return {name: root / f'recordings/library/stories/{name}/readers/{name}/checkpoints.json'
            for name in ('horse', 'fat_cat', 'tea', 'little_mermaid')}
