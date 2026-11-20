"""Add local media to a closed MapMap project using its calibration meshes."""

from copy import deepcopy
from hashlib import sha256
import json
import math
from pathlib import Path
import subprocess
import sys
from tempfile import NamedTemporaryFile

import av


IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg'}
VIDEO_EXTENSIONS = {'.mp4', '.mov', '.webm'}


def ensure_mapmap_closed():
    if sys.platform == 'win32':
        query = "$ErrorActionPreference = 'Stop'; [Diagnostics.Process]::GetProcessesByName('MapMap') | ForEach-Object ProcessName"
        command = ['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', query]
        flag = subprocess.CREATE_NO_WINDOW
    else:
        command = ['ps', '-A', '-o', 'comm=']
        flag = 0
    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True, errors='replace',
                                timeout=5, creationflags=flag)
    except (OSError, subprocess.SubprocessError) as error:
        raise ValueError('Could not verify whether MapMap is closed.') from error
    for line in result.stdout.splitlines():
        name = Path(line.strip()).name.casefold()
        if name in ('mapmap', 'mapmap.exe'):
            raise ValueError('Save your work and close MapMap, then try again.')


def video_duration(clip, stream):
    if stream.duration and stream.time_base:
        return float(stream.duration * stream.time_base)
    return (clip.duration or 0) / av.time_base


def add_scene_sources(data, project, directory):
    """Extend a project in memory and report which folder entries were accepted."""
    sources, layers = data['sources'], data['layers']
    known_media = {
        (project.parent / source['uri']).resolve()
        for source in sources
        if source.get('className') in ('Image', 'Video') and source.get('uri')
        and not source['uri'].startswith(('//', '\\'))
    }
    new_sources, new_layers, skipped = [], [], []
    already_imported = 0
    directory = directory.resolve()
    next_source = max((source['id'] for source in sources), default=0)
    next_layer = max((layer['id'] for layer in layers), default=0)
    template = None

    for path in sorted(directory.rglob('*'), key=lambda item: str(item).casefold()):
        suffix = path.suffix.lower()
        if suffix not in IMAGE_EXTENSIONS | VIDEO_EXTENSIONS or not path.is_file():
            continue
        relative = path.relative_to(directory)
        media = path.resolve()
        if not media.is_relative_to(directory):
            skipped.append(f'{relative}: file points outside the scenes folder.')
            continue
        if media in known_media:
            already_imported += 1
            continue
        is_video = suffix in VIDEO_EXTENSIONS
        try:
            with av.open(str(media)) as clip:
                stream = clip.streams.video[0]
                frame = next(clip.decode(stream))
                if is_video:
                    duration = video_duration(clip, stream)
                    if not math.isfinite(duration) or duration <= 0:
                        raise ValueError('video duration is unavailable.')
        except (OSError, av.FFmpegError, IndexError, StopIteration, ValueError):
            skipped.append(f'{relative}: media could not be decoded.')
            continue

        if template is None:
            template = calibration_meshes(data)
            vertices = [point for layer in template for point in layer['source']['vertices']]
            xs, ys = zip(*vertices)
            left, top = min(xs), min(ys)
            width, height = max(xs) - left, max(ys) - top
            if width <= 0 or height <= 0:
                raise ValueError('The calibration meshes must cover a two-dimensional source area.')
        # Preserve aspect ratio and center-crop to the original three-wall source area.
        scale = min(frame.width / width, frame.height / height)
        offset_x = (frame.width - width * scale) / 2
        offset_y = (frame.height - height * scale) / 2
        next_source += 1
        name = relative.with_suffix('').as_posix().replace('_', ' ')
        source = {'className': 'Video' if is_video else 'Image', 'id': next_source,
                  'name': name, 'uri': media.as_posix(), 'opacity': '0', 'locked': 'false',
                  'rate': '1', 'x': 0, 'y': 0}
        if is_video:
            source['volume'] = '0'
        new_sources.append(source)
        known_media.add(media)
        for wall in template:
            next_layer += 1
            layer = deepcopy(wall)
            layer.update(id=next_layer, sourceId=next_source, name=f"{name} | {wall['name']}",
                         locked='false', opacity='1', solo='false')
            layer['source']['vertices'] = [
                [offset_x + (x - left) * scale, offset_y + (y - top) * scale]
                for x, y in wall['source']['vertices']
            ]
            new_layers.append(layer)

    if new_sources:
        if max(next_source, next_layer) >= 2**31:
            raise ValueError('The project has run out of MapMap source or layer IDs.')
        sources.extend(new_sources)
        layers[:0] = new_layers
        for depth, layer in enumerate(layers, 1):
            layer['depth'] = str(depth)
    return new_sources, already_imported, skipped


def calibration_meshes(data):
    calibration = next((source for source in data['sources']
                        if source.get('className') == 'Image'
                        and source.get('name', '').casefold() == 'wall calibration'), None)
    walls = [] if calibration is None else [
        layer for layer in data['layers']
        if layer.get('sourceId') == calibration['id']
        and str(layer.get('visible', True)).lower() == 'true'
        and is_wall_mesh(layer)
    ]
    if len(walls) != 3:
        raise ValueError('This project needs a Wall calibration source with three visible mesh layers.')
    return walls


def is_wall_mesh(layer):
    return layer.get('className') == 'TextureLayer' and all(
        layer.get(side, {}).get('className') == 'Mesh' and layer[side].get('vertices')
        for side in ('source', 'destination')
    )


def source_center_x(layer):
    points = layer['source']['vertices']
    return sum(point[0] for point in points) / len(points)


def apply_wall_layout(data):
    """Copy the saved calibration corners to the existing three-wall scenes."""
    walls = sorted(calibration_meshes(data), key=source_center_x)
    calibration_id = walls[0]['sourceId']
    updated, skipped = 0, []
    layer_ids = {wall['id'] for wall in walls}
    for source in data['sources']:
        if source['id'] == calibration_id or source.get('className') not in ('Image', 'Video'):
            continue
        layers = [layer for layer in data['layers'] if layer.get('sourceId') == source['id']]
        if len(layers) != len(walls) or not all(is_wall_mesh(layer) for layer in layers):
            skipped.append(source['name'])
            continue
        pairs = list(zip(sorted(layers, key=source_center_x), walls))
        if any(any(layer['destination'][key] != wall['destination'][key] for key in ('nRows', 'nColumns'))
               for layer, wall in pairs):
            skipped.append(source['name'])
            continue
        layer_ids.update(layer['id'] for layer in layers)
        if any(layer['destination']['vertices'] != wall['destination']['vertices'] for layer, wall in pairs):
            for layer, wall in pairs:
                layer['destination']['vertices'] = deepcopy(wall['destination']['vertices'])
            updated += 1
    return {'updated': updated, 'skipped': skipped}, layer_ids


def editable_walls(data):
    walls = sorted(calibration_meshes(data), key=source_center_x)
    if any(str(wall['destination'][axis]) != '2' for wall in walls for axis in ('nColumns', 'nRows')):
        raise ValueError('The wall editor requires a four-corner mesh for each wall.')
    if any(len(wall['destination']['vertices']) != 4 for wall in walls):
        raise ValueError('The saved wall layout does not have four corners per wall.')
    return walls


def wall_layout_for_editor(contents, preview_vertices=None):
    walls = editable_walls(json.loads(contents.decode('utf-8-sig')))
    result = {'revision': sha256(contents).hexdigest(), 'walls': [
        {'name': wall['name'], 'corners': wall['destination']['vertices']} for wall in walls
    ]}
    if preview_vertices is not None and all(wall['id'] in preview_vertices for wall in walls):
        result['preview_corners'] = [preview_vertices[wall['id']] for wall in walls]
    return result


def verify_layout_revision(contents, revision):
    if revision != sha256(contents).hexdigest():
        raise ValueError('The saved project changed. Reopen the wall editor to load its current layout.')


def apply_edited_corners(data, corners):
    walls = editable_walls(data)
    if not isinstance(corners, list) or len(corners) != len(walls):
        raise ValueError('Provide four corners for each of the three walls.')

    changed = False
    for wall, points in zip(walls, corners):
        if (not isinstance(points, list) or len(points) != 4 or
                any(not isinstance(point, list) or len(point) != 2 or
                    any(type(value) not in (int, float) or not -32768 <= value <= 32768 for value in point)
                    for point in points)):
            raise ValueError('Four valid coordinate pairs are required for each wall.')

        # MapMap lists mesh vertices by row. Visit them in perimeter order.
        path = [points[i] for i in (0, 1, 3, 2)]
        edges = [(b[0] - a[0], b[1] - a[1]) for a, b in zip(path, path[1:] + path[:1])]
        turns = [ax * by - ay * bx for (ax, ay), (bx, by) in zip(edges, edges[1:] + edges[:1])]
        if not (all(turn > 0 for turn in turns) or all(turn < 0 for turn in turns)):
            raise ValueError(f"Keep the four corners of {wall['name']} in order without crossing edges.")
        changed |= points != wall['destination']['vertices']
        wall['destination']['vertices'] = points

    report, layer_ids = apply_wall_layout(data)
    return changed or report['updated'] > 0, report, layer_ids


def save_project(project, original, data, *, allow_live=False):
    with NamedTemporaryFile(dir=project.parent, prefix=project.name + '.', suffix='.tmp', delete=False) as file:
        pending = Path(file.name)
    try:
        pending.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
        if not allow_live:
            ensure_mapmap_closed()
        if project.read_bytes() != original:
            raise ValueError('The MapMap project changed while it was being edited. Try again.')
        pending.replace(project)
    finally:
        pending.unlink(missing_ok=True)
