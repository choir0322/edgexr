# Postpone type evaluation so optional drivers/libraries stay optional.
from __future__ import annotations

# Validate finite numbers and perform scalar numerical calculations.
import math

# Express hardware-independent behavior as executable checks.
import unittest

# Reuse imu.rotation_test helpers rather than duplicating their behavior here.
from imu.rotation_test import (
    estimate_stationary_offset,
    format_report,
    integrate_rotation,
)


class ImuRotationTests(unittest.TestCase):
    def test_estimates_offset_from_stationary_samples(self) -> None:
        """Verify estimates offset from stationary samples.

        Args:
            None.

        Returns:
            None: unittest assertions fail if the expected contract is violated.
        """
        # Set up still for this independent test scenario.
        still = [(0.0, (1.0, 2.0, 3.0)), (1.0, (3.0, 4.0, 5.0))]
        # Check the expected Equal relationship for this case.
        self.assertEqual(estimate_stationary_offset(still), (2.0, 3.0, 4.0))

    def test_integrates_corrected_rate_using_real_intervals(self) -> None:
        """Verify integrates corrected rate using real intervals.

        Args:
            None.

        Returns:
            None: unittest assertions fail if the expected contract is violated.
        """
        # Set up turning for this independent test scenario.
        turning = [
            (0.0, (1.0, 2.0, 10.0)),
            (0.25, (1.0, 2.0, 110.0)),
            (1.0, (1.0, 2.0, 110.0)),
        ]
        # Prepare or exercise integrate_rotation with the controlled test inputs.
        result = integrate_rotation(turning, (1.0, 2.0, 10.0))
        # Check the expected Equal relationship for this case.
        self.assertEqual(result["samples"], 3)
        # Check the expected AlmostEqual relationship for this case.
        self.assertAlmostEqual(result["span_seconds"], 1.0)
        # Check the expected AlmostEqual relationship for this case.
        self.assertAlmostEqual(result["median_interval_ms"], 500.0)
        # Check the expected AlmostEqual relationship for this case.
        self.assertAlmostEqual(result["max_interval_ms"], 750.0)
        # Check the expected Equal relationship for this case.
        self.assertEqual(result["angle_degrees"][:2], (0.0, 0.0))
        # Check the expected AlmostEqual relationship for this case.
        self.assertAlmostEqual(result["angle_degrees"][2], 87.5)
        # Check the expected In relationship for this case.
        self.assertIn("not compass heading", format_report((1, 2, 10), result))

    def test_rejects_bad_timestamps_and_readings(self) -> None:
        """Verify rejects bad timestamps and readings.

        Args:
            None.

        Returns:
            None: unittest assertions fail if the expected contract is violated.
        """
        # Require this invalid case to fail with the expected exception.
        with self.assertRaises(ValueError):
            # Call estimate_stationary_offset for this step; its contract describes the result
            # or side effect.
            estimate_stationary_offset([(0.0, (0, 0, 0))])
        # Require this invalid case to fail with the expected exception.
        with self.assertRaises(ValueError):
            # Call integrate_rotation for this step; its contract describes the result or side
            # effect.
            integrate_rotation([(0.0, (0, 0, 0)), (0.0, (0, 0, 1))], (0, 0, 0))
        # Require this invalid case to fail with the expected exception.
        with self.assertRaises(ValueError):
            # Call integrate_rotation for this step; its contract describes the result or side
            # effect.
            integrate_rotation([(0.0, (0, 0, 0)), (1.0, (math.nan, 0, 1))], (0, 0, 0))
        # Require this invalid case to fail with the expected exception.
        with self.assertRaises(ValueError):
            # Call integrate_rotation for this step; its contract describes the result or side
            # effect.
            integrate_rotation([(0.0, (0, 0, 0)), (1.0, (0, 0, 1))], (0, 0))


# Run the command only when executed directly, not when imported by tests or another module.
if __name__ == "__main__":
    # Call unittest.main for this step; its contract describes the result or side effect.
    unittest.main()
