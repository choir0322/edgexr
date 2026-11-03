"""Hardware-free checks for the single-run remembered-direction diagnostic."""

import math
import unittest

from spatial.servo_orientation_demo import checkpoint_names, checkpoint_summary


def checkpoint(label: str, seconds: float, turn: float, epoch: float = 1) -> dict:
    """Build a fresh synthetic camera-Y rotation checkpoint.

    Args:
        label (str): Checkpoint stage name.
        seconds (float): HTTP observation midpoint.
        turn (float): Rotation about camera Y in degrees.
        epoch (float): Integration reference timestamp.
    Returns:
        dict: Minimal saved checkpoint with a unit quaternion.
    """
    half = math.radians(turn) / 2
    return {"label": label, "host_poll_midpoint_s": seconds,
            "orientation": {"status": "ready", "sample_age_ms": 10,
                "reference_monotonic_s": epoch,
                "quaternion_wxyz": [math.cos(half), 0, math.sin(half), 0]}}


class DirectionValidationTests(unittest.TestCase):
    def test_still_period_is_bounded_and_default_unchanged(self) -> None:
        """Require one extra checkpoint only for a finite positive still interval.

        Args: None.
        Returns: None; assertions enforce the protocol bounds.
        """
        self.assertEqual(checkpoint_names(0), ("before_pan", "after_pan", "after_tilt"))
        self.assertEqual(checkpoint_names(30), ("before_still", "before_pan", "after_pan", "after_tilt"))
        for bad in (-1, 61, math.nan, math.inf):
            with self.assertRaises(ValueError):
                checkpoint_names(bad)

    def test_differences_are_local_not_angles_from_startup(self) -> None:
        """Separate still drift, individual return changes and combined change.

        Args: None.
        Returns: None; assertions compare known synthetic angular differences.
        """
        rows = [checkpoint("before_still", 10, 10), checkpoint("before_pan", 40, 12),
                checkpoint("after_pan", 50, 15), checkpoint("after_tilt", 60, 16)]
        result = checkpoint_summary(rows)
        for item, expected in zip(result["comparisons"], (2, 3, 1, 4)):
            self.assertEqual(item["status"], "ready")
            self.assertAlmostEqual(item["pointing_separation_deg"], expected)
        self.assertIn("pending_image_review", result["validation"])
        self.assertEqual(checkpoint_summary([])["comparisons"], [])

    def test_unknown_stale_invalid_and_restarted_contexts_do_not_pass(self) -> None:
        """Invalid gyro context remains unknown rather than a zero-angle return.

        Args: None.
        Returns: None; assertions cover stale, invalid and different epochs.
        """
        for changes in ({"status": "unknown"}, {"sample_age_ms": 500},
                        {"quaternion_wxyz": [2, 0, 0, 0]},
                        {"reference_monotonic_s": 2}, {"sample_age_ms": None}):
            a = checkpoint("before_pan", 10, 0)
            b = checkpoint("after_pan", 20, 0)
            b["orientation"].update(changes)
            result = checkpoint_summary([a, b])["comparisons"][0]
            self.assertEqual(result["status"], "unknown")
            self.assertNotIn("pointing_separation_deg", result)
