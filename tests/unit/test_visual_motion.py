# Postpone type evaluation so optional drivers/libraries stay optional.
from __future__ import annotations

# Express hardware-independent behavior as executable checks.
import unittest

# Keep failure handling alongside the operation so cleanup/status remains explicit.
try:
    # Perform typed array and numerical operations; no sensor access occurs on import.
    import numpy as np
# Handle this failure without losing the error or skipping the enclosing cleanup.
except ImportError:
    # Set up np for this independent test scenario.
    np = None

# Choose the next branch using np is not None.
if np is not None:
    # Reuse recording.visual_motion helpers rather than duplicating their behavior here.
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
        # Prepare or exercise np.random.default_rng(4).normal with the controlled test inputs.
        image = np.random.default_rng(4).normal(120, 30, (56, 80))
        # Exercise each fixture or edge case independently.
        for dx, dy in [(0, 0), (3, -2), (-4, 2)]:
            # Prepare or exercise patch_shift with the controlled test inputs.
            result = patch_shift(image, np.roll(image, (dy, dx), axis=(0, 1)))
            # Check the expected IsNotNone relationship for this case.
            self.assertIsNotNone(result)
            # Check the expected AlmostEqual relationship for this case.
            self.assertAlmostEqual(result[0], dx, delta=0.15)
            # Check the expected AlmostEqual relationship for this case.
            self.assertAlmostEqual(result[1], dy, delta=0.15)

    def test_flat_and_unrelated_patches_rejected(self) -> None:
        """Verify flat and unrelated patches rejected.

        Args:
            None.

        Returns:
            None: unittest assertions fail if the expected contract is violated.
        """
        # Check the expected IsNone relationship for this case.
        self.assertIsNone(patch_shift(np.zeros((56, 80)), np.zeros((56, 80))))
        # Prepare or exercise np.random.default_rng with the controlled test inputs.
        rng = np.random.default_rng(32)
        # Check the expected IsNone relationship for this case.
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
        # Prepare or exercise np.random.default_rng with the controlled test inputs.
        rng = np.random.default_rng(9)
        # Prepare or exercise rng.normal with the controlled test inputs.
        a = rng.normal(120, 30, (180, 320))
        # Prepare or exercise np.roll with the controlled test inputs.
        b = np.roll(a, (1, 3), axis=(0, 1))
        # Prepare or exercise rng.normal with the controlled test inputs.
        b[:61, :85] = rng.normal(120, 30, b[:61, :85].shape)
        # Prepare or exercise image_shift with the controlled test inputs.
        result = image_shift(a, b)
        # Check the expected IsNotNone relationship for this case.
        self.assertIsNotNone(result)
        # Check the expected AlmostEqual relationship for this case.
        self.assertAlmostEqual(result[0], 3, delta=0.2)
        # Check the expected AlmostEqual relationship for this case.
        self.assertAlmostEqual(result[1], 1, delta=0.2)

    def test_video_log_pairing_checks_count_and_pts(self) -> None:
        """Verify video log pairing checks count and pts.

        Args:
            None.

        Returns:
            None: unittest assertions fail if the expected contract is violated.
        """
        # Set up rows for this independent test scenario.
        rows = [
            dict(frame_index=i, camera_pts_s=t)
            for i, t in enumerate([0, 0.14802, 0.180026])
        ]
        # Check the expected Less relationship for this case.
        self.assertLess(validate_video_times([0, 0.148, 0.180], rows), 0.001)
        # Exercise each fixture or edge case independently.
        for times in ([0, 0.148], [0, 0.148, 0.28], [0, 0.148, 0.148]):
            # Require this invalid case to fail with the expected exception.
            with self.assertRaises(ValueError):
                # Call validate_video_times for this step; its contract describes the result or
                # side effect.
                validate_video_times(times, rows)
        # Set up rows[-1]['frame_index'] for this independent test scenario.
        rows[-1]["frame_index"] = 9
        # Require this invalid case to fail with the expected exception.
        with self.assertRaises(ValueError):
            # Call validate_video_times for this step; its contract describes the result or side
            # effect.
            validate_video_times([0, 0.148, 0.180], rows)

    def test_interpolation_never_extrapolates_or_crosses_large_gap(self) -> None:
        """Verify interpolation never extrapolates or crosses large gap.

        Args:
            None.

        Returns:
            None: unittest assertions fail if the expected contract is violated.
        """
        # Prepare or exercise np.array with the controlled test inputs.
        times = np.array([0, 0.05, 0.10, 0.4])
        # Prepare or exercise np.array with the controlled test inputs.
        values = np.array([[0, 0, 0], [2, 4, 6], [4, 8, 12], [6, 12, 18]])
        # Check the expected _allclose relationship for this case.
        np.testing.assert_allclose(gyro_at(0.025, times, values), [1, 2, 3])
        # Exercise each fixture or edge case independently.
        for t in [-0.1, 0.2, 0.5]:
            # Check the expected IsNone relationship for this case.
            self.assertIsNone(gyro_at(t, times, values))
