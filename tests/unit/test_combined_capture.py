import argparse
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from recording.combined_capture import camera_command, parse_frame, positive, read_row, record


class Sensor:
    def read_raw(self):
        return (0, 0, 1), (2, 3, 4), 25


class Process:
    def __init__(self):
        self.stderr = io.StringIO(
            "[Parsed_showinfo_0] n: 0 pts: 0 pts_time:0\n"
            "[Parsed_showinfo_0] n: 1 pts: 33333 pts_time:0.033333\n")
        self.returncode = None

    def poll(self):
        return self.returncode

    def send_signal(self, _signal):
        self.returncode = 255

    def wait(self, timeout):
        return self.returncode


class CombinedCaptureTests(unittest.TestCase):
    def test_pts_and_receipt_are_not_confused(self):
        self.assertEqual(parse_frame("[Parsed_showinfo_0] n: 8 pts: 10 pts_time:1.25e-2"), (8, 0.0125))
        self.assertIsNone(parse_frame("other n: 8 pts: 10 pts_time:0.01"))
        ticks = iter([2_000_000_000, 2_020_000_000])
        row = read_row(Sensor(), 1_000_000_000, lambda: next(ticks))
        self.assertAlmostEqual(row[0], 1.01)
        self.assertAlmostEqual(row[1], 0.02)
        self.assertEqual(row[2:], [0, 0, 1, 2, 3, 4])

    def test_invalid_duration_and_sensor_values_rejected(self):
        for value in ("nan", "inf", "0", "-1"):
            with self.assertRaises(argparse.ArgumentTypeError):
                positive(value)
        sensor = Sensor()
        sensor.read_raw = lambda: ((float("nan"), 0, 1), (0, 0, 0), 25)
        with self.assertRaises(ValueError):
            read_row(sensor, 0)

    def test_video_packet_copy_is_separate_from_decoded_log(self):
        command = camera_command("/dev/video9", Path("recordings/run/camera.mkv"))
        self.assertEqual(command[command.index("-i") + 1], "/dev/video9")
        self.assertEqual(command[command.index("-c:v") + 1], "copy")
        self.assertLess(command.index("recordings/run/camera.mkv"), command.index("-vf"))
        self.assertIn("-n", command)

    def run_fake(self, sensor, directory):
        process = Process()
        args = argparse.Namespace(output=Path(directory) / "run", device="fake",
                                  seconds=0.02, interval=0.001, notes="unit test")
        with patch("recording.combined_capture.platform.platform", return_value="test host"), patch("recording.combined_capture.subprocess.Popen", return_value=process):
            code = record(sensor, args)
        data = json.loads((args.output / "metadata.json").read_text())
        self.assertEqual(process.returncode, 255)
        return code, data, args

    def test_success_saves_both_logs_and_metadata_without_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            code, data, args = self.run_fake(Sensor(), directory)
            self.assertEqual(code, 0)
            self.assertEqual(data["status"], "complete")
            self.assertEqual(data["decoded_frames"], 2)
            self.assertGreater(data["imu_samples"], 1)
            self.assertIn("host_receipt_s", (args.output / "frames.csv").read_text())
            with self.assertRaises(FileExistsError):
                record(Sensor(), args)

    def test_read_error_preserves_failed_run_and_stops_camera(self):
        sensor = Sensor()
        def fail():
            raise OSError("I2C failed")
        sensor.read_raw = fail
        with tempfile.TemporaryDirectory() as directory:
            code, data, _ = self.run_fake(sensor, directory)
            self.assertEqual(code, 1)
            self.assertEqual(data["status"], "failed")
            self.assertEqual(data["error"], "I2C failed")

    def test_interrupt_marks_partial_run(self):
        sensor = Sensor()
        def interrupt():
            raise KeyboardInterrupt
        sensor.read_raw = interrupt
        with tempfile.TemporaryDirectory() as directory:
            code, data, _ = self.run_fake(sensor, directory)
            self.assertEqual(code, 1)
            self.assertEqual(data["error"], "Interrupted by user")


if __name__ == "__main__":
    unittest.main()
