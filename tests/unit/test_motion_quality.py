"""Hardware-free checks for the four-trial motion-quality report."""

from __future__ import annotations

import unittest

from recording.motion_quality import summarize


def row(time: float, dx: str = "", dy: str = "", gyro: str = "") -> dict[str, str]:
    """Make one representative visual_motion CSV row for a unit test.

    Args:
        time (float): Seconds after recording cue.
        dx (str): Optional horizontal displacement in pixels.
        dy (str): Optional vertical displacement in pixels.
        gyro (str): Optional corrected Y gyro rate in degrees per second.

    Returns:
        dict[str, str]: Minimal row consumed by summarize.
    """
    return dict(host_after_cue_s=str(time), dx_pixels=dx, dy_pixels=dy, gy_dps=gyro)


class MotionQualityTests(unittest.TestCase):
    def test_rejections_are_not_zero_displacement(self) -> None:
        """Rejected frame pairs reduce coverage but never lower shift statistics."""
        result = summarize(
            [row(0.1, "2", "0", "1"), row(0.2), row(1.1, "4", "0")], "fast_turn"
        )
        self.assertEqual(result["total_pairs"], 3)
        self.assertEqual(result["visual_pairs"], 2)
        self.assertEqual(result["gyro_covered_pairs"], 1)
        self.assertEqual(result["paired_pairs"], 1)
        self.assertAlmostEqual(result["median_shift_pixels"], 3)
        self.assertEqual(result["noticeable_shift_pairs"], 2)
        self.assertEqual(len(result["per_second"]), 2)

    def test_all_rejected_clip_remains_reportable(self) -> None:
        """A quality failure must still yield a report with null, not zero, metrics."""
        result = summarize([row(0.1, gyro="0"), row(0.2)], "still")
        self.assertEqual(result["visual_coverage"], 0)
        self.assertIsNone(result["median_shift_pixels"])
        self.assertIsNone(result["noticeable_shift_fraction_of_visual"])

    def test_invalid_rows_are_rejected(self) -> None:
        """An incomplete or nonfinite shift cannot silently enter the report."""
        for bad in [row(0, "2", ""), row(0, "nan", "0"), row(-1)]:
            with self.assertRaises(ValueError):
                summarize([bad], "moving_person")
