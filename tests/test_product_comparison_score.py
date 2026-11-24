import unittest

import numpy as np

from benchmarks.product_comparison.score import (
    anchor_interval, audible_offset, clock, frame_time, template_matches,
)


class ProductComparisonScoreTests(unittest.TestCase):
    def test_native_frame_interpolation_accounts_for_delivery_gap(self):
        evidence = (np.array([0, 48000, 96000]), np.array([10., 11., 12.3]))
        self.assertAlmostEqual(frame_time(72000, evidence), 11.65)
        with self.assertRaises(ValueError):
            frame_time(100000, evidence)

    def test_repeated_native_timestamp_does_not_create_extra_frames(self):
        events = [dict(kind='source_clock', frame=48000, nano=11000000000),
                  dict(kind='source_clock', frame=48000, nano=11000000000),
                  dict(kind='output_clock', frame=999, nano=1),
                  dict(kind='source_clock', frame=96000, nano=12000000000)]
        frames, seconds = clock(events, 'source_clock')
        np.testing.assert_array_equal(frames, [48000, 96000])
        np.testing.assert_array_equal(seconds, [11, 12])

    def test_anchor_requires_unique_reference_occurrence(self):
        words = [dict(text='the', start=0., end=.1), dict(text='moon', start=.1, end=.4)]
        self.assertEqual(anchor_interval(words, 'The moon!'), (0., .4))
        with self.assertRaises(ValueError):
            anchor_interval(words + words, 'the moon')

    def test_asset_detector_finds_scaled_signal_and_rejects_unrelated_noise(self):
        rng = np.random.default_rng(412)
        template = rng.normal(0, .1, 8000)
        output = rng.normal(0, .001, 64000)
        output[24000:32000] += template * .4
        matches = template_matches(output, template)
        self.assertEqual(matches[0][0], 24000)
        self.assertGreater(matches[0][1], .99)
        self.assertEqual(template_matches(rng.normal(0,.01,64000), template), [])

    def test_audible_onset_uses_signal_not_file_start(self):
        signal = np.concatenate([np.zeros(1600), np.ones(3200) * .1])
        self.assertAlmostEqual(audible_offset(signal), .1)
        with self.assertRaises(ValueError):
            audible_offset(np.zeros(3200))


if __name__ == '__main__':
    unittest.main()
