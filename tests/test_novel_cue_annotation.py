from pathlib import Path
import tempfile
import unittest

import numpy as np

from benchmarks.product_comparison.annotate_novel import opening, ncc, shared_component_edge


class SyntheticCapture:
    def __init__(self, signal):
        self.signal=signal
        self.folder=Path('synthetic-unit-fixture')
    def bounds(self,start,end):
        return round(start*16000),round(end*16000)
    def seconds(self,sample):
        return sample/16000


class NovelCueAnnotationTests(unittest.TestCase):
    def captures(self,negative_has_response=False):
        rng=np.random.default_rng(9001)
        before=np.zeros(10*16000);after=before.copy();full=before.copy()
        chime=rng.normal(0,.05,16000)
        before[1600:17600]=chime
        after[1600:17600]=chime
        component=rng.normal(0,.05,19200)
        after[49600:68800]=component
        full[52800:72000]=component
        if negative_has_response:before[49600:68800]=component
        return tuple(SyntheticCapture(x) for x in (before,after,full))
    def test_startup_chime_is_excluded_from_speech_dependent_opening(self):
        with tempfile.TemporaryDirectory() as tmp:
            result=opening(*self.captures(),Path(tmp))
            self.assertEqual(result['status'],'causally_verified')
            self.assertAlmostEqual(result['estimated_calibration_onset_seconds'],3.1)
            self.assertEqual(result['negative_control_ncc'],0)
            self.assertGreater(result['calibration_match_ncc'],.99)
    def test_component_in_silent_control_is_not_claimed_as_a_speech_cue(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):opening(*self.captures(True),Path(tmp))
    def test_zero_control_does_not_create_a_match(self):
        _,score=ncc(np.zeros(32000),np.random.default_rng(1).normal(size=4000))
        self.assertEqual(score,0)
    def test_distinct_component_edge_is_localized_within_analysis_window(self):
        rng=np.random.default_rng(66);a=rng.normal(0,.001,80000);b=rng.normal(0,.001,80000)
        component=rng.normal(0,.05,16000);a[48000:64000]+=component;b[48000:64000]+=component
        edge,_=shared_component_edge(a,b,32000,64000,0)
        self.assertIsNotNone(edge)
        self.assertLessEqual(abs(edge/16000-3),.08)
    def test_continuing_common_background_is_not_a_new_component(self):
        x=np.random.default_rng(7).normal(0,.01,80000)
        edge,_=shared_component_edge(x,x.copy(),32000,64000,0)
        self.assertIsNone(edge)


if __name__=='__main__':unittest.main()
