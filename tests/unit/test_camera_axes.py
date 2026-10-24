"""Hardware-free checks for the provisional IMU-to-camera axis transform."""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from spatial.camera_axes import camera_components, fit_camera_axes, validate_recording


class CameraAxesTests(unittest.TestCase):
    """Verify signed axes, handedness and rejection of misleading sweeps."""

    def test_observed_up_and_right_define_camera_coordinates(self) -> None:
        """Independent tilt and pan sweeps map into positive camera X and Y.

        Args:
            None.

        Returns:
            None: Assertions fail if basis signs or orthogonality regress.
        """
        pan = ((1, 5, 0), (-2, -10, 0), (1, 5, 0))
        tilt = ((0, 0, 2), (0, 0, -4), (0, 0, 2))
        result = fit_camera_axes(pan, tilt, pan_first="right", tilt_first="up")
        basis = result["camera_axes_in_imu_xyz"]

        for actual, expected in zip(camera_components(pan[0], basis), (0, 5.0990195136, 0)):
            self.assertAlmostEqual(actual, expected, places=6)
        self.assertEqual(camera_components(tilt[0], basis), (2, 0, 0))
        self.assertEqual(camera_components(tilt[1], basis), (-4, 0, 0))
        self.assertAlmostEqual(result["raw_pan_tilt_axis_angle_deg"], 90)

    def test_physical_signs_change_the_camera_frame(self) -> None:
        """Opposite lens observations reverse X and Y without changing handedness.

        Args:
            None.

        Returns:
            None: Assertions fail if servo sign is mistaken for camera sign.
        """
        pan = ((0, 4, 0), (0, -8, 0), (0, 4, 0))
        tilt = ((0, 0, 1), (0, 0, -2), (0, 0, 1))
        result = fit_camera_axes(pan, tilt, pan_first="left", tilt_first="down")
        basis = result["camera_axes_in_imu_xyz"]
        self.assertEqual(basis, [[0, 0, -1], [0, -1, 0], [-1, 0, 0]])
        self.assertEqual(camera_components(tilt[0], basis), (-1, 0, 0))
        self.assertEqual(camera_components(pan[0], basis), (0, -4, 0))

    def test_weak_inconsistent_or_collinear_sweeps_fail(self) -> None:
        """A fit requires visible movement, consistent return and two axes.

        Args:
            None.

        Returns:
            None: Assertions fail if invalid movement fabricates a camera basis.
        """
        good_pan = ((0, 5, 0), (0, -10, 0), (0, 5, 0))
        good_tilt = ((0, 0, 1), (0, 0, -2), (0, 0, 1))
        for tilt in (((0, 0, .1), (0, 0, -.2), (0, 0, .1)),
                     ((0, 0, 1), (0, 0, -2), (0, 0, -1)),
                     ((0, 1, 0), (0, -2, 0), (0, 1, 0))):
            with self.subTest(tilt=tilt), self.assertRaises(ValueError):
                fit_camera_axes(good_pan, tilt, pan_first="right", tilt_first="up")
        self.assertEqual(len(fit_camera_axes(good_pan, good_tilt,
                         pan_first="right", tilt_first="up")["camera_axes_in_imu_xyz"]), 3)

    def test_separate_combined_capture_checks_both_axes(self) -> None:
        """A single held-out capture may contain sequential pan and tilt legs.

        Args:
            None.

        Returns:
            None: Assertions fail if other-axis commands confuse the leg parser.
        """
        with TemporaryDirectory() as directory:
            folder = Path(directory)
            commands = []
            targets = (-1, -2, -1, 0, 1, 2, 1, 0)
            for axis, start in (("pan", 2.5), ("tilt", 5.5)):
                commands.extend({"axis": axis, "angle_deg": angle,
                                 "host_command_ns": round((start + index * .2) * 1e9)}
                                for index, angle in enumerate(targets))
            (folder / "servo_commands.json").write_text(
                json.dumps({"issued_commands": commands}))

            # Synthetic still bias plus sign-reversing angular rates; no real
            # hardware, images or servo travel is needed for this parser check.
            rows = []
            for index in range(201):
                stamp = round(index * .05, 4)
                pan = 5 if 2.5 <= stamp < 2.9 or 3.7 <= stamp <= 4.05 else (
                    -5 if 2.9 <= stamp < 3.7 else 0)
                tilt = 5 if 5.5 <= stamp < 5.9 or 6.7 <= stamp <= 7.05 else (
                    -5 if 5.9 <= stamp < 6.7 else 0)
                rows.append(f"{stamp},1,{2 + pan},{3 + tilt}\n")
            (folder / "imu.csv").write_text(
                "host_read_midpoint_s,gx_dps,gy_dps,gz_dps\n" + "".join(rows))
            (folder / "metadata.json").write_text(json.dumps({
                "status": "complete", "requested_seconds_after_first_frame": 10,
                "recording_cue_host_s": 0, "origin_monotonic_ns": 0,
                "imu_samples": len(rows), "requested_mode": "synthetic",
            }))

            basis = ((0, 0, 1), (0, 1, 0), (-1, 0, 0))
            result = validate_recording(folder, basis,
                                        pan_first="right", tilt_first="up")
            self.assertEqual(len(result["pan"]["axis_deviation_deg"]), 3)
            self.assertEqual(len(result["tilt"]["axis_deviation_deg"]), 3)
            self.assertLess(max(result["pan"]["axis_deviation_deg"]), 1)
            self.assertLess(max(result["tilt"]["axis_deviation_deg"]), 1)
            reversed_tilt_basis = ((0, 0, -1), (0, 1, 0), (1, 0, 0))
            with self.assertRaisesRegex(ValueError, "tilt leg 1 disagrees"):
                validate_recording(folder, reversed_tilt_basis,
                                   pan_first="right", tilt_first="up")


if __name__ == "__main__":
    unittest.main()
