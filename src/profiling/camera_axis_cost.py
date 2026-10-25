"""Measure the offline IMU-to-camera vector conversion without sensor I/O.

This measures Python's current ``camera_components`` call, including its input
checks. It does not benchmark I2C reads, gyro integration, or the live worker.
"""

from __future__ import annotations

import argparse
import json
import math
import platform
import statistics
import subprocess
import time
from pathlib import Path
from typing import Sequence

from spatial.camera_axes import analyze_recordings, camera_components


def git_revision() -> str | None:
    """Return the current source revision, or None outside a Git worktree."""
    result = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True,
                            text=True, check=False)
    return result.stdout.strip() if result.returncode == 0 else None


def measure(basis: Sequence[Sequence[float]], *, warmup_seconds: float = 1.0,
            measure_seconds: float = 5.0, batch_size: int = 1000) -> dict[str, object]:
    """Time repeated real conversion calls on one process, with no I/O in the loop.

    Args:
        basis (Sequence[Sequence[float]]): Fitted camera XYZ axes in IMU XYZ.
        warmup_seconds (float): Untimed warm-up duration on a monotonic clock.
        measure_seconds (float): Minimum elapsed duration of measured batches.
        batch_size (int): Calls timed together to amortize timer overhead.

    Returns:
        dict[str, object]: Batch-amortized latency, total process CPU cost and
            hypothetical one-core usage at three rates. The input vector is a
            fixed finite angular rate in degrees/second.
    """
    if (not math.isfinite(warmup_seconds) or warmup_seconds < 0 or
            not math.isfinite(measure_seconds) or measure_seconds <= 0 or
            batch_size <= 0):
        raise ValueError("Warm-up, measurement duration or batch size is invalid")

    vector = (0.1, 0.2, 0.3)
    # Validate the basis before starting clocks; each measured call still runs
    # the ordinary camera_components input checks and dot products.
    expected = camera_components(vector, basis)
    warmup_end = time.perf_counter() + warmup_seconds
    while time.perf_counter() < warmup_end:
        for _ in range(batch_size):
            camera_components(vector, basis)

    batch_us_per_call: list[float] = []
    calls = 0
    cpu_start = time.process_time_ns()
    wall_start = time.perf_counter_ns()
    deadline = wall_start + int(measure_seconds * 1e9)
    last = expected
    while time.perf_counter_ns() < deadline:
        batch_start = time.perf_counter_ns()
        for _ in range(batch_size):
            last = camera_components(vector, basis)
        batch_end = time.perf_counter_ns()
        batch_us_per_call.append((batch_end - batch_start) / batch_size / 1000)
        calls += batch_size
    wall_ns = time.perf_counter_ns() - wall_start
    cpu_ns = time.process_time_ns() - cpu_start
    if last != expected:
        raise RuntimeError("Camera-axis conversion changed during the benchmark")

    # Total process CPU includes the Python benchmark loop and timer calls; it
    # is an upper-bound-like estimate, not a profiler's isolated function cost.
    cpu_us_per_call = cpu_ns / calls / 1000
    sorted_batches = sorted(batch_us_per_call)
    p95_index = math.ceil(0.95 * len(sorted_batches)) - 1
    return {
        "calls": calls,
        "batches": len(batch_us_per_call),
        "warmup_requested_s": warmup_seconds,
        "measurement_requested_s": measure_seconds,
        "measurement_elapsed_s": wall_ns / 1e9,
        "input_imu_xyz_dps": list(vector),
        "output_camera_xyz_dps": list(expected),
        "wall_us_per_call_batch_median": statistics.median(batch_us_per_call),
        "wall_us_per_call_batch_p95": sorted_batches[p95_index],
        "process_cpu_us_per_call_total": cpu_us_per_call,
        "projected_one_core_cpu_pct": {
            str(rate): cpu_us_per_call * rate / 10000 for rate in (20, 30, 100)
        },
        "scope": ("Read-only, single-process repeated camera_components calls on "
                  "a fixed vector and fitted basis. Batch wall times amortize timer "
                  "overhead; total CPU includes Python loop and timers. Projection "
                  "excludes sensor I/O, scheduling, integration, rendering and "
                  "contention; it is not measured live-pipeline CPU or latency."),
    }


def main() -> None:
    """Fit the current saved basis, then print a read-only Pi cost report."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pan_folder", type=Path)
    parser.add_argument("tilt_folder", type=Path)
    parser.add_argument("--pan-first", choices=("right", "left"), required=True)
    parser.add_argument("--tilt-first", choices=("up", "down"), required=True)
    parser.add_argument("--warmup-seconds", type=float, default=1.0)
    parser.add_argument("--measure-seconds", type=float, default=5.0)
    parser.add_argument("--batch-size", type=int, default=1000)
    args = parser.parse_args()
    try:
        fit = analyze_recordings(args.pan_folder, args.tilt_folder,
                                 pan_first=args.pan_first, tilt_first=args.tilt_first)
        result = measure(fit["camera_axes_in_imu_xyz"],
                         warmup_seconds=args.warmup_seconds,
                         measure_seconds=args.measure_seconds,
                         batch_size=args.batch_size)
        result.update({"host": platform.platform(), "python": platform.python_version(),
                       "git_commit": git_revision(),
                       "pan_recording": args.pan_folder.name,
                       "tilt_recording": args.tilt_folder.name,
                       "camera_axes_in_imu_xyz": fit["camera_axes_in_imu_xyz"]})
        print(json.dumps(result, indent=2, allow_nan=False))
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(1, f"Camera-axis cost benchmark failed: {error}\n")


if __name__ == "__main__":
    main()
