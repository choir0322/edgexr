"""Hardware-free safety and accounting tests for servo quality experiments."""

from __future__ import annotations

import argparse
import contextlib
import io
from pathlib import Path
import unittest
from unittest.mock import patch

from recording.servo_motion_quality import (
    AMPLITUDES,
    Phase,
    ServoCommand,
    build_schedule,
    capture_command,
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
    def test_fast_read_request_precedes_first_command_without_changing_timing(self) -> None:
        """Notify the child 300 ms before motion, preserving the command deadline.

        Args:
            None.

        Returns:
            None: Checks control lead and physical command timestamp.
        """
        now,requests = [0],[]

        def pause(seconds: float) -> None:
            """Advance the fake clock by the requested seconds.

            Args:
                seconds (float): Simulated wait duration.

            Returns:
                None: Updates the deterministic clock.
            """
            now[0] += round(seconds*1e9)

        issued=execute_commands([ServoCommand(2.7,'pan',-1,'test')],{'pan':FakeServo()},
            0,alive=lambda:True,clock=lambda:now[0],pause=pause,
            prepare_motion=lambda:requests.append(now[0]))
        self.assertEqual(requests,[2_400_000_000])
        self.assertEqual(issued[0]['host_command_ns'],2_700_000_000)

    def test_adaptive_capture_arguments_preserve_idle_and_active_settings(self) -> None:
        """The servo wrapper forwards policy and both sleeps to its child.

        Args:
            None.

        Returns:
            None: Checks argument forwarding without hardware.
        """
        args=argparse.Namespace(device='test',output=Path('recordings/test'),
            imu_interval=.05,imu_policy='command-driven',imu_active_interval=.01,
            quick_pan=False,wide_pan=True,commission=True,scene='test',power='test',cooling='test')
        command=capture_command(args,21.5)
        self.assertEqual(command[command.index('--imu-policy')+1],'command-driven')
        self.assertEqual(command[command.index('--active-interval')+1],'0.01')
        self.assertEqual(command[command.index('--interval')+1],'0.05')
    def test_imu_sleep_reaches_recorder_without_changing_servo_schedule(self) -> None:
        """CLI selection must reach the child recorder, preserving the 50 ms default."""
        for options, expected in (([], .05), (["--imu-interval", "0.01"], .01)):
            with self.subTest(expected=expected), contextlib.redirect_stdout(io.StringIO()):
                with patch("recording.servo_motion_quality.validate_arming"), \
                     patch("recording.servo_motion_quality.run_capture", return_value=Path("test")) as run, \
                     patch("recording.servo_motion_quality.analyze_run", return_value={}):
                    self.assertEqual(main(["--execute", "--measure-resources", "--commission", "--wide-pan",
                                           "--axes", "pan", "--device", "/dev/video0",
                                           "--output", "recordings/test", *options]), 0)
                args, commands, phases, duration = run.call_args.args
                command = capture_command(args, duration)
                self.assertEqual(float(command[command.index("--interval") + 1]), expected)
                self.assertIn("--measure-resources", command)
                self.assertEqual(len(commands), 80)
                self.assertEqual(commands[-1].angle_deg, 0)
                self.assertEqual(phases[0].amplitude_deg, 20)
                self.assertAlmostEqual(duration, 21.5)

    def test_invalid_imu_sleep_is_rejected_before_hardware(self) -> None:
        """Zero, negative and nonfinite sleep values cannot arm a real run."""
        for value in ("0", "-0.01", "nan", "inf"):
            with self.subTest(value=value), contextlib.redirect_stderr(io.StringIO()):
                with patch("recording.servo_motion_quality.run_capture") as run:
                    with self.assertRaises(SystemExit) as error:
                        main(["--execute", "--imu-interval", value])
                    self.assertEqual(error.exception.code, 2)
                    run.assert_not_called()

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

    def test_quick_pan_has_requested_path_and_stops_at_plus_forty(self) -> None:
        """Quick pan is one bounded path, not the multi-phase full series."""
        commands, phases, duration = build_schedule("pan", quick_pan=True)
        self.assertEqual(len(phases), 1)
        self.assertEqual(phases[0].speed_deg_s, 20)
        self.assertEqual(len(commands), 120)
        self.assertEqual(commands[39].angle_deg, -40)
        self.assertEqual(commands[-1].angle_deg, 40)
        self.assertAlmostEqual(duration, 11.5)
        self.assertTrue(all(command.axis == "pan" for command in commands))
        with self.assertRaisesRegex(ValueError, "requires"):
            build_schedule("both", quick_pan=True)
        with self.assertRaisesRegex(ValueError, "requires"):
            build_schedule("pan", commission=True, quick_pan=True)

    def test_quick_pan_arming_requires_wider_clearance_confirmation(self) -> None:
        """A completed ±20° run does not establish safe travel through ±40°."""
        args = argparse.Namespace(
            confirm_centered=True,
            confirm_cable_slack=True,
            confirm_quick_pan_clearance=False,
            confirm_commissioned=False,
            commission=False,
            wide_pan=False,
            quick_pan=True,
        )
        with self.assertRaisesRegex(ValueError, "±40° pan"):
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
            [ServoCommand(0.1, "pan", 41, "bad")],
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
