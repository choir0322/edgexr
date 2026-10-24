"""Hardware-free checks for gyro-only relative IMU orientation."""

from __future__ import annotations

import math
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from spatial.relative_orientation import analyze, integrate_gyro, quaternion_product


class RelativeOrientationTests(unittest.TestCase):
    """Check rotation composition, cancellation and explicit gap rejection."""

    def test_quarter_turn_and_return_with_bias(self) -> None:
        """A time-weighted Y turn reaches 90 degrees then returns near identity.

        Args:
            None.

        Returns:
            None: Assertions fail if integration or bias subtraction changes.
        """
        bias = (10.0, -5.0, 2.0)
        rates = (0.0, 900.0, 0.0, -900.0, 0.0)
        samples = [(i * .1, (bias[0], bias[1] + rate, bias[2]))
                   for i, rate in enumerate(rates)]
        result = integrate_gyro(samples, bias)
        self.assertAlmostEqual(result["peak_angle_deg"], 90.0, places=8)
        self.assertAlmostEqual(result["peak_rotation_vector_deg"][1], 90.0, places=8)
        for value in result["final_rotation_vector_deg"]:
            self.assertAlmostEqual(value, 0.0, places=8)

    def test_quaternion_order_matters(self) -> None:
        """Successive X and Y turns do not commute as independent XYZ sums do.

        Args:
            None.

        Returns:
            None: Verifies the body-axis composition convention.
        """
        half = math.sqrt(.5)
        x = (half, half, 0.0, 0.0)
        y = (half, 0.0, half, 0.0)
        xy = quaternion_product(x, y)
        yx = quaternion_product(y, x)
        self.assertAlmostEqual(xy[3], .5)
        self.assertAlmostEqual(yx[3], -.5)

    def test_rejects_gap_and_invalid_readings(self) -> None:
        """Invalid timing must yield no apparently continuous orientation.

        Args:
            None.

        Returns:
            None: Verifies explicit failure for gaps and nonfinite rates.
        """
        with self.assertRaisesRegex(ValueError, "excessive"):
            integrate_gyro([(0, (0, 0, 0)), (.25, (0, 0, 0))], (0, 0, 0))
        with self.assertRaisesRegex(ValueError, "finite"):
            integrate_gyro([(0, (0, 0, 0)), (.1, (math.nan, 0, 0))], (0, 0, 0))

    def test_rejects_gap_between_still_window_and_motion(self) -> None:
        """Do not hide a dropped interval by splitting bias and motion samples.

        Args:
            None.

        Returns:
            None: Asserts the entire selected recording remains gap-checked.
        """
        with TemporaryDirectory() as directory:
            folder = Path(directory)
            stamps = (0, .05, .10, .15, .20, .25, 1.0, 1.05)
            metadata = {
                "status": "complete",
                "requested_seconds_after_first_frame": 2.0,
                "recording_cue_host_s": 0.0,
                "imu_samples": len(stamps),
                "requested_mode": "test",
            }
            (folder / "metadata.json").write_text(json.dumps(metadata))
            (folder / "imu.csv").write_text(
                "host_read_midpoint_s,gx_dps,gy_dps,gz_dps\n" +
                "".join(f"{stamp},0,0,0\n" for stamp in stamps)
            )
            with self.assertRaisesRegex(ValueError, "excessive"):
                analyze(folder, bias_seconds=.3)
