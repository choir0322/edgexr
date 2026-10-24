"""Dry-run-first, bounded servo motion with camera/IMU quality measurements.

The real mode requires an explicitly confirmed 0-degree physical center and
actual Fusion HAT channel mapping. No hardware is imported in dry-run mode.
"""

from __future__ import annotations

import argparse
from collections import Counter
import csv
from dataclasses import asdict, dataclass
from importlib.util import find_spec
import json
import math
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import threading
import time
from typing import Callable, Sequence


AMPLITUDES = {"pan": 8, "tilt": 6}  # Degrees about the confirmed physical center.
MAX_COMMAND_AMPLITUDES = {"pan": 40, "tilt": 6}  # Includes opt-in quick pan test.
SPEEDS = (5, 10, 20)  # Commanded degrees/second, not measured shaft speed.
INITIAL_STILL_S = 2.5
BETWEEN_PHASES_S = 1.0
FINAL_STILL_S = 2.0
MAX_TOTAL_S = 60.0
FAST_READ_LEAD_S = 0.3
FAST_READ_SETTLE_S = 1.0


def positive_interval(value: str) -> float:
    """Parse a finite positive post-read sleep duration in seconds.

    Args:
        value (str): Text supplied to --imu-interval.

    Returns:
        float: Valid sleep duration, or raises argparse.ArgumentTypeError.
    """
    interval = float(value)
    if not math.isfinite(interval) or interval <= 0:
        raise argparse.ArgumentTypeError("IMU interval must be finite and greater than zero")
    return interval


@dataclass(frozen=True)
class ServoCommand:
    """One scheduled 1-degree command relative to the recording cue."""

    at_s: float
    axis: str
    angle_deg: int
    phase: str


@dataclass(frozen=True)
class Phase:
    """One bounded single-axis sweep at a commanded rate."""

    name: str
    axis: str
    speed_deg_s: int
    amplitude_deg: int
    start_s: float
    end_s: float


def build_schedule(
    axes: str = "both", *, commission: bool = False, wide_pan: bool = False,
    quick_pan: bool = False,
) -> tuple[list[ServoCommand], list[Phase], float]:
    """Build a center-bounded, sequential speed series with no hardware access.

    Args:
        axes (str): ``pan``, ``tilt`` or ``both``; both tests one axis at a time.
        commission (bool): Use one 5°/s phase at ±2° for initial supervised
            physical verification, before the full speed series.
        wide_pan (bool): Use ±20° for a pan-only commissioning sweep.
        quick_pan (bool): Command pan 0° → −40° → +40° at 20°/s, ending at +40°.

    Returns:
        tuple[list[ServoCommand], list[Phase], float]: Timed commands, phase
            windows, and capture duration in seconds.
    """
    if axes not in ("pan", "tilt", "both"):
        raise ValueError("axes must be pan, tilt or both")
    if wide_pan and (not commission or axes != "pan"):
        raise ValueError("--wide-pan requires --commission --axes pan")
    if quick_pan and (commission or wide_pan or axes != "pan"):
        raise ValueError("--quick-pan requires --axes pan without --commission or --wide-pan")
    selected = ("pan", "tilt") if axes == "both" else (axes,)
    speeds = (20,) if quick_pan else (5,) if commission else SPEEDS
    commands: list[ServoCommand] = []
    phases: list[Phase] = []
    elapsed = INITIAL_STILL_S

    # Move in 1° steps; only the quick test intentionally ends away from center.
    # Never command both axes within the same phase or exceed the selected bounds.
    for speed in speeds:
        for axis in selected:
            amplitude = 40 if quick_pan else (20 if wide_pan else 2) if commission else AMPLITUDES[axis]
            current = 0
            start = elapsed
            name = f"{axis}-quick-{speed}dps" if quick_pan else f"{axis}-{speed}dps"
            targets = (-amplitude, amplitude) if quick_pan else (-amplitude, amplitude, 0)
            for target in targets:
                while current != target:
                    current += 1 if target > current else -1
                    elapsed += 1 / speed
                    commands.append(ServoCommand(elapsed, axis, current, name))
            phases.append(Phase(name, axis, speed, amplitude, start, elapsed))
            elapsed += BETWEEN_PHASES_S

    duration = elapsed + FINAL_STILL_S
    if duration > MAX_TOTAL_S:
        raise ValueError("Servo schedule exceeds bounded capture duration")
    return commands, phases, duration


def validate_arming(args: argparse.Namespace) -> None:
    """Reject unsafe or ambiguous real-run arguments before importing hardware.

    Args:
        args (argparse.Namespace): Parsed CLI values including explicit confirmations.

    Returns:
        None: Raises ValueError if a real run lacks physical safeguards.
    """
    if not args.confirm_centered or not args.confirm_cable_slack:
        raise ValueError("Confirm physical 0° center and free cable travel first")
    if getattr(args, "wide_pan", False) and not getattr(args, "confirm_wide_pan_clearance", False):
        raise ValueError("Confirm clear travel and cable slack through ±20° pan first")
    if getattr(args, "quick_pan", False) and not getattr(args, "confirm_quick_pan_clearance", False):
        raise ValueError("Confirm clear travel and cable slack through ±40° pan first")
    if not args.commission and not getattr(args, "quick_pan", False) and not args.confirm_commissioned:
        raise ValueError("Complete supervised --commission checks before the full series")
    if not args.device or not args.output:
        raise ValueError("Real run requires --device and --output")
    if args.pan_channel is None or args.tilt_channel is None:
        raise ValueError("Supply actual --pan-channel and --tilt-channel; never guess")
    if (
        args.pan_channel == args.tilt_channel
        or not 0 <= args.pan_channel <= 14
        or not 0 <= args.tilt_channel <= 14
    ):
        raise ValueError("Channels must be distinct Fusion HAT channels 0–14")
    if not Path(args.device).exists():
        raise ValueError(f"Camera device does not exist: {args.device}")
    output = args.output.resolve()
    if not output.is_relative_to(Path("recordings").resolve()):
        raise ValueError("Output must be a new directory under recordings/")
    for target in (output, output.with_name(output.name + "-analysis"),
                   output.with_name(output.name + "-patch")):
        if target.exists():
            raise ValueError(f"Output already exists: {target}")
    if not Path("src/recording/combined_capture.py").exists():
        raise ValueError("Run from the EdgeXR repository root")
    if not all(shutil.which(name) for name in ("ffmpeg", "ffprobe")):
        raise ValueError("Existing ffmpeg and ffprobe are required")
    if not all(
        find_spec(name) is not None
        for name in ("fusion_hat", "sunfounder_imu", "numpy")
    ):
        raise ValueError("Existing fusion_hat, sunfounder_imu and NumPy are required")


def execute_commands(
    commands: Sequence[ServoCommand],
    servos: dict[str, object],
    cue_observed_ns: int,
    alive: Callable[[], bool],
    *,
    clock: Callable[[], int] = time.monotonic_ns,
    pause: Callable[[float], None] = time.sleep,
    issued: list[dict[str, object]] | None = None,
    prepare_motion: Callable[[], None] | None = None,
) -> list[dict[str, object]]:
    """Issue bounded commands on time, aborting before the next command on fault.

    Args:
        commands (Sequence[ServoCommand]): Prevalidated relative-time schedule.
        servos (dict[str, object]): Pan/tilt objects with SunFounder-compatible
            ``angle(degrees)`` methods, or fake objects in unit tests.
        cue_observed_ns (int): Parent's monotonic time when capture cue was read.
        alive (Callable[[], bool]): Reports whether the capture process is alive.
        clock (Callable[[], int]): Monotonic nanosecond clock.
        pause (Callable[[float], None]): Bounded pause; injectable for tests.
        issued (list[dict[str, object]] | None): Optional caller-owned command log
            retained even when an interrupted run raises before completion.
        prepare_motion (Callable[[], None] | None): Request fast reads 0.3 s before
            the first command; called once without changing command deadlines.

    Returns:
        list[dict[str, object]]: Actual host command times and planned values.
    """
    if issued is None:
        issued = []
    previous_command: ServoCommand | None = None
    previous_actual_ns: int | None = None
    last_angle = {"pan": 0, "tilt": 0}
    for command in commands:
        if command.axis not in AMPLITUDES:
            raise ValueError("Unknown servo axis")
        if not 0 <= command.at_s <= MAX_TOTAL_S:
            raise ValueError("Command lies outside bounded capture time")
        if abs(command.angle_deg) > MAX_COMMAND_AMPLITUDES[command.axis]:
            raise ValueError("Command exceeds hard axis bound")
        if abs(command.angle_deg - last_angle[command.axis]) != 1:
            raise ValueError("Servo commands must move exactly one degree per step")
        if previous_command is not None and command.at_s - previous_command.at_s < 0.05 - 1e-9:
            raise ValueError("Servo commands exceed the 20-degree/s hard cap")
        deadline = cue_observed_ns + round(command.at_s * 1e9)
        if previous_command is not None and previous_command.phase == command.phase:
            assert previous_actual_ns is not None
            # If hardware or Linux falls behind, preserve the minimum step
            # interval instead of bursting late commands to catch up.
            minimum_gap_ns = round((command.at_s - previous_command.at_s) * 1e9)
            deadline = max(deadline, previous_actual_ns + minimum_gap_ns)
        if previous_command is None and prepare_motion is not None:
            # Request fast polling before motion, allowing the child to finish a
            # slow sleep and receive the pipe message before the first command.
            prepare_at = deadline-round(FAST_READ_LEAD_S*1e9)
            while clock() < prepare_at:
                if not alive():
                    raise RuntimeError("Camera recorder stopped before motion preparation")
                pause(min(.05,(prepare_at-clock())/1e9))
            if not alive():
                raise RuntimeError("Camera recorder stopped before fast-read request")
            prepare_motion()
        while clock() < deadline:
            if not alive():
                raise RuntimeError("Camera recorder stopped during servo schedule")
            pause(min(0.05, (deadline - clock()) / 1e9))
        if not alive():
            raise RuntimeError("Camera recorder stopped before servo command")
        before_ns = clock()
        servos[command.axis].angle(command.angle_deg)
        issued.append(dict(**asdict(command), host_command_ns=before_ns))
        last_angle[command.axis] = command.angle_deg
        previous_command, previous_actual_ns = command, clock()
    return issued


def phase_report(
    phases: Sequence[Phase],
    issued: Sequence[dict[str, object]],
    metadata: dict[str, object],
    motion_rows: Sequence[dict[str, str]],
    frame_rows: Sequence[dict[str, str]],
    patch_rows: Sequence[dict[str, object]],
) -> list[dict[str, object]]:
    """Separate visual rejection rate from possible camera-PTS timing gaps.

    Args:
        phases (Sequence[Phase]): Planned axis/speed bands.
        issued (Sequence[dict[str, object]]): Actual monotonic servo command log.
        metadata (dict[str, object]): Complete combined-capture metadata.
        motion_rows (Sequence[dict[str, str]]): visual_motion CSV rows.
        frame_rows (Sequence[dict[str, str]]): Decoded-frame receipt/PTS CSV rows.
        patch_rows (Sequence[dict[str, object]]): Rejected-pair diagnostics.

    Returns:
        list[dict[str, object]]: Per-band counts with honest clock and loss labels.
    """
    origin_ns = int(metadata["origin_monotonic_ns"])
    cue_s = float(metadata["recording_cue_host_s"])
    results = []
    for phase in phases:
        phase_commands = [row for row in issued if row["phase"] == phase.name]
        if not phase_commands:
            raise ValueError(f"No issued commands for {phase.name}")
        start_s = (int(phase_commands[0]["host_command_ns"]) - origin_ns) / 1e9 - cue_s
        end_s = (int(phase_commands[-1]["host_command_ns"]) - origin_ns) / 1e9 - cue_s
        visual = [
            row for row in motion_rows
            if start_s <= float(row["host_after_cue_s"]) <= end_s
        ]
        rejected = sum(row["dx_pixels"] == "" for row in visual)

        # A PTS interval above 1.5 × the requested 30-fps interval is only a
        # timing-gap flag. It cannot distinguish a sensor loss from other delay.
        frame_intervals = []
        for first, second in zip(frame_rows, frame_rows[1:]):
            midpoint = (
                float(first["host_receipt_s"]) + float(second["host_receipt_s"])
            ) / 2 - cue_s
            if start_s <= midpoint <= end_s:
                frame_intervals.append(float(second["camera_pts_s"]) - float(first["camera_pts_s"]))
        pts_gaps = sum(dt > 1.5 / 30 for dt in frame_intervals)
        patches = [
            row for row in patch_rows
            if start_s <= float(row["host_after_cue_s"]) <= end_s
        ]
        failed_checks = Counter(
            check for row in patches for patch in row["patches"]
            for check in patch["failed_checks"]
        )
        gyro_y = [abs(float(row["gy_dps"])) for row in visual if row["gy_dps"]]
        gyro_norm = [
            math.sqrt(sum(float(row[key]) ** 2 for key in ("gx_dps", "gy_dps", "gz_dps")))
            for row in visual
            if all(row.get(key) for key in ("gx_dps", "gy_dps", "gz_dps"))
        ]
        results.append(dict(
            phase=phase.name,
            axis=phase.axis,
            commanded_speed_deg_s=phase.speed_deg_s,
            commanded_amplitude_deg=phase.amplitude_deg,
            first_command_after_cue_s=start_s,
            last_command_after_cue_s=end_s,
            visual_pairs=len(visual),
            visual_rejected_pairs=rejected,
            visual_rejection_fraction=rejected / len(visual) if visual else None,
            pts_intervals=len(frame_intervals),
            pts_gap_flags=pts_gaps,
            pts_gap_fraction=pts_gaps / len(frame_intervals) if frame_intervals else None,
            max_abs_interpolated_gyro_y_dps=max(gyro_y) if gyro_y else None,
            max_interpolated_gyro_norm_dps=max(gyro_norm) if gyro_norm else None,
            rejected_pair_patch_checks=dict(failed_checks),
        ))
    return results


def capture_command(args: argparse.Namespace, duration: float) -> list[str]:
    """Build the existing recorder's command with the selected IMU sleep.

    Args:
        args (argparse.Namespace): Parsed camera/output, policy, idle/active sleeps
            and scene options.
        duration (float): Capture duration in seconds from the unchanged servo schedule.

    Returns:
        list[str]: Subprocess arguments; building them never opens hardware.
    """
    # combined_capture owns polling and records --interval as imu_sleep_seconds
    # in metadata.json. Read duration and scheduling add to this requested sleep.
    command = [
        sys.executable, "-u", "src/recording/combined_capture.py",
        "--device", args.device, "--seconds", f"{duration:.2f}",
        "--interval", str(args.imu_interval),
        "--output", str(args.output),
        "--notes", "Guarded servo test; sequential pan/tilt, "
        + ("quick pan 0 to -40 to +40 degrees" if args.quick_pan else
           "wide pan commission ±20 degrees" if args.wide_pan else
           "commission ±2 degrees" if args.commission else "series ±8/±6 degrees")
        + f"; scene={args.scene}; power={args.power}; cooling={args.cooling}",
    ]
    if getattr(args, "measure_resources", False):
        command.append("--measure-resources")
    if getattr(args, "imu_policy", "fixed") == "command-driven":
        command.extend(["--imu-policy", "command-driven", "--active-interval",
                        str(args.imu_active_interval)])
    return command


def run_capture(args: argparse.Namespace, commands: list[ServoCommand], phases: list[Phase],
                duration: float) -> Path:
    """Arm servos, capture one bounded run, and save actual command timestamps.

    Args:
        args (argparse.Namespace): Validated real-run CLI options.
        commands (list[ServoCommand]): Bounded command schedule.
        phases (list[Phase]): Named speed windows for subsequent reporting.
        duration (float): Requested recording duration after first frame.

    Returns:
        Path: New combined-capture directory after a complete run.
    """
    # The import and the first physical command occur only in explicitly armed
    # mode. The user must watch this 0° initialization and abort if anything binds.
    from fusion_hat.servo import Servo

    print("Armed. Ctrl+C within 3 seconds to cancel before servo initialization.", flush=True)
    time.sleep(3)
    servos = {"pan": Servo(args.pan_channel), "tilt": Servo(args.tilt_channel)}
    servos["pan"].angle(0)
    servos["tilt"].angle(0)
    time.sleep(1)

    command = capture_command(args, duration)
    adaptive = getattr(args, "imu_policy", "fixed") == "command-driven"
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               stdin=subprocess.PIPE if adaptive else subprocess.DEVNULL,
                               text=True, bufsize=1,
                               env={**os.environ, "PYTHONPATH": "src"})
    cue = threading.Event()

    def read_capture_output() -> None:
        """Relay child output and signal when its recording window begins."""
        assert process.stdout is not None
        for line in process.stdout:
            print(line, end="", flush=True)
            if line.startswith("RECORDING for "):
                cue.set()

    reader = threading.Thread(target=read_capture_output, daemon=True)
    reader.start()
    issued: list[dict[str, object]] = []
    policy_requests: list[dict[str, object]] = []

    def request_fast_reads() -> None:
        """Signal the child recorder before the first physical servo command.

        Args:
            None.

        Returns:
            None: Writes one small pipe message and logs its send timestamp.
        """
        assert process.stdin is not None
        process.stdin.write("fast\n")
        process.stdin.flush()
        policy_requests.append(dict(mode="fast",host_command_ns=time.monotonic_ns()))
    try:
        startup_deadline = time.monotonic() + 15
        while not cue.wait(0.05):
            if process.poll() is not None:
                raise RuntimeError("Capture exited before its recording cue")
            if time.monotonic() > startup_deadline:
                raise RuntimeError("No camera recording cue within 15 seconds")
        observed_ns = time.monotonic_ns()
        execute_commands(commands, servos, observed_ns,
                         alive=lambda: process.poll() is None, issued=issued,
                         prepare_motion=request_fast_reads if adaptive else None)
        if adaptive:
            # The whole sequence remains fast, including command pauses. Wait
            # after actual command completion, so late commands cannot outlast
            # a purely precomputed high-rate window.
            settle_until = time.monotonic()+FAST_READ_SETTLE_S
            while time.monotonic() < settle_until:
                if process.poll() is not None:
                    raise RuntimeError("Recorder stopped before settling completed")
                time.sleep(min(.05,max(0.,settle_until-time.monotonic())))
            assert process.stdin is not None
            process.stdin.write("idle\n")
            process.stdin.flush()
            policy_requests.append(dict(mode="idle",host_command_ns=time.monotonic_ns()))
        process.wait(timeout=FINAL_STILL_S + BETWEEN_PHASES_S + 15)
        reader.join(timeout=3)
        if process.returncode != 0:
            raise RuntimeError("Camera/IMU capture failed; inspect its metadata and log")
    finally:
        # On interruption or fault, do not command an automatic return through
        # a possible obstruction. Stop the recorder and issue no more angles.
        if process.poll() is None:
            process.send_signal(signal.SIGINT)
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        reader.join(timeout=3)
        if process.stdin is not None:
            try:
                process.stdin.close()
            except OSError:
                pass  # An exited child may have closed its read end; retain the logs.
        if args.output.exists():
            (args.output / "servo_commands.json").write_text(
                json.dumps(dict(planned_phases=[asdict(p) for p in phases],
                                issued_commands=issued,
                                imu_policy_requests=policy_requests,
                                imu_policy=dict(mode="command-driven" if adaptive else "fixed",
                                                fast_lead_s=FAST_READ_LEAD_S,
                                                fast_settle_s=FAST_READ_SETTLE_S)), indent=2) + "\n"
            )
    return args.output


def analyze_run(output: Path, phases: Sequence[Phase]) -> dict[str, object]:
    """Use existing offline tools, then summarize each commanded speed phase.

    Args:
        output (Path): Complete combined-capture run directory.
        phases (Sequence[Phase]): Original deterministic schedule.

    Returns:
        dict[str, object]: Read-only quality metrics saved in the run directory.
    """
    analysis = output.with_name(output.name + "-analysis")
    patch = output.with_name(output.name + "-patch")
    for module, options in (
        ("recording.visual_motion", [str(output), "--output", str(analysis)]),
        ("recording.patch_diagnostics", ["--video", str(output / "camera.mkv"),
                                         "--analysis", str(analysis), "--output", str(patch)]),
    ):
        subprocess.run([sys.executable, "-m", module, *options], check=True,
                       env={**os.environ, "PYTHONPATH": "src"})
    metadata = json.loads((output / "metadata.json").read_text())
    if metadata["status"] != "complete":
        raise ValueError("Capture did not complete")
    issued = json.loads((output / "servo_commands.json").read_text())["issued_commands"]
    with (analysis / "motion.csv").open(newline="") as handle:
        motion_rows = list(csv.DictReader(handle))
    with (output / "frames.csv").open(newline="") as handle:
        frame_rows = list(csv.DictReader(handle))
    with (patch / "pairs.jsonl").open() as handle:
        patch_rows = [json.loads(line) for line in handle]
    revision = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True,
                              text=True, check=True).stdout.strip()
    result = dict(
        scope=("Commanded servo speed versus visual rejection, not true shaft "
               "speed or sensor frame loss"),
        git_commit=revision,
        host=metadata["host"],
        python=metadata["python"],
        notes=metadata["notes"],
        capture_status=metadata["status"],
        requested_camera_mode=metadata["requested_mode"],
        imu_sleep_seconds=metadata["imu_sleep_seconds"],
        imu_policy=metadata.get("imu_policy", "fixed"),
        decoded_frames=metadata["decoded_frames"],
        timestamp_scope=metadata["timestamp_scope"],
        phases=phase_report(phases, issued, metadata, motion_rows, frame_rows, patch_rows),
    )
    if metadata.get("measure_resources"):
        resources = json.loads((output / "resources.json").read_text())
        if resources["status"] != "complete":
            raise ValueError("Resource measurement incomplete; inspect resources.json")
        result["resource_measurement"] = {key: value for key, value in resources.items()
                                          if key != "samples"}
    (output / "servo_quality_summary.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def main(argv: Sequence[str] | None = None) -> int:
    """Preview a safe schedule or explicitly arm one automated Pi experiment.

    Args:
        argv (Sequence[str] | None): CLI tokens, or None for system arguments.

    Returns:
        int: Exit code; a dry run never imports a servo or camera driver.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--axes", choices=("pan", "tilt", "both"), default="both")
    parser.add_argument("--commission", action="store_true",
                        help="one supervised ±2° phase at 5 commanded °/s")
    parser.add_argument("--wide-pan", action="store_true",
                        help="opt-in pan-only commissioning sweep at ±20°")
    parser.add_argument("--quick-pan", action="store_true",
                        help="opt-in pan-only 0° → −40° → +40° at 20 commanded °/s")
    parser.add_argument("--execute", action="store_true", help="enable real Pi hardware")
    parser.add_argument("--confirm-centered", action="store_true")
    parser.add_argument("--confirm-cable-slack", action="store_true")
    parser.add_argument("--confirm-wide-pan-clearance", action="store_true",
                        help="confirm clear pan travel and cable slack through ±20°")
    parser.add_argument("--confirm-quick-pan-clearance", action="store_true",
                        help="confirm clear pan travel and cable slack through ±40°")
    parser.add_argument("--confirm-commissioned", action="store_true",
                        help="acknowledge successful pan and tilt commissioning before full run")
    parser.add_argument("--pan-channel", type=int)
    parser.add_argument("--tilt-channel", type=int)
    parser.add_argument("--device")
    parser.add_argument("--imu-interval", type=positive_interval, default=0.05,
                        help="seconds to sleep after each IMU read (default: 0.05); not a fixed sample period")
    parser.add_argument("--imu-policy", choices=("fixed", "command-driven"), default="fixed")
    parser.add_argument("--imu-active-interval", type=positive_interval, default=0.01,
                        help="active sleep for command-driven policy (default: 0.01 seconds)")
    parser.add_argument("--measure-resources", action="store_true",
                        help="save capture-window CPU/RSS observations to resources.json")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--scene", default="unknown")
    parser.add_argument("--power", default="unknown")
    parser.add_argument("--cooling", default="unknown")
    args = parser.parse_args(argv)
    if args.imu_policy == "command-driven" and args.imu_active_interval > args.imu_interval:
        parser.error("active IMU sleep must not exceed idle sleep")
    commands, phases, duration = build_schedule(
        args.axes, commission=args.commission, wide_pan=args.wide_pan,
        quick_pan=args.quick_pan,
    )
    print(f"Schedule: {len(commands)} 1° commands, {len(phases)} phases, {duration:.1f} s")
    print(f"IMU sleep: {args.imu_interval * 1000:g} ms after each read; measured rate also includes read time.")
    if args.imu_policy == "command-driven":
        print(f"Command-driven: {args.imu_active_interval*1000:g} ms active sleep, "
              f"{FAST_READ_LEAD_S:g} s lead and {FAST_READ_SETTLE_S:g} s settling.")
    for phase in phases:
        path = (f"0° → −{phase.amplitude_deg}° → +{phase.amplitude_deg}°"
                if args.quick_pan else f"±{phase.amplitude_deg}° → 0°")
        print(f"  {phase.name}: {path}, {phase.speed_deg_s} commanded °/s; "
              f"{phase.start_s:.1f}–{phase.end_s:.1f} s after cue")
    if not args.execute:
        print("DRY RUN ONLY: no camera, IMU, Fusion HAT import or servo commands.")
        return 0
    try:
        validate_arming(args)
        output = run_capture(args, commands, phases, duration)
        result = analyze_run(output, phases)
        print(json.dumps(result, indent=2))
        return 0
    except KeyboardInterrupt:
        print("Interrupted: no more angles sent. Servo may hold its last position; "
              "power down if binding.", file=sys.stderr)
        return 130
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        print(f"Servo quality run failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
