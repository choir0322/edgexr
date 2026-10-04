"""Measure a V4L2 MJPEG stream using FFmpeg's decoded-frame timestamps."""

import argparse
import math
import re
import shutil
import statistics
import subprocess
import sys
import time


TIMESTAMP_RE = re.compile(r"\bn:\s*\d+\s+pts:\s*\S+\s+pts_time:\s*(-?\d+(?:\.\d+)?)")


def frame_timestamps(ffmpeg_log: str) -> list[float]:
    """Read presentation timestamps from FFmpeg showinfo frame lines."""
    timestamps = []
    for line in ffmpeg_log.splitlines():
        if "Parsed_showinfo" not in line:
            continue
        match = TIMESTAMP_RE.search(line)
        if match:
            timestamps.append(float(match.group(1)))
    return timestamps


def summarize(timestamps: list[float], wall_seconds: float) -> dict[str, float | int | None]:
    """Keep throughput and camera timestamp spacing as separate measurements."""
    intervals = [later - earlier for earlier, later in zip(timestamps, timestamps[1:])]
    positive_intervals = sorted(interval for interval in intervals if interval > 0)
    timestamp_span = timestamps[-1] - timestamps[0] if len(timestamps) > 1 else 0
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
            if positive_intervals else None
        ),
        "equal_timestamps": sum(interval == 0 for interval in intervals),
        "backward_timestamps": sum(interval < 0 for interval in intervals),
    }


def positive_int(value: str) -> int:
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return number


def positive_float(value: str) -> float:
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise argparse.ArgumentTypeError("must be a finite number greater than zero")
    return number


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", required=True, help="V4L2 capture device, such as /dev/video0")
    parser.add_argument("--width", type=positive_int, default=1280)
    parser.add_argument("--height", type=positive_int, default=720)
    parser.add_argument("--fps", type=positive_int, default=120)
    parser.add_argument("--seconds", type=positive_float, default=10)
    args = parser.parse_args()

    if not shutil.which("ffmpeg"):
        parser.error("ffmpeg is required; it was available in the first Pi camera check")

    command = [
        "ffmpeg", "-hide_banner", "-nostdin", "-loglevel", "info",
        "-f", "v4l2", "-input_format", "mjpeg",
        "-video_size", f"{args.width}x{args.height}",
        "-framerate", str(args.fps), "-i", args.device,
        "-t", str(args.seconds), "-fps_mode", "passthrough",
        "-vf", "showinfo=checksum=0", "-f", "null", "-",
    ]
    print(f"Request: {args.width}x{args.height} MJPEG at {args.fps} fps for {args.seconds:g} s")
    start = time.monotonic()
    process = subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    wall_seconds = time.monotonic() - start

    if process.returncode:
        print("FFmpeg failed; its last messages follow:", file=sys.stderr)
        print("\n".join(process.stderr.splitlines()[-15:]), file=sys.stderr)
        return process.returncode

    input_video_line = next(
        (line.strip() for line in process.stderr.splitlines()
         if "Stream #0:0: Video:" in line),
        "unavailable",
    )
    timestamps = frame_timestamps(process.stderr)
    if not timestamps:
        print("No decoded-frame timestamps found in FFmpeg output.", file=sys.stderr)
        return 1

    result = summarize(timestamps, wall_seconds)
    print(f"Negotiated input: {input_video_line}")
    print(f"Decoded frames: {result['frames']}")
    print(f"Wall time: {wall_seconds:.2f} s")
    print(f"Decoded throughput: {result['wall_fps']:.2f} frames/s")
    if result["timestamp_fps"] is not None:
        print(f"Camera timestamp rate: {result['timestamp_fps']:.2f} frames/s")
    if result["median_interval_ms"] is not None:
        print(f"Frame interval: median {result['median_interval_ms']:.2f} ms, "
              f"p95 {result['p95_interval_ms']:.2f} ms")
    print(f"Timestamp anomalies: {result['equal_timestamps']} equal, "
          f"{result['backward_timestamps']} backward")
    print("Scope: capture + MJPEG decode + timestamp logging; no RGB conversion, display, or detection")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
