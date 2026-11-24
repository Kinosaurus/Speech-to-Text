"""Playable overlays in a saved MapMap project and their local OSC transport."""

from dataclasses import dataclass
from hashlib import sha256
import importlib.util
import json
import logging
import math
from pathlib import Path
import socket
import struct
from threading import Event, Lock, Thread, Timer
from time import monotonic

import av

from books_to_life.runtime.mapmap_scenes import (
    add_scene_sources, apply_edited_corners, apply_wall_layout, ensure_mapmap_closed,
    save_project, verify_layout_revision, video_duration, wall_layout_for_editor,
)

DEFAULT_FADE_MS = 450
VIDEO_SEEK_SECONDS = .18
VIDEO_SETTLE_SECONDS = .07
FIRST_FRAME_TIMEOUT = 4
FADE_STEPS_PER_SECOND = 30


@dataclass(frozen=True)
class ProjectionCue:
    source: int
    title: str
    has_audio: bool = False
    hold_seconds: float | None = None
    layer_range: tuple[int, int] | None = None


def output_vertices(data):
    return tuple(
        (layer['id'], tuple(tuple(point) for point in layer['destination']['vertices']))
        for layer in data['layers'] if (layer.get('destination') or {}).get('vertices')
    )


class MapMapCue:
    def __init__(self, path, port, project=None):
        bridge = None
        if path is not None:
            spec = importlib.util.spec_from_file_location('reading_pod_mapmap_bridge', path)
            bridge = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(bridge)
        self.bridge = bridge
        self.port = port
        self.project = Path(project or getattr(bridge, 'VIDEO_PROJECT', path)).resolve()
        self.has_project_file = self.project.suffix.lower() == '.mmp' and self.project.is_file()
        self.silver_seed = None
        self.output_layers = ()
        self.output_preview = None
        if project is not None or (hasattr(bridge, 'VIDEO_PROJECT') and self.project.is_file()):
            data = json.loads(self.project.read_text(encoding='utf-8-sig'))
            self.cues, self.silver_seed, self.output_layers = self.project_catalog(data)
        else:
            # Older handoff bridges expose a single fixed source.
            source = bridge.GARDEN_SOURCE
            self.silver_seed = str(source)
            self.cues = {self.silver_seed: ProjectionCue(
                source, 'Silver Seed video and soundtrack', True, bridge.VIDEO_HOLD_SECONDS,
            )}
        self.active = None
        self.incoming = None
        self.transition = None
        self.timer = None
        self.lock = Lock()
        self.story_key = None
        self.story_cues = None
        self.story_layers = None
        self.story_project = None
        self.prepared = None
        self.playback_error = None

    def project_catalog(self, data):
        mapped = {}
        # MapMap saves layers front to back. Earlier layers cover later ones.
        for index, layer in enumerate(data['layers']):
            if 'sourceId' in layer and str(layer.get('visible', True)).lower() == 'true':
                mapped.setdefault(layer['sourceId'], []).append(index)
        cues = {}
        silver_seed = None
        for source in data['sources']:
            ident = source['id']
            kind = source.get('className')
            uri = source.get('uri')
            # The grid and other visible-by-default layers belong to the base scene.
            if (type(ident) is not int or not 0 < ident < 2**31 or ident not in mapped
                    or kind not in ('Image', 'Video') or not isinstance(uri, str) or not uri
                    or uri.startswith(('//', '\\\\'))
                    or str(source.get('opacity')) not in ('0', '0.0')):
                continue
            media = self.project.parent / uri
            if not media.is_file():
                continue
            title = str(source.get('name') or media.stem)
            layers = (mapped[ident][0], mapped[ident][-1])
            if kind == 'Image':
                cue = ProjectionCue(ident, title, layer_range=layers)
            elif (ident == getattr(self.bridge, 'GARDEN_SOURCE', None)
                    and media.name == getattr(self.bridge, 'VIDEO_FILE', None)):
                silver_seed = str(ident)
                cue = ProjectionCue(ident, 'Silver Seed video and soundtrack', True, self.bridge.VIDEO_HOLD_SECONDS, layers)
            else:
                try:
                    with av.open(str(media)) as clip:
                        if not clip.streams.video:
                            continue
                        video = clip.streams.video[0]
                        duration = video_duration(clip, video)
                        has_audio = bool(clip.streams.audio)
                except (OSError, av.FFmpegError):
                    continue
                if not math.isfinite(duration) or duration <= 0:
                    continue
                cue = ProjectionCue(ident, title, has_audio, max(.01, duration - .15), layers)
            cues[str(ident)] = cue
        bundled_seed = str(data.get('readingPodSilverSeed'))
        if silver_seed is None and bundled_seed in cues:
            silver_seed = bundled_seed
        return cues, silver_seed, output_vertices(data)

    def update_project(self, edit, *, revision=None):
        with self.lock:
            ensure_mapmap_closed()
            original = self.project.read_bytes()
            if revision is not None:
                verify_layout_revision(original, revision)
            data = json.loads(original.decode('utf-8-sig'))
            source_count = len(data['sources'])
            changed, result = edit(data)
            cues, silver_seed, output_layers = self.project_catalog(data)
            if any(str(source['id']) not in cues for source in data['sources'][source_count:]):
                raise ValueError('An imported scene changed while the project was being prepared. Try again.')
            if changed:
                save_project(self.project, original, data)
            self.cancel_hold()
            self.cancel_transition()
            self.active = None
            self.output_preview = None
            self.cues, self.silver_seed, self.output_layers = cues, silver_seed, output_layers
            return result

    def import_scenes(self, directory):
        def edit(data):
            directory.mkdir(parents=True, exist_ok=True)
            imported, existing, skipped = add_scene_sources(data, self.project, directory)
            return bool(imported), {'imported': [source['name'] for source in imported],
                                    'existing': existing, 'skipped': skipped}

        return self.update_project(edit)

    def apply_wall_layout(self):
        def edit(data):
            result, _ = apply_wall_layout(data)
            return result['updated'] > 0, result

        return self.update_project(edit)

    def wall_layout(self, pid=None):
        with self.lock:
            contents = self.project.read_bytes()
            preview = self.output_preview
            vertices = None
            if preview and pid is not None and preview['pid'] == pid and preview['revision'] == sha256(contents).hexdigest():
                vertices = preview['vertices']
            return wall_layout_for_editor(contents, vertices)

    def save_wall_layout(self, revision, corners, *, live=False):
        with self.lock:
            if live and (self.story_project is None or self.story_project.path.resolve() == self.project.resolve()):
                raise ValueError('Live layout saving requires a separate selected-story project.')
            if not live:
                ensure_mapmap_closed()
            original = self.project.read_bytes()
            verify_layout_revision(original, revision)
            data = json.loads(original.decode('utf-8-sig'))
            changed, result, _ = apply_edited_corners(data, corners)
            if changed:
                save_project(self.project, original, data, allow_live=live)
            self.output_layers = output_vertices(data)
            self.output_preview = None
            return {**result, **wall_layout_for_editor(self.project.read_bytes())}

    def preview_wall_layout(self, revision, corners, *, pid=None):
        with self.lock:
            original = self.project.read_bytes()
            verify_layout_revision(original, revision)
            data = json.loads(original.decode('utf-8-sig'))
            _, result, layers = apply_edited_corners(data, corners)
            vertices = self.send_output_vertices(
                ((layer, points) for layer, points in output_vertices(data) if layer in layers),
                pid=pid, revision=revision,
            )
            self.output_preview = {'revision': revision, 'pid': pid, 'vertices': vertices}
            return result

    def set_output_layout(self, size=None, *, pid=None):
        if not self.output_layers:
            raise ValueError('The saved MapMap project has no adjustable destination vertices.')
        scale, offset_x, offset_y = 1.0, 0.0, 0.0
        if size is not None:
            width, height = size
            all_x, all_y = zip(*(point for _, vertices in self.output_layers for point in vertices))
            left, right = min(all_x), max(all_x)
            top, bottom = min(all_y), max(all_y)
            if left == right or top == bottom:
                raise ValueError('The saved MapMap project has no two-dimensional output area.')
            margin = min(48, width / 16, height / 16)
            scale = min((width - 2*margin) / (right-left), (height - 2*margin) / (bottom-top))
            offset_x = (width - (left+right)*scale) / 2
            offset_y = (height - (top+bottom)*scale) / 2
        with self.lock:
            revision = sha256(self.project.read_bytes()).hexdigest()
            vertices = self.send_output_vertices(self.output_layers, scale, offset_x, offset_y, pid=pid, revision=revision)
            self.output_preview = {'revision': revision, 'pid': pid, 'vertices': vertices}

    def send_output_vertices(self, layers, scale=1.0, offset_x=0.0, offset_y=0.0, *, pid=None, revision=None):
        sent = {layer: [[x*scale + offset_x, y*scale + offset_y] for x, y in vertices]
                for layer, vertices in layers if self.story_layers is None or layer in self.story_layers}
        if self.story_project is not None:
            if pid is None:
                raise ValueError('Could not confirm MapMap. Check its connection before applying the wall layout.')
            self.story_project.apply_layout(sent.items(), pid, revision, persist=False)
            return sent
        address = b'/mapmap/layer/vertex/destination/xy\0'
        header = address + b'\0' * (-len(address) % 4) + b',iiff\0\0\0'
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sender:
            for layer, points in sent.items():
                for index, (x, y) in enumerate(points):
                    packet = header + struct.pack('>iiff', layer, index, x, y)
                    sender.sendto(packet, ('127.0.0.1', self.port))
        return sent

    def send(self, cue, command, value=None):
        address = f'/mapmap/source/{command}'.encode() + b'\0'
        packet = address + b'\0' * (-len(address) % 4)
        if value is None:
            packet += b',i\0\0' + struct.pack('>i', cue.source)
        else:
            packet += b',if\0' + struct.pack('>if', cue.source, value)
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sender:
            sender.sendto(packet, ('127.0.0.1', self.port))

    def stop(self, cue):
        self.send(cue, 'opacity', 0.0)
        if cue.hold_seconds is not None:
            if self.story_project:
                self.story_project.release_video(cue.source)
            else:
                self.pause(cue)
                self.send(cue, 'rewind')

    def pause(self, cue):
        self.send(cue, 'volume', 0.0)
        self.send(cue, 'pause')

    def cancel_hold(self):
        if self.timer:
            self.timer.cancel()
            self.timer = None

    def cancel_transition(self):
        if self.transition is not None:
            self.transition.set()
            self.transition = None
        incoming = self.incoming
        self.incoming = None
        return incoming

    def set_story_scope(self, key, cues, layers):
        with self.lock:
            self.output_preview = None
            if key != self.story_key:
                self.cancel_hold()
                self.cancel_transition()
                self.active = None
                self.prepared = None
                self.playback_error = None
            self.story_key = key
            self.story_cues = frozenset(cue.source for cue in cues.values())
            self.story_layers = frozenset(layers)

    def reset(self):
        with self.lock:
            self.cancel_hold()
            self.cancel_transition()
            self.active = None
            self.prepared = None
            self.playback_error = None
            for cue in self.cues.values():
                if self.story_cues is None or cue.source in self.story_cues:
                    self.stop(cue)

    def preload(self, cue):
        with self.lock:
            self.set_preload(cue)

    def set_preload(self, cue):
        if not self.story_project or not self.story_key or self.story_key[1] is None:
            return
        if self.prepared and self.prepared[0] == cue:
            return
        if self.prepared:
            previous, _ = self.prepared
            self.prepared = None
            self.story_project.release_video(previous.source)
        if cue and cue.hold_seconds is not None and cue != self.active:
            self.prepared = (cue, self.story_project.prepare_video(cue.source))

    def start_video(self, cue):
        self.send(cue, 'volume', float(cue.has_audio))
        self.send(cue, 'play')
        timer = Timer(cue.hold_seconds, lambda: self.hold(cue, timer))
        timer.daemon = True
        self.timer = timer
        timer.start()

    def play(self, cue, fade_ms=DEFAULT_FADE_MS, *, next_cue=None):
        with self.lock:
            if self.story_project and (not self.story_key or self.story_key[1] is None):
                return
            self.playback_error = None
            abandoned = self.cancel_transition()
            self.cancel_hold()
            outgoing = self.active
            if abandoned is not None:
                # Restore a fully visible scene before discarding a partial transition.
                if outgoing:
                    self.send(outgoing, 'opacity', 1.0)
                self.stop(abandoned)
            ticket = None
            if self.story_project and cue.hold_seconds is not None and outgoing != cue:
                self.set_preload(cue)
                _, ticket = self.prepared
                self.prepared = None
            if (outgoing is None and ticket is None) or outgoing == cue:
                # Replaying the same source leaves its texture visible while it seeks.
                self.active = cue
                if cue.hold_seconds is not None:
                    self.send(cue, 'rewind')
                self.send(cue, 'opacity', 1.0)
                if cue.hold_seconds is not None:
                    self.start_video(cue)
                self.set_preload(next_cue)
                return
            if outgoing and outgoing.hold_seconds is not None:
                self.pause(outgoing)
            self.send(cue, 'opacity', 0.0)
            if cue.hold_seconds is not None and ticket is None:
                self.send(cue, 'rewind')
            self.incoming = cue
            cancelled = self.transition = Event()
            Thread(target=self.crossfade, args=(outgoing, cue, fade_ms / 1000, cancelled, ticket, next_cue),
                   daemon=True).start()

    def fade_opacity(self, cue, start, end, seconds, cancelled):
        steps = max(1, math.ceil(seconds * FADE_STEPS_PER_SECOND))
        began = monotonic()
        for step in range(1, steps + 1):
            progress = step / steps
            if cancelled.wait(max(0, began + seconds * progress - monotonic())):
                return
            with self.lock:
                if self.transition is not cancelled:
                    return
                self.send(cue, 'opacity', start + (end - start) * progress)

    def crossfade(self, outgoing, incoming, seconds, cancelled, ticket=None, next_cue=None):
        try:
            if ticket:
                deadline = monotonic() + FIRST_FRAME_TIMEOUT
                while not cancelled.is_set():
                    ready = self.story_project.video_ready(incoming.source, ticket)
                    if ready is True:
                        break
                    if ready is False or monotonic() >= deadline:
                        raise ValueError(f'{incoming.title} did not produce a first frame.')
                    cancelled.wait(.02)
                with self.lock:
                    if self.transition is not cancelled:
                        return
                    self.start_video(incoming)
            elif incoming.hold_seconds is not None:
                # The bundled OSC receiver has no frame-ready reply. Seek while
                # hidden and give the already loaded player time to show a frame.
                if cancelled.wait(VIDEO_SEEK_SECONDS):
                    return
                with self.lock:
                    if self.transition is not cancelled:
                        return
                    self.start_video(incoming)
                if cancelled.wait(VIDEO_SETTLE_SECONDS):
                    return
            old_layers = outgoing.layer_range if outgoing else None
            new_layers = incoming.layer_range
            if not outgoing:
                self.fade_opacity(incoming, 0.0, 1.0, 0, cancelled)
            elif old_layers and new_layers and new_layers[1] < old_layers[0]:
                self.fade_opacity(incoming, 0.0, 1.0, seconds, cancelled)
            elif old_layers and new_layers and old_layers[1] < new_layers[0]:
                self.fade_opacity(incoming, 0.0, 1.0, 0, cancelled)
                self.fade_opacity(outgoing, 1.0, 0.0, seconds, cancelled)
            else:
                # Interleaved layers need an overlap in both directions. Keep one
                # source opaque so the calibration grid never enters the blend.
                self.fade_opacity(incoming, 0.0, 1.0, seconds / 2, cancelled)
                self.fade_opacity(outgoing, 1.0, 0.0, seconds / 2, cancelled)
            with self.lock:
                if self.transition is cancelled:
                    if outgoing:
                        self.stop(outgoing)
                    self.active = incoming
                    self.cancel_transition()
                    self.set_preload(next_cue)
        except (OSError, ValueError) as error:
            logging.warning('MapMap transition failed: %s', error)
            with self.lock:
                if self.transition is cancelled:
                    self.cancel_transition()
                    self.cancel_hold()
                    self.playback_error = str(error)
                    try:
                        if outgoing:
                            self.send(outgoing, 'opacity', 1.0)
                        self.stop(incoming)
                    except OSError:
                        logging.exception('Could not restore the outgoing MapMap scene.')

    def hold(self, cue, timer):
        with self.lock:
            if self.timer is timer:
                try:
                    self.pause(cue)
                finally:
                    self.timer = None
