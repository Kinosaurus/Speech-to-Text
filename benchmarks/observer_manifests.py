"""Resolve the exact book manifests used by live benchmark observers."""
from pathlib import Path


def observer_manifest_paths(root, checkpoint_path=None):
    root = Path(root)
    if checkpoint_path is not None:
        path = Path(checkpoint_path)
        if not path.is_absolute():
            path = root / path
        if not path.is_file():
            raise FileNotFoundError(path)
        return {path.stem.removesuffix('_story'): path}
    return {name: root / f'examples/{name}_story.json'
            for name in ('horse', 'fat_cat', 'tea', 'little_mermaid')}
