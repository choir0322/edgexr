# Postpone type evaluation so optional drivers/libraries stay optional.
from __future__ import annotations

# Express hardware-independent behavior as executable checks.
import unittest

# Reuse recording.analyze_capture helpers rather than duplicating their behavior here.
from recording.analyze_capture import timing, integrate, mean_axes


class CaptureAnalysisTests(unittest.TestCase):
    def test_timing_preserves_startup_gap_and_nearest_rank_percentile(self) -> None:
        """Verify timing preserves startup gap and nearest rank percentile.

        Args:
            None.

        Returns:
            None: unittest assertions fail if the expected contract is violated.
        """
        # Prepare or exercise timing with the controlled test inputs.
        result = timing([0, 0.15, 0.18, 0.21])
        # Check the expected AlmostEqual relationship for this case.
        self.assertAlmostEqual(result["max_gap_ms"], 150)
        # Check the expected AlmostEqual relationship for this case.
        self.assertAlmostEqual(result["median_gap_ms"], 30)
        # Check the expected AlmostEqual relationship for this case.
        self.assertAlmostEqual(result["p95_gap_ms"], 150)
        # Check the expected AlmostEqual relationship for this case.
        self.assertAlmostEqual(result["rate_hz"], 3 / 0.21)
        # Exercise each fixture or edge case independently.
        for times in ([0], [0, 0], [1, 0], [0, float("nan")]):
            # Require this invalid case to fail with the expected exception.
            with self.assertRaises(ValueError):
                # Call timing for this step; its contract describes the result or side effect.
                timing(times)

    def test_irregular_turn_return_cancels_with_independent_bias(self) -> None:
        """Verify irregular turn return cancels with independent bias.

        Args:
            None.

        Returns:
            None: unittest assertions fail if the expected contract is violated.
        """
        # Set up rows for this independent test scenario.
        rows = [
            dict(host_read_midpoint_s=t, gx_dps=2, gy_dps=y + 3, gz_dps=4)
            for t, y in [(0, 0), (1, 10), (3, 0), (5, -10), (6, 0)]
        ]
        # Prepare or exercise integrate with the controlled test inputs.
        path = integrate(rows, [2, 3, 4])
        # Check the expected Equal relationship for this case.
        self.assertEqual(path[-1][1:], [0, 0, 0])
        # Check the expected Equal relationship for this case.
        self.assertEqual(max(r[2] for r in path), 15)

    def test_mean_does_not_normalize_gyro(self) -> None:
        """Verify mean does not normalize gyro.

        Args:
            None.

        Returns:
            None: unittest assertions fail if the expected contract is violated.
        """
        # Set up rows for this independent test scenario.
        rows = [
            dict(gx_dps=-4, gy_dps=15, gz_dps=-3),
            dict(gx_dps=-6, gy_dps=17, gz_dps=-1),
        ]
        # Check the expected Equal relationship for this case.
        self.assertEqual(mean_axes(rows), [-5, 16, -2])
        # Require this invalid case to fail with the expected exception.
        with self.assertRaises(ValueError):
            # Call mean_axes for this step; its contract describes the result or side effect.
            mean_axes(rows[:1])
