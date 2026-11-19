"""Bearings from known synthetic geometry; no camera, IMU or OpenCV required."""

import dataclasses
import json
import math
from pathlib import Path
import tempfile
import unittest

from app.live_preview import State
from spatial.bearing import (CameraModel, attach_bearings, box_bearing, distort,
                             load_camera_model, rotate, undistort)

CONFIG = Path(__file__).resolve().parents[2] / "configs" / "camera_calibration.json"


def turn(yaw_deg: float = 0.0, pitch_deg: float = 0.0) -> list[float]:
    """Head orientation for a pan (about camera down axis) then a tilt (about its right axis).

    Args:
        yaw_deg (float): Pan, right positive.
        pitch_deg (float): Tilt, up positive (rotation about +x by +angle looks up).
    Returns:
        list[float]: Unit quaternion (w, x, y, z), body-frame composition pan then tilt.
    """
    a, b = math.radians(yaw_deg) / 2, math.radians(pitch_deg) / 2
    pan, tilt = (math.cos(a), 0.0, math.sin(a), 0.0), (math.cos(b), math.sin(b), 0.0, 0.0)
    w1, x1, y1, z1 = pan
    w2, x2, y2, z2 = tilt
    return [w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2, w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2,
            w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2, w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2]


def context(q: list[float], frame_s: float = 10.0, lag_s: float = 0.01) -> dict:
    """Ready orientation context shaped like LiveImu.orientation_at().

    Args:
        q (list[float]): Unit quaternion.
        frame_s (float): Frame receipt seconds.
        lag_s (float): Frame time minus gyro sample time.
    Returns:
        dict: Orientation context.
    """
    return {"status": "ready", "quaternion_wxyz": q, "reference_monotonic_s": 1.0,
            "sample_monotonic_s": frame_s - lag_s}


def box_for_bearing(model: CameraModel, yaw: float, pitch: float, q: list[float]) -> list[float]:
    """Small box centred where a start-frame direction appears for a head orientation.

    Args:
        model (CameraModel): Calibration.
        yaw (float): Start-frame yaw of the object, degrees.
        pitch (float): Start-frame pitch, degrees.
        q (list[float]): Head orientation.
    Returns:
        list[float]: Box [l, t, r, b] in source pixels.
    """
    ya, pa = math.radians(yaw), math.radians(pitch)
    world = (math.sin(ya) * math.cos(pa), -math.sin(pa), math.cos(ya) * math.cos(pa))
    x, y, z = rotate([q[0], -q[1], -q[2], -q[3]], world)   # start frame -> camera frame
    u, v = distort(model, x / z, y / z)
    return [u - 20, v - 50, u + 20, v + 50]


class BearingTests(unittest.TestCase):
    """The same object must keep its bearing while the head turns."""

    def setUp(self) -> None:
        """Load the committed working calibration.

        Args: None.
        Returns: None.
        """
        self.model = load_camera_model(CONFIG)

    def test_lens_round_trip_inside_measured_region(self) -> None:
        """Undistort then distort returns the pixel across the measured image area.

        Args: None.
        Returns: None.
        """
        for u, v in [(640, 360), (253, 330), (1100, 600), (60, 300), (1200, 120)]:
            x, y, error = undistort(self.model, u, v)
            self.assertLess(error, 1e-6)
            pu, pv = distort(self.model, x, y)
            self.assertAlmostEqual(pu, u, places=6)
            self.assertAlmostEqual(pv, v, places=6)

    def test_bearing_constant_while_head_pans_and_tilts(self) -> None:
        """A bottle at −30° keeps that bearing as its pixel position moves.

        Args: None.
        Returns: None.
        """
        image_yaws = []
        for pan, tilt in [(-20, 0), (0, 0), (12, 0), (0, -15), (0, 15), (-10, 8)]:
            q = turn(pan, tilt)
            bearing = box_bearing(self.model, box_for_bearing(self.model, -30, 2, q), context(q), 10.0)
            self.assertEqual(bearing["status"], "ready")
            self.assertAlmostEqual(bearing["yaw_deg"], -30, places=5)
            self.assertAlmostEqual(bearing["pitch_deg"], 2, places=5)
            self.assertAlmostEqual(bearing["orientation_lag_ms"], 10, places=6)
            if tilt == 0:
                self.assertAlmostEqual(bearing["head_yaw_deg"], pan, places=6)
            image_yaws.append(bearing["image_yaw_deg"])
        # Without the gyro the same bottle would appear to move by tens of degrees.
        self.assertGreater(max(image_yaws) - min(image_yaws), 25)

    def test_unknown_or_stale_orientation_is_explicit(self) -> None:
        """No gyro context, or a sample older than 200 ms, gives no bearing.

        Args: None.
        Returns: None.
        """
        box = [600, 300, 680, 420]
        missing = box_bearing(self.model, box, {"status": "unknown", "reason": "IMU error"}, 10.0)
        stale = box_bearing(self.model, box, context(turn(), lag_s=0.25), 10.0)
        for bearing in (missing, stale):
            self.assertEqual(bearing["status"], "unknown")
            self.assertNotIn("yaw_deg", bearing)
            self.assertIn("image_yaw_deg", bearing)

    def test_extrapolated_and_non_invertible_regions(self) -> None:
        """Corner pixels are flagged; a folding lens model refuses to invert.

        Args: None.
        Returns: None.
        """
        corner = box_bearing(self.model, [0, 0, 20, 20], context(turn()), 10.0)
        self.assertTrue(corner["extrapolated"])
        centre = box_bearing(self.model, [620, 320, 660, 400], context(turn()), 10.0)
        self.assertFalse(centre["extrapolated"])
        # Calibration 01's polynomial folds before the top-left corner.
        folding = dataclasses.replace(self.model, fx=733.56, fy=733.16, cx=670.33, cy=330.78,
                                      k1=0.0862, k2=-0.0657, k3=-0.0696)
        result = box_bearing(folding, [0, 0, 2, 2], context(turn()), 10.0)
        self.assertEqual(result["reason"], "lens_model_not_invertible")

    def test_attach_does_not_mutate_and_bad_config_rejected(self) -> None:
        """Boxes are copied; malformed support grids fail loudly.

        Args: None.
        Returns: None.
        """
        boxes = [{"label": "bottle", "box_xyxy": [600, 300, 680, 420]}]
        out = attach_bearings(boxes, self.model, context(turn()), 10.0)
        self.assertNotIn("bearing", boxes[0])
        self.assertEqual(out[0]["bearing"]["status"], "ready")
        config = json.loads(CONFIG.read_text())
        config["support_grid"] = config["support_grid"][:-1]
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "bad.json"
            path.write_text(json.dumps(config))
            with self.assertRaises(ValueError):
                load_camera_model(path)

    def test_detector_frames_get_orientation_only_with_bearings(self) -> None:
        """Frame/gyro pairing is enabled for the detector only when bearings are on.

        Args: None.
        Returns: None.
        """
        basis = [[1, 0, 0], [0, 1, 0], [0, 0, 1]]
        for model, expected in ((None, None), (self.model, "ready")):
            state = State(imu_enabled=True, camera_axis_basis=basis, relative_orientation=True,
                          detection_enabled=True)
            state.camera_model = model
            state.imu.offset = (0, 0, 0)
            state.imu.publish(10.0, (0, 0, 0))
            state.imu.publish(10.02, (0, 5, 0))
            state.publish_frame(b"small", 10.05, b"full")
            pairing = state.detection_orientation
            self.assertEqual(None if pairing is None else pairing["status"], expected)


if __name__ == "__main__":
    unittest.main()
