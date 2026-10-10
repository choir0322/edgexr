from __future__ import annotations
from typing import NoReturn, TYPE_CHECKING

if TYPE_CHECKING:
    from _contracts import Axes, Record, Sensor

import argparse
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
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
        return (0, 0, 1), (2, 3, 4), 25


class Process:
    def __init__(self) -> None:
        """Initialize the deterministic state used by this test double.

        Args:
            None.

        Returns:
            None: The declared test-double result; only synthetic state is changed.
        """
        # Emulate two showinfo frames and a running process; shutdown changes its
        # return code to the same 255 permitted for deliberate FFmpeg interruption.
        self.stderr = io.StringIO(
            "[Parsed_showinfo_0] n: 0 pts: 0 pts_time:0\n"
            "[Parsed_showinfo_0] n: 1 pts: 33333 pts_time:0.033333\n"
        )
        self.returncode = None

    def poll(self) -> int | None:
        """Expose the fake child exit state without starting a real process.

        Args:
            None.

        Returns:
            int | None: The declared test-double result; only synthetic state is changed.
        """
        return self.returncode

    def send_signal(self, _signal: int) -> None:
        """Simulate FFmpeg returning 255 after an intentional interrupt.

        Args:
            _signal (int): Synthetic input used by this test double.

        Returns:
            None: The declared test-double result; only synthetic state is changed.
        """
        self.returncode = 255

    def wait(self, timeout: float) -> int | None:
        """Simulate waiting using the enclosing test state rather than real hardware.

        Args:
            timeout (float): Synthetic input used by this test double.

        Returns:
            int | None: The declared test-double result; only synthetic state is changed.
        """
        return self.returncode


class CombinedCaptureTests(unittest.TestCase):
    def test_pts_and_receipt_are_not_confused(self) -> None:
        """Verify pts and receipt are not confused.

        Args:
            None.

        Returns:
            None: unittest assertions fail if the expected contract is violated.
        """
        # Keep decoded PTS parsing separate from midpoint/read-duration calculations
        # using a fake clock with a known origin and 20 ms read.
        self.assertEqual(
            parse_frame("[Parsed_showinfo_0] n: 8 pts: 10 pts_time:1.25e-2"),
            (8, 0.0125),
        )
        self.assertIsNone(parse_frame("other n: 8 pts: 10 pts_time:0.01"))
        ticks = iter([2_000_000_000, 2_020_000_000])

        def next_read_tick() -> int:
            """Return the next deterministic nanosecond timestamp for the read test.

            Args:
                None; values are captured from the enclosing function.

            Returns:
                int: The callback result described above.
            """
            return next(ticks)

        row = read_row(Sensor(), 1_000_000_000, next_read_tick)
        self.assertAlmostEqual(row[0], 1.01)
        self.assertAlmostEqual(row[1], 0.02)
        self.assertEqual(row[2:], [0, 0, 1, 2, 3, 4])

    def test_invalid_duration_and_sensor_values_rejected(self) -> None:
        """Verify invalid duration and sensor values rejected.

        Args:
            None.

        Returns:
            None: unittest assertions fail if the expected contract is violated.
        """
        # Reject invalid durations and a sensor with a nonfinite acceleration axis.
        for value in ("nan", "inf", "0", "-1"):
            with self.assertRaises(argparse.ArgumentTypeError):
                positive(value)
        sensor = Sensor()

        def invalid_sensor_read() -> tuple[Axes, Axes, float]:
            """Return a nonfinite acceleration fixture to test recording validation.

            Args:
                None; values are captured from the enclosing function.

            Returns:
                tuple[Axes, Axes, float]: The callback result described above.
            """
            return ((float("nan"), 0, 1), (0, 0, 0), 25)

        sensor.read_raw = invalid_sensor_read
        with self.assertRaises(ValueError):
            read_row(sensor, 0)

    def test_video_packet_copy_is_separate_from_decoded_log(self) -> None:
        """Verify video packet copy is separate from decoded log.

        Args:
            None.

        Returns:
            None: unittest assertions fail if the expected contract is violated.
        """
        command = camera_command("/dev/video9", Path("recordings/run/camera.mkv"))
        self.assertEqual(command[command.index("-i") + 1], "/dev/video9")
        self.assertEqual(command[command.index("-c:v") + 1], "copy")
        self.assertLess(
            command.index("recordings/run/camera.mkv"), command.index("-vf")
        )
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
        # Run the recording lifecycle against a fake camera and short acquisition
        # window, then read its metadata and confirm orderly process shutdown.
        process = Process()
        args = argparse.Namespace(
            output=Path(directory) / "run",
            device="fake",
            seconds=0.02,
            interval=0.001,
            notes="unit test",
        )
        with patch(
            "recording.combined_capture.platform.platform", return_value="test host"
        ), patch("recording.combined_capture.subprocess.Popen", return_value=process):
            code = record(sensor, args)
        data = json.loads((args.output / "metadata.json").read_text())
        self.assertEqual(process.returncode, 255)
        return code, data, args

    def test_success_saves_both_logs_and_metadata_without_overwrite(self) -> None:
        """Verify success saves both logs and metadata without overwrite.

        Args:
            None.

        Returns:
            None: unittest assertions fail if the expected contract is violated.
        """
        # Check both streams and complete metadata, then verify the run cannot overwrite itself.
        with tempfile.TemporaryDirectory() as directory:
            code, data, args = self.run_fake(Sensor(), directory)
            self.assertEqual(code, 0)
            self.assertEqual(data["status"], "complete")
            self.assertEqual(data["decoded_frames"], 2)
            self.assertGreater(data["imu_samples"], 1)
            self.assertIn("host_receipt_s", (args.output / "frames.csv").read_text())
            with self.assertRaises(FileExistsError):
                record(Sensor(), args)

    def test_read_error_preserves_failed_run_and_stops_camera(self) -> None:
        """Verify read error preserves failed run and stops camera.

        Args:
            None.

        Returns:
            None: unittest assertions fail if the expected contract is violated.
        """
        sensor = Sensor()

        def fail() -> NoReturn:
            """Inject an I2C read failure to verify failed-run preservation.

            Args:
                None.

            Returns:
                NoReturn: The declared test-double result; only synthetic state is changed.
            """
            raise OSError("I2C failed")

        # Inject I2C failure and ensure the partial run is saved with a failed status.
        sensor.read_raw = fail
        with tempfile.TemporaryDirectory() as directory:
            code, data, _ = self.run_fake(sensor, directory)
            self.assertEqual(code, 1)
            self.assertEqual(data["status"], "failed")
            self.assertEqual(data["error"], "I2C failed")

    def test_interrupt_marks_partial_run(self) -> None:
        """Verify interrupt marks partial run.

        Args:
            None.

        Returns:
            None: unittest assertions fail if the expected contract is violated.
        """
        sensor = Sensor()

        def interrupt() -> NoReturn:
            """Inject Ctrl+C behavior without interrupting the test runner.

            Args:
                None.

            Returns:
                NoReturn: The declared test-double result; only synthetic state is changed.
            """
            raise KeyboardInterrupt

        # Inject interruption and confirm it is recorded as incomplete, not successful.
        sensor.read_raw = interrupt
        with tempfile.TemporaryDirectory() as directory:
            code, data, _ = self.run_fake(sensor, directory)
            self.assertEqual(code, 1)
            self.assertEqual(data["error"], "Interrupted by user")


if __name__ == "__main__":
    unittest.main()
