import json
from pathlib import Path
import tempfile
from threading import Event
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from books_to_life.cli.operator_panel import ROOT, Sessions, initialize_mapmap_project, load_passages
from books_to_life.runtime.mapmap_application import MapMapApplication
from books_to_life.runtime.mapmap_cues import MapMapCue


class BundledMapMapTests(unittest.TestCase):
    def test_clean_project_uses_packaged_media_and_cue_assignments(self):
        bundle = ROOT / 'pod/mapmap'
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            project = Path(directory) / 'local state' / 'Reading Pod.mmp'
            initialize_mapmap_project(bundle / 'Reading Pod.mmp', project)
            data = json.loads(project.read_text(encoding='utf-8'))
            for source in data['sources']:
                path = Path(source['uri'])
                self.assertFalse(path.is_absolute())
                self.assertTrue((project.parent / path).is_file())
            cue = MapMapCue(None, 12346, project)
            sessions = Sessions(load_passages(), {}, cue, assignment_defaults=bundle / 'assignments.json')
            self.assertEqual(cue.silver_seed, '2')
            self.assertTrue(cue.cues['2'].has_audio)
            media_by_source = {source['id']: Path(source['uri']).name for source in data['sources']}
            self.assertEqual(
                {key: media_by_source[value.source] for key, value in sessions.mapmap_cues('sample').items()},
                {'seed_found': 'silver-seed-at-the-gate.mp4',
                 'grass_grows': 'ribbon-of-grass.mp4',
                 'clouds_arrive': 'clouds-over-golden-hills.mp4',
                 'flower_opens': 'blue-flower-reveal.mp4'},
            )
            self.assertEqual(len(sessions.mapmap_cues('night_tiger')), 8)
            self.assertEqual(sessions.fade_ms, 250)

            data['local_edit'] = True
            project.write_text(json.dumps(data), encoding='utf-8')
            initialize_mapmap_project(bundle / 'Reading Pod.mmp', project)
            self.assertTrue(json.loads(project.read_text(encoding='utf-8'))['local_edit'])


class MapMapApplicationTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        self.launcher = root / 'Start Reading Pod.ps1'
        self.launcher.touch()
        self.project = SimpleNamespace(path=root / 'Selected Story.mmp', status_path=root / 'story.status')
        self.project.path.write_text(json.dumps({'readingPodRevision': 'chosen-story'}), encoding='utf-8')
        self.project.status_path.write_text(json.dumps({'pid': 123, 'revision': 'chosen-story'}), encoding='utf-8')
        self.ready = {'state': 'ready', 'pid': 123, 'detail': 'Listener found'}
        self.offline = {'state': 'error', 'detail': 'No listener'}

    def application(self, probe):
        application = MapMapApplication(self.launcher, self.project, 12346, probe)
        application.state['managed'] = True
        return application

    def finish(self, application):
        application.worker.join(timeout=3)
        self.assertFalse(application.worker.is_alive())
        return application.snapshot(refresh=False)

    def test_open_reuses_running_mapmap_without_another_launch(self):
        app = self.application(Mock(return_value=self.ready))
        with patch('books_to_life.runtime.mapmap_application.subprocess.run') as launch:
            app.open()
            self.assertEqual(self.finish(app)['pid'], 123)
        launch.assert_not_called()

    def test_open_passes_project_and_port_then_waits_for_acknowledgement(self):
        app = self.application(Mock(side_effect=[self.offline, self.ready, self.ready]))
        with patch('books_to_life.runtime.mapmap_application.subprocess.run', return_value=Mock(returncode=0)) as launch, \
                patch.object(app, '_project_loaded', side_effect=[False, True]), \
                patch('books_to_life.runtime.mapmap_application.sleep'):
            app.open()
            state = self.finish(app)
        self.assertEqual(state['state'], 'ready')
        self.assertFalse(state['busy'])
        command = launch.call_args.args[0]
        self.assertEqual(command[command.index('-ProjectPath') + 1], str(self.project.path))
        self.assertEqual(command[command.index('-OscPort') + 1], '12346')

    def test_project_acknowledgement_must_match_pid_and_revision(self):
        app = self.application(Mock())
        self.assertTrue(app._project_loaded(123))
        self.assertFalse(app._project_loaded(456))
        self.project.status_path.write_text(json.dumps({'pid': 123, 'revision': 'other-story'}), encoding='utf-8')
        self.assertFalse(app._project_loaded(123))

    def test_duplicate_clicks_cannot_launch_concurrently(self):
        entered, release = Event(), Event()

        def probe(port):
            entered.set()
            release.wait(2)
            return self.ready

        app = self.application(probe)
        app.open()
        try:
            self.assertTrue(entered.wait(1))
            with self.assertRaises(ValueError):
                app.open()
        finally:
            release.set()
            self.finish(app)

    def test_launcher_error_is_visible_and_clears_busy(self):
        app = self.application(Mock(return_value=self.offline))
        with patch('books_to_life.runtime.mapmap_application.subprocess.run',
                   return_value=Mock(returncode=1, stderr='Save and close MapMap first.')):
            app.open()
            state = self.finish(app)
        self.assertEqual(state['state'], 'error')
        self.assertIn('Save and close MapMap first.', state['detail'])
        self.assertFalse(state['busy'])

    def test_unrelated_port_owner_prevents_launch(self):
        app = self.application(Mock(return_value={'state': 'error', 'reason': 'port_in_use',
                                                  'detail': 'Another process owns the port.'}))
        with patch('books_to_life.runtime.mapmap_application.subprocess.run') as launch:
            app.open()
            self.assertEqual(self.finish(app)['state'], 'error')
        launch.assert_not_called()


if __name__ == '__main__':
    unittest.main()
