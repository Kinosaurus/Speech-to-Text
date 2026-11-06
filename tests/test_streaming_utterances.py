import unittest
import numpy as np
from books_to_life.runtime.streaming_utterances import SilenceBoundedSession


class Core:
    def __init__(self):
        self.audio = []
        self.closed = False
        self.finishes = 0
        self.hints = []

    def feed(self, audio):
        self.audio.extend(audio.tolist())
        return ['heard'] if np.any(audio) else []

    def finish(self):
        self.finishes += 1
        return 'heard' if any(self.audio) else ''

    def close(self): self.closed = True
    def set_hints(self, value): self.hints.append(value)


class UtteranceTests(unittest.TestCase):
    def make(self, right=4):
        cores = []
        def factory():
            core = Core();cores.append(core);return core
        return SilenceBoundedSession(factory,right),cores

    def test_packet_independent_boundaries_preserve_all_nonzero_audio(self):
        audio=np.array([1,2,0,0,3,0,0,0,0,0,0,4,5,0],dtype=np.float32)
        for size in (1,3,7,len(audio)):
            with self.subTest(size=size):
                session,cores=self.make()
                for i in range(0,len(audio),size):session.feed(audio[i:i+size])
                final=session.finish()
                self.assertEqual([c.audio for c in cores],[[1,2,0,0,3,0,0,0,0],[4,5,0]])
                self.assertEqual([s['start']*16000 for s in final],[0,11])
                self.assertEqual(final[-1]['end']*16000,len(audio))
                self.assertTrue(all(s['completed'] for s in final))
                self.assertTrue(all(c.closed and c.finishes==1 for c in cores))

    def test_soft_speech_and_noise_cannot_be_classified_as_silence(self):
        session,cores=self.make()
        audio=np.full(30,1e-12,dtype=np.float32)
        session.feed(audio);session.finish()
        self.assertEqual(len(cores),1)
        np.testing.assert_array_equal(cores[0].audio,audio)

    def test_finalization_and_cleanup_are_idempotent_and_preserve_hints(self):
        session,cores=self.make();session.set_hints('book')
        session.feed(np.array([1,0,0,0,0,0,2],dtype=np.float32))
        first=session.finish();self.assertEqual(first,session.finish())
        session.close();session.close()
        self.assertTrue(all(c.hints==['book'] for c in cores))
        self.assertTrue(all(c.finishes==1 for c in cores))
        with self.assertRaises(ValueError):session.feed(np.ones(1))

    def test_empty_and_all_quiet_stream_keep_original_clock(self):
        for count in (0,3,20):
            session,cores=self.make();session.feed(np.zeros(count))
            self.assertEqual(session.finish(),[dict(start=0,end=count/16000,text='',completed=True)])
