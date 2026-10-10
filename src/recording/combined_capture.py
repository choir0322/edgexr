"""Record local MJPEG video and raw IMU data; timestamps are not synchronized."""

from __future__ import annotations
from typing import Callable, Sequence, TYPE_CHECKING

if TYPE_CHECKING:
    from _contracts import Sensor


import argparse
import csv
import json
import math
from pathlib import Path
import platform
import re
import shutil
import signal
import subprocess
import sys
import threading
import time


FRAME_RE = re.compile(r"\bn:\s*(\d+)\s+pts:\s*\S+\s+pts_time:\s*([-+\d.eE]+)")


def parse_frame(line: str) -> tuple[int, float] | None:
    """Parse an FFmpeg showinfo frame number and finite presentation timestamp.

    Args:
        line (str): One FFmpeg diagnostic line, not binary image bytes.

    Returns:
        tuple[int, float] | None: Frame index and camera PTS seconds, or None for
            other/invalid log lines.
    """
    if "Parsed_showinfo" not in line:
        return None
    match = FRAME_RE.search(line)
    if not match:
        return None
    number, pts = int(match[1]), float(match[2])
    return (number, pts) if math.isfinite(pts) else None


def positive(value: str) -> float:
    """Validate a finite positive duration or interval from the command line.

    Args:
        value (str): Command-line text to convert and validate.

    Returns:
        float: Positive number; rejects zero, negative or nonfinite values.
    """
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise argparse.ArgumentTypeError("must be finite and greater than zero")
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
    # Bracket one raw sensor read on the monotonic clock and validate its axes.
    # Store midpoint seconds relative to the common origin plus read duration.
    before = clock()
    accel, gyro, _temperature = sensor.read_raw()
    after = clock()
    if (
        len(accel) != 3
        or len(gyro) != 3
        or not all(math.isfinite(value) for value in (*accel, *gyro))
    ):
        raise ValueError("IMU returned invalid axes")
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
    # Request 720p MJPEG at 30 fps. Copy compressed video to disk while a second
    # output decodes solely for showinfo timestamps; those PTS are not host receipts.
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
    # Ask FFmpeg to finalize normally first; force termination only on timeout
    # and report that the recording may be incomplete.
    if process.poll() is None:
        process.send_signal(signal.SIGINT)
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)
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
    # Reserve a new run directory and write incomplete metadata immediately.
    # A common monotonic origin relates host camera receipts and IMU reads.
    output = args.output
    output.mkdir(parents=True, exist_ok=False)
    origin = time.monotonic_ns()
    command = camera_command(args.device, output / "camera.mkv")
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
    (output / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")

    # Coordinate camera startup and collect failures so cleanup can produce an
    # honest final status even after an interrupted or partially written recording.
    first_frame = threading.Event()
    frames = []
    reader_errors = []
    imu_count = 0
    process = None
    reader = None
    failure = None

    def drain_camera() -> None:
        """Drain showinfo diagnostics while saving frame receipts and waking the recorder.

        Args:
            None.

        Returns:
            None: writes the enclosing run's log/CSV and collects reader errors.
        """
        # Drain diagnostics continuously, logging each decoded frame with its host
        # receipt time. The first valid frame releases the main recording countdown.
        try:
            with (output / "ffmpeg.log").open("w") as log, (output / "frames.csv").open(
                "w", newline=""
            ) as handle:
                writer = csv.writer(handle)
                writer.writerow(["frame_index", "camera_pts_s", "host_receipt_s"])
                for line in process.stderr:
                    received = (time.monotonic_ns() - origin) / 1e9
                    log.write(line)
                    frame = parse_frame(line)
                    if frame is not None:
                        row = [*frame, received]
                        writer.writerow(row)
                        frames.append(row)
                        first_frame.set()
        except Exception as error:
            reader_errors.append(str(error))

    # Start camera logging in parallel with IMU acquisition. Establish the CSV
    # schema before entering the acquisition loop.
    try:
        process = subprocess.Popen(
            command, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True
        )
        reader = threading.Thread(target=drain_camera)
        reader.start()
        print("Starting camera; remain still until RECORDING appears.", flush=True)
        startup = time.monotonic()
        deadline = None
        with (output / "imu.csv").open("w", newline="") as handle:
            writer = csv.writer(handle)
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

            # Watch camera errors and bound startup; start the requested duration only
            # after a decoded frame arrives, recording the visible cue time separately.
            while True:
                now = time.monotonic()
                if reader_errors:
                    raise RuntimeError(reader_errors[0])
                if process.poll() is not None:
                    raise RuntimeError("FFmpeg exited early; inspect ffmpeg.log")
                if deadline is None and first_frame.is_set():
                    deadline = now + args.seconds
                    metadata["recording_cue_host_s"] = now - origin / 1e9
                    print(f"RECORDING for {args.seconds:g} seconds.", flush=True)
                if deadline is not None and now >= deadline:
                    break
                if deadline is None and now - startup > 10:
                    raise RuntimeError("No decoded camera frame within 10 seconds")

                # Write one timestamped raw sample per read, then sleep. The interval is an
                # additional pause, not a guarantee of that exact sample period.
                writer.writerow(read_row(sensor, origin))
                imu_count += 1
                time.sleep(args.interval)
    except KeyboardInterrupt:
        failure = "Interrupted by user"
    except Exception as error:
        failure = str(error)

    # Always finalize camera/log resources and fold shutdown errors into run status.
    # FFmpeg code 255 is allowed for the deliberate interrupt used to stop capture.
    finally:
        if process is not None:
            try:
                stop_camera(process)
            except Exception as error:
                failure = failure or str(error)
            if reader is not None:
                reader.join(timeout=5)
            if process.stderr:
                process.stderr.close()
            metadata["ffmpeg_returncode"] = process.returncode
            if process.returncode not in (0, 255):
                failure = failure or "FFmpeg failed; inspect ffmpeg.log"

        # Check sample sufficiency and timestamp order, then replace initial metadata
        # with final counts/status so partial runs remain inspectable.
        if reader_errors:
            failure = failure or reader_errors[0]
        if len(frames) < 2 or imu_count < 2:
            failure = failure or "Insufficient frames or IMU samples"
        metadata.update(
            status="failed" if failure else "complete",
            error=failure,
            decoded_frames=len(frames),
            imu_samples=imu_count,
            elapsed_seconds=(time.monotonic_ns() - origin) / 1e9,
        )
        if frames:
            metadata["first_frame_host_receipt_s"] = frames[0][2]
            metadata["last_frame_host_receipt_s"] = frames[-1][2]
            metadata["camera_pts_nonincreasing"] = sum(
                b[1] <= a[1] for a, b in zip(frames, frames[1:])
            )
        (output / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")

    # Report what was saved and return failure for incomplete acquisition.
    print(
        f"Saved {len(frames)} decoded-frame records and {imu_count} IMU samples to {output}"
    )
    if failure:
        print(f"Incomplete run: {failure}", file=sys.stderr)
        return 1
    print(
        "Video: camera.mkv. Timing is approximate host observation, not exposure synchronization."
    )
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
    # Parse the camera, duration, polling pause, run directory and experiment notes.
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", required=True)
    parser.add_argument("--seconds", type=positive, default=15)
    parser.add_argument("--interval", type=positive, default=0.05)
    parser.add_argument(
        "--output", type=Path, required=True, help="new directory under recordings/"
    )
    parser.add_argument(
        "--notes", default="Not supplied; experiment conditions unknown"
    )
    args = parser.parse_args(argv)

    # Reject unsafe/existing output paths and missing FFmpeg before touching hardware.
    if not args.output.resolve().is_relative_to(Path("recordings").resolve()):
        parser.error("output must be under recordings/ (run from repository root)")
    if args.output.exists():
        parser.error("output already exists; choose a new run directory")
    if not shutil.which("ffmpeg"):
        parser.error("the existing FFmpeg installation is required")

    # Import and open the raw sensor only after validation, then record or report
    # a setup error without installing drivers or changing calibration.
    try:
        from sunfounder_imu import IMU

        sensor = IMU().accel_gyro
        if sensor is None:
            raise RuntimeError("No accelerometer/gyro found")
        return record(sensor, args)
    except Exception as error:
        print(f"Capture failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
