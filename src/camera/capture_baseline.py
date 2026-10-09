"""Measure a V4L2 MJPEG stream using FFmpeg's decoded-frame timestamps."""

# Postpone type evaluation so optional drivers/libraries stay optional.
from __future__ import annotations

# Describe data contracts without adding third-party runtime dependencies.
from typing import Sequence, TYPE_CHECKING

# Resolve documentation-only types for editors; this block does not run in production.
if TYPE_CHECKING:
    # Reuse the documented frame, sensor and report vocabulary for type checking.
    from _contracts import Record


# Parse and validate explicit command-line options.
import argparse

# Validate finite numbers and perform scalar numerical calculations.
import math

# Extract frame fields only from matching FFmpeg diagnostic lines.
import re

# Check whether an existing external tool is available on PATH.
import shutil

# Compute means, spreads and medians from collected measurements.
import statistics

# Run existing FFmpeg/ffprobe/Git tools with explicit argument lists.
import subprocess

# Report failures on stderr and handle command-line exit behavior.
import sys

# Measure host intervals and provide bounded polling pauses.
import time


# Prepare TIMESTAMP_RE for the next step using the values calculated so far.
TIMESTAMP_RE = re.compile(r"\bn:\s*\d+\s+pts:\s*\S+\s+pts_time:\s*(-?\d+(?:\.\d+)?)")


def frame_timestamps(ffmpeg_log: str) -> list[float]:
    """Extract decoded-frame presentation times from FFmpeg showinfo diagnostics.

    Args:
        ffmpeg_log (str): Complete text diagnostic stream containing showinfo messages.

    Returns:
        list[float]: Ordered camera PTS seconds, excluding unrelated log messages.
    """
    # Prepare timestamps for the next step using the values calculated so far.
    timestamps = []
    # Process each line in the selected collection.
    for line in ffmpeg_log.splitlines():
        # Choose the next branch using 'Parsed_showinfo' not in line.
        if "Parsed_showinfo" not in line:
            # Skip this unusable item and look for the next eligible observation.
            continue
        # Prepare match for the next step using the values calculated so far.
        match = TIMESTAMP_RE.search(line)
        # Choose the next branch using match.
        if match:
            # Retain this item/chunk for the current calculation or bounded history.
            timestamps.append(float(match.group(1)))
    # Return the documented result to the caller without starting another operation.
    return timestamps


def summarize(timestamps: Sequence[float], wall_seconds: float) -> Record:
    """Report decoded throughput separately from camera timestamp spacing.

    Args:
        timestamps (Sequence[float]): Decoded-frame camera presentation times in
            seconds.
        wall_seconds (float): Actual elapsed capture/decode wall duration in seconds.

    Returns:
        Record: Counts, wall/PTS rates, median/p95 spacing and equal/backward timestamp
            counts.
    """
    # Keep real timestamp gaps instead of assuming an exact polling frequency.
    intervals = [later - earlier for earlier, later in zip(timestamps, timestamps[1:])]
    # Use only forward intervals for spacing statistics while still reporting anomalies.
    positive_intervals = sorted(interval for interval in intervals if interval > 0)
    # Measure elapsed camera PTS coverage rather than wall-clock execution duration.
    timestamp_span = timestamps[-1] - timestamps[0] if len(timestamps) > 1 else 0
    # Return the documented result to the caller without starting another operation.
    return {
        "frames": len(timestamps),
        "wall_fps": len(timestamps) / wall_seconds if wall_seconds > 0 else None,
        "timestamp_fps": (
            (len(timestamps) - 1) / timestamp_span if timestamp_span > 0 else None
        ),
        "median_interval_ms": (
            statistics.median(positive_intervals) * 1000 if positive_intervals else None
        ),
        "p95_interval_ms": (
            positive_intervals[math.ceil(0.95 * len(positive_intervals)) - 1] * 1000
            if positive_intervals
            else None
        ),
        "equal_timestamps": sum(interval == 0 for interval in intervals),
        "backward_timestamps": sum(interval < 0 for interval in intervals),
    }


def positive_int(value: str) -> int:
    """Parse a strictly positive integer command-line argument.

    Args:
        value (str): Command-line text to convert and validate.

    Returns:
        int: Positive integer; conversion or argparse validation errors propagate.
    """
    # Convert command-line or parsed input to a number before validating its allowed range.
    number = int(value)
    # Reject this invalid input before it can produce misleading output.
    if number <= 0:
        # Stop this operation with an explicit error rather than publishing invalid data.
        raise argparse.ArgumentTypeError("must be greater than zero")
    # Return the documented result to the caller without starting another operation.
    return number


def positive_float(value: str) -> float:
    """Parse a finite, strictly positive command-line duration.

    Args:
        value (str): Command-line text to convert and validate.

    Returns:
        float: Positive seconds; rejects zero, negative and nonfinite values.
    """
    # Convert command-line or parsed input to a number before validating its allowed range.
    number = float(value)
    # Reject this invalid input before it can produce misleading output.
    if not math.isfinite(number) or number <= 0:
        # Stop this operation with an explicit error rather than publishing invalid data.
        raise argparse.ArgumentTypeError("must be a finite number greater than zero")
    # Return the documented result to the caller without starting another operation.
    return number


def main() -> int:
    """Run the camera-only capture/decode benchmark without saving video.

    Args:
        None.

    Returns:
        int: Process-style exit code; prints results or FFmpeg failure diagnostics.
    """
    # Define the command-line interface without starting hardware work yet.
    parser = argparse.ArgumentParser(description=__doc__)
    # Declare --device with its existing default, validation and help text.
    parser.add_argument(
        "--device", required=True, help="V4L2 capture device, such as /dev/video0"
    )
    # Declare --width with its existing default, validation and help text.
    parser.add_argument("--width", type=positive_int, default=1280)
    # Declare --height with its existing default, validation and help text.
    parser.add_argument("--height", type=positive_int, default=720)
    # Declare --fps with its existing default, validation and help text.
    parser.add_argument("--fps", type=positive_int, default=120)
    # Declare --seconds with its existing default, validation and help text.
    parser.add_argument("--seconds", type=positive_float, default=10)
    # Parse command-line values into the namespace used by this operation.
    args = parser.parse_args()

    # Choose the next branch using not shutil.which('ffmpeg').
    if not shutil.which("ffmpeg"):
        # Call parser.error for this step; its contract describes the result or side effect.
        parser.error(
            "ffmpeg is required; it was available in the first Pi camera check"
        )

    # Build the explicit external-tool argument list with the existing settings.
    command = [
        "ffmpeg",
        "-hide_banner",
        "-nostdin",
        "-loglevel",
        "info",
        "-f",
        "v4l2",
        "-input_format",
        "mjpeg",
        "-video_size",
        f"{args.width}x{args.height}",
        "-framerate",
        str(args.fps),
        "-i",
        args.device,
        "-t",
        str(args.seconds),
        "-fps_mode",
        "passthrough",
        "-vf",
        "showinfo=checksum=0",
        "-f",
        "null",
        "-",
    ]
    # Explain the current result, progress or failure in the terminal.
    print(
        f"Request: {args.width}x{args.height} MJPEG at {args.fps} fps for {args.seconds:g} s"
    )
    # Read host monotonic time for this stage's timing boundary.
    start = time.monotonic()
    # Hold the child-process handle so its lifecycle can be managed safely.
    process = subprocess.run(
        command, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True
    )
    # Include capture/decode/startup overhead in the measured wall duration.
    wall_seconds = time.monotonic() - start

    # Choose the next branch using process.returncode.
    if process.returncode:
        # Explain the current result, progress or failure in the terminal.
        print("FFmpeg failed; its last messages follow:", file=sys.stderr)
        # Explain the current result, progress or failure in the terminal.
        print("\n".join(process.stderr.splitlines()[-15:]), file=sys.stderr)
        # Return the documented result to the caller without starting another operation.
        return process.returncode

    # Keep FFmpeg's reported input format distinct from the originally requested mode.
    input_video_line = next(
        (
            line.strip()
            for line in process.stderr.splitlines()
            if "Stream #0:0: Video:" in line
        ),
        "unavailable",
    )
    # Prepare timestamps for the next step using the values calculated so far.
    timestamps = frame_timestamps(process.stderr)
    # Choose the next branch using not timestamps.
    if not timestamps:
        # Explain the current result, progress or failure in the terminal.
        print("No decoded-frame timestamps found in FFmpeg output.", file=sys.stderr)
        # Return the process-style status code to the caller.
        return 1

    # Prepare result for the next step using the values calculated so far.
    result = summarize(timestamps, wall_seconds)
    # Explain the current result, progress or failure in the terminal.
    print(f"Negotiated input: {input_video_line}")
    # Explain the current result, progress or failure in the terminal.
    print(f"Decoded frames: {result['frames']}")
    # Explain the current result, progress or failure in the terminal.
    print(f"Wall time: {wall_seconds:.2f} s")
    # Explain the current result, progress or failure in the terminal.
    print(f"Decoded throughput: {result['wall_fps']:.2f} frames/s")
    # Choose the next branch using result['timestamp_fps'] is not None.
    if result["timestamp_fps"] is not None:
        # Explain the current result, progress or failure in the terminal.
        print(f"Camera timestamp rate: {result['timestamp_fps']:.2f} frames/s")
    # Choose the next branch using result['median_interval_ms'] is not None.
    if result["median_interval_ms"] is not None:
        # Explain the current result, progress or failure in the terminal.
        print(
            f"Frame interval: median {result['median_interval_ms']:.2f} ms, "
            f"p95 {result['p95_interval_ms']:.2f} ms"
        )
    # Explain the current result, progress or failure in the terminal.
    print(
        f"Timestamp anomalies: {result['equal_timestamps']} equal, "
        f"{result['backward_timestamps']} backward"
    )
    # Explain the current result, progress or failure in the terminal.
    print(
        "Scope: capture + MJPEG decode + timestamp logging; no RGB conversion, display, or detection"
    )
    # Return the process-style status code to the caller.
    return 0


# Run the command only when executed directly, not when imported by tests or another module.
if __name__ == "__main__":
    # Return the command's status to the shell instead of leaving success ambiguous.
    raise SystemExit(main())
