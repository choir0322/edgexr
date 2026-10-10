from __future__ import annotations
import unittest

try:
    import numpy as np
except ImportError:
    np = None

if np is not None:
    from recording.visual_motion import (
        patch_shift,
        image_shift,
        validate_video_times,
        gyro_at,
    )


@unittest.skipIf(np is None, "Optional NumPy required for offline image-analysis tests")
class VisualMotionTests(unittest.TestCase):
    def test_known_shifts_have_correct_sign(self) -> None:
        """Verify known shifts have correct sign.

        Args:
            None.

        Returns:
            None: unittest assertions fail if the expected contract is violated.
        """
        # Roll reproducible texture by known signed offsets and check recovered motion
        # within subpixel tolerance; this avoids requiring a physical camera.
        image = np.random.default_rng(4).normal(120, 30, (56, 80))
        for dx, dy in [(0, 0), (3, -2), (-4, 2)]:
            result = patch_shift(image, np.roll(image, (dy, dx), axis=(0, 1)))
            self.assertIsNotNone(result)
            self.assertAlmostEqual(result[0], dx, delta=0.15)
            self.assertAlmostEqual(result[1], dy, delta=0.15)

    def test_flat_and_unrelated_patches_rejected(self) -> None:
        """Verify flat and unrelated patches rejected.

        Args:
            None.

        Returns:
            None: unittest assertions fail if the expected contract is violated.
        """
        self.assertIsNone(patch_shift(np.zeros((56, 80)), np.zeros((56, 80))))
        rng = np.random.default_rng(32)
        self.assertIsNone(
            patch_shift(rng.normal(120, 30, (56, 80)), rng.normal(120, 30, (56, 80)))
        )

    def test_patch_consensus_handles_local_outlier(self) -> None:
        """Verify patch consensus handles local outlier.

        Args:
            None.

        Returns:
            None: unittest assertions fail if the expected contract is violated.
        """
        # Corrupt one patch of an otherwise shifted image; the remaining patch
        # consensus should still recover the common displacement.
        rng = np.random.default_rng(9)
        a = rng.normal(120, 30, (180, 320))
        b = np.roll(a, (1, 3), axis=(0, 1))
        b[:61, :85] = rng.normal(120, 30, b[:61, :85].shape)
        result = image_shift(a, b)
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result[0], 3, delta=0.2)
        self.assertAlmostEqual(result[1], 1, delta=0.2)

    def test_video_log_pairing_checks_count_and_pts(self) -> None:
        """Verify video log pairing checks count and pts.

        Args:
            None.

        Returns:
            None: unittest assertions fail if the expected contract is violated.
        """
        # Allow container rounding but reject count/time/index mismatches before pairing.
        rows = [
            dict(frame_index=i, camera_pts_s=t)
            for i, t in enumerate([0, 0.14802, 0.180026])
        ]
        self.assertLess(validate_video_times([0, 0.148, 0.180], rows), 0.001)
        for times in ([0, 0.148], [0, 0.148, 0.28], [0, 0.148, 0.148]):
            with self.assertRaises(ValueError):
                validate_video_times(times, rows)
        rows[-1]["frame_index"] = 9
        with self.assertRaises(ValueError):
            validate_video_times([0, 0.148, 0.180], rows)

    def test_interpolation_never_extrapolates_or_crosses_large_gap(self) -> None:
        """Verify interpolation never extrapolates or crosses large gap.

        Args:
            None.

        Returns:
            None: unittest assertions fail if the expected contract is violated.
        """
        # Check interpolation inside a short gap and rejection outside coverage or
        # inside a long gap; missing sensor data must not become invented observations.
        times = np.array([0, 0.05, 0.10, 0.4])
        values = np.array([[0, 0, 0], [2, 4, 6], [4, 8, 12], [6, 12, 18]])
        np.testing.assert_allclose(gyro_at(0.025, times, values), [1, 2, 3])
        for t in [-0.1, 0.2, 0.5]:
            self.assertIsNone(gyro_at(t, times, values))
