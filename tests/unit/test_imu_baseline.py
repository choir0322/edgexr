from __future__ import annotations
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
    def test_summary_keeps_raw_axes_and_reports_stationary_offset(self) -> None:
        """Verify summary keeps raw axes and reports stationary offset.

        Args:
            None.

        Returns:
            None: unittest assertions fail if the expected contract is violated.
        """
        # Use opposite gravity vectors to distinguish mean acceleration from mean
        # magnitude; the known gyro spread also checks population standard deviation.
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

    def test_rejects_invalid_samples(self) -> None:
        """Verify rejects invalid samples.

        Args:
            None.

        Returns:
            None: unittest assertions fail if the expected contract is violated.
        """
        # Reject short windows, invalid duration and malformed/nonfinite sensor axes.
        good = ((0.0, 0.0, 1.0), (0.0, 0.0, 0.0))
        with self.assertRaises(ValueError):
            summarize([good], 1.0)
        with self.assertRaises(ValueError):
            summarize([good, good], 0.0)
        with self.assertRaises(ValueError):
            summarize([good, ((math.nan, 0, 1), (0, 0, 0))], 1.0)
        with self.assertRaises(ValueError):
            summarize([good, ((0, 1), (0, 0, 0))], 1.0)

    def test_gyro_offset_is_checked_on_separate_samples(self) -> None:
        """Verify gyro offset is checked on separate samples.

        Args:
            None.

        Returns:
            None: unittest assertions fail if the expected contract is violated.
        """
        # Build different baseline and verification samples so correction cannot
        # appear successful merely by subtracting a window from itself.
        baseline = summarize(
            [
                ((0, 0, 1), (1, 2, 3)),
                ((0, 0, 1), (3, 4, 5)),
            ],
            1.0,
        )
        verification = summarize(
            [
                ((0, 0, 1), (2.0, 2.5, 4.0)),
                ((0, 0, 1), (2.2, 3.1, 4.2)),
            ],
            1.0,
        )

        # Check independent residual means and unchanged spread, plus the no-save caveat.
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

    def test_verify_mode_collects_two_distinct_windows(self) -> None:
        """Verify verify mode collects two distinct windows.

        Args:
            None.

        Returns:
            None: unittest assertions fail if the expected contract is violated.
        """
        # Replace the sensor and acquisition with two deterministic windows; capture
        # terminal output without waiting for real hardware or the settling pause.
        first = [((0, 0, 1), (1, 2, 3)), ((0, 0, 1), (3, 4, 5))]
        second = [((0, 0, 1), (2, 3, 4)), ((0, 0, 1), (2.2, 3, 4))]

        def make_fake_imu() -> types.SimpleNamespace:
            """Supply a fake IMU wrapper so the CLI test never opens real hardware.

            Args:
                None; values are captured from the enclosing function.

            Returns:
                types.SimpleNamespace: The callback result described above.
            """
            return types.SimpleNamespace(accel_gyro=object())

        fake_module = types.SimpleNamespace(IMU=make_fake_imu)
        output = io.StringIO()
        with (
            patch.dict(sys.modules, {"sunfounder_imu": fake_module}),
            patch(
                "imu.raw_baseline.collect", side_effect=[(first, 1), (second, 1)]
            ) as reader,
            patch("imu.raw_baseline.time.sleep") as pause,
            contextlib.redirect_stdout(output),
        ):
            self.assertEqual(main(["--seconds", "1", "--verify-gyro"]), 0)

        # Verify two acquisitions and one settling pause, not two uses of one window.
        self.assertEqual(reader.call_count, 2)
        pause.assert_called_once_with(2.0)
        self.assertIn("Second-window corrected gyro mean", output.getvalue())


if __name__ == "__main__":
    unittest.main()
