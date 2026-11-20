import json
from pathlib import Path
import tempfile
from threading import Event
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from books_to_life.runtime.mapmap_application import MapMapApplication


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
