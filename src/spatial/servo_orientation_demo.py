"""One-shot, attended ±20° pan/tilt demonstration for the live IMU view.

Run the read-only live preview separately first. This command does not open the
camera, read the IMU, or expose servo controls over HTTP.
"""

from __future__ import annotations

import argparse
import base64
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import threading
import time
from typing import Callable, Protocol
from urllib.request import urlopen


PAN_CHANNEL = 2
TILT_CHANNEL = 3
LIMIT_DEG = 20
STEP_SECONDS = 0.1  # 1 commanded degree per 100 ms: at most 10 commanded °/s.
FINAL_SETTLE_SECONDS = 2.0
TELEMETRY_URL = "http://127.0.0.1:8765/api/telemetry"
FRAME_URL = "http://127.0.0.1:8765/api/frame"
FRAME_WIDTH = 320
FRAME_HEIGHT = 180
CHECKPOINT_NAMES = ("before_pan", "after_pan", "after_tilt")


class ServoPort(Protocol):
    """Only the existing Fusion HAT angle method is needed by this test."""

    def angle(self, degrees: int) -> None:
        """Command one servo position in degrees."""


@dataclass(frozen=True)
class Step:
    """One bounded motor command after the initial 0° center."""

    axis: str
    angle_deg: int
    due_s: float


def build_steps() -> list[Step]:
    """Make sequential pan and tilt paths: 0 → −20 → +20 → 0.

    Returns:
        list[Step]: 160 one-degree commands, with 2 s settling between axes.
    """
    steps: list[Step] = []
    due = 0.0
    for axis in ("pan", "tilt"):
        current = 0
        for target in (-LIMIT_DEG, LIMIT_DEG, 0):
            while current != target:
                current += 1 if target > current else -1
                due += STEP_SECONDS
                steps.append(Step(axis, current, due))
        due += 2.0
    return steps


def run_steps(
    steps: list[Step], servos: dict[str, ServoPort], *,
    clock: Callable[[], float] = time.monotonic,
    pause: Callable[[float], None] = time.sleep,
    on_command: Callable[[Step, float], None] | None = None,
) -> int:
    """Send one axis at a time, preserving step spacing if Linux runs late.

    Args:
        steps (list[Step]): Fixed, prevalidated center-bounded schedule.
        servos (dict[str, ServoPort]): Hardware servos or test doubles.
        clock (Callable[[], float]): Monotonic seconds for deadlines.
        pause (Callable[[float], None]): Sleep callback, injectable in tests.
        on_command (Callable[[Step, float], None] | None): Record each issued
            command and its host monotonic time; omitted in hardware-free tests.

    Returns:
        int: Number of issued 1° steps; interruption stops future commands.
    """
    last_angle = {"pan": 0, "tilt": 0}
    start = clock()
    previous_actual: float | None = None
    previous_due = 0.0
    for step in steps:
        if (step.axis not in last_angle or abs(step.angle_deg) > LIMIT_DEG or
                abs(step.angle_deg - last_angle[step.axis]) != 1 or
                step.due_s - previous_due < STEP_SECONDS - 1e-9):
            raise ValueError("Invalid servo schedule; no further commands sent")
        deadline = start + step.due_s
        if previous_actual is not None:
            deadline = max(deadline, previous_actual + step.due_s - previous_due)
        while clock() < deadline:
            pause(min(0.05, deadline - clock()))
        servos[step.axis].angle(step.angle_deg)
        actual = clock()
        if on_command is not None:
            on_command(step, actual)
        last_angle[step.axis] = step.angle_deg
        previous_actual = actual
        previous_due = step.due_s
    return len(steps)


def preview_snapshot() -> dict:
    """Read the existing local telemetry route without camera/image bytes."""
    with urlopen(TELEMETRY_URL, timeout=1.0) as response:
        return json.load(response)


def preview_frame() -> dict:
    """Read the existing display-size frame route, without opening the camera."""
    with urlopen(FRAME_URL, timeout=1.0) as response:
        return json.load(response)


def save_image_checkpoint(folder: Path, label: str) -> dict:
    """Save one fresh 320×180 grayscale preview frame and its host timing.

    Args:
        folder (Path): New ignored run directory for image/checkpoint logs.
        label (str): One of the three fixed still-point names.

    Returns:
        dict: JSON-ready image source, freshness and host-poll midpoint.
    """
    if label not in CHECKPOINT_NAMES:
        raise ValueError("Unknown image checkpoint")
    before = time.monotonic()
    snapshot = preview_frame()
    midpoint = (before + time.monotonic()) / 2
    age = snapshot.get("result_age_ms")
    if (snapshot.get("status") != "live" or snapshot.get("width") != FRAME_WIDTH or
            snapshot.get("height") != FRAME_HEIGHT or not isinstance(age, (int, float)) or
            not 0 <= age <= 300):
        raise ValueError(f"{label}: camera frame is unavailable or too old")
    encoded = snapshot.get("pixels_b64")
    if not isinstance(encoded, str):
        raise ValueError(f"{label}: missing grayscale pixels")
    try:
        pixels = base64.b64decode(encoded, validate=True)
    except ValueError as error:
        raise ValueError(f"{label}: invalid grayscale encoding") from error
    if len(pixels) != FRAME_WIDTH * FRAME_HEIGHT:
        raise ValueError(f"{label}: wrong grayscale byte count")
    name = f"{label}.pgm"
    (folder / name).write_bytes(f"P5\n{FRAME_WIDTH} {FRAME_HEIGHT}\n255\n".encode() + pixels)
    return {
        "label": label, "file": name, "host_poll_midpoint_s": midpoint,
        "frame_sequence": snapshot.get("sequence"), "frame_age_ms": age,
        "imu_poll_sleep_ms": snapshot.get("imu_poll_sleep_ms"),
        "orientation_status": snapshot.get("imu", {}).get("relative_orientation", {}).get("status"),
        "timing_scope": "host observation; image and IMU are not exposure-synchronized",
    }


def output_folder(selected: Path | None) -> Path:
    """Resolve a new ignored recordings directory; never overwrite a prior run.

    Args:
        selected (Path | None): Explicit output or a generated timestamped name.

    Returns:
        Path: Validated path below this checkout's recordings directory.
    """
    if selected is None:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        selected = Path("recordings") / f"servo-orientation-{stamp}"
    root = (Path.cwd() / "recordings").resolve()
    path = selected.resolve()
    if path == root or not path.is_relative_to(root) or path.exists():
        raise ValueError("Output must be a new directory under recordings/")
    return path


def has_settled_sample(final_command_s: float | None,
                       last_ready_sample_s: float | None) -> bool:
    """Check that live orientation was captured at least one second after stop.

    Args:
        final_command_s (float | None): Host time of final issued servo command.
        last_ready_sample_s (float | None): Host time of latest live/ready poll.

    Returns:
        bool: Whether the final position has a post-command observation.
    """
    return (final_command_s is not None and last_ready_sample_s is not None
            and last_ready_sample_s >= final_command_s + 1.0)


def record_telemetry(stop: threading.Event, path: Path, counts: dict) -> None:
    """Poll all non-image preview fields during motion and save timestamped JSONL.

    Args:
        stop (threading.Event): End signal from the motor-owning main thread.
        path (Path): New telemetry.jsonl within this run's output directory.
        counts (dict): Shared sample counts, peak and last orientation, and
            logger failure status.
    """
    try:
        with path.open("w") as log:
            while not stop.is_set():
                before = time.monotonic()
                try:
                    snapshot = preview_snapshot()
                    row = {"host_poll_midpoint_s": (before + time.monotonic()) / 2,
                           "telemetry": snapshot}
                    orientation = snapshot.get("imu", {}).get("relative_orientation", {})
                    if snapshot.get("status") == "live" and orientation.get("status") == "ready":
                        counts["ready_samples"] += 1
                        angle = orientation.get("angle_deg")
                        if angle is not None and angle > counts["peak_angle_deg"]:
                            counts["peak_angle_deg"] = angle
                        counts["final_orientation"] = orientation
                        counts["last_ready_sample_s"] = row["host_poll_midpoint_s"]
                    counts["samples"] += 1
                except Exception as error:
                    row = {"host_poll_midpoint_s": (before + time.monotonic()) / 2,
                           "error": str(error)}
                    counts["errors"] += 1
                log.write(json.dumps(row, allow_nan=False) + "\n")
                log.flush()
                stop.wait(0.05)
    except Exception as error:
        counts["logger_error"] = str(error)


def main() -> int:
    """Arm and execute one supervised sweep without opening camera or IMU.

    Returns:
        int: Zero on a full center return, nonzero on interrupted/failed motion.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", help="actually command the servos")
    parser.add_argument("--confirm-centered", action="store_true", help="both axes' 0° positions are safe")
    parser.add_argument("--confirm-clearance", action="store_true", help="both axes and cables are clear through ±20°")
    parser.add_argument("--output", type=Path,
                        help="new recordings/ directory for servo commands and sampled non-image preview telemetry")
    args = parser.parse_args()
    steps = build_steps()
    print("Pan 0 → −20 → +20 → 0, then tilt 0 → −20 → +20 → 0; "
          f"{len(steps)} one-degree commands at ≤10 commanded °/s.", flush=True)
    if not args.execute:
        print("No motors commanded. Add --execute and both confirmation flags for the real run.")
        return 0
    if not args.confirm_centered or not args.confirm_clearance:
        parser.error("Real motion requires --confirm-centered --confirm-clearance")

    # Require a live, ready quaternion before actuating. Repeated image-free
    # snapshots let the user inspect sampled peak and return values afterward.
    try:
        folder = output_folder(args.output)
        first = preview_snapshot()
        if first.get("status") != "live" or first.get("imu", {}).get(
            "relative_orientation", {}
        ).get("status") != "ready":
            raise ValueError("Start the quaternion preview and wait for camera/IMU ready")
        imu_sleep_ms = first.get("imu_poll_sleep_ms")
        if imu_sleep_ms not in (10, 50):
            raise ValueError("Restart the updated preview with --imu-sleep-ms 10 or 50")
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(1, f"Servo test preflight failed: {error}\n")

    # The user observes the rig during a cancel window. Importing the vendor
    # driver and writing 0° only happens after explicit arming.
    stop_log = threading.Event()
    counts = {"samples": 0, "ready_samples": 0, "errors": 0,
              "peak_angle_deg": 0.0, "final_orientation": None,
              "last_ready_sample_s": None, "logger_error": None}
    started = time.monotonic()
    status = "partial"
    failure = None
    exit_code = 1
    logger: threading.Thread | None = None
    final_command_s: float | None = None
    checkpoints: list[str] = []
    folder.mkdir(parents=True)
    commands_path = folder / "servo_commands.jsonl"
    try:
        with commands_path.open("w") as command_log, (folder / "checkpoints.jsonl").open("w") as checkpoint_log:
            def save_command(axis: str, angle: int, actual: float) -> None:
                """Flush a motor command so even an interrupted run keeps its history."""
                nonlocal final_command_s
                command_log.write(json.dumps({"host_command_s": actual,
                                              "axis": axis, "angle_deg": angle}) + "\n")
                command_log.flush()
                final_command_s = actual

            def save_checkpoint(label: str) -> None:
                """Persist a still-point image and its source/timing row."""
                row = save_image_checkpoint(folder, label)
                checkpoint_log.write(json.dumps(row, allow_nan=False) + "\n")
                checkpoint_log.flush()
                checkpoints.append(label)

            def after_step(step: Step, actual: float) -> None:
                """Use the existing pan-to-tilt pause for a settled pan image."""
                save_command(step.axis, step.angle_deg, actual)
                if step.axis == "pan" and step.angle_deg == 0:
                    time.sleep(1.4)
                    save_checkpoint("after_pan")

            logger = threading.Thread(target=record_telemetry,
                args=(stop_log, folder / "telemetry.jsonl", counts), daemon=True)
            logger.start()
            print(f"Saving non-image telemetry and motor commands to {folder}", flush=True)
            print("Armed. Ctrl+C within 3 seconds to cancel before servo initialization.", flush=True)
            time.sleep(3)
            from fusion_hat.servo import Servo

            servos: dict[str, ServoPort] = {
                "pan": Servo(PAN_CHANNEL), "tilt": Servo(TILT_CHANNEL),
            }
            for axis in ("pan", "tilt"):
                servos[axis].angle(0)
                save_command(axis, 0, time.monotonic())
            print("Centered both axes. Hold still for 2 seconds; then pan starts.", flush=True)
            time.sleep(2)
            save_checkpoint("before_pan")
            count = run_steps(steps, servos, on_command=after_step)
            print("Final 0° command sent; logging two seconds of settled orientation.", flush=True)
            time.sleep(FINAL_SETTLE_SECONDS)
            save_checkpoint("after_tilt")
            status = "complete"
            print(f"Completed {count} commands; pan and tilt returned to commanded 0°.", flush=True)
            exit_code = 0
    except KeyboardInterrupt:
        failure = "interrupted"
        print("Interrupted: no further commands. A servo may hold its last position; "
              "inspect the rig before moving it.", flush=True)
        exit_code = 130
    except Exception as error:
        failure = str(error)
        print(f"Servo test stopped: {error}. A servo may hold its last position.", flush=True)
        exit_code = 1
    finally:
        stop_log.set()
        if logger is not None:
            logger.join(timeout=2)
        if logger is not None and logger.is_alive():
            counts["logger_error"] = "logger did not stop within two seconds"
        settled_sample = has_settled_sample(final_command_s, counts["last_ready_sample_s"])
        if status == "complete" and (counts["logger_error"] or not settled_sample or
                                     tuple(checkpoints) != CHECKPOINT_NAMES):
            status = "telemetry_incomplete"
            failure = (counts["logger_error"] or
                       "missing settled orientation or camera checkpoint")
            exit_code = 1
        (folder / "metadata.json").write_text(json.dumps({
            "status": status, "error": failure,
            "started_monotonic_s": started, "ended_monotonic_s": time.monotonic(),
            "pan_channel": PAN_CHANNEL, "tilt_channel": TILT_CHANNEL,
            "commanded_limit_deg": LIMIT_DEG, "minimum_step_seconds": STEP_SECONDS,
            "telemetry_url": TELEMETRY_URL,
            "image_url": FRAME_URL,
            "imu_poll_sleep_ms": imu_sleep_ms,
            "image_checkpoints": checkpoints,
            "image_shape": f"{FRAME_WIDTH}x{FRAME_HEIGHT} grayscale PGM",
            "telemetry_samples": counts["samples"],
            "ready_orientation_samples": counts["ready_samples"],
            "telemetry_errors": counts["errors"], "logger_error": counts["logger_error"],
            "peak_sampled_angle_deg": counts["peak_angle_deg"],
            "final_sampled_orientation": counts["final_orientation"],
            "final_command_monotonic_s": final_command_s,
            "last_ready_sample_monotonic_s": counts["last_ready_sample_s"],
            "settled_final_sample": settled_sample,
            "final_settle_seconds": FINAL_SETTLE_SECONDS,
            "telemetry_poll_interval_seconds": 0.05,
            "timestamp_scope": "Pi host monotonic command times and HTTP poll midpoints; not camera exposure synchronization",
        }, indent=2) + "\n")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
