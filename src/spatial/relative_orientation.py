"""Estimate IMU-relative rotation from a completed combined capture.

This is gyro-only dead reckoning in sensor axes. It does not infer camera/world
orientation, depth, position, or exposure-synchronized motion.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import statistics
import time
from typing import Sequence, TYPE_CHECKING

from recording.analyze_capture import numeric_csv, timing

if TYPE_CHECKING:
    from _contracts import Axes, Record, TimedGyro


def quaternion_product(left: Sequence[float], right: Sequence[float]) -> tuple[float, float, float, float]:
    """Compose two scalar-first rotations, applying the body-axis increment on the right.

    Args:
        left (Sequence[float]): Current unit quaternion (w, x, y, z).
        right (Sequence[float]): Incremental unit quaternion in current IMU axes.

    Returns:
        tuple[float, float, float, float]: Composed quaternion (w, x, y, z).
    """
    a, b, c, d = left
    e, f, g, h = right
    return (a * e - b * f - c * g - d * h,
            a * f + b * e + c * h - d * g,
            a * g - b * h + c * e + d * f,
            a * h + b * g - c * f + d * e)


def rotation_vector_degrees(quaternion: Sequence[float]) -> tuple[float, float, float]:
    """Express the shortest rotation from identity as an IMU-axis vector.

    Args:
        quaternion (Sequence[float]): Unit quaternion (w, x, y, z).

    Returns:
        tuple[float, float, float]: Axis times angle in degrees, limited to
            the shortest 0–180 degree representation; this is not Euler XYZ.
    """
    w, x, y, z = quaternion
    if w < 0:
        w, x, y, z = -w, -x, -y, -z
    vector_norm = math.sqrt(x * x + y * y + z * z)
    if vector_norm < 1e-12:
        return (0.0, 0.0, 0.0)
    scale = math.degrees(2 * math.atan2(vector_norm, max(0.0, w))) / vector_norm
    return (x * scale, y * scale, z * scale)


def integrate_gyro(samples: Sequence[TimedGyro], bias_dps: Axes,
                   max_gap_seconds: float = 0.2) -> Record:
    """Integrate a time-ordered gyro sequence into relative IMU orientation.

    Args:
        samples (Sequence[TimedGyro]): Host-midpoint seconds and raw XYZ deg/s,
            starting after the still bias window.
        bias_dps (Axes): Per-run stationary XYZ deg/s offset.
        max_gap_seconds (float): Largest trusted adjacent host interval in seconds.

    Returns:
        Record: Final and largest-from-start relative rotation plus compute time.
            Raises ValueError before returning any pose on invalid data or a gap.
    """
    if (len(samples) < 2 or len(bias_dps) != 3 or
            not all(math.isfinite(v) for v in bias_dps) or
            not math.isfinite(max_gap_seconds) or max_gap_seconds <= 0):
        raise ValueError("Need two samples, finite XYZ bias and a positive gap limit")
    for stamp, rates in samples:
        if (not math.isfinite(stamp) or len(rates) != 3 or
                not all(math.isfinite(rate) for rate in rates)):
            raise ValueError("Every sample needs finite time and XYZ angular rates")
    gaps = [b[0] - a[0] for a, b in zip(samples, samples[1:])]
    if any(gap <= 0 or gap > max_gap_seconds for gap in gaps):
        raise ValueError("Invalid or excessive IMU interval; orientation is unknown")

    # Average adjacent body-axis rates, subtract the local stationary offset,
    # then compose the corresponding small 3D rotations in timestamp order.
    start = time.perf_counter()
    orientation = (1.0, 0.0, 0.0, 0.0)
    peak_vector = (0.0, 0.0, 0.0)
    peak_time = samples[0][0]
    for (first_time, first_rates), (next_time, next_rates) in zip(samples, samples[1:]):
        dt = next_time - first_time
        vector = tuple(math.radians((a + b) / 2 - bias) * dt
                       for a, b, bias in zip(first_rates, next_rates, bias_dps))
        angle = math.sqrt(sum(value * value for value in vector))
        if angle:
            factor = math.sin(angle / 2) / angle
            increment = (math.cos(angle / 2), *(value * factor for value in vector))
            composed = quaternion_product(orientation, increment)
            magnitude = math.sqrt(sum(value * value for value in composed))
            orientation = tuple(value / magnitude for value in composed)
        current_vector = rotation_vector_degrees(orientation)
        if sum(value * value for value in current_vector) > sum(value * value for value in peak_vector):
            peak_vector, peak_time = current_vector, next_time
    compute_ms = (time.perf_counter() - start) * 1000

    return {
        "samples": len(samples),
        "span_s": samples[-1][0] - samples[0][0],
        "max_gap_ms": max(gaps) * 1000,
        "gap_limit_ms": max_gap_seconds * 1000,
        "final_quaternion_wxyz": list(orientation),
        "final_rotation_vector_deg": list(rotation_vector_degrees(orientation)),
        "peak_rotation_vector_deg": list(peak_vector),
        "peak_angle_deg": math.sqrt(sum(value * value for value in peak_vector)),
        "peak_time_from_start_s": peak_time - samples[0][0],
        "integration_compute_ms": compute_ms,
    }


def analyze(folder: Path, bias_seconds: float = 2.0,
            max_gap_seconds: float = 0.2, max_still_std_dps: float = 2.0) -> Record:
    """Load one saved capture, estimate a local still bias and integrate later gyro reads.

    Args:
        folder (Path): Completed combined-capture directory, read only.
        bias_seconds (float): Initial physically still window after RECORDING cue.
        max_gap_seconds (float): Maximum trusted adjacent IMU midpoint interval.
        max_still_std_dps (float): Maximum allowed baseline standard deviation
            on any sensor gyro axis, in deg/s.

    Returns:
        Record: Relative IMU rotation summary with explicit data and timing scope.
    """
    meta = json.loads((folder / "metadata.json").read_text())
    duration = float(meta["requested_seconds_after_first_frame"])
    cue = float(meta["recording_cue_host_s"])
    if (meta["status"] != "complete" or not all(map(math.isfinite, (duration, cue,
            bias_seconds, max_still_std_dps))) or not 0 < bias_seconds < duration or
            max_still_std_dps <= 0):
        raise ValueError("Need a complete run and a finite initial still window")
    rows = numeric_csv(folder / "imu.csv")
    if len(rows) != meta["imu_samples"]:
        raise ValueError("IMU CSV count disagrees with metadata")
    window = [row for row in rows if cue <= row["host_read_midpoint_s"] <= cue + duration]
    timing([row["host_read_midpoint_s"] for row in window])
    if (not math.isfinite(max_gap_seconds) or max_gap_seconds <= 0 or
            any(b["host_read_midpoint_s"] - a["host_read_midpoint_s"] > max_gap_seconds
                for a, b in zip(window, window[1:]))):
        raise ValueError("Invalid gap limit or excessive IMU interval anywhere in the run")
    still = [row for row in window if row["host_read_midpoint_s"] < cue + bias_seconds]
    if len(still) < 5:
        raise ValueError("Need at least five physically still gyro samples")
    keys = ("gx_dps", "gy_dps", "gz_dps")
    std_dps = [statistics.pstdev(row[key] for row in still) for key in keys]
    if max(std_dps) > max_still_std_dps:
        raise ValueError("Initial gyro window varies too much to use as still bias")
    bias = tuple(statistics.mean(row[key] for row in still) for key in keys)
    motion = [row for row in window if row["host_read_midpoint_s"] >= cue + bias_seconds]
    samples = [(row["host_read_midpoint_s"],
                tuple(row[key] for key in keys)) for row in motion]
    result = integrate_gyro(samples, bias, max_gap_seconds)
    return {
        "recording": folder.name,
        "requested_mode": meta["requested_mode"],
        "bias_window_after_cue_s": [0, bias_seconds],
        "bias_samples": len(still),
        "bias_dps": list(bias),
        "bias_std_dps": std_dps,
        **result,
        "scope": ("Gyro-only relative IMU orientation from host read midpoints. "
                  "No camera-axis calibration, gravity correction, world heading, "
                  "position, depth, exposure synchronization or drift correction. "
                  "Compute time is one local integration run, excluding CSV I/O; "
                  "it is not a Pi benchmark unless run and repeated on the Pi."),
    }


def main() -> None:
    """Print a read-only relative-rotation summary for a saved recording.

    Args:
        None: Options come from the command line.

    Returns:
        None: Prints JSON; invalid recordings exit nonzero without writing files.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path)
    parser.add_argument("--bias-seconds", type=float, default=2.0)
    parser.add_argument("--max-gap-seconds", type=float, default=0.2)
    parser.add_argument("--max-still-std-dps", type=float, default=2.0)
    args = parser.parse_args()
    try:
        print(json.dumps(analyze(args.folder, args.bias_seconds,
                                 args.max_gap_seconds, args.max_still_std_dps),
                         indent=2, allow_nan=False))
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(1, f"Orientation analysis failed: {error}\n")


if __name__ == "__main__":
    main()
