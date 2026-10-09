"""Inspect saved timing and sensor-axis rotation; does not synchronize sensors."""

# Postpone type evaluation so optional drivers/libraries stay optional.
from __future__ import annotations

# Describe data contracts without adding third-party runtime dependencies.
from typing import Sequence, TYPE_CHECKING

# Resolve documentation-only types for editors; this block does not run in production.
if TYPE_CHECKING:
    # Reuse the documented frame, sensor and report vocabulary for type checking.
    from _contracts import NumericRow, Record


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

# Compute means, spreads and medians from collected measurements.
import statistics


def timing(times: Sequence[float]) -> Record:
    """Validate increasing observation times and summarize their spacing.

    Args:
        times (Sequence[float]): Ordered observation timestamps in seconds; arrays are
            one-dimensional.

    Returns:
        Record: Count, span, rate and median/nearest-rank-p95/maximum gaps in
            milliseconds.
    """
    # Reject this invalid input before it can produce misleading output.
    if len(times) < 2 or not all(math.isfinite(t) for t in times):
        # Stop this operation with an explicit error rather than publishing invalid data.
        raise ValueError("Need at least two finite timestamps")
    # Subtract adjacent timestamps to expose irregular or non-increasing observations.
    gaps = [b - a for a, b in zip(times, times[1:])]
    # Reject this invalid input before it can produce misleading output.
    if min(gaps) <= 0:
        # Stop this operation with an explicit error rather than publishing invalid data.
        raise ValueError("Timestamps must strictly increase")
    # Prepare ordered for the next step using the values calculated so far.
    ordered = sorted(gaps)
    # Return the documented result to the caller without starting another operation.
    return dict(
        count=len(times),
        span_s=times[-1] - times[0],
        rate_hz=(len(times) - 1) / (times[-1] - times[0]),
        median_gap_ms=1000 * statistics.median(gaps),
        p95_gap_ms=1000 * ordered[math.ceil(0.95 * len(ordered)) - 1],
        max_gap_ms=1000 * max(gaps),
    )


def mean_axes(rows: Sequence[NumericRow]) -> list[float]:
    """Average the three gyro columns from a stationary row selection.

    Args:
        rows (Sequence[NumericRow]): Named numeric CSV rows or seven-column SSD rows, as
            specified by this function.

    Returns:
        list[float]: XYZ degrees/s means; requires at least two rows.
    """
    # Reject this invalid input before it can produce misleading output.
    if len(rows) < 2:
        # Stop this operation with an explicit error rather than publishing invalid data.
        raise ValueError("Stationary window needs at least two samples")
    # Return the documented result to the caller without starting another operation.
    return [statistics.mean(r[k] for r in rows) for k in ("gx_dps", "gy_dps", "gz_dps")]


def integrate(rows: Sequence[NumericRow], bias: Sequence[float]) -> list[list[float]]:
    """Integrate corrected gyro rates with trapezoids over actual host-time gaps.

    Args:
        rows (Sequence[NumericRow]): Named numeric CSV rows or seven-column SSD rows, as
            specified by this function.
        bias (Sequence[float]): Three XYZ gyro offsets in degrees/second; must come from
            a still window.

    Returns:
        list[list[float]]: Rows of host seconds and cumulative XYZ sensor-axis degrees,
            starting at zero.
    """
    # Call timing for this step; its contract describes the result or side effect.
    timing([r["host_read_midpoint_s"] for r in rows])
    # Start all three sensor-axis integrals at zero degrees.
    angles = [0.0] * 3
    # Record cumulative sensor-axis angles alongside their host times.
    trajectory = [[rows[0]["host_read_midpoint_s"], *angles]]
    # Process adjacent observations using their actual time separation.
    for a, b in zip(rows, rows[1:]):
        # Prepare dt for the next step using the values calculated so far.
        dt = b["host_read_midpoint_s"] - a["host_read_midpoint_s"]
        # Process each (axis, key) in the selected collection.
        for axis, key in enumerate(("gx_dps", "gy_dps", "gz_dps")):
            # Accumulate corrected degrees/second times real elapsed seconds into sensor-axis
            # degrees.
            angles[axis] += ((a[key] + b[key]) / 2 - bias[axis]) * dt
        # Retain this item/chunk for the current calculation or bounded history.
        trajectory.append([b["host_read_midpoint_s"], *angles])
    # Return the documented result to the caller without starting another operation.
    return trajectory


def numeric_csv(path: Path) -> list[NumericRow]:
    """Read a named-column CSV and reject empty or nonfinite numeric data.

    Args:
        path (Path): Local filesystem path read by this operation.

    Returns:
        list[NumericRow]: Dictionary rows with every field converted to float.
    """
    # Keep these resources scoped so they are released even if the operation fails.
    with path.open() as handle:
        # Prepare/read the detailed rows that will be validated or summarized next.
        rows = [{k: float(v) for k, v in row.items()} for row in csv.DictReader(handle)]
    # Reject this invalid input before it can produce misleading output.
    if not rows or any(not math.isfinite(v) for row in rows for v in row.values()):
        # Stop this operation with an explicit error rather than publishing invalid data.
        raise ValueError(f"Empty or nonfinite data: {path}")
    # Return the documented result to the caller without starting another operation.
    return rows


def analyze(folder: Path, baseline_seconds: float = 1.0) -> Record:
    """Validate a saved run and summarize host/PTS timing and assumed-still gyro correction.

    Args:
        folder (Path): Existing local recording/comparison directory; raw data remains
            out of Git.
        baseline_seconds (float): Duration of the assumed stationary window after the
            recording cue.

    Returns:
        Record: Report with timing, bias, rotation extrema and limitations; does not
            write files.
    """
    # Reject this invalid input before it can produce misleading output.
    if not math.isfinite(baseline_seconds) or baseline_seconds <= 0:
        # Stop this operation with an explicit error rather than publishing invalid data.
        raise ValueError("Baseline seconds must be finite and positive")
    # Read the existing recording metadata before trusting frame or IMU logs.
    meta = json.loads((folder / "metadata.json").read_text())
    # Reject this invalid input before it can produce misleading output.
    if meta["status"] != "complete":
        # Stop this operation with an explicit error rather than publishing invalid data.
        raise ValueError("Recording is incomplete; inspect metadata and FFmpeg log")
    # Prepare duration for the next step using the values calculated so far.
    duration = meta["requested_seconds_after_first_frame"]
    # Reject this invalid input before it can produce misleading output.
    if not math.isfinite(duration) or not 0 < baseline_seconds < duration:
        # Stop this operation with an explicit error rather than publishing invalid data.
        raise ValueError("Baseline must be shorter than the finite recording duration")
    # Collect frame-log rows used for saved counts and timing checks.
    frames = numeric_csv(folder / "frames.csv")
    # Prepare imu for the next step using the values calculated so far.
    imu = numeric_csv(folder / "imu.csv")
    # Reject this invalid input before it can produce misleading output.
    if len(frames) != meta["decoded_frames"] or len(imu) != meta["imu_samples"]:
        # Stop this operation with an explicit error rather than publishing invalid data.
        raise ValueError("CSV counts disagree with metadata")
    # Use the saved RECORDING cue as the experiment-relative time origin.
    cue = meta["recording_cue_host_s"]
    # Reject this invalid input before it can produce misleading output.
    if not math.isfinite(cue):
        # Stop this operation with an explicit error rather than publishing invalid data.
        raise ValueError("Invalid recording cue")
    # Prepare baseline for the next step using the values calculated so far.
    baseline = [
        r for r in imu if cue <= r["host_read_midpoint_s"] < cue + baseline_seconds
    ]
    # Prepare bias for the next step using the values calculated so far.
    bias = mean_axes(baseline)
    # Select the requested analysis window without silently changing recorded timestamps.
    window = [
        r
        for r in imu
        if cue
        <= r["host_read_midpoint_s"]
        <= cue + meta["requested_seconds_after_first_frame"]
    ]
    # Record cumulative sensor-axis angles alongside their host times.
    trajectory = integrate(window, bias)
    # Select the last two seconds of readings to inspect residual still-rate behavior.
    final_window = [
        r
        for r in window
        if r["host_read_midpoint_s"] >= window[-1]["host_read_midpoint_s"] - 2
    ]
    # Compute the final-window mean independently of the initial bias window.
    tail_mean = mean_axes(final_window)
    # Prepare coarse time bins without claiming exact instructed motion boundaries.
    per_second = []
    # Process each second in the selected collection.
    for second in range(math.ceil(meta["requested_seconds_after_first_frame"])):
        # Take the next chunk or selected subset needed by this operation.
        part = [
            r for r in window if second <= r["host_read_midpoint_s"] - cue < second + 1
        ]
        # Choose the next branch using len(part) >= 2.
        if len(part) >= 2:
            # Retain this item/chunk for the current calculation or bounded history.
            per_second.append(
                dict(
                    second=second,
                    corrected_mean_dps=[a - b for a, b in zip(mean_axes(part), bias)],
                )
            )
    # Extract camera presentation timestamps independently of host log receipt time.
    pts = [r["camera_pts_s"] for r in frames]
    # Extract host frame-receipt times for a separate timing summary.
    receipts = [r["host_receipt_s"] for r in frames]
    # Prepare times for the next step using the values calculated so far.
    times = [r["host_read_midpoint_s"] for r in imu]
    # Return the documented result to the caller without starting another operation.
    return {
        "recording": folder.name,
        "camera_pts_all": timing(pts),
        "camera_pts_excluding_first_interval": timing(pts[1:]),
        "camera_host_receipts": timing(receipts),
        "imu_host_midpoints": timing(times),
        "common_host_coverage_s": max(
            0, min(receipts[-1], times[-1]) - max(receipts[0], times[0])
        ),
        "baseline_window_after_cue_s": [0, baseline_seconds],
        "baseline_samples": len(baseline),
        "baseline_gyro_dps": bias,
        "baseline_std_dps": [
            statistics.pstdev(r[k] for r in baseline)
            for k in ("gx_dps", "gy_dps", "gz_dps")
        ],
        "last_two_seconds_corrected_mean_dps": [a - b for a, b in zip(tail_mean, bias)],
        "integrated_span_s": trajectory[-1][0] - trajectory[0][0],
        "final_sensor_axis_degrees": trajectory[-1][1:],
        "min_sensor_axis_degrees": [min(r[i] for r in trajectory) for i in (1, 2, 3)],
        "max_sensor_axis_degrees": [max(r[i] for r in trajectory) for i in (1, 2, 3)],
        "per_second": per_second,
        "limitations": "Baseline must be stationary. Integrated sensor-axis rates are not 3D pose. Host overlap is not exposure synchronization; startup exclusion is explicit.",
    }


def main() -> None:
    """Print analysis of one saved recording using a chosen initial still window.

    Args:
        None.

    Returns:
        None: argparse exits with an error for invalid recordings.
    """
    # Define the command-line interface without starting hardware work yet.
    parser = argparse.ArgumentParser(description=__doc__)
    # Declare folder with its existing default, validation and help text.
    parser.add_argument("folder", type=Path)
    # Declare --baseline-seconds with its existing default, validation and help text.
    parser.add_argument(
        "--baseline-seconds",
        type=float,
        default=1.0,
        help="assumed still window after RECORDING cue; inspect before accepting",
    )
    # Parse command-line values into the namespace used by this operation.
    args = parser.parse_args()
    # Keep failure handling alongside the operation so cleanup/status remains explicit.
    try:
        # Explain the current result, progress or failure in the terminal.
        print(
            json.dumps(
                analyze(args.folder, args.baseline_seconds), indent=2, allow_nan=False
            )
        )
    # Handle this failure without losing the error or skipping the enclosing cleanup.
    except (OSError, ValueError, KeyError, TypeError) as error:
        # Call parser.exit for this step; its contract describes the result or side effect.
        parser.exit(1, f"Analysis failed: {error}\n")


# Run the command only when executed directly, not when imported by tests or another module.
if __name__ == "__main__":
    # Call main for this step; its contract describes the result or side effect.
    main()
