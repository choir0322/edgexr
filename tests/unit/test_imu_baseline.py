import math
import unittest

from imu.raw_baseline import format_report, summarize


class ImuBaselineTests(unittest.TestCase):
    def test_summary_keeps_raw_axes_and_reports_stationary_offset(self):
        samples = [
            ((0.0, 0.0, 1.0), (1.0, 2.0, 3.0)),
            ((0.0, 0.0, -1.0), (3.0, 4.0, 5.0)),
        ]
        result = summarize(samples, 2.0)
        self.assertEqual(result["samples"], 2)
        self.assertEqual(result["sample_rate_hz"], 1.0)
        self.assertEqual(result["accel_mean_g"], (0.0, 0.0, 0.0))
        self.assertEqual(result["accel_std_g"], (0.0, 0.0, 1.0))
        self.assertEqual(result["accel_magnitude_mean_g"], 1.0)
        self.assertEqual(result["gyro_offset_estimate_dps"], (2.0, 3.0, 4.0))
        self.assertEqual(result["gyro_std_dps"], (1.0, 1.0, 1.0))
        self.assertIn("Read-only", format_report(result))

    def test_rejects_invalid_samples(self):
        good = ((0.0, 0.0, 1.0), (0.0, 0.0, 0.0))
        with self.assertRaises(ValueError):
            summarize([good], 1.0)
        with self.assertRaises(ValueError):
            summarize([good, good], 0.0)
        with self.assertRaises(ValueError):
            summarize([good, ((math.nan, 0, 1), (0, 0, 0))], 1.0)
        with self.assertRaises(ValueError):
            summarize([good, ((0, 1), (0, 0, 0))], 1.0)


if __name__ == "__main__":
    unittest.main()
