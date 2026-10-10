from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from _contracts import Axes

import threading
import unittest
from imu.live_reader import LiveImu, stationary_offset, poll_imu


class LiveImuTests(unittest.TestCase):
    def test_independent_still_window_estimates_offset_and_corrects_new_sample(
        self,
    ) -> None:
        """Verify independent still window estimates offset and corrects new sample.

        Args:
            None.

        Returns:
            None: unittest assertions fail if the expected contract is violated.
        """
        # Feed one second of nearly constant bias, then a separate moving sample.
        # The latter must reflect motion after subtracting the initial mean.
        imu = LiveImu(enabled=True)
        for i in range(11):
            imu.publish(i * 0.1, (-4.0 + 0.02 * (i % 2), 15.0, -3.0))
        result = imu.snapshot(1.01)
        self.assertEqual(result["status"], "ready")
        self.assertAlmostEqual(result["offset_dps"][1], 15.0)
        self.assertAlmostEqual(result["gyro_dps"][1], 0.0)
        imu.publish(1.1, (-4.0, 25.0, -3.0))
        result = imu.snapshot(1.11)
        self.assertEqual(result["gyro_dps"][1], 10.0)
        self.assertEqual(result["samples"], 12)
        self.assertGreater(result["rate_hz"], 9.0)

    def test_motion_during_calibration_is_reported_not_applied(self) -> None:
        """Verify motion during calibration is reported not applied.

        Args:
            None.

        Returns:
            None: unittest assertions fail if the expected contract is violated.
        """
        # Inject a step during calibration and verify that later stillness does not
        # silently clear the error or expose an untrusted corrected rate.
        imu = LiveImu(enabled=True)
        for i in range(11):
            imu.publish(i * 0.1, (0.0, 0.0 if i < 5 else 12.0, 0.0))
        result = imu.snapshot(1.02)
        self.assertEqual(result["status"], "error")
        self.assertIsNone(result["gyro_dps"])
        self.assertIn("restart", result["error"])
        imu.publish(1.1, (0.0, 0.0, 0.0))
        self.assertEqual(imu.snapshot(1.12)["status"], "error")

    def test_stale_and_read_error_do_not_return_old_corrected_rate(self) -> None:
        """Verify stale and read error do not return old corrected rate.

        Args:
            None.

        Returns:
            None: unittest assertions fail if the expected contract is violated.
        """
        # Exercise missing startup, stale calibrated readings and explicit I2C failure;
        # none may return an old corrected rate as current.
        imu = LiveImu(enabled=True)
        self.assertEqual(imu.snapshot(imu.started + 3)["status"], "stale")
        for i in range(11):
            imu.publish(i * 0.1, (0.0, 0.0, 0.0))
        self.assertEqual(imu.snapshot(1.31)["status"], "stale")
        self.assertIsNone(imu.snapshot(1.31)["gyro_dps"])
        imu.fail("i2c failed")
        self.assertEqual(imu.snapshot(1.11)["status"], "error")
        self.assertIsNone(imu.snapshot(1.11)["gyro_dps"])

    def test_not_enough_samples_nonfinite_and_out_of_order_rejected(self) -> None:
        """Verify not enough samples nonfinite and out of order rejected.

        Args:
            None.

        Returns:
            None: unittest assertions fail if the expected contract is violated.
        """
        # Reject insufficient calibration data, invalid axes and repeated timestamps.
        with self.assertRaises(ValueError):
            stationary_offset([(0.0, (0.0, 0.0, 0.0))])
        imu = LiveImu(enabled=True)
        for gyro in [(0.0, float("nan"), 0.0), (1.0, 2.0), (1.0, float("inf"), 2.0)]:
            with self.assertRaises(ValueError):
                imu.publish(0.0, gyro)
        imu.publish(1.0, (1.0, 2.0, 3.0))
        with self.assertRaises(ValueError):
            imu.publish(1.0, (1.0, 2.0, 3.0))

    def test_fake_sensor_is_polled_and_failure_is_isolated(self) -> None:
        """Verify fake sensor is polled and failure is isolated.

        Args:
            None.

        Returns:
            None: unittest assertions fail if the expected contract is violated.
        """

        # Use a deterministic clock and a sensor that disconnects after twelve reads
        # to check the worker failure path without sleeping through real calibration.
        class Sensor:
            def __init__(self) -> None:
                """Initialize the deterministic state used by this test double.

                Args:
                    None.

                Returns:
                    None: The declared test-double result; only synthetic state is changed.
                """
                self.calls = 0

            def read_raw(self) -> tuple[Axes, Axes, float]:
                """Return synthetic driver-unit readings or inject the test read failure.

                Args:
                    None.

                Returns:
                    tuple[Axes, Axes, float]: The declared test-double result; only synthetic state
                        is changed.
                """
                self.calls += 1
                if self.calls > 12:
                    raise OSError("disconnected")
                return (0.0, 0.0, 1.0), (-4.0, 15.0, -3.0), 25.0

        class Clock:
            def __init__(self) -> None:
                """Initialize the deterministic state used by this test double.

                Args:
                    None.

                Returns:
                    None: The declared test-double result; only synthetic state is changed.
                """
                self.n = 0

            def __call__(self) -> float:
                """Advance and return the deterministic test clock in seconds.

                Args:
                    None.

                Returns:
                    float: The declared test-double result; only synthetic state is changed.
                """
                value = self.n * 0.05
                self.n += 1
                return value

        # Run the real polling loop against the fakes and inspect its isolated status.
        imu = LiveImu(enabled=True)
        poll_imu(imu, Sensor(), threading.Event(), interval=0.00001, clock=Clock())
        self.assertEqual(imu.samples, 12)
        self.assertIn("disconnected", imu.snapshot(1.2)["error"])
