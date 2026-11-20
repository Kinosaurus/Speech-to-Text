"""Prepare and activate the selected book's generated MapMap project."""

from hashlib import sha256
import json
from pathlib import Path
import socket
import struct
from tempfile import NamedTemporaryFile
from time import monotonic, sleep
from uuid import uuid4

from books_to_life.runtime.mapmap_scenes import calibration_meshes


def osc_string(value):
    encoded = value.encode('ascii') + b'\0'
    return encoded + b'\0' * (-len(encoded) % 4)


class StoryProject:
    def __init__(self, directory, master, port):
        self.path = directory / 'Reading Pod - Selected Story.mmp'
        self.status_path = self.path.with_suffix('.mmp.status')
        self.master = master
        self.port = port

    def saved_passage(self):
        try:
            return json.loads(self.path.read_text(encoding='utf-8-sig')).get('readingPodStory')
        except (OSError, ValueError, AttributeError):
            return None

    def prepare(self, passage, cues):
        data = json.loads(self.master.read_text(encoding='utf-8-sig'))
        calibration = calibration_meshes(data)[0]['sourceId']
        sources = {calibration, *(cue.source for cue in cues.values())}
        data['sources'] = [source for source in data['sources'] if source['id'] in sources]
        data['layers'] = [layer for layer in data['layers'] if layer.get('sourceId') in sources]
        for position, layer in enumerate(data['layers'], 1):
            layer['depth'] = str(position)
        for source in data['sources']:
            if source.get('uri'):
                source['uri'] = (self.master.parent / source['uri']).resolve().as_posix()
            if source['className'] == 'Video':
                source['volume'] = '0'
                source['readingPodDeferred'] = True

        data['readingPodStory'] = passage
        revision = sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()
        data['readingPodRevision'] = revision
        payload = json.dumps(data, indent=2, ensure_ascii=False) + '\n'
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.is_file() or self.path.read_text(encoding='utf-8-sig') != payload:
            with NamedTemporaryFile(mode='w', encoding='utf-8', dir=self.path.parent, delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(payload)
            try:
                temporary.replace(self.path)
            finally:
                temporary.unlink(missing_ok=True)
        return revision, {layer['id'] for layer in data['layers']}

    def load(self, revision, pid):
        self.status_path.unlink(missing_ok=True)
        packet = osc_string('/mapmap/reading-pod/load') + osc_string(',s') + osc_string(revision)
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as channel:
            channel.sendto(packet, ('127.0.0.1', self.port))
        deadline = monotonic() + 15
        while monotonic() < deadline:
            try:
                reply = json.loads(self.status_path.read_text(encoding='utf-8'))
            except (OSError, ValueError):
                reply = None
            if isinstance(reply, dict) and reply.get('revision') == revision and reply.get('pid') == pid:
                if reply.get('error'):
                    raise ValueError(reply['error'])
                return
            sleep(.05)
        raise ValueError('MapMap did not confirm the story load. Start it with the Reading Pod launcher and retry.')

    def prepare_video(self, source):
        ticket = uuid4().hex
        body = osc_string(',is') + struct.pack('>i', source) + osc_string(ticket)
        self.video_command('prepare', body)
        return ticket

    def require_live_layout(self, pid, *, preview=False):
        try:
            status = json.loads(self.status_path.read_text(encoding='utf-8'))
            project = json.loads(self.path.read_text(encoding='utf-8-sig'))
        except (OSError, ValueError) as error:
            raise ValueError('Select the story in MapMap before saving its live layout.') from error
        if not isinstance(status, dict) or not isinstance(project, dict):
            raise ValueError('The selected-story status is invalid. Reselect the story and try again.')
        if (not project.get('readingPodRevision') or status.get('pid') != pid or status.get('error')
                or status.get('revision') != project.get('readingPodRevision')):
            raise ValueError('Reselect the story so MapMap can confirm the live layout connection.')
        if status.get('layoutUpdates') is not True:
            raise ValueError('This MapMap build needs the live-layout update. Close and reopen MapMap once using Open MapMap to install it.')
        if preview and status.get('layoutPreview') is not True:
            raise ValueError('MapMap needs the complete-wall Fit update. Close and reopen it once using Open MapMap to install it.')

    def apply_layout(self, vertices, pid, master_revision, *, persist=True):
        self.require_live_layout(pid, preview=not persist)
        project = json.loads(self.path.read_text(encoding='utf-8-sig'))
        try:
            layer_ids = {layer['id'] for layer in project['layers']}
        except (KeyError, TypeError) as error:
            raise ValueError('The selected-story file changed. Reselect the story and retry Save and apply.') from error
        ticket = uuid4().hex
        body = {'ticket': ticket, 'storyRevision': project['readingPodRevision'], 'persist': persist,
                'masterRevision': master_revision,
                'layers': [{'id': layer, 'vertices': [list(point) for point in points]}
                           for layer, points in vertices if layer in layer_ids]}
        if not body['layers']:
            raise ValueError('The selected story has no matching wall layers.')
        request_path = self.path.with_suffix('.mmp.layout-request')
        with NamedTemporaryFile(mode='w', encoding='utf-8', dir=self.path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(body, stream)
        try:
            temporary.replace(request_path)
        finally:
            temporary.unlink(missing_ok=True)
        packet = osc_string('/mapmap/reading-pod/layout') + osc_string(',s') + osc_string(ticket)
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as channel:
            channel.sendto(packet, ('127.0.0.1', self.port))
        status_path = self.path.with_suffix('.mmp.layout-status')
        deadline = monotonic() + 10
        while monotonic() < deadline:
            try:
                reply = json.loads(status_path.read_text(encoding='utf-8'))
            except (OSError, ValueError):
                reply = None
            if isinstance(reply, dict) and reply.get('ticket') == ticket and reply.get('pid') == pid:
                if reply.get('error'):
                    raise ValueError(reply['error'])
                try:
                    actual = {layer['id']: layer['vertices'] for layer in reply.get('layers', [])}
                except (KeyError, TypeError) as error:
                    raise ValueError('MapMap returned an invalid layout confirmation. Retry Save and apply.') from error
                expected = {layer['id']: layer['vertices'] for layer in body['layers']}
                if actual != expected:
                    raise ValueError('MapMap confirmed different wall coordinates. Retry Save and apply.')
                return
            sleep(.05)
        raise ValueError('MapMap did not acknowledge the live layout update. Check its connection and retry Save and apply.')

    def release_video(self, source):
        self.video_command('release', osc_string(',i') + struct.pack('>i', source))

    def video_command(self, command, body):
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as channel:
            channel.sendto(osc_string(f'/mapmap/reading-pod/{command}') + body, ('127.0.0.1', self.port))

    def video_ready(self, source, ticket):
        try:
            path = self.path.with_suffix(f'.mmp.video-{source}')
            reply = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            return None
        if isinstance(reply, dict) and reply.get('ticket') == ticket:
            return reply.get('ready')
        return None
