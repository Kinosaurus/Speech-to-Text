import hashlib
import json
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from benchmarks.nemo_latency_server import Socket,PROFILES
from books_to_life.runtime.nemo_defaults import microphone_arguments,MIC_PACKET_SAMPLES
from benchmarks.latency_human_replay import native_cue_replay
from unittest.mock import patch


class LatencyProtocolTests(unittest.TestCase):
    def test_replay_uses_native_audio_clock_instead_of_sender_backlog(self):
        segment={'start':0,'end':1.25,'text':'a seed','completed':False}
        event=dict(text='a seed',segments=[segment],delivered_audio_seconds=90,
                   wall_seconds=.5,final=False)
        with patch('benchmarks.latency_human_replay.TimelyEvidenceMatcher') as factory:
            factory.return_value.process.return_value.triggered=False
            native_cue_replay([event],{})
            self.assertEqual(factory.return_value.process.call_args.kwargs['segments'],[segment])
    def test_only_nemo_microphone_packets_change(self):
        self.assertEqual(microphone_arguments('parakeet-nemo'),['--audio_chunk',str(MIC_PACKET_SAMPLES)])
        for model in ['base.en','parakeet','moonshine']:
            self.assertEqual(microphone_arguments(model),[])
    def test_profiles_stay_within_model_trained_context_axes(self):
        for chunk,right in PROFILES.values():
            self.assertIn(chunk//80,[1,2,7,13])
            self.assertIn(right//80,[0,1,2,3,4,7,13])
    def test_acknowledgement_uses_actual_context_and_exact_hints(self):
        ws=Mock();session=SimpleNamespace(context=SimpleNamespace(chunk=2560,right=5120),
                                        phrases=['small seed'],boost=1.0)
        proxy=Socket(ws,{'hotwords':'small seed'},session,'balanced')
        proxy.send(json.dumps({'message':'SERVER_READY'}))
        ack=json.loads(ws.send.call_args.args[0])
        self.assertEqual((ack['chunk_ms'],ack['right_ms']),(160,320))
        self.assertEqual(ack['applied_hotwords_sha256'],hashlib.sha256(b'small seed').hexdigest())
    def test_wrong_applied_hints_cannot_be_acknowledged(self):
        ws=Mock();session=SimpleNamespace(phrases=['wrong'])
        with self.assertRaises(AssertionError):Socket(ws,{'hotwords':'small seed'},session,'fast').send(json.dumps({'message':'SERVER_READY'}))
        ws.send.assert_not_called()


if __name__=='__main__':unittest.main()
