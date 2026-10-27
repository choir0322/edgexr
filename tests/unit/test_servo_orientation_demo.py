"""No-hardware checks for the supervised live-orientation servo demonstration."""

import unittest
import base64
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event
from unittest.mock import patch
import json

from spatial.servo_orientation_demo import (
    FRAME_HEIGHT, FRAME_WIDTH, LIMIT_DEG, build_steps, final_pan_step, has_settled_sample,
    record_telemetry, run_steps, save_image_checkpoint,
)


class FakeServo:
    """Record position calls without importing or touching the Fusion HAT."""

    def __init__(self) -> None:
        self.commands: list[int] = []

    def angle(self, degrees: int) -> None:
        self.commands.append(degrees)


class ServoOrientationDemoTests(unittest.TestCase):
    def test_fixed_path_is_sequential_bounded_and_centered(self) -> None:
        """Both axes traverse only ±20° and return to the confirmed center."""
        steps = build_steps()
        self.assertEqual(len(steps), 160)
        self.assertEqual({step.axis for step in steps[:80]}, {"pan"})
        self.assertEqual({step.axis for step in steps[80:]}, {"tilt"})
        for segment in (steps[:80], steps[80:]):
            self.assertEqual([segment[i].angle_deg for i in (19, 59, 79)], [-20, 20, 0])
            self.assertLessEqual(max(abs(step.angle_deg) for step in segment), LIMIT_DEG)
        self.assertGreaterEqual(steps[80].due_s - steps[79].due_s, 2.1 - 1e-9)

    def test_pan_checkpoint_only_follows_final_zero_command(self) -> None:
        """Crossing 0° mid-sweep must not trigger the after-pan checkpoint."""
        steps = build_steps()
        pan_zeros = [step for step in steps if step.axis == "pan" and step.angle_deg == 0]
        self.assertEqual(len(pan_zeros), 2)
        self.assertIs(final_pan_step(steps), pan_zeros[-1])
        self.assertIsNot(final_pan_step(steps), pan_zeros[0])
        self.assertEqual(sum(step is final_pan_step(steps) for step in steps), 1)

    def test_fake_clock_sends_one_degree_steps_without_catchup_burst(self) -> None:
        """A delayed command cannot make the next step fire immediately."""
        now = [0.0]
        commands: list[tuple[float, int]] = []

        class TimedFakeServo(FakeServo):
            def angle(self, degrees: int) -> None:
                super().angle(degrees)
                commands.append((now[0], degrees))
                if len(commands) == 1:
                    now[0] += 0.35  # Simulate Linux/vendor call running late.

        def pause(seconds: float) -> None:
            now[0] += seconds

        servo = TimedFakeServo()
        issued = run_steps(build_steps()[:3], {"pan": servo},
                           clock=lambda: now[0], pause=pause)
        self.assertEqual(issued, 3)
        self.assertEqual(servo.commands, [-1, -2, -3])
        self.assertGreaterEqual(commands[1][0] - commands[0][0], 0.35)
        self.assertGreaterEqual(commands[2][0] - commands[1][0], 0.1 - 1e-9)

    def test_invalid_schedule_stops_before_unsafe_command(self) -> None:
        """Motor writes never follow an over-limit or multi-degree target."""
        from spatial.servo_orientation_demo import Step

        servo = FakeServo()
        for target in (21, -2):
            with self.subTest(target=target), self.assertRaises(ValueError):
                run_steps([Step("pan", target, 0.1)], {"pan": servo},
                          clock=lambda: 0.0, pause=lambda _: None)
        self.assertEqual(servo.commands, [])

    def test_issued_commands_include_host_times_for_logging(self) -> None:
        """Command callbacks receive the actual time after each fake servo call."""
        now = [0.0]
        observed = []

        def pause(seconds: float) -> None:
            now[0] += seconds

        run_steps(build_steps()[:2], {"pan": FakeServo()},
                  clock=lambda: now[0], pause=pause,
                  on_command=lambda step, at: observed.append((step.angle_deg, at)))
        self.assertEqual([angle for angle, _ in observed], [-1, -2])
        self.assertGreaterEqual(observed[1][1] - observed[0][1], 0.1 - 1e-9)

    def test_logger_retains_full_orientation_sample(self) -> None:
        """Polling saves the quaternion and derived angle, without image bytes."""
        stop = Event()
        orientation = {"status": "ready", "angle_deg": 12.5,
                       "quaternion_wxyz": [0.9, 0.1, 0.2, 0.3]}

        def one_snapshot() -> dict:
            stop.set()
            return {"status": "live", "imu": {"relative_orientation": orientation}}

        counts = {"samples": 0, "ready_samples": 0, "errors": 0,
                  "peak_angle_deg": 0.0, "final_orientation": None,
                  "last_ready_sample_s": None, "logger_error": None}
        with TemporaryDirectory() as directory:
            path = Path(directory) / "telemetry.jsonl"
            with patch("spatial.servo_orientation_demo.preview_snapshot", one_snapshot):
                record_telemetry(stop, path, counts)
            row = json.loads(path.read_text().strip())
        self.assertEqual(row["telemetry"]["imu"]["relative_orientation"], orientation)
        self.assertEqual(counts["ready_samples"], 1)
        self.assertEqual(counts["peak_angle_deg"], 12.5)
        self.assertIsNotNone(counts["last_ready_sample_s"])
        self.assertIsNone(counts["logger_error"])

    def test_final_observation_must_follow_last_command(self) -> None:
        """A sample from just before commanded zero cannot validate return."""
        self.assertFalse(has_settled_sample(336.369, 336.367))
        self.assertFalse(has_settled_sample(336.369, 337.0))
        self.assertTrue(has_settled_sample(336.369, 337.5))

    def test_fresh_checkpoint_writes_display_size_grayscale_pgm(self) -> None:
        """Saved view bytes and timing metadata come from the existing preview."""
        pixels = bytes([73]) * (FRAME_WIDTH * FRAME_HEIGHT)
        snapshot = {
            "status": "live", "width": FRAME_WIDTH, "height": FRAME_HEIGHT,
            "result_age_ms": 25.0, "sequence": 21, "imu_poll_sleep_ms": 10,
            "imu": {"relative_orientation": {"status": "ready"}},
            "pixels_b64": base64.b64encode(pixels).decode(),
        }
        with TemporaryDirectory() as directory:
            with patch("spatial.servo_orientation_demo.preview_frame", return_value=snapshot):
                row = save_image_checkpoint(Path(directory), "before_pan")
            image = (Path(directory) / "before_pan.pgm").read_bytes()
        self.assertEqual(image, b"P5\n320 180\n255\n" + pixels)
        self.assertEqual(row["frame_sequence"], 21)
        self.assertEqual(row["imu_poll_sleep_ms"], 10)

    def test_stale_or_wrong_size_checkpoint_fails(self) -> None:
        """A missing or old display image cannot be mistaken for a visual return."""
        snapshot = {"status": "live", "width": FRAME_WIDTH, "height": FRAME_HEIGHT,
                    "result_age_ms": 301, "pixels_b64": ""}
        with TemporaryDirectory() as directory:
            with patch("spatial.servo_orientation_demo.preview_frame", return_value=snapshot):
                with self.assertRaisesRegex(ValueError, "too old"):
                    save_image_checkpoint(Path(directory), "after_pan")
            snapshot["result_age_ms"] = 10
            with patch("spatial.servo_orientation_demo.preview_frame", return_value=snapshot):
                with self.assertRaisesRegex(ValueError, "byte count"):
                    save_image_checkpoint(Path(directory), "after_pan")
            self.assertEqual(list(Path(directory).iterdir()), [])


if __name__ == "__main__":
    unittest.main()
