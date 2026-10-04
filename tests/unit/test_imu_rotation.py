import math
import unittest

from imu.rotation_test import (
    estimate_stationary_offset,
    format_report,
    integrate_rotation,
)


class ImuRotationTests(unittest.TestCase):
    def test_estimates_offset_from_stationary_samples(self):
        still = [(0.0, (1.0, 2.0, 3.0)), (1.0, (3.0, 4.0, 5.0))]
        self.assertEqual(estimate_stationary_offset(still), (2.0, 3.0, 4.0))

    def test_integrates_corrected_rate_using_real_intervals(self):
        turning = [
            (0.0, (1.0, 2.0, 10.0)),
            (0.25, (1.0, 2.0, 110.0)),
            (1.0, (1.0, 2.0, 110.0)),
        ]
        result = integrate_rotation(turning, (1.0, 2.0, 10.0))
        self.assertEqual(result["samples"], 3)
        self.assertAlmostEqual(result["span_seconds"], 1.0)
        self.assertAlmostEqual(result["median_interval_ms"], 500.0)
        self.assertAlmostEqual(result["max_interval_ms"], 750.0)
        self.assertEqual(result["angle_degrees"][:2], (0.0, 0.0))
        self.assertAlmostEqual(result["angle_degrees"][2], 87.5)
        self.assertIn("not compass heading", format_report((1, 2, 10), result))

    def test_rejects_bad_timestamps_and_readings(self):
        with self.assertRaises(ValueError):
            estimate_stationary_offset([(0.0, (0, 0, 0))])
        with self.assertRaises(ValueError):
            integrate_rotation([(0.0, (0, 0, 0)), (0.0, (0, 0, 1))], (0, 0, 0))
        with self.assertRaises(ValueError):
            integrate_rotation(
                [(0.0, (0, 0, 0)), (1.0, (math.nan, 0, 1))], (0, 0, 0)
            )
        with self.assertRaises(ValueError):
            integrate_rotation(
                [(0.0, (0, 0, 0)), (1.0, (0, 0, 1))], (0, 0)
            )


if __name__ == "__main__":
    unittest.main()
