import contextlib
import io
import math
import sys
import types
import unittest
from unittest.mock import patch

from imu.raw_baseline import (
    format_gyro_validation,
    format_report,
    main,
    summarize,
    validate_gyro_offset,
)


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

    def test_gyro_offset_is_checked_on_separate_samples(self):
        baseline = summarize([
            ((0, 0, 1), (1, 2, 3)),
            ((0, 0, 1), (3, 4, 5)),
        ], 1.0)
        verification = summarize([
            ((0, 0, 1), (2.0, 2.5, 4.0)),
            ((0, 0, 1), (2.2, 3.1, 4.2)),
        ], 1.0)
        result = validate_gyro_offset(baseline, verification)
        self.assertEqual(result["offset_dps"], (2, 3, 4))
        for actual, expected in zip(
            result["verification_corrected_mean_dps"], (0.1, -0.2, 0.1)
        ):
            self.assertAlmostEqual(actual, expected)
        self.assertEqual(
            result["verification_corrected_std_dps"],
            verification["gyro_std_dps"],
        )
        self.assertIn("not saved", format_gyro_validation(result))

    def test_verify_mode_collects_two_distinct_windows(self):
        first = [((0, 0, 1), (1, 2, 3)), ((0, 0, 1), (3, 4, 5))]
        second = [((0, 0, 1), (2, 3, 4)), ((0, 0, 1), (2.2, 3, 4))]
        fake_module = types.SimpleNamespace(
            IMU=lambda: types.SimpleNamespace(accel_gyro=object())
        )
        output = io.StringIO()
        with (
            patch.dict(sys.modules, {"sunfounder_imu": fake_module}),
            patch("imu.raw_baseline.collect", side_effect=[(first, 1), (second, 1)]) as reader,
            patch("imu.raw_baseline.time.sleep") as pause,
            contextlib.redirect_stdout(output),
        ):
            self.assertEqual(main(["--seconds", "1", "--verify-gyro"]), 0)
        self.assertEqual(reader.call_count, 2)
        pause.assert_called_once_with(2.0)
        self.assertIn("Second-window corrected gyro mean", output.getvalue())


if __name__ == "__main__":
    unittest.main()
