"""No-hardware checks for the supervised live-orientation servo demonstration."""

import unittest

from spatial.servo_orientation_demo import LIMIT_DEG, build_steps, run_steps


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


if __name__ == "__main__":
    unittest.main()
