import unittest

from recording.analyze_capture import timing, integrate, mean_axes


class CaptureAnalysisTests(unittest.TestCase):
    def test_timing_preserves_startup_gap_and_nearest_rank_percentile(self):
        result = timing([0, .15, .18, .21])
        self.assertAlmostEqual(result["max_gap_ms"], 150)
        self.assertAlmostEqual(result["median_gap_ms"], 30)
        self.assertAlmostEqual(result["p95_gap_ms"], 150)
        self.assertAlmostEqual(result["rate_hz"], 3/.21)
        for times in ([0], [0, 0], [1, 0], [0, float("nan")]):
            with self.assertRaises(ValueError):
                timing(times)

    def test_irregular_turn_return_cancels_with_independent_bias(self):
        rows = [dict(host_read_midpoint_s=t, gx_dps=2, gy_dps=y+3, gz_dps=4)
                for t,y in [(0,0), (1,10), (3,0), (5,-10), (6,0)]]
        path = integrate(rows, [2,3,4])
        self.assertEqual(path[-1][1:], [0,0,0])
        self.assertEqual(max(r[2] for r in path), 15)

    def test_mean_does_not_normalize_gyro(self):
        rows = [dict(gx_dps=-4, gy_dps=15, gz_dps=-3),
                dict(gx_dps=-6, gy_dps=17, gz_dps=-1)]
        self.assertEqual(mean_axes(rows), [-5,16,-2])
        with self.assertRaises(ValueError):
            mean_axes(rows[:1])
