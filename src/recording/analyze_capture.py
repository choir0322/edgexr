"""Inspect saved timing and sensor-axis rotation; does not synchronize sensors."""

import argparse
import csv
import json
import math
from pathlib import Path
import statistics


def timing(times):
    if len(times) < 2 or not all(math.isfinite(t) for t in times):
        raise ValueError("Need at least two finite timestamps")
    gaps = [b - a for a, b in zip(times, times[1:])]
    if min(gaps) <= 0:
        raise ValueError("Timestamps must strictly increase")
    ordered = sorted(gaps)
    return dict(count=len(times), span_s=times[-1] - times[0],
                rate_hz=(len(times) - 1) / (times[-1] - times[0]),
                median_gap_ms=1000 * statistics.median(gaps),
                p95_gap_ms=1000 * ordered[math.ceil(0.95 * len(ordered)) - 1],
                max_gap_ms=1000 * max(gaps))


def mean_axes(rows):
    if len(rows) < 2:
        raise ValueError("Stationary window needs at least two samples")
    return [statistics.mean(r[k] for r in rows) for k in ("gx_dps", "gy_dps", "gz_dps")]


def integrate(rows, bias):
    timing([r["host_read_midpoint_s"] for r in rows])
    angles = [0.0] * 3
    trajectory = [[rows[0]["host_read_midpoint_s"], *angles]]
    for a, b in zip(rows, rows[1:]):
        dt = b["host_read_midpoint_s"] - a["host_read_midpoint_s"]
        for axis, key in enumerate(("gx_dps", "gy_dps", "gz_dps")):
            angles[axis] += ((a[key] + b[key]) / 2 - bias[axis]) * dt
        trajectory.append([b["host_read_midpoint_s"], *angles])
    return trajectory


def numeric_csv(path):
    with path.open() as handle:
        rows = [{k: float(v) for k, v in row.items()} for row in csv.DictReader(handle)]
    if not rows or any(not math.isfinite(v) for row in rows for v in row.values()):
        raise ValueError(f"Empty or nonfinite data: {path}")
    return rows


def analyze(folder, baseline_seconds=1.0):
    if not math.isfinite(baseline_seconds) or baseline_seconds <= 0:
        raise ValueError("Baseline seconds must be finite and positive")
    meta = json.loads((folder / "metadata.json").read_text())
    if meta["status"] != "complete":
        raise ValueError("Recording is incomplete; inspect metadata and FFmpeg log")
    duration = meta["requested_seconds_after_first_frame"]
    if not math.isfinite(duration) or not 0 < baseline_seconds < duration:
        raise ValueError("Baseline must be shorter than the finite recording duration")
    frames = numeric_csv(folder / "frames.csv")
    imu = numeric_csv(folder / "imu.csv")
    if len(frames) != meta["decoded_frames"] or len(imu) != meta["imu_samples"]:
        raise ValueError("CSV counts disagree with metadata")
    cue = meta["recording_cue_host_s"]
    if not math.isfinite(cue):
        raise ValueError("Invalid recording cue")
    baseline = [r for r in imu if cue <= r["host_read_midpoint_s"] < cue + baseline_seconds]
    bias = mean_axes(baseline)
    window = [r for r in imu if cue <= r["host_read_midpoint_s"] <= cue + meta["requested_seconds_after_first_frame"]]
    trajectory = integrate(window, bias)
    final_window = [r for r in window if r["host_read_midpoint_s"] >= window[-1]["host_read_midpoint_s"] - 2]
    tail_mean = mean_axes(final_window)
    per_second = []
    for second in range(math.ceil(meta["requested_seconds_after_first_frame"])):
        part = [r for r in window if second <= r["host_read_midpoint_s"] - cue < second + 1]
        if len(part) >= 2:
            per_second.append(dict(second=second, corrected_mean_dps=[a-b for a,b in zip(mean_axes(part),bias)]))
    pts = [r["camera_pts_s"] for r in frames]
    receipts = [r["host_receipt_s"] for r in frames]
    times = [r["host_read_midpoint_s"] for r in imu]
    return {
        "recording": folder.name,
        "camera_pts_all": timing(pts),
        "camera_pts_excluding_first_interval": timing(pts[1:]),
        "camera_host_receipts": timing(receipts), "imu_host_midpoints": timing(times),
        "common_host_coverage_s": max(0, min(receipts[-1], times[-1]) - max(receipts[0], times[0])),
        "baseline_window_after_cue_s": [0, baseline_seconds],
        "baseline_samples": len(baseline), "baseline_gyro_dps": bias,
        "baseline_std_dps": [statistics.pstdev(r[k] for r in baseline) for k in ("gx_dps", "gy_dps", "gz_dps")],
        "last_two_seconds_corrected_mean_dps": [a-b for a,b in zip(tail_mean,bias)],
        "integrated_span_s": trajectory[-1][0] - trajectory[0][0],
        "final_sensor_axis_degrees": trajectory[-1][1:],
        "min_sensor_axis_degrees": [min(r[i] for r in trajectory) for i in (1,2,3)],
        "max_sensor_axis_degrees": [max(r[i] for r in trajectory) for i in (1,2,3)],
        "per_second": per_second,
        "limitations": "Baseline must be stationary. Integrated sensor-axis rates are not 3D pose. Host overlap is not exposure synchronization; startup exclusion is explicit.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path)
    parser.add_argument("--baseline-seconds", type=float, default=1.0,
                        help="assumed still window after RECORDING cue; inspect before accepting")
    args = parser.parse_args()
    try:
        print(json.dumps(analyze(args.folder, args.baseline_seconds), indent=2, allow_nan=False))
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(1, f"Analysis failed: {error}\n")


if __name__ == "__main__":
    main()
