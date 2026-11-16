"""Playable overlays in a saved MapMap project and their local OSC transport."""

from dataclasses import dataclass
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

DEFAULT_FADE_MS = 450
VIDEO_SEEK_SECONDS = .18
VIDEO_SETTLE_SECONDS = .07
FADE_STEPS_PER_SECOND = 30


@dataclass(frozen=True)
class ProjectionCue:
    source: int
    title: str
    has_audio: bool = False
    hold_seconds: float | None = None
    layer_range: tuple[int, int] | None = None


class MapMapCue:
    def __init__(self, path, port, project=None):
        spec = importlib.util.spec_from_file_location('reading_pod_mapmap_bridge', path)
        bridge = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(bridge)
        self.port = port
        self.project = Path(project or getattr(bridge, 'VIDEO_PROJECT', path)).resolve()
        self.silver_seed = None
        if project is not None or (hasattr(bridge, 'VIDEO_PROJECT') and self.project.is_file()):
            self.cues = self.load_project(bridge)
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

    def load_project(self, bridge):
        data = json.loads(self.project.read_text(encoding='utf-8-sig'))
        mapped = {}
        # MapMap saves layers front to back. Earlier layers cover later ones.
        for index, layer in enumerate(data['layers']):
            if 'sourceId' in layer and str(layer.get('visible', True)).lower() == 'true':
                mapped.setdefault(layer['sourceId'], []).append(index)
        cues = {}
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
            elif (self.project == getattr(bridge, 'VIDEO_PROJECT', None)
                    and ident == bridge.GARDEN_SOURCE and media.name == bridge.VIDEO_FILE):
                self.silver_seed = str(ident)
                cue = ProjectionCue(ident, 'Silver Seed video and soundtrack', True, bridge.VIDEO_HOLD_SECONDS, layers)
            else:
                try:
                    with av.open(str(media)) as clip:
                        if not clip.streams.video:
                            continue
                        video = clip.streams.video[0]
                        duration = (float(video.duration * video.time_base) if video.duration and video.time_base
                                    else (clip.duration or 0) / av.time_base)
                        has_audio = bool(clip.streams.audio)
                except (OSError, av.FFmpegError):
                    continue
                if not math.isfinite(duration) or duration <= 0:
                    continue
                cue = ProjectionCue(ident, title, has_audio, max(.01, duration - .15), layers)
            cues[str(ident)] = cue
        return cues

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

    def reset(self):
        with self.lock:
            self.cancel_hold()
            self.cancel_transition()
            self.active = None
            for cue in self.cues.values():
                self.stop(cue)

    def start_video(self, cue):
        self.send(cue, 'volume', float(cue.has_audio))
        self.send(cue, 'play')
        timer = Timer(cue.hold_seconds, lambda: self.hold(cue, timer))
        timer.daemon = True
        self.timer = timer
        timer.start()

    def play(self, cue, fade_ms=DEFAULT_FADE_MS):
        with self.lock:
            abandoned = self.cancel_transition()
            self.cancel_hold()
            outgoing = self.active
            if abandoned is not None:
                # Restore a fully visible scene before discarding a partial transition.
                self.send(outgoing, 'opacity', 1.0)
                self.stop(abandoned)
            if outgoing is None or outgoing.source == cue.source:
                # Replaying the same source leaves its texture visible while it seeks.
                self.active = cue
                if cue.hold_seconds is not None:
                    self.send(cue, 'rewind')
                self.send(cue, 'opacity', 1.0)
                if cue.hold_seconds is not None:
                    self.start_video(cue)
                return
            if outgoing.hold_seconds is not None:
                self.pause(outgoing)
            self.send(cue, 'opacity', 0.0)
            if cue.hold_seconds is not None:
                self.send(cue, 'rewind')
            self.incoming = cue
            cancelled = self.transition = Event()
            Thread(target=self.crossfade, args=(outgoing, cue, fade_ms / 1000, cancelled), daemon=True).start()

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

    def crossfade(self, outgoing, incoming, seconds, cancelled):
        try:
            if incoming.hold_seconds is not None:
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
            old_layers, new_layers = outgoing.layer_range, incoming.layer_range
            if old_layers and new_layers and new_layers[1] < old_layers[0]:
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
                    self.stop(outgoing)
                    self.active = incoming
                    self.cancel_transition()
        except OSError:
            logging.exception('Could not send MapMap transition commands.')
            with self.lock:
                if self.transition is cancelled:
                    self.cancel_transition()
                    self.cancel_hold()
                    try:
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
