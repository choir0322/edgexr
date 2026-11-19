"""The trial analyzer on a synthetic servo sweep with a known camera delay."""

import importlib.util
import json
import math
from pathlib import Path
import tempfile
import unittest

from spatial.bearing import attach_bearings, distort, load_camera_model, rotate

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("analyze_bearing_trial", ROOT / "scripts" / "analyze_bearing_trial.py")
analyzer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(analyzer)


def head_yaw(t: float) -> float:
    """Pan schedule like the servo test: still, 0 → −20 → +20 → 0 at 10 °/s, still.

    Args:
        t (float): Seconds from start.
    Returns:
        float: Head yaw in degrees.
    """
    legs = [(2, 0, 0), (2, -10, 2), (4, 10, 4), (2, -10, 8), (4, 0, 10)]   # duration, rate, start
    yaw = 0.0
    for duration, rate, start in legs:
        yaw += rate * max(0.0, min(t, start + duration) - start)
    return yaw


def write_run(folder: Path, delay_s: float) -> None:
    """Write telemetry.jsonl for a bottle at −30° seen through a delayed camera.

    Args:
        folder (Path): Run folder to create files in.
        delay_s (float): Exposure-to-receipt delay; the head moved meanwhile.
    Returns:
        None: Writes 2 Hz detector results inside 20 Hz telemetry rows.
    """
    model = load_camera_model(ROOT / "configs" / "camera_calibration.json")
    lines = []
    for k in range(28):
        receipt = 0.5 * k + 0.25
        exposure_yaw = head_yaw(receipt - delay_s)
        q_exposure = [math.cos(math.radians(exposure_yaw) / 2), 0, math.sin(math.radians(exposure_yaw) / 2), 0]
        ya = math.radians(-30)
        x, y, z = rotate([q_exposure[0], 0, -q_exposure[2], 0], (math.sin(ya), 0.0, math.cos(ya)))
        u, v = distort(model, x / z, y / z)
        receipt_yaw = head_yaw(receipt)
        q = [math.cos(math.radians(receipt_yaw) / 2), 0, math.sin(math.radians(receipt_yaw) / 2), 0]
        orientation = {"status": "ready", "quaternion_wxyz": q, "reference_monotonic_s": 0.0,
                       "sample_monotonic_s": receipt - 0.005}
        boxes = attach_bearings([{"label": "bottle", "confidence": 0.8, "box_xyxy": [u - 15, v - 40, u + 15, v + 40]}],
                                model, orientation, receipt)
        for repeat in range(3):   # the same result appears in several telemetry polls
            poll = receipt + 0.3 + 0.05 * repeat
            lines.append(json.dumps({"host_poll_midpoint_s": poll, "telemetry": {"detector": {
                "status": "ready", "sequence": k, "age_ms": (poll - receipt) * 1000, "boxes": boxes}}}))
    (folder / "telemetry.jsonl").write_text("\n".join(lines) + "\n")


class TrialAnalysisTests(unittest.TestCase):
    """Constant bearings pass; a known delay appears as a turn-direction offset."""

    def test_pass_and_latency_estimate(self) -> None:
        """A 40 ms delay at 10 °/s shifts bearings ±0.4°, estimated back as ≈40 ms.

        Args: None.
        Returns: None.
        """
        with tempfile.TemporaryDirectory() as folder:
            run = Path(folder)
            write_run(run, 0.04)
            summary = analyzer.summarize(run, "bottle")
        self.assertEqual(summary["counts"]["unique_results"], 28)
        self.assertTrue(summary["pass"], summary["checks"])
        self.assertAlmostEqual(summary["bearing_yaw_by_motion_deg"]["still"]["median"], -30, places=3)
        self.assertGreater(summary["image_yaw_deg_without_gyro"]["spread_p5_p95"], 20)
        self.assertAlmostEqual(summary["latency_estimate_ms"], 40, delta=8)

    def test_from_centre_matches_image_angles_when_centred(self) -> None:
        """Seen from the centred head, a direction equals its image angles at that pose.

        Args: None.
        Returns: None.
        """
        model = load_camera_model(ROOT / "configs" / "camera_calibration.json")
        tilt, roll = math.radians(-12) / 2, math.radians(3) / 2
        # A start pose with pan, tilt and a little roll, as left over from an earlier run.
        head = analyzer.hamilton((math.cos(math.radians(7) / 2), 0, math.sin(math.radians(7) / 2), 0),
                                 analyzer.hamilton((math.cos(tilt), math.sin(tilt), 0, 0),
                                                   (math.cos(roll), 0, 0, math.sin(roll))))
        orientation = {"status": "ready", "quaternion_wxyz": list(head), "reference_monotonic_s": 0.0,
                       "sample_monotonic_s": 9.99}
        u, v = distort(model, math.tan(math.radians(-35)), 0.2)
        box = {"box_xyxy": [u - 10, v - 10, u + 10, v + 10]}
        bearing = attach_bearings([box], model, orientation, 10.0)[0]["bearing"]
        yaw, pitch = analyzer.from_centre(bearing["yaw_deg"], bearing["pitch_deg"], bearing["head_quaternion_wxyz"])
        self.assertAlmostEqual(yaw, bearing["image_yaw_deg"], places=6)
        self.assertAlmostEqual(pitch, bearing["image_pitch_deg"], places=6)

if __name__ == "__main__":
    unittest.main()
