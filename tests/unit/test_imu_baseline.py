# Postpone type evaluation so optional drivers/libraries stay optional.
from __future__ import annotations

# Capture or manage test-side effects within a scoped context.
import contextlib

# Simulate binary/text streams entirely in memory.
import io

# Validate finite numbers and perform scalar numerical calculations.
import math

# Report failures on stderr and handle command-line exit behavior.
import sys

# Build lightweight fake runtime objects for unit tests.
import types

# Express hardware-independent behavior as executable checks.
import unittest

# Replace external effects with controlled test fixtures.
from unittest.mock import patch

# Reuse imu.raw_baseline helpers rather than duplicating their behavior here.
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
        # Set up samples for this independent test scenario.
        samples = [
            ((0.0, 0.0, 1.0), (1.0, 2.0, 3.0)),
            ((0.0, 0.0, -1.0), (3.0, 4.0, 5.0)),
        ]
        # Prepare or exercise summarize with the controlled test inputs.
        result = summarize(samples, 2.0)
        # Check the expected Equal relationship for this case.
        self.assertEqual(result["samples"], 2)
        # Check the expected Equal relationship for this case.
        self.assertEqual(result["sample_rate_hz"], 1.0)
        # Check the expected Equal relationship for this case.
        self.assertEqual(result["accel_mean_g"], (0.0, 0.0, 0.0))
        # Check the expected Equal relationship for this case.
        self.assertEqual(result["accel_std_g"], (0.0, 0.0, 1.0))
        # Check the expected Equal relationship for this case.
        self.assertEqual(result["accel_magnitude_mean_g"], 1.0)
        # Check the expected Equal relationship for this case.
        self.assertEqual(result["gyro_offset_estimate_dps"], (2.0, 3.0, 4.0))
        # Check the expected Equal relationship for this case.
        self.assertEqual(result["gyro_std_dps"], (1.0, 1.0, 1.0))
        # Check the expected In relationship for this case.
        self.assertIn("Read-only", format_report(result))

    def test_rejects_invalid_samples(self) -> None:
        """Verify rejects invalid samples.

        Args:
            None.

        Returns:
            None: unittest assertions fail if the expected contract is violated.
        """
        # Set up good for this independent test scenario.
        good = ((0.0, 0.0, 1.0), (0.0, 0.0, 0.0))
        # Require this invalid case to fail with the expected exception.
        with self.assertRaises(ValueError):
            # Call summarize for this step; its contract describes the result or side effect.
            summarize([good], 1.0)
        # Require this invalid case to fail with the expected exception.
        with self.assertRaises(ValueError):
            # Call summarize for this step; its contract describes the result or side effect.
            summarize([good, good], 0.0)
        # Require this invalid case to fail with the expected exception.
        with self.assertRaises(ValueError):
            # Call summarize for this step; its contract describes the result or side effect.
            summarize([good, ((math.nan, 0, 1), (0, 0, 0))], 1.0)
        # Require this invalid case to fail with the expected exception.
        with self.assertRaises(ValueError):
            # Call summarize for this step; its contract describes the result or side effect.
            summarize([good, ((0, 1), (0, 0, 0))], 1.0)

    def test_gyro_offset_is_checked_on_separate_samples(self) -> None:
        """Verify gyro offset is checked on separate samples.

        Args:
            None.

        Returns:
            None: unittest assertions fail if the expected contract is violated.
        """
        # Prepare or exercise summarize with the controlled test inputs.
        baseline = summarize(
            [
                ((0, 0, 1), (1, 2, 3)),
                ((0, 0, 1), (3, 4, 5)),
            ],
            1.0,
        )
        # Prepare or exercise summarize with the controlled test inputs.
        verification = summarize(
            [
                ((0, 0, 1), (2.0, 2.5, 4.0)),
                ((0, 0, 1), (2.2, 3.1, 4.2)),
            ],
            1.0,
        )
        # Prepare or exercise validate_gyro_offset with the controlled test inputs.
        result = validate_gyro_offset(baseline, verification)
        # Check the expected Equal relationship for this case.
        self.assertEqual(result["offset_dps"], (2, 3, 4))
        # Exercise each fixture or edge case independently.
        for actual, expected in zip(
            result["verification_corrected_mean_dps"], (0.1, -0.2, 0.1)
        ):
            # Check the expected AlmostEqual relationship for this case.
            self.assertAlmostEqual(actual, expected)
        # Check the expected Equal relationship for this case.
        self.assertEqual(
            result["verification_corrected_std_dps"],
            verification["gyro_std_dps"],
        )
        # Check the expected In relationship for this case.
        self.assertIn("not saved", format_gyro_validation(result))

    def test_verify_mode_collects_two_distinct_windows(self) -> None:
        """Verify verify mode collects two distinct windows.

        Args:
            None.

        Returns:
            None: unittest assertions fail if the expected contract is violated.
        """
        # Set up first for this independent test scenario.
        first = [((0, 0, 1), (1, 2, 3)), ((0, 0, 1), (3, 4, 5))]
        # Set up second for this independent test scenario.
        second = [((0, 0, 1), (2, 3, 4)), ((0, 0, 1), (2.2, 3, 4))]

        def make_fake_imu() -> types.SimpleNamespace:
            """Supply a fake IMU wrapper so the CLI test never opens real hardware.

            Args:
                None; values are captured from the enclosing function.

            Returns:
                types.SimpleNamespace: The callback result described above.
            """
            # Evaluate the original callback expression only when the caller invokes it.
            return types.SimpleNamespace(accel_gyro=object())

        # Prepare or exercise types.SimpleNamespace with the controlled test inputs.
        fake_module = types.SimpleNamespace(IMU=make_fake_imu)
        # Prepare or exercise io.StringIO with the controlled test inputs.
        output = io.StringIO()
        # Replace external effects only within this controlled test scope.
        with (
            patch.dict(sys.modules, {"sunfounder_imu": fake_module}),
            patch(
                "imu.raw_baseline.collect", side_effect=[(first, 1), (second, 1)]
            ) as reader,
            patch("imu.raw_baseline.time.sleep") as pause,
            contextlib.redirect_stdout(output),
        ):
            # Check the expected Equal relationship for this case.
            self.assertEqual(main(["--seconds", "1", "--verify-gyro"]), 0)
        # Check the expected Equal relationship for this case.
        self.assertEqual(reader.call_count, 2)
        # Check the expected _called_once_with relationship for this case.
        pause.assert_called_once_with(2.0)
        # Check the expected In relationship for this case.
        self.assertIn("Second-window corrected gyro mean", output.getvalue())


# Run the command only when executed directly, not when imported by tests or another module.
if __name__ == "__main__":
    # Call unittest.main for this step; its contract describes the result or side effect.
    unittest.main()
