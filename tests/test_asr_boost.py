from hashlib import sha256
import json
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from benchmarks.nemo_boost_server import HandshakeSocket, validate_boost
from benchmarks.sweep_nemo_boost import profile_name


class BoostProtocolTests(unittest.TestCase):
    def test_boost_bounds_are_not_silently_clamped(self):
        for level in (0, .5, 1, 2, 3, 5):
            self.assertEqual(validate_boost(level), level)
        for value in (True, -.1, 5.1, float('nan'), float('inf'), '2', None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_boost(value)

    def test_acknowledges_actual_session_boost_and_exact_text(self):
        socket = Mock()
        options = {'hotwords': 'tiny seed, old gate', 'uid': 'trial'}
        session = SimpleNamespace(phrases=['tiny seed', 'old gate'], boost=3)
        proxy = HandshakeSocket(socket, options, session)
        proxy.send(json.dumps({'message': 'SERVER_READY', 'uid': 'trial'}))
        ack = json.loads(socket.send.call_args.args[0])
        self.assertEqual(ack['benchmark_boost'], 3)
        self.assertEqual(ack['phrase_count'], 2)
        self.assertEqual(ack['applied_hotwords_sha256'], sha256(options['hotwords'].encode()).hexdigest())

    def test_ready_is_refused_if_actual_phrases_do_not_match(self):
        socket = Mock()
        proxy = HandshakeSocket(socket, {'hotwords': 'tiny seed'}, SimpleNamespace(phrases=[], boost=2))
        with self.assertRaises(ValueError):
            proxy.send(json.dumps({'message': 'SERVER_READY'}))
        socket.send.assert_not_called()

    def test_distinct_boost_levels_have_distinct_preserved_trial_names(self):
        profiles = [profile_name(value) for value in (0, .5, 1, 2, 3, 5)]
        self.assertEqual(len(profiles), len(set(profiles)))
        self.assertEqual(profile_name(.5), 'nemo-full-boost-0p5')
