"""Record local MJPEG video and raw IMU data; timestamps are not synchronized."""

# Postpone type evaluation so optional drivers/libraries stay optional.
from __future__ import annotations

# Describe data contracts without adding third-party runtime dependencies.
from typing import Callable, Sequence, TYPE_CHECKING

# Resolve documentation-only types for editors; this block does not run in production.
if TYPE_CHECKING:
    # Reuse the documented frame, sensor and report vocabulary for type checking.
    from _contracts import Sensor


# Parse and validate explicit command-line options.
import argparse

# Read/write explicit numeric columns for reproducible offline analysis.
import csv

# Read or serialize metadata and browser/report payloads.
import json

# Validate finite numbers and perform scalar numerical calculations.
import math

# Work with explicit filesystem paths rather than shell expansions.
from pathlib import Path

# Record the operating system/runtime context of a measured run.
import platform

# Extract frame fields only from matching FFmpeg diagnostic lines.
import re

# Check whether an existing external tool is available on PATH.
import shutil

# Request graceful FFmpeg shutdown so the video container can be finalized.
import signal

# Run existing FFmpeg/ffprobe/Git tools with explicit argument lists.
import subprocess

# Report failures on stderr and handle command-line exit behavior.
import sys

# Coordinate independent workers using threads, locks, conditions and events.
import threading

# Measure host intervals and provide bounded polling pauses.
import time


# Prepare FRAME_RE for the next step using the values calculated so far.
FRAME_RE = re.compile(r"\bn:\s*(\d+)\s+pts:\s*\S+\s+pts_time:\s*([-+\d.eE]+)")


def parse_frame(line: str) -> tuple[int, float] | None:
    """Parse an FFmpeg showinfo frame number and finite presentation timestamp.

    Args:
        line (str): One FFmpeg diagnostic line, not binary image bytes.

    Returns:
        tuple[int, float] | None: Frame index and camera PTS seconds, or None for
            other/invalid log lines.
    """
    # Choose the next branch using 'Parsed_showinfo' not in line.
    if "Parsed_showinfo" not in line:
        # Represent missing or rejected data explicitly as None, not a measured zero.
        return None
    # Prepare match for the next step using the values calculated so far.
    match = FRAME_RE.search(line)
    # Choose the next branch using not match.
    if not match:
        # Represent missing or rejected data explicitly as None, not a measured zero.
        return None
    # Prepare number, pts for the next step using the values calculated so far.
    number, pts = int(match[1]), float(match[2])
    # Return the documented result to the caller without starting another operation.
    return (number, pts) if math.isfinite(pts) else None


def positive(value: str) -> float:
    """Validate a finite positive duration or interval from the command line.

    Args:
        value (str): Command-line text to convert and validate.

    Returns:
        float: Positive number; rejects zero, negative or nonfinite values.
    """
    # Convert command-line or parsed input to a number before validating its allowed range.
    number = float(value)
    # Reject this invalid input before it can produce misleading output.
    if not math.isfinite(number) or number <= 0:
        # Stop this operation with an explicit error rather than publishing invalid data.
        raise argparse.ArgumentTypeError("must be finite and greater than zero")
    # Return the documented result to the caller without starting another operation.
    return number


def read_row(
    sensor: Sensor, origin_ns: int, clock: Callable[[], int] = time.monotonic_ns
) -> list[float]:
    """Read an IMU sample and express its midpoint relative to this recording's origin.

    Args:
        sensor (Sensor): Read-only object implementing read_raw: acceleration g, gyro
            degrees/s, temperature C.
        origin_ns (int): Shared host monotonic origin in integer nanoseconds.
        clock (Callable[[], int]): Zero-argument clock returning integer monotonic
            nanoseconds.

    Returns:
        list[float]: Midpoint seconds, read-duration seconds, XYZ g and XYZ degrees/s.
    """
    # Read the host clock immediately before the sensor call.
    before = clock()
    # Read acceleration and angular rate; temperature is not recorded here.
    accel, gyro, _temperature = sensor.read_raw()
    # Read the host clock immediately after the sensor call.
    after = clock()
    # Reject this invalid input before it can produce misleading output.
    if (
        len(accel) != 3
        or len(gyro) != 3
        or not all(math.isfinite(value) for value in (*accel, *gyro))
    ):
        # Stop this operation with an explicit error rather than publishing invalid data.
        raise ValueError("IMU returned invalid axes")
    # Store host-relative seconds followed by driver-unit acceleration and angular rates.
    return [
        (before + after) / 2e9 - origin_ns / 1e9,
        (after - before) / 1e9,
        *accel,
        *gyro,
    ]


def camera_command(device: str, video: Path) -> list[str]:
    """Build dual FFmpeg outputs: compressed video copy and decoded-frame timing logs.

    Args:
        device (str): Verified V4L2 path such as /dev/video0; demo mode does not read
            it.
        video (Path): New local video output path passed to FFmpeg with no-overwrite
            enabled.

    Returns:
        list[str]: Argument list with no overwrite and 720p MJPEG/30 fps request.
    """
    # Return the documented result to the caller without starting another operation.
    return [
        "ffmpeg",
        "-hide_banner",
        "-nostdin",
        "-nostats",
        "-loglevel",
        "info",
        "-n",
        "-f",
        "v4l2",
        "-input_format",
        "mjpeg",
        "-video_size",
        "1280x720",
        "-framerate",
        "30",
        "-i",
        device,
        "-map",
        "0:v:0",
        "-c:v",
        "copy",
        str(video),
        "-map",
        "0:v:0",
        "-vf",
        "showinfo=checksum=0",
        "-fps_mode",
        "passthrough",
        "-f",
        "null",
        "-",
    ]


def stop_camera(process: subprocess.Popen[str]) -> None:
    """Interrupt FFmpeg so its container can finish, escalating only on timeout.

    Args:
        process (subprocess.Popen[str]): FFmpeg child handle whose pipes/lifetime belong
            to this caller.

    Returns:
        None: raises RuntimeError after forced shutdown because video may be incomplete.
    """
    # Handle absent data explicitly instead of interpreting it as a valid zero.
    if process.poll() is None:
        # Call process.send_signal for this step; its contract describes the result or side
        # effect.
        process.send_signal(signal.SIGINT)
    # Keep failure handling alongside the operation so cleanup/status remains explicit.
    try:
        # Pause for the configured interval; read/compute overhead is additional time.
        process.wait(timeout=5)
    # Handle this failure without losing the error or skipping the enclosing cleanup.
    except subprocess.TimeoutExpired:
        # Call process.kill for this step; its contract describes the result or side effect.
        process.kill()
        # Pause for the configured interval; read/compute overhead is additional time.
        process.wait(timeout=5)
        # Stop this operation with an explicit error rather than publishing invalid data.
        raise RuntimeError("FFmpeg required forced shutdown; video may be incomplete")


def record(sensor: Sensor, args: argparse.Namespace) -> int:
    """Save one new camera/IMU run with metadata that records partial failures honestly.

    Args:
        sensor (Sensor): Read-only object implementing read_raw: acceleration g, gyro
            degrees/s, temperature C.
        args (argparse.Namespace): Parsed command-line options (or a compatible test
            fixture); see main for fields.

    Returns:
        int: Exit code 0 for a complete run or 1 for failure; writes local recording
            files.
    """
    # Prepare output for the next step using the values calculated so far.
    output = args.output
    # Create the explicit output/test directory using the existing overwrite policy.
    output.mkdir(parents=True, exist_ok=False)
    # Choose a shared monotonic nanosecond origin for this recording only.
    origin = time.monotonic_ns()
    # Build the explicit external-tool argument list with the existing settings.
    command = camera_command(args.device, output / "camera.mkv")
    # Record settings and timing scope so a saved run can be interpreted later.
    metadata = {
        "status": "incomplete",
        "host": platform.platform(),
        "python": platform.python_version(),
        "notes": args.notes,
        "requested_mode": "1280x720 MJPEG 30 fps",
        "requested_seconds_after_first_frame": args.seconds,
        "imu_sleep_seconds": args.interval,
        "origin_monotonic_ns": origin,
        "started_unix_seconds": time.time(),
        "command": command,
        "timestamp_scope": "camera PTS separate; host receipts and IMU read midpoints share monotonic clock",
        "calibration": "raw SH3001 driver units; no saved corrections applied",
    }
    # Persist this explicitly requested local output; raw artifacts stay outside Git.
    (output / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
    # Signal when the first decoded camera timestamp has arrived.
    first_frame = threading.Event()
    # Collect frame-log rows used for saved counts and timing checks.
    frames = []
    # Transfer diagnostic-reader failures back to the controlling thread.
    reader_errors = []
    # Track how many sensor rows were actually written.
    imu_count = 0
    # Hold the child-process handle so its lifecycle can be managed safely.
    process = None
    # Keep the diagnostic-thread handle for cleanup even after partial startup.
    reader = None
    # Remember the earliest failure instead of reporting a partial run as complete.
    failure = None

    def drain_camera() -> None:
        """Drain showinfo diagnostics while saving frame receipts and waking the recorder.

        Args:
            None.

        Returns:
            None: writes the enclosing run's log/CSV and collects reader errors.
        """
        # Keep failure handling alongside the operation so cleanup/status remains explicit.
        try:
            # Keep these resources scoped so they are released even if the operation fails.
            with (output / "ffmpeg.log").open("w") as log, (output / "frames.csv").open(
                "w", newline=""
            ) as handle:
                # Serialize named measurements as CSV rather than conflating them with image
                # bytes.
                writer = csv.writer(handle)
                # Write the documented CSV fields in a reproducible column order.
                writer.writerow(["frame_index", "camera_pts_s", "host_receipt_s"])
                # Process each line in the selected collection.
                for line in process.stderr:
                    # Stamp host receipt; this is not the camera sensor exposure time.
                    received = (time.monotonic_ns() - origin) / 1e9
                    # Call log.write for this step; its contract describes the result or side
                    # effect.
                    log.write(line)
                    # Hold a local reference to the latest slot so replacement cannot change
                    # this work item.
                    frame = parse_frame(line)
                    # Choose the next branch using frame is not None.
                    if frame is not None:
                        # Prepare row for the next step using the values calculated so far.
                        row = [*frame, received]
                        # Write the documented CSV fields in a reproducible column order.
                        writer.writerow(row)
                        # Retain this item/chunk for the current calculation or bounded history.
                        frames.append(row)
                        # Signal waiting work through the shared event rather than a busy loop.
                        first_frame.set()
        # Handle this failure without losing the error or skipping the enclosing cleanup.
        except Exception as error:
            # Retain this item/chunk for the current calculation or bounded history.
            reader_errors.append(str(error))

    # Keep failure handling alongside the operation so cleanup/status remains explicit.
    try:
        # Hold the child-process handle so its lifecycle can be managed safely.
        process = subprocess.Popen(
            command, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True
        )
        # Keep the diagnostic-thread handle for cleanup even after partial startup.
        reader = threading.Thread(target=drain_camera)
        # Start the worker so it can run independently of the caller's next step.
        reader.start()
        # Explain the current result, progress or failure in the terminal.
        print("Starting camera; remain still until RECORDING appears.", flush=True)
        # Start the deadline for receiving the first decoded frame.
        startup = time.monotonic()
        # Set the recording end time only after the first frame cue.
        deadline = None
        # Keep these resources scoped so they are released even if the operation fails.
        with (output / "imu.csv").open("w", newline="") as handle:
            # Serialize named measurements as CSV rather than conflating them with image bytes.
            writer = csv.writer(handle)
            # Write the documented CSV fields in a reproducible column order.
            writer.writerow(
                [
                    "host_read_midpoint_s",
                    "read_duration_s",
                    "ax_g",
                    "ay_g",
                    "az_g",
                    "gx_dps",
                    "gy_dps",
                    "gz_dps",
                ]
            )
            # Repeat until the stop signal, deadline or explicit exit condition is reached.
            while True:
                # Read host monotonic time for this stage's timing boundary.
                now = time.monotonic()
                # Reject this invalid input before it can produce misleading output.
                if reader_errors:
                    # Stop this operation with an explicit error rather than publishing invalid
                    # data.
                    raise RuntimeError(reader_errors[0])
                # Reject this invalid input before it can produce misleading output.
                if process.poll() is not None:
                    # Stop this operation with an explicit error rather than publishing invalid
                    # data.
                    raise RuntimeError("FFmpeg exited early; inspect ffmpeg.log")
                # Handle absent data explicitly instead of interpreting it as a valid zero.
                if deadline is None and first_frame.is_set():
                    # Set the recording end time only after the first frame cue.
                    deadline = now + args.seconds
                    # Prepare metadata['recording_cue_host_s'] for the next step using the
                    # values calculated so far.
                    metadata["recording_cue_host_s"] = now - origin / 1e9
                    # Explain the current result, progress or failure in the terminal.
                    print(f"RECORDING for {args.seconds:g} seconds.", flush=True)
                # Choose the next branch using deadline is not None and now >= deadline.
                if deadline is not None and now >= deadline:
                    # Leave this loop; the enclosing cleanup/status code still runs.
                    break
                # Reject this invalid input before it can produce misleading output.
                if deadline is None and now - startup > 10:
                    # Stop this operation with an explicit error rather than publishing invalid
                    # data.
                    raise RuntimeError("No decoded camera frame within 10 seconds")
                # Write the documented CSV fields in a reproducible column order.
                writer.writerow(read_row(sensor, origin))
                # Track how many sensor rows were actually written.
                imu_count += 1
                # Pause for the configured interval; read/compute overhead is additional time.
                time.sleep(args.interval)
    # Handle this failure without losing the error or skipping the enclosing cleanup.
    except KeyboardInterrupt:
        # Remember the earliest failure instead of reporting a partial run as complete.
        failure = "Interrupted by user"
    # Handle this failure without losing the error or skipping the enclosing cleanup.
    except Exception as error:
        # Remember the earliest failure instead of reporting a partial run as complete.
        failure = str(error)
    finally:
        # Choose the next branch using process is not None.
        if process is not None:
            # Keep failure handling alongside the operation so cleanup/status remains explicit.
            try:
                # Call stop_camera for this step; its contract describes the result or side
                # effect.
                stop_camera(process)
            # Handle this failure without losing the error or skipping the enclosing cleanup.
            except Exception as error:
                # Remember the earliest failure instead of reporting a partial run as complete.
                failure = failure or str(error)
            # Choose the next branch using reader is not None.
            if reader is not None:
                # Wait for this worker to finish, respecting the existing bounded timeout.
                reader.join(timeout=5)
            # Choose the next branch using process.stderr.
            if process.stderr:
                # Release the stream or server resource after use.
                process.stderr.close()
            # Prepare metadata['ffmpeg_returncode'] for the next step using the values
            # calculated so far.
            metadata["ffmpeg_returncode"] = process.returncode
            # FFmpeg normally returns 255 after intentional SIGINT shutdown.
            if process.returncode not in (0, 255):
                # Remember the earliest failure instead of reporting a partial run as complete.
                failure = failure or "FFmpeg failed; inspect ffmpeg.log"
        # Choose the next branch using reader_errors.
        if reader_errors:
            # Remember the earliest failure instead of reporting a partial run as complete.
            failure = failure or reader_errors[0]
        # Choose the next branch using len(frames) < 2 or imu_count < 2.
        if len(frames) < 2 or imu_count < 2:
            # Remember the earliest failure instead of reporting a partial run as complete.
            failure = failure or "Insufficient frames or IMU samples"
        # Add the fields produced by this step while preserving the other report fields.
        metadata.update(
            status="failed" if failure else "complete",
            error=failure,
            decoded_frames=len(frames),
            imu_samples=imu_count,
            elapsed_seconds=(time.monotonic_ns() - origin) / 1e9,
        )
        # Choose the next branch using frames.
        if frames:
            # Prepare metadata['first_frame_host_receipt_s'] for the next step using the values
            # calculated so far.
            metadata["first_frame_host_receipt_s"] = frames[0][2]
            # Prepare metadata['last_frame_host_receipt_s'] for the next step using the values
            # calculated so far.
            metadata["last_frame_host_receipt_s"] = frames[-1][2]
            # Prepare metadata['camera_pts_nonincreasing'] for the next step using the values
            # calculated so far.
            metadata["camera_pts_nonincreasing"] = sum(
                b[1] <= a[1] for a, b in zip(frames, frames[1:])
            )
        # Persist this explicitly requested local output; raw artifacts stay outside Git.
        (output / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
    # Explain the current result, progress or failure in the terminal.
    print(
        f"Saved {len(frames)} decoded-frame records and {imu_count} IMU samples to {output}"
    )
    # Choose the next branch using failure.
    if failure:
        # Explain the current result, progress or failure in the terminal.
        print(f"Incomplete run: {failure}", file=sys.stderr)
        # Return the process-style status code to the caller.
        return 1
    # Explain the current result, progress or failure in the terminal.
    print(
        "Video: camera.mkv. Timing is approximate host observation, not exposure synchronization."
    )
    # Return the process-style status code to the caller.
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Validate a new output path and existing hardware/software before recording.

    Args:
        argv (Sequence[str] | None): Command-line tokens, or None to parse the current
            process arguments.

    Returns:
        int: Process-style exit code; never downloads dependencies or overwrites an old
            run.
    """
    # Define the command-line interface without starting hardware work yet.
    parser = argparse.ArgumentParser(description=__doc__)
    # Declare --device with its existing default, validation and help text.
    parser.add_argument("--device", required=True)
    # Declare --seconds with its existing default, validation and help text.
    parser.add_argument("--seconds", type=positive, default=15)
    # Declare --interval with its existing default, validation and help text.
    parser.add_argument("--interval", type=positive, default=0.05)
    # Declare --output with its existing default, validation and help text.
    parser.add_argument(
        "--output", type=Path, required=True, help="new directory under recordings/"
    )
    # Declare --notes with its existing default, validation and help text.
    parser.add_argument(
        "--notes", default="Not supplied; experiment conditions unknown"
    )
    # Parse command-line values into the namespace used by this operation.
    args = parser.parse_args(argv)
    # Choose the next branch using not
    # args.output.resolve().is_relative_to(Path('recordings').resolve()).
    if not args.output.resolve().is_relative_to(Path("recordings").resolve()):
        # Call parser.error for this step; its contract describes the result or side effect.
        parser.error("output must be under recordings/ (run from repository root)")
    # Choose the next branch using args.output.exists().
    if args.output.exists():
        # Call parser.error for this step; its contract describes the result or side effect.
        parser.error("output already exists; choose a new run directory")
    # Choose the next branch using not shutil.which('ffmpeg').
    if not shutil.which("ffmpeg"):
        # Call parser.error for this step; its contract describes the result or side effect.
        parser.error("the existing FFmpeg installation is required")
    # Keep failure handling alongside the operation so cleanup/status remains explicit.
    try:
        # Import the existing Pi driver only when a real sensor path is requested.
        from sunfounder_imu import IMU

        # Select the accelerometer/gyroscope driver interface, not the saved calibration output.
        sensor = IMU().accel_gyro
        # Reject this invalid input before it can produce misleading output.
        if sensor is None:
            # Stop this operation with an explicit error rather than publishing invalid data.
            raise RuntimeError("No accelerometer/gyro found")
        # Return the documented result to the caller without starting another operation.
        return record(sensor, args)
    # Handle this failure without losing the error or skipping the enclosing cleanup.
    except Exception as error:
        # Explain the current result, progress or failure in the terminal.
        print(f"Capture failed: {error}", file=sys.stderr)
        # Return the process-style status code to the caller.
        return 1


# Run the command only when executed directly, not when imported by tests or another module.
if __name__ == "__main__":
    # Return the command's status to the shell instead of leaving success ambiguous.
    raise SystemExit(main())
