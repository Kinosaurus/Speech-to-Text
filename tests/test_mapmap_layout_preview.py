from copy import deepcopy
import json
from pathlib import Path
import struct
import tempfile
from threading import Lock
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from books_to_life.cli.operator_panel import Sessions
from books_to_life.runtime.mapmap_cues import MapMapCue, output_vertices
from books_to_life.runtime.mapmap_story import StoryProject


class MapMapLayoutPreviewTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.project = Path(directory.name) / 'master.mmp'
        layers = []
        for index in range(3):
            corners = [[index * 100, 0], [(index + 1) * 100, 0],
                       [index * 100, 100], [(index + 1) * 100, 100]]
            mesh = {'className': 'Mesh', 'nRows': '2', 'nColumns': '2', 'vertices': corners}
            layers.append({'id': index + 1, 'name': f'Wall {index}', 'className': 'TextureLayer',
                           'sourceId': 1, 'source': deepcopy(mesh), 'destination': deepcopy(mesh)})
        scene_layers = [dict(deepcopy(layer), id=layer['id'] + 3, sourceId=2) for layer in layers]
        data = {'sources': [{'id': 1, 'className': 'Image', 'name': 'Wall calibration'},
                            {'id': 2, 'className': 'Image', 'name': 'Scene'}],
                'layers': layers + scene_layers}
        self.project.write_text(json.dumps(data), encoding='utf-8')
        self.original = self.project.read_bytes()
        self.cue = MapMapCue.__new__(MapMapCue)
        self.cue.project = self.project
        self.cue.port = 12346
        self.cue.lock = Lock()
        self.cue.output_layers = output_vertices(data)
        self.cue.output_preview = None
        self.cue.story_layers = None
        self.cue.story_project = None

    def fit(self):
        with patch('books_to_life.runtime.mapmap_cues.socket.socket') as channel:
            self.cue.set_output_layout((1920, 1080), pid=7)
        return channel.return_value.__enter__.return_value.sendto.call_args_list

    def test_editor_fit_matches_sent_vertices_and_keeps_saved_geometry(self):
        packets = self.fit()
        result = self.cue.wall_layout(pid=7)
        corners = result['preview_corners']
        self.assertGreater(max(point[0] for wall in corners for point in wall), 1280)
        for call in packets:
            layer, vertex, x, y = struct.unpack('>iiff', call.args[0][-16:])
            if layer <= 3:
                self.assertAlmostEqual(corners[layer - 1][vertex][0], x, places=3)
                self.assertAlmostEqual(corners[layer - 1][vertex][1], y, places=3)
        self.assertEqual(result['walls'][0]['corners'][0], [0, 0])
        self.assertEqual(self.project.read_bytes(), self.original)

    def test_manual_preview_replaces_fitted_snapshot(self):
        self.fit()
        fitted = self.cue.wall_layout(pid=7)
        moved = [[[x + 1, y] for x, y in wall] for wall in fitted['preview_corners']]
        with patch('books_to_life.runtime.mapmap_cues.socket.socket'):
            self.cue.preview_wall_layout(fitted['revision'], moved, pid=7)
        self.assertEqual(self.cue.wall_layout(pid=7)['preview_corners'], moved)
        self.assertEqual(self.project.read_bytes(), self.original)

    def test_restore_original_restores_editor_snapshot(self):
        self.fit()
        with patch('books_to_life.runtime.mapmap_cues.socket.socket'):
            self.cue.set_output_layout(pid=7)
        result = self.cue.wall_layout(pid=7)
        self.assertEqual(result['preview_corners'], [wall['corners'] for wall in result['walls']])

    def test_managed_fit_uses_one_confirmed_batch_instead_of_corner_packets(self):
        self.cue.story_project = Mock()
        with patch('books_to_life.runtime.mapmap_cues.socket.socket') as channel:
            self.cue.set_output_layout((1920, 1080), pid=7)
        channel.assert_not_called()
        self.cue.story_project.apply_layout.assert_called_once()
        args, kwargs = self.cue.story_project.apply_layout.call_args
        self.assertEqual(args[1], 7)
        self.assertEqual(kwargs, {'persist': False})
        self.assertEqual(dict(args[0]), self.cue.output_preview['vertices'])

    def test_repeated_fit_sends_identical_whole_wall_coordinates(self):
        self.cue.story_project = Mock()
        self.cue.set_output_layout((1920, 1080), pid=7)
        self.cue.set_output_layout((1920, 1080), pid=7)
        first, second = self.cue.story_project.apply_layout.call_args_list
        self.assertEqual(dict(first.args[0]), dict(second.args[0]))
        self.assertEqual(self.project.read_bytes(), self.original)

    def test_failed_fit_does_not_report_an_unconfirmed_preview(self):
        self.cue.story_project = Mock()
        self.cue.story_project.apply_layout.side_effect = ValueError('No matching acknowledgement')
        with self.assertRaisesRegex(ValueError, 'acknowledgement'):
            self.cue.set_output_layout((1920, 1080), pid=7)
        self.assertIsNone(self.cue.output_preview)

    def test_preview_is_ignored_for_another_process_or_changed_master(self):
        self.fit()
        self.assertNotIn('preview_corners', self.cue.wall_layout(pid=8))
        self.assertNotIn('preview_corners', self.cue.wall_layout())
        self.project.write_bytes(self.original + b'\n')
        self.assertNotIn('preview_corners', self.cue.wall_layout(pid=7))

    def test_story_reload_clears_temporary_geometry(self):
        self.fit()
        self.cue.story_key = ('same-project', 7)
        self.cue.set_story_scope(('same-project', 7), {}, {1, 2, 3})
        self.assertNotIn('preview_corners', self.cue.wall_layout(pid=7))

    def test_wall_endpoint_returns_actual_output_size_without_sending_changes(self):
        sessions = Sessions({}, {'parakeet-nemo': 9097})
        sessions.scene_directory = self.project.parent
        sessions.cue = Mock(port=12346)
        sessions.cue.wall_layout.return_value = {'walls': []}
        with patch('books_to_life.cli.operator_panel.check_mapmap_listener', return_value={'state': 'ready', 'pid': 7}), \
                patch('books_to_life.cli.operator_panel.detect_output_size', return_value=(1920, 1080)):
            result = sessions.wall_layout()
        self.assertEqual(result['output_size'], (1920, 1080))
        sessions.cue.wall_layout.assert_called_once_with(pid=7)
        sessions.cue.set_output_layout.assert_not_called()

    def test_live_save_updates_all_master_meshes_without_stopping_current_scene(self):
        self.cue.story_project = SimpleNamespace(path=self.project.parent / 'runtime.mmp')
        self.cue.active = object()
        active = self.cue.active
        self.cue.cancel_hold = Mock()
        self.cue.cancel_transition = Mock()
        before = self.cue.wall_layout()
        moved = [[[x + 5, y + 10] for x, y in wall['corners']] for wall in before['walls']]
        with patch('books_to_life.runtime.mapmap_cues.ensure_mapmap_closed') as guard, \
                patch('books_to_life.runtime.mapmap_scenes.ensure_mapmap_closed') as file_guard:
            result = self.cue.save_wall_layout(before['revision'], moved, live=True)
        guard.assert_not_called()
        file_guard.assert_not_called()
        self.cue.cancel_hold.assert_not_called()
        self.cue.cancel_transition.assert_not_called()
        self.assertIs(self.cue.active, active)
        self.assertNotEqual(result['revision'], before['revision'])
        saved = json.loads(self.project.read_text())
        original = json.loads(self.original)
        self.assertEqual(saved['sources'], original['sources'])
        for index, layer in enumerate(saved['layers']):
            self.assertEqual(layer['destination']['vertices'], moved[index % 3])
            self.assertEqual(layer['source'], original['layers'][index]['source'])

    def test_live_save_refuses_the_master_as_runtime(self):
        self.cue.story_project = SimpleNamespace(path=self.project)
        layout = self.cue.wall_layout()
        with self.assertRaisesRegex(ValueError, 'separate selected-story'):
            self.cue.save_wall_layout(layout['revision'], [wall['corners'] for wall in layout['walls']], live=True)
        self.assertEqual(self.project.read_bytes(), self.original)

    def save_session(self):
        sessions = Sessions({}, {'parakeet-nemo': 9097})
        sessions.scene_directory = self.project.parent
        sessions.story_project = Mock()
        sessions.story_passage = 'story'
        sessions.prepare_story = Mock()
        sessions.cue = Mock(port=12346, output_layers=((1, ((1, 2),)),))
        sessions.cue.save_wall_layout.return_value = {'revision': 'new-master', 'walls': [], 'updated': 1, 'skipped': []}
        return sessions

    def test_live_save_waits_for_native_apply_without_reloading_story(self):
        sessions = self.save_session()
        with patch('books_to_life.cli.operator_panel.check_mapmap_listener', return_value={'state': 'ready', 'pid': 7}):
            result = sessions.wall_layout('save', {'revision': 'old-master', 'corners': []})
        self.assertTrue(result['live_applied'])
        sessions.story_project.require_live_layout.assert_called_once_with(7)
        sessions.story_project.apply_layout.assert_called_once_with(sessions.cue.output_layers, 7, 'new-master')
        sessions.prepare_story.assert_not_called()

    def test_apply_failure_reports_committed_revision_for_retry(self):
        sessions = self.save_session()
        sessions.story_project.apply_layout.side_effect = ValueError('Connection lost')
        with patch('books_to_life.cli.operator_panel.check_mapmap_listener', return_value={'state': 'ready', 'pid': 7}):
            result = sessions.wall_layout('save', {'revision': 'old-master', 'corners': []})
        self.assertEqual(result['revision'], 'new-master')
        self.assertFalse(result['live_applied'])
        self.assertIn('Connection lost', result['apply_error'])
        sessions.prepare_story.assert_not_called()

    def test_old_renderer_is_detected_before_master_changes(self):
        sessions = self.save_session()
        sessions.story_project.require_live_layout.side_effect = ValueError('Renderer update required')
        with patch('books_to_life.cli.operator_panel.check_mapmap_listener', return_value={'state': 'ready', 'pid': 7}):
            with self.assertRaisesRegex(ValueError, 'Renderer update'):
                sessions.wall_layout('save', {'revision': 'old-master', 'corners': []})
        sessions.cue.save_wall_layout.assert_not_called()

    def test_layout_acknowledgement_verifies_the_applied_coordinates(self):
        story = StoryProject(self.project.parent / 'live', self.project, 24567)
        story.path.parent.mkdir()
        story.path.write_text(json.dumps({'readingPodRevision': 'story', 'layers': [{'id': 1}]}))
        story.status_path.write_text(json.dumps({'pid': 7, 'revision': 'story', 'layoutUpdates': True}))

        def reply(packet, address):
            request = json.loads(story.path.with_suffix('.mmp.layout-request').read_text())
            story.path.with_suffix('.mmp.layout-status').write_text(json.dumps({
                'ticket': request['ticket'], 'pid': 7, 'error': '', 'layers': request['layers']}))

        with patch('books_to_life.runtime.mapmap_story.socket.socket') as channel:
            channel.return_value.__enter__.return_value.sendto.side_effect = reply
            story.apply_layout(((1, ((5, 6), (7, 8))),), 7, 'master')
        request = json.loads(story.path.with_suffix('.mmp.layout-request').read_text())
        self.assertEqual(request['masterRevision'], 'master')
        self.assertEqual(request['layers'][0]['vertices'], [[5, 6], [7, 8]])


if __name__ == '__main__':
    unittest.main()
