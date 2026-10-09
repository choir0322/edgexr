# Postpone type evaluation so optional drivers/libraries stay optional.
from __future__ import annotations

# Describe data contracts without adding third-party runtime dependencies.
from typing import NoReturn, TYPE_CHECKING

# Resolve documentation-only types for editors; this block does not run in production.
if TYPE_CHECKING:
    # Reuse the documented frame, sensor and report vocabulary for type checking.
    from _contracts import Axes, Record, Sensor

# Parse and validate explicit command-line options.
import argparse

# Simulate binary/text streams entirely in memory.
import io

# Read or serialize metadata and browser/report payloads.
import json

# Work with explicit filesystem paths rather than shell expansions.
from pathlib import Path

# Create isolated temporary test outputs that are cleaned up afterwards.
import tempfile

# Express hardware-independent behavior as executable checks.
import unittest

# Replace external effects with controlled test fixtures.
from unittest.mock import patch

# Reuse recording.combined_capture helpers rather than duplicating their behavior here.
from recording.combined_capture import (
    camera_command,
    parse_frame,
    positive,
    read_row,
    record,
)


class Sensor:
    def read_raw(self) -> tuple[Axes, Axes, float]:
        """Return synthetic driver-unit readings or inject the test read failure.

        Args:
            None.

        Returns:
            tuple[Axes, Axes, float]: The declared test-double result; only synthetic state
                is changed.
        """
        # Return the documented result to the caller without starting another operation.
        return (0, 0, 1), (2, 3, 4), 25


class Process:
    def __init__(self) -> None:
        """Initialize the deterministic state used by this test double.

        Args:
            None.

        Returns:
            None: The declared test-double result; only synthetic state is changed.
        """
        # Prepare or exercise io.StringIO with the controlled test inputs.
        self.stderr = io.StringIO(
            "[Parsed_showinfo_0] n: 0 pts: 0 pts_time:0\n"
            "[Parsed_showinfo_0] n: 1 pts: 33333 pts_time:0.033333\n"
        )
        # Set up self.returncode for this independent test scenario.
        self.returncode = None

    def poll(self) -> int | None:
        """Expose the fake child exit state without starting a real process.

        Args:
            None.

        Returns:
            int | None: The declared test-double result; only synthetic state is changed.
        """
        # Return the documented result to the caller without starting another operation.
        return self.returncode

    def send_signal(self, _signal: int) -> None:
        """Simulate FFmpeg returning 255 after an intentional interrupt.

        Args:
            _signal (int): Synthetic input used by this test double.

        Returns:
            None: The declared test-double result; only synthetic state is changed.
        """
        # Set up self.returncode for this independent test scenario.
        self.returncode = 255

    def wait(self, timeout: float) -> int | None:
        """Simulate waiting using the enclosing test state rather than real hardware.

        Args:
            timeout (float): Synthetic input used by this test double.

        Returns:
            int | None: The declared test-double result; only synthetic state is changed.
        """
        # Return the documented result to the caller without starting another operation.
        return self.returncode


class CombinedCaptureTests(unittest.TestCase):
    def test_pts_and_receipt_are_not_confused(self) -> None:
        """Verify pts and receipt are not confused.

        Args:
            None.

        Returns:
            None: unittest assertions fail if the expected contract is violated.
        """
        # Check the expected Equal relationship for this case.
        self.assertEqual(
            parse_frame("[Parsed_showinfo_0] n: 8 pts: 10 pts_time:1.25e-2"),
            (8, 0.0125),
        )
        # Check the expected IsNone relationship for this case.
        self.assertIsNone(parse_frame("other n: 8 pts: 10 pts_time:0.01"))
        # Prepare or exercise iter with the controlled test inputs.
        ticks = iter([2_000_000_000, 2_020_000_000])

        def next_read_tick() -> int:
            """Return the next deterministic nanosecond timestamp for the read test.

            Args:
                None; values are captured from the enclosing function.

            Returns:
                int: The callback result described above.
            """
            # Evaluate the original callback expression only when the caller invokes it.
            return next(ticks)

        # Prepare or exercise read_row with the controlled test inputs.
        row = read_row(Sensor(), 1_000_000_000, next_read_tick)
        # Check the expected AlmostEqual relationship for this case.
        self.assertAlmostEqual(row[0], 1.01)
        # Check the expected AlmostEqual relationship for this case.
        self.assertAlmostEqual(row[1], 0.02)
        # Check the expected Equal relationship for this case.
        self.assertEqual(row[2:], [0, 0, 1, 2, 3, 4])

    def test_invalid_duration_and_sensor_values_rejected(self) -> None:
        """Verify invalid duration and sensor values rejected.

        Args:
            None.

        Returns:
            None: unittest assertions fail if the expected contract is violated.
        """
        # Exercise each fixture or edge case independently.
        for value in ("nan", "inf", "0", "-1"):
            # Require this invalid case to fail with the expected exception.
            with self.assertRaises(argparse.ArgumentTypeError):
                # Call positive for this step; its contract describes the result or side effect.
                positive(value)
        # Prepare or exercise Sensor with the controlled test inputs.
        sensor = Sensor()

        def invalid_sensor_read() -> tuple[Axes, Axes, float]:
            """Return a nonfinite acceleration fixture to test recording validation.

            Args:
                None; values are captured from the enclosing function.

            Returns:
                tuple[Axes, Axes, float]: The callback result described above.
            """
            # Evaluate the original callback expression only when the caller invokes it.
            return ((float("nan"), 0, 1), (0, 0, 0), 25)

        # Set up sensor.read_raw for this independent test scenario.
        sensor.read_raw = invalid_sensor_read
        # Require this invalid case to fail with the expected exception.
        with self.assertRaises(ValueError):
            # Call read_row for this step; its contract describes the result or side effect.
            read_row(sensor, 0)

    def test_video_packet_copy_is_separate_from_decoded_log(self) -> None:
        """Verify video packet copy is separate from decoded log.

        Args:
            None.

        Returns:
            None: unittest assertions fail if the expected contract is violated.
        """
        # Prepare or exercise camera_command with the controlled test inputs.
        command = camera_command("/dev/video9", Path("recordings/run/camera.mkv"))
        # Check the expected Equal relationship for this case.
        self.assertEqual(command[command.index("-i") + 1], "/dev/video9")
        # Check the expected Equal relationship for this case.
        self.assertEqual(command[command.index("-c:v") + 1], "copy")
        # Check the expected Less relationship for this case.
        self.assertLess(
            command.index("recordings/run/camera.mkv"), command.index("-vf")
        )
        # Check the expected In relationship for this case.
        self.assertIn("-n", command)

    def run_fake(
        self, sensor: Sensor, directory: str
    ) -> tuple[int, Record, argparse.Namespace]:
        """Run the recorder against fake sensors/processes in an isolated directory.

        Args:
            sensor (Sensor): Read-only object implementing read_raw: acceleration g, gyro
                degrees/s, temperature C.
            directory (str): Synthetic input used by this test double.

        Returns:
            tuple[int, Record, argparse.Namespace]: The declared test-double result; only
                synthetic state is changed.
        """
        # Prepare or exercise Process with the controlled test inputs.
        process = Process()
        # Prepare or exercise argparse.Namespace with the controlled test inputs.
        args = argparse.Namespace(
            output=Path(directory) / "run",
            device="fake",
            seconds=0.02,
            interval=0.001,
            notes="unit test",
        )
        # Replace external effects only within this controlled test scope.
        with patch(
            "recording.combined_capture.platform.platform", return_value="test host"
        ), patch("recording.combined_capture.subprocess.Popen", return_value=process):
            # Prepare or exercise record with the controlled test inputs.
            code = record(sensor, args)
        # Prepare or exercise json.loads with the controlled test inputs.
        data = json.loads((args.output / "metadata.json").read_text())
        # Check the expected Equal relationship for this case.
        self.assertEqual(process.returncode, 255)
        # Return the documented result to the caller without starting another operation.
        return code, data, args

    def test_success_saves_both_logs_and_metadata_without_overwrite(self) -> None:
        """Verify success saves both logs and metadata without overwrite.

        Args:
            None.

        Returns:
            None: unittest assertions fail if the expected contract is violated.
        """
        # Keep these resources scoped so they are released even if the operation fails.
        with tempfile.TemporaryDirectory() as directory:
            # Prepare or exercise self.run_fake with the controlled test inputs.
            code, data, args = self.run_fake(Sensor(), directory)
            # Check the expected Equal relationship for this case.
            self.assertEqual(code, 0)
            # Check the expected Equal relationship for this case.
            self.assertEqual(data["status"], "complete")
            # Check the expected Equal relationship for this case.
            self.assertEqual(data["decoded_frames"], 2)
            # Check the expected Greater relationship for this case.
            self.assertGreater(data["imu_samples"], 1)
            # Check the expected In relationship for this case.
            self.assertIn("host_receipt_s", (args.output / "frames.csv").read_text())
            # Require this invalid case to fail with the expected exception.
            with self.assertRaises(FileExistsError):
                # Call record for this step; its contract describes the result or side effect.
                record(Sensor(), args)

    def test_read_error_preserves_failed_run_and_stops_camera(self) -> None:
        """Verify read error preserves failed run and stops camera.

        Args:
            None.

        Returns:
            None: unittest assertions fail if the expected contract is violated.
        """
        # Prepare or exercise Sensor with the controlled test inputs.
        sensor = Sensor()

        def fail() -> NoReturn:
            """Inject an I2C read failure to verify failed-run preservation.

            Args:
                None.

            Returns:
                NoReturn: The declared test-double result; only synthetic state is changed.
            """
            # Stop this operation with an explicit error rather than publishing invalid data.
            raise OSError("I2C failed")

        # Set up sensor.read_raw for this independent test scenario.
        sensor.read_raw = fail
        # Keep these resources scoped so they are released even if the operation fails.
        with tempfile.TemporaryDirectory() as directory:
            # Prepare or exercise self.run_fake with the controlled test inputs.
            code, data, _ = self.run_fake(sensor, directory)
            # Check the expected Equal relationship for this case.
            self.assertEqual(code, 1)
            # Check the expected Equal relationship for this case.
            self.assertEqual(data["status"], "failed")
            # Check the expected Equal relationship for this case.
            self.assertEqual(data["error"], "I2C failed")

    def test_interrupt_marks_partial_run(self) -> None:
        """Verify interrupt marks partial run.

        Args:
            None.

        Returns:
            None: unittest assertions fail if the expected contract is violated.
        """
        # Prepare or exercise Sensor with the controlled test inputs.
        sensor = Sensor()

        def interrupt() -> NoReturn:
            """Inject Ctrl+C behavior without interrupting the test runner.

            Args:
                None.

            Returns:
                NoReturn: The declared test-double result; only synthetic state is changed.
            """
            # Stop this operation with an explicit error rather than publishing invalid data.
            raise KeyboardInterrupt

        # Set up sensor.read_raw for this independent test scenario.
        sensor.read_raw = interrupt
        # Keep these resources scoped so they are released even if the operation fails.
        with tempfile.TemporaryDirectory() as directory:
            # Prepare or exercise self.run_fake with the controlled test inputs.
            code, data, _ = self.run_fake(sensor, directory)
            # Check the expected Equal relationship for this case.
            self.assertEqual(code, 1)
            # Check the expected Equal relationship for this case.
            self.assertEqual(data["error"], "Interrupted by user")


# Run the command only when executed directly, not when imported by tests or another module.
if __name__ == "__main__":
    # Call unittest.main for this step; its contract describes the result or side effect.
    unittest.main()
