from pathlib import Path
import signal
import tempfile
from threading import Event
import unittest
from unittest.mock import Mock, patch

from books_to_life.cli.manage_nemo_server import manage, server_processes
from books_to_life.cli.operator_panel import Sessions
from books_to_life.runtime.recognition_server import RecognitionServer


class RecognitionServerTests(unittest.TestCase):
    def test_nemotron_request_launches_its_checkpoint_and_reports_selected_backend(self):
        probe = Mock(side_effect=[{'state':'error','detail':'Wrong model'}, {'state':'ready','detail':'Nemotron 160 ms'}])
        server = RecognitionServer(self.root,9097,probe,model=self.model,nemotron_model=self.root/'nemotron.nemo')
        server.state['managed'] = True
        with patch('books_to_life.runtime.recognition_server.subprocess.run',return_value=Mock(returncode=0)) as launch:
            server.request('start',backend='nemotron')
            state = self.finish(server)
        command = launch.call_args.args[0]
        self.assertEqual(command[command.index('--backend')+1],'nemotron')
        self.assertIn('nemotron.nemo',command[command.index('--model-path')+1])
        self.assertEqual((state['backend'],state['state']),('nemotron','ready'))

    def test_start_switches_existing_managed_backend_before_loading_nemotron(self):
        with patch('books_to_life.cli.manage_nemo_server.server_processes',side_effect=[[123],[],[],[],[]]), \
                patch('books_to_life.cli.manage_nemo_server.port_in_use',return_value=False), \
                patch('books_to_life.cli.manage_nemo_server.os.kill') as stop, \
                patch('books_to_life.cli.manage_nemo_server.subprocess.Popen',return_value=Mock(pid=456)) as launch:
            manage('start',9097,self.model,self.root/'nemo.log',backend='nemotron')
        stop.assert_called_once_with(123,signal.SIGTERM)
        command = launch.call_args.args[0]
        self.assertEqual(command[command.index('--backend')+1],'nemotron')
        self.assertEqual(command[command.index('--chunk-ms')+1],'160')

    def test_nemotron_readiness_reuses_active_session_without_connecting(self):
        sessions = Sessions({}, {'parakeet-nemo':9097,'nemotron':9097})
        self.assertEqual(sessions.recognition.backend, 'nemotron')
        sessions.process = Mock()
        sessions.process.poll.return_value = None
        sessions.state['settings'] = {'model':'nemotron'}
        with patch('books_to_life.cli.operator_panel.check_nemo') as probe:
            self.assertEqual(sessions.probe_recognition()['state'],'ready')
        probe.assert_not_called()

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.model = self.root / 'model.nemo'
        self.model.touch()

    def server(self, probe):
        server = RecognitionServer(self.root, 9097, probe, model=self.model)
        server.state['managed'] = True
        return server

    def finish(self, server):
        server.worker.join(timeout=3)
        self.assertFalse(server.worker.is_alive())
        return server.snapshot(refresh=False)

    def test_start_reuses_ready_server_without_launching(self):
        server = self.server(Mock(return_value={'state': 'ready', 'detail': 'SERVER_READY'}))
        with patch('books_to_life.runtime.recognition_server.subprocess.run') as launch:
            server.request('start')
            self.assertEqual(self.finish(server)['state'], 'ready')
        launch.assert_not_called()

    def test_restart_finishes_reader_then_waits_for_ready(self):
        order = []
        probe = Mock(side_effect=[{'state': 'error', 'detail': 'Loading'},
                                  {'state': 'ready', 'detail': 'SERVER_READY'}])
        server = self.server(probe)

        def finish_reading():
            order.append('end reading')

        def launch(*args, **kwargs):
            order.append('restart server')
            return Mock(returncode=0)

        with patch('books_to_life.runtime.recognition_server.subprocess.run', side_effect=launch) as command, \
                patch('books_to_life.runtime.recognition_server.sleep'):
            server.request('restart', finish_reading)
            state = self.finish(server)
        self.assertEqual(order, ['end reading', 'restart server'])
        self.assertEqual(probe.call_count, 2)
        self.assertEqual(state['state'], 'ready')
        self.assertFalse(state['busy'])
        self.assertIn('books_to_life.cli.manage_nemo_server', command.call_args.args[0])

    def test_duplicate_request_is_rejected_until_operation_finishes(self):
        entered, release = Event(), Event()

        def probe():
            entered.set()
            release.wait(2)
            return {'state': 'ready', 'detail': 'SERVER_READY'}

        server = self.server(probe)
        server.request('start')
        try:
            self.assertTrue(entered.wait(1))
            self.assertTrue(server.snapshot(refresh=False)['busy'])
            with self.assertRaises(ValueError):
                server.request('restart')
        finally:
            release.set()
            self.finish(server)

    def test_failed_wsl_launch_shows_error_and_allows_retry(self):
        server = self.server(Mock(return_value={'state': 'error', 'detail': 'Offline'}))
        with patch('books_to_life.runtime.recognition_server.subprocess.run',
                   return_value=Mock(returncode=1, stderr='WSL environment is missing')):
            server.request('start')
            state = self.finish(server)
        self.assertEqual(state['state'], 'error')
        self.assertIn('WSL environment is missing', state['detail'])
        self.assertFalse(state['busy'])

    def test_start_refuses_an_unrelated_port_owner(self):
        with patch('books_to_life.cli.manage_nemo_server.server_processes', return_value=[]), \
                patch('books_to_life.cli.manage_nemo_server.port_in_use', return_value=True), \
                patch('books_to_life.cli.manage_nemo_server.subprocess.Popen') as launch:
            with self.assertRaisesRegex(ValueError, 'another process'):
                manage('restart', 9097, self.model, self.root / 'nemo.log')
        launch.assert_not_called()

    def test_process_identification_respects_explicit_port_forms(self):
        entry = Mock()
        entry.name = '123'
        entry.stat.return_value.st_uid = 1000
        for options, expected in [([], [123]), (['--port', '9098'], []), (['--port=9098'], [])]:
            with self.subTest(options=options):
                args = ['python', '-m', 'books_to_life.cli.run_nemo_server', *options]
                entry.joinpath.return_value.read_bytes.return_value = ('\0'.join(args) + '\0').encode()
                with patch('books_to_life.cli.manage_nemo_server.Path') as path, \
                        patch('books_to_life.cli.manage_nemo_server.os.getuid', return_value=1000, create=True):
                    path.return_value.iterdir.return_value = [entry]
                    self.assertEqual(server_processes(9097), expected)

    def test_restart_targets_identified_nemo_process_only(self):
        with patch('books_to_life.cli.manage_nemo_server.server_processes', side_effect=[[123], [], [], []]), \
                patch('books_to_life.cli.manage_nemo_server.port_in_use', return_value=False), \
                patch('books_to_life.cli.manage_nemo_server.os.kill') as stop, \
                patch('books_to_life.cli.manage_nemo_server.subprocess.Popen', return_value=Mock(pid=456)) as launch:
            result = manage('restart', 9097, self.model, self.root / 'nemo.log')
        stop.assert_called_once_with(123, signal.SIGTERM)
        self.assertEqual(result['pid'], 456)
        self.assertTrue(launch.call_args.kwargs['start_new_session'])
        self.assertIn(str(self.model), launch.call_args.args[0])

    def test_buffer_overrides_are_preserved_in_launch_command(self):
        with patch('books_to_life.cli.manage_nemo_server.server_processes', return_value=[]), \
                patch('books_to_life.cli.manage_nemo_server.port_in_use', return_value=False), \
                patch('books_to_life.cli.manage_nemo_server.subprocess.Popen',return_value=Mock(pid=456)) as launch:
            manage('start',9097,self.model,self.root/'nemo.log',160,320)
        command=launch.call_args.args[0]
        self.assertEqual(command[command.index('--chunk-ms')+1],'160')
        self.assertEqual(command[command.index('--right-ms')+1],'320')

    def test_invalid_buffers_do_not_stop_the_existing_server(self):
        with patch('books_to_life.cli.manage_nemo_server.os.kill') as stop:
            with self.assertRaises(ValueError):manage('restart',9097,self.model,self.root/'nemo.log',123,560)
        stop.assert_not_called()

    def test_restart_ends_active_reader_before_server_restart(self):
        sessions = Sessions({}, {'parakeet-nemo': 9097})
        reader = Mock()
        sessions.process = reader

        def request(action, before_restart):
            self.assertEqual(action, 'restart')
            before_restart()
            reader.stdin.close.assert_called_once()
            reader.wait.assert_called_once_with(timeout=75)
            return {'state': 'restarting'}

        with patch.object(sessions.recognition, 'request', side_effect=request):
            self.assertEqual(sessions.recognition_action('restart')['state'], 'restarting')
        self.assertEqual(sessions.state['phase'], 'ending')

    def test_health_check_reuses_active_reading_session_without_probe(self):
        sessions = Sessions({}, {'parakeet-nemo': 9097})
        sessions.recognition.backend = 'parakeet-nemo'
        sessions.process = Mock()
        sessions.process.poll.return_value = None
        sessions.state['settings'] = {'model': 'parakeet-nemo'}
        with patch('books_to_life.cli.operator_panel.check_nemo') as probe:
            self.assertEqual(sessions.probe_recognition()['state'], 'ready')
        probe.assert_not_called()


if __name__ == '__main__':
    unittest.main()
