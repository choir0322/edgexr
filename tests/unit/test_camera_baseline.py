import unittest

from camera.capture_baseline import frame_timestamps, summarize


class CameraBaselineTests(unittest.TestCase):
    def test_extracts_only_frame_timestamps(self):
        log = "\n".join([
            "[Parsed_showinfo_0 @ 0x1] config in time_base: 1/1000000",
            "[Parsed_showinfo_0 @ 0x1] n:   0 pts: 1000000 pts_time:1.000000 fmt:yuvj422p",
            "[null @ 0x2] Application provided invalid dts",
            "[Parsed_showinfo_0 @ 0x1] n:   1 pts: 1008333 pts_time:1.008333 fmt:yuvj422p",
        ])
        self.assertEqual(frame_timestamps(log), [1.0, 1.008333])

    def test_reports_rate_spacing_and_timestamp_anomalies(self):
        result = summarize([1.0, 1.01, 1.02, 1.02, 1.05, 1.04], 0.1)
        self.assertEqual(result["frames"], 6)
        self.assertAlmostEqual(result["wall_fps"], 60)
        self.assertAlmostEqual(result["median_interval_ms"], 10)
        self.assertAlmostEqual(result["p95_interval_ms"], 30)
        self.assertEqual(result["equal_timestamps"], 1)
        self.assertEqual(result["backward_timestamps"], 1)

    def test_short_capture_has_no_interval_estimate(self):
        result = summarize([1.0], 0.5)
        self.assertIsNone(result["timestamp_fps"])
        self.assertIsNone(result["median_interval_ms"])


if __name__ == "__main__":
    unittest.main()
