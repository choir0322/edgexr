# Postpone type evaluation so optional drivers/libraries stay optional.
from __future__ import annotations

# Express hardware-independent behavior as executable checks.
import unittest

# Reuse camera.capture_baseline helpers rather than duplicating their behavior here.
from camera.capture_baseline import frame_timestamps, summarize


class CameraBaselineTests(unittest.TestCase):
    def test_extracts_only_frame_timestamps(self) -> None:
        """Verify extracts only frame timestamps.

        Args:
            None.

        Returns:
            None: unittest assertions fail if the expected contract is violated.
        """
        # Prepare or exercise '\n'.join with the controlled test inputs.
        log = "\n".join(
            [
                "[Parsed_showinfo_0 @ 0x1] config in time_base: 1/1000000",
                "[Parsed_showinfo_0 @ 0x1] n:   0 pts: 1000000 pts_time:1.000000 fmt:yuvj422p",
                "[null @ 0x2] Application provided invalid dts",
                "[Parsed_showinfo_0 @ 0x1] n:   1 pts: 1008333 pts_time:1.008333 fmt:yuvj422p",
            ]
        )
        # Check the expected Equal relationship for this case.
        self.assertEqual(frame_timestamps(log), [1.0, 1.008333])

    def test_reports_rate_spacing_and_timestamp_anomalies(self) -> None:
        """Verify reports rate spacing and timestamp anomalies.

        Args:
            None.

        Returns:
            None: unittest assertions fail if the expected contract is violated.
        """
        # Prepare or exercise summarize with the controlled test inputs.
        result = summarize([1.0, 1.01, 1.02, 1.02, 1.05, 1.04], 0.1)
        # Check the expected Equal relationship for this case.
        self.assertEqual(result["frames"], 6)
        # Check the expected AlmostEqual relationship for this case.
        self.assertAlmostEqual(result["wall_fps"], 60)
        # Check the expected AlmostEqual relationship for this case.
        self.assertAlmostEqual(result["median_interval_ms"], 10)
        # Check the expected AlmostEqual relationship for this case.
        self.assertAlmostEqual(result["p95_interval_ms"], 30)
        # Check the expected Equal relationship for this case.
        self.assertEqual(result["equal_timestamps"], 1)
        # Check the expected Equal relationship for this case.
        self.assertEqual(result["backward_timestamps"], 1)

    def test_short_capture_has_no_interval_estimate(self) -> None:
        """Verify short capture has no interval estimate.

        Args:
            None.

        Returns:
            None: unittest assertions fail if the expected contract is violated.
        """
        # Prepare or exercise summarize with the controlled test inputs.
        result = summarize([1.0], 0.5)
        # Check the expected IsNone relationship for this case.
        self.assertIsNone(result["timestamp_fps"])
        # Check the expected IsNone relationship for this case.
        self.assertIsNone(result["median_interval_ms"])


# Run the command only when executed directly, not when imported by tests or another module.
if __name__ == "__main__":
    # Call unittest.main for this step; its contract describes the result or side effect.
    unittest.main()
