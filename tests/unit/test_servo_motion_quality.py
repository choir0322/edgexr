"""Hardware-free safety and accounting tests for servo quality experiments."""

from __future__ import annotations

import argparse
from pathlib import Path
import unittest
from unittest.mock import patch

from recording.servo_motion_quality import (
    AMPLITUDES,
    Phase,
    ServoCommand,
    build_schedule,
    execute_commands,
    main,
    phase_report,
    validate_arming,
)


class FakeServo:
    """Record commanded angles without any hardware library."""

    def __init__(self) -> None:
        """Start with no observed commands."""
        self.angles: list[int] = []

    def angle(self, degrees: int) -> None:
        """Append a fake servo command for an assertion."""
        self.angles.append(degrees)


class ServoQualityTests(unittest.TestCase):
    def test_schedule_is_small_sequential_and_rate_limited(self) -> None:
        """Every command stays near center and each phase returns to zero."""
        commands, phases, duration = build_schedule()
        self.assertEqual(len(phases), 6)
        self.assertLess(duration, 60)
        self.assertGreater(commands[0].at_s, 2.5)
        for phase in phases:
            group = [command for command in commands if command.phase == phase.name]
            self.assertEqual(group[-1].angle_deg, 0)
            self.assertEqual({command.axis for command in group}, {phase.axis})
            previous = 0
            for command in group:
                self.assertLessEqual(abs(command.angle_deg), AMPLITUDES[phase.axis])
                self.assertEqual(abs(command.angle_deg - previous), 1)
                previous = command.angle_deg

    def test_default_cli_does_not_touch_capture_or_hardware(self) -> None:
        """Dry-run must stop before real-run validation and physical imports."""
        with patch("recording.servo_motion_quality.run_capture", side_effect=AssertionError):
            with patch(
                "recording.servo_motion_quality.validate_arming",
                side_effect=AssertionError,
            ):
                self.assertEqual(main([]), 0)

    def test_arming_refuses_unknown_channels_or_physical_state(self) -> None:
        """No real run may assume SunFounder's example matches user wiring."""
        args = argparse.Namespace(
            confirm_centered=False,
            confirm_cable_slack=False,
            confirm_commissioned=False,
            commission=True,
            device="/dev/video0",
            output=Path("recordings/new-servo-run"),
            pan_channel=None,
            tilt_channel=None,
        )
        with self.assertRaisesRegex(ValueError, "Confirm physical"):
            validate_arming(args)
        args.confirm_centered = args.confirm_cable_slack = True
        with self.assertRaisesRegex(ValueError, "Supply actual"):
            validate_arming(args)
        args.pan_channel = args.tilt_channel = 2
        with self.assertRaisesRegex(ValueError, "distinct"):
            validate_arming(args)

    def test_commission_schedule_stays_within_two_degrees(self) -> None:
        """A first hardware trial is smaller and shorter than the full series."""
        commands, phases, duration = build_schedule("pan", commission=True)
        self.assertEqual(len(phases), 1)
        self.assertEqual(phases[0].speed_deg_s, 5)
        self.assertTrue(all(abs(command.angle_deg) <= 2 for command in commands))
        self.assertLess(duration, 10)

    def test_wide_pan_schedule_reaches_both_twenty_degree_bounds(self) -> None:
        """Opt-in pan commissioning follows center, left, right, center."""
        commands, phases, duration = build_schedule(
            "pan", commission=True, wide_pan=True
        )
        self.assertEqual(len(phases), 1)
        self.assertEqual(phases[0].amplitude_deg, 20)
        self.assertEqual(len(commands), 80)
        self.assertEqual(
            [command.angle_deg for command in commands if command.angle_deg in (-20, 20)],
            [-20, 20],
        )
        self.assertEqual(commands[-1].angle_deg, 0)
        self.assertAlmostEqual(duration, 21.5)
        with self.assertRaisesRegex(ValueError, "requires"):
            build_schedule("tilt", commission=True, wide_pan=True)
        with self.assertRaisesRegex(ValueError, "requires"):
            build_schedule("pan", wide_pan=True)

    def test_wide_pan_arming_requires_specific_clearance_confirmation(self) -> None:
        """The existing small-sweep cable check does not arm a ±20° sweep."""
        args = argparse.Namespace(
            confirm_centered=True,
            confirm_cable_slack=True,
            confirm_wide_pan_clearance=False,
            confirm_commissioned=False,
            commission=True,
            wide_pan=True,
        )
        with self.assertRaisesRegex(ValueError, "±20° pan"):
            validate_arming(args)

    def test_command_fault_stops_and_preserves_partial_log(self) -> None:
        """An unavailable recorder prevents later servo commands."""
        servo = FakeServo()
        now = [0]
        commands = [ServoCommand(0.1, "pan", -1, "pan-5dps"),
                    ServoCommand(0.2, "pan", -2, "pan-5dps")]
        issued: list[dict[str, object]] = []

        def pause(seconds: float) -> None:
            """Advance a fake monotonic clock."""
            now[0] += round(seconds * 1e9)

        with self.assertRaisesRegex(RuntimeError, "stopped"):
            execute_commands(
                commands,
                {"pan": servo},
                0,
                alive=lambda: len(servo.angles) == 0,
                clock=lambda: now[0],
                pause=pause,
                issued=issued,
            )
        self.assertEqual(servo.angles, [-1])
        self.assertEqual(len(issued), 1)

    def test_late_servo_call_never_causes_catch_up_burst(self) -> None:
        """A delayed first command must not collapse the next 200 ms interval."""
        now = [0]

        class SlowServo(FakeServo):
            """Simulate a blocked first hardware call."""

            def angle(self, degrees: int) -> None:
                """Record the call, then make the first one consume 500 ms."""
                super().angle(degrees)
                if len(self.angles) == 1:
                    now[0] += 500_000_000

        def pause(seconds: float) -> None:
            """Advance simulated monotonic time."""
            now[0] += round(seconds * 1e9)

        commands = [ServoCommand(0.2, "pan", -1, "pan-5dps"),
                    ServoCommand(0.4, "pan", -2, "pan-5dps")]
        issued = execute_commands(
            commands, {"pan": SlowServo()}, 0, alive=lambda: True,
            clock=lambda: now[0], pause=pause,
        )
        self.assertGreaterEqual(
            issued[1]["host_command_ns"] - issued[0]["host_command_ns"],
            700_000_000,
        )

    def test_executor_refuses_large_or_too_fast_step(self) -> None:
        """The actuator boundary checks bounds even if given a bad schedule."""
        servo = FakeServo()
        for commands in (
            [ServoCommand(0.1, "pan", 21, "bad")],
            [ServoCommand(0.1, "pan", -2, "bad")],
            [ServoCommand(0.1, "pan", -1, "bad"),
             ServoCommand(0.11, "pan", -2, "bad")],
        ):
            with self.subTest(commands=commands):
                servo.angles.clear()
                with self.assertRaises(ValueError):
                    execute_commands(
                        commands, {"pan": servo}, 0, alive=lambda: True,
                        clock=lambda: 1_000_000_000,
                    )

    def test_report_separates_visual_rejection_from_pts_gaps(self) -> None:
        """A rejected match and a long camera PTS interval are separate counts."""
        phase = Phase("pan-5dps", "pan", 5, 8, 0.5, 2.0)
        issued = [
            dict(phase=phase.name, host_command_ns=1_000_000_000),
            dict(phase=phase.name, host_command_ns=2_000_000_000),
        ]
        metadata = dict(origin_monotonic_ns=0, recording_cue_host_s=0)
        motion = [
            dict(host_after_cue_s="1.2", dx_pixels="", gy_dps="10"),
            dict(host_after_cue_s="1.6", dx_pixels="2", gy_dps="20"),
        ]
        frames = [
            dict(host_receipt_s="1.1", camera_pts_s="1.0"),
            dict(host_receipt_s="1.15", camera_pts_s="1.033"),
            dict(host_receipt_s="1.3", camera_pts_s="1.100"),
        ]
        patches = [dict(host_after_cue_s=1.2,
                        patches=[dict(failed_checks=["weak_peak"])])]
        result = phase_report([phase], issued, metadata, motion, frames, patches)[0]
        self.assertEqual(result["visual_rejection_fraction"], 0.5)
        self.assertEqual(result["pts_gap_flags"], 1)
        self.assertEqual(result["pts_gap_fraction"], 0.5)
        self.assertEqual(result["rejected_pair_patch_checks"], {"weak_peak": 1})
