"""Hardware-free checks for bounded camera-frame gyro integration."""

import unittest

from spatial.live_orientation import RelativeCameraOrientation
from spatial.relative_orientation import integrate_gyro
from imu.live_reader import LiveImu


class LiveOrientationTests(unittest.TestCase):
    def test_single_axis_and_offline_replay(self) -> None:
        """A half-second 90-degree turn matches offline quaternion composition."""
        samples = [(index * 0.1, (0.0, 180.0, 0.0)) for index in range(6)]
        live = RelativeCameraOrientation()
        for timestamp, rates in samples:
            live.add(timestamp, rates)
        result = live.snapshot(0.5)
        offline = integrate_gyro(samples, (0.0, 0.0, 0.0))
        self.assertEqual(result["status"], "ready")
        self.assertAlmostEqual(result["angle_deg"], 90.0)
        for actual, expected in zip(result["quaternion_wxyz"], offline["final_quaternion_wxyz"]):
            self.assertAlmostEqual(actual, expected)
        self.assertAlmostEqual(sum(value * value for value in result["quaternion_wxyz"]), 1.0)

    def test_irregular_alternating_axes_match_offline(self) -> None:
        """Incremental update and offline integration use the same ordered math."""
        samples = [(0.0, (0, 0, 0)), (0.08, (50, 0, 0)),
                   (0.19, (0, -30, 0)), (0.29, (0, 0, 40))]
        live = RelativeCameraOrientation()
        for stamp, rate in samples:
            live.add(stamp, rate)
        offline = integrate_gyro(samples, (0, 0, 0))
        for actual, expected in zip(live.snapshot(0.29)["quaternion_wxyz"], offline["final_quaternion_wxyz"]):
            self.assertAlmostEqual(actual, expected)

    def test_gap_and_invalid_data_never_resume_without_new_state(self) -> None:
        """Unknown motion is not guessed by integrating over a dropout."""
        for second in (0.21, 0.0, float("nan")):
            live = RelativeCameraOrientation()
            live.add(0.0, (0, 0, 0))
            live.add(second, (0, 20, 0))
            self.assertEqual(live.snapshot(0.3)["status"], "unknown")
            live.add(0.31, (0, 20, 0))
            self.assertIsNone(live.snapshot(0.31)["quaternion_wxyz"])

    def test_live_imu_bias_conversion_and_stale_gate(self) -> None:
        """Only post-bias camera rates enter the orientation state."""
        basis = ((1, 0, 0), (0, 1, 0), (0, 0, 1))
        imu = LiveImu(True, basis, True)
        for index in range(11):
            imu.publish(index * 0.1, (-4, 15, -3))
        imu.publish(1.1, (-4, 105, -3))
        imu.publish(1.2, (-4, 105, -3))
        ready = imu.snapshot(1.21)["relative_orientation"]
        self.assertEqual(ready["status"], "ready")
        self.assertAlmostEqual(ready["rotation_vector_deg"][1], 13.5, places=5)
        self.assertEqual(ready["integrated_intervals"], 2)
        stale = imu.snapshot(2.0)["relative_orientation"]
        self.assertEqual(stale["status"], "unknown")
        self.assertIsNone(stale["quaternion_wxyz"])

    def test_requires_fitted_camera_basis(self) -> None:
        """Do not label sensor-frame rotations as camera-frame rotations."""
        with self.assertRaises(ValueError):
            LiveImu(True, relative_orientation=True)


if __name__ == "__main__":
    unittest.main()
