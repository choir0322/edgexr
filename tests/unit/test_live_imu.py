# Postpone type evaluation so optional drivers/libraries stay optional.
from __future__ import annotations

# Describe data contracts without adding third-party runtime dependencies.
from typing import TYPE_CHECKING

# Resolve documentation-only types for editors; this block does not run in production.
if TYPE_CHECKING:
    # Reuse the documented frame, sensor and report vocabulary for type checking.
    from _contracts import Axes

# Coordinate independent workers using threads, locks, conditions and events.
import threading

# Express hardware-independent behavior as executable checks.
import unittest

# Reuse imu.live_reader helpers rather than duplicating their behavior here.
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
        # Prepare or exercise LiveImu with the controlled test inputs.
        imu = LiveImu(enabled=True)
        # Exercise each fixture or edge case independently.
        for i in range(11):
            # Publish completed work through the state object's synchronization boundary.
            imu.publish(i * 0.1, (-4.0 + 0.02 * (i % 2), 15.0, -3.0))
        # Prepare or exercise imu.snapshot with the controlled test inputs.
        result = imu.snapshot(1.01)
        # Check the expected Equal relationship for this case.
        self.assertEqual(result["status"], "ready")
        # Check the expected AlmostEqual relationship for this case.
        self.assertAlmostEqual(result["offset_dps"][1], 15.0)
        # Check the expected AlmostEqual relationship for this case.
        self.assertAlmostEqual(result["gyro_dps"][1], 0.0)
        # Publish completed work through the state object's synchronization boundary.
        imu.publish(1.1, (-4.0, 25.0, -3.0))
        # Prepare or exercise imu.snapshot with the controlled test inputs.
        result = imu.snapshot(1.11)
        # Check the expected Equal relationship for this case.
        self.assertEqual(result["gyro_dps"][1], 10.0)
        # Check the expected Equal relationship for this case.
        self.assertEqual(result["samples"], 12)
        # Check the expected Greater relationship for this case.
        self.assertGreater(result["rate_hz"], 9.0)

    def test_motion_during_calibration_is_reported_not_applied(self) -> None:
        """Verify motion during calibration is reported not applied.

        Args:
            None.

        Returns:
            None: unittest assertions fail if the expected contract is violated.
        """
        # Prepare or exercise LiveImu with the controlled test inputs.
        imu = LiveImu(enabled=True)
        # Exercise each fixture or edge case independently.
        for i in range(11):
            # Publish completed work through the state object's synchronization boundary.
            imu.publish(i * 0.1, (0.0, 0.0 if i < 5 else 12.0, 0.0))
        # Prepare or exercise imu.snapshot with the controlled test inputs.
        result = imu.snapshot(1.02)
        # Check the expected Equal relationship for this case.
        self.assertEqual(result["status"], "error")
        # Check the expected IsNone relationship for this case.
        self.assertIsNone(result["gyro_dps"])
        # Check the expected In relationship for this case.
        self.assertIn("restart", result["error"])
        # Publish completed work through the state object's synchronization boundary.
        imu.publish(1.1, (0.0, 0.0, 0.0))
        # Check the expected Equal relationship for this case.
        self.assertEqual(imu.snapshot(1.12)["status"], "error")

    def test_stale_and_read_error_do_not_return_old_corrected_rate(self) -> None:
        """Verify stale and read error do not return old corrected rate.

        Args:
            None.

        Returns:
            None: unittest assertions fail if the expected contract is violated.
        """
        # Prepare or exercise LiveImu with the controlled test inputs.
        imu = LiveImu(enabled=True)
        # Check the expected Equal relationship for this case.
        self.assertEqual(imu.snapshot(imu.started + 3)["status"], "stale")
        # Exercise each fixture or edge case independently.
        for i in range(11):
            # Publish completed work through the state object's synchronization boundary.
            imu.publish(i * 0.1, (0.0, 0.0, 0.0))
        # Check the expected Equal relationship for this case.
        self.assertEqual(imu.snapshot(1.31)["status"], "stale")
        # Check the expected IsNone relationship for this case.
        self.assertIsNone(imu.snapshot(1.31)["gyro_dps"])
        # Call imu.fail for this step; its contract describes the result or side effect.
        imu.fail("i2c failed")
        # Check the expected Equal relationship for this case.
        self.assertEqual(imu.snapshot(1.11)["status"], "error")
        # Check the expected IsNone relationship for this case.
        self.assertIsNone(imu.snapshot(1.11)["gyro_dps"])

    def test_not_enough_samples_nonfinite_and_out_of_order_rejected(self) -> None:
        """Verify not enough samples nonfinite and out of order rejected.

        Args:
            None.

        Returns:
            None: unittest assertions fail if the expected contract is violated.
        """
        # Require this invalid case to fail with the expected exception.
        with self.assertRaises(ValueError):
            # Call stationary_offset for this step; its contract describes the result or side
            # effect.
            stationary_offset([(0.0, (0.0, 0.0, 0.0))])
        # Prepare or exercise LiveImu with the controlled test inputs.
        imu = LiveImu(enabled=True)
        # Exercise each fixture or edge case independently.
        for gyro in [(0.0, float("nan"), 0.0), (1.0, 2.0), (1.0, float("inf"), 2.0)]:
            # Require this invalid case to fail with the expected exception.
            with self.assertRaises(ValueError):
                # Publish completed work through the state object's synchronization boundary.
                imu.publish(0.0, gyro)
        # Publish completed work through the state object's synchronization boundary.
        imu.publish(1.0, (1.0, 2.0, 3.0))
        # Require this invalid case to fail with the expected exception.
        with self.assertRaises(ValueError):
            # Publish completed work through the state object's synchronization boundary.
            imu.publish(1.0, (1.0, 2.0, 3.0))

    def test_fake_sensor_is_polled_and_failure_is_isolated(self) -> None:
        """Verify fake sensor is polled and failure is isolated.

        Args:
            None.

        Returns:
            None: unittest assertions fail if the expected contract is violated.
        """

        class Sensor:
            def __init__(self) -> None:
                """Initialize the deterministic state used by this test double.

                Args:
                    None.

                Returns:
                    None: The declared test-double result; only synthetic state is changed.
                """
                # Set up self.calls for this independent test scenario.
                self.calls = 0

            def read_raw(self) -> tuple[Axes, Axes, float]:
                """Return synthetic driver-unit readings or inject the test read failure.

                Args:
                    None.

                Returns:
                    tuple[Axes, Axes, float]: The declared test-double result; only synthetic state
                        is changed.
                """
                # Update self.calls with this step's contribution.
                self.calls += 1
                # Reject this invalid input before it can produce misleading output.
                if self.calls > 12:
                    # Stop this operation with an explicit error rather than publishing invalid
                    # data.
                    raise OSError("disconnected")
                # Return the documented result to the caller without starting another operation.
                return (0.0, 0.0, 1.0), (-4.0, 15.0, -3.0), 25.0

        class Clock:
            def __init__(self) -> None:
                """Initialize the deterministic state used by this test double.

                Args:
                    None.

                Returns:
                    None: The declared test-double result; only synthetic state is changed.
                """
                # Set up self.n for this independent test scenario.
                self.n = 0

            def __call__(self) -> float:
                """Advance and return the deterministic test clock in seconds.

                Args:
                    None.

                Returns:
                    float: The declared test-double result; only synthetic state is changed.
                """
                # Set up value for this independent test scenario.
                value = self.n * 0.05
                # Update self.n with this step's contribution.
                self.n += 1
                # Return the documented result to the caller without starting another operation.
                return value

        # Prepare or exercise LiveImu with the controlled test inputs.
        imu = LiveImu(enabled=True)
        # Call poll_imu for this step; its contract describes the result or side effect.
        poll_imu(imu, Sensor(), threading.Event(), interval=0.00001, clock=Clock())
        # Check the expected Equal relationship for this case.
        self.assertEqual(imu.samples, 12)
        # Check the expected In relationship for this case.
        self.assertIn("disconnected", imu.snapshot(1.2)["error"])
