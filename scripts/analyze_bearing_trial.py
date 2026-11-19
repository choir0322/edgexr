"""Summarize a step-1 bearing trial recorded by spatial.servo_orientation_demo.

Usage (Mac or Pi, standard library only):
    python3 scripts/analyze_bearing_trial.py recordings/bearing-trial-01 --output summary.json
Reads the run's telemetry.jsonl (preview snapshots about every 50 ms), keeps each
detector result once (by detector sequence), takes the highest-scoring box of the
chosen label and reports how stable its bearing stayed while the head moved.
Criteria were fixed on 2026-11-20 before any trial (docs/STEP1_BEARING_TRIAL.md).
Reads only the run folder; writes only --output.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

CRITERIA = {"min_ready_bearings": 20, "min_head_yaw_span_deg": 15.0,
            "max_yaw_spread_p5_p95_deg": 4.0, "max_pitch_spread_p5_p95_deg": 4.0,
            "max_still_yaw_spread_p5_p95_deg": 3.0, "max_first_last_still_difference_deg": 2.0}


def percentile(values: list[float], fraction: float) -> float:
    """Linear-interpolated percentile of a non-empty list.

    Args:
        values (list[float]): Samples.
        fraction (float): 0..1.
    Returns:
        float: Percentile value.
    """
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    low, high = math.floor(position), math.ceil(position)
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def stats(values: list[float]) -> dict[str, float] | None:
    """Median, 5th/95th percentiles and their spread.

    Args:
        values (list[float]): Samples in degrees.
    Returns:
        dict[str, float] | None: Summary, or None when empty.
    """
    if not values:
        return None
    p5, p95 = percentile(values, 0.05), percentile(values, 0.95)
    return {"n": len(values), "median": percentile(values, 0.5), "p5": p5, "p95": p95, "spread_p5_p95": p95 - p5}


def score(box: dict[str, Any]) -> float:
    """Detector confidence used to pick one box per result.

    Args:
        box (dict[str, Any]): Detection record.
    Returns:
        float: Confidence, zero when absent.
    """
    return float(box.get("confidence", 0))


def frame_time(row: dict[str, Any]) -> float:
    """Sort key: estimated frame receipt time of a bearing row.

    Args:
        row (dict[str, Any]): Bearing row.
    Returns:
        float: Host monotonic seconds.
    """
    return float(row["frame_s"])


def detections(run: Path, label: str) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Unique detector results with their best box of the chosen label.

    Args:
        run (Path): Servo-demo output folder.
        label (str): Detector class name, e.g. "bottle".
    Returns:
        tuple: Rows (frame time, bearing record) in time order and counts of skipped cases.
    """
    seen, rows = set(), []
    counts = {"telemetry_rows": 0, "unique_results": 0, "results_without_label": 0, "results_with_several": 0}
    for line in (run / "telemetry.jsonl").read_text().splitlines():
        row = json.loads(line)
        counts["telemetry_rows"] += 1
        detector = row.get("telemetry", {}).get("detector", {})
        sequence = detector.get("sequence")
        if detector.get("status") != "ready" or sequence is None or sequence in seen:
            continue
        seen.add(sequence)
        counts["unique_results"] += 1
        boxes = [b for b in detector.get("boxes", []) if b.get("label") == label and "bearing" in b]
        if not boxes:
            counts["results_without_label"] += 1
            continue
        counts["results_with_several"] += len(boxes) > 1
        best = max(boxes, key=score)
        frame_s = row["host_poll_midpoint_s"] - detector.get("age_ms", 0) / 1000
        rows.append({"frame_s": frame_s, "sequence": sequence, **best["bearing"]})
    rows.sort(key=frame_time)
    return rows, counts


def classify_motion(rows: list[dict[str, Any]]) -> None:
    """Label each ready row still / turning_right / turning_left from head yaw change.

    Args:
        rows (list[dict[str, Any]]): Time-ordered bearing rows (modified in place).
    Returns:
        None: Adds head_rate_dps and motion keys (rate over neighbouring results).
    """
    ready = [r for r in rows if r.get("status") == "ready"]
    for i, row in enumerate(ready):
        before, after = ready[max(0, i - 1)], ready[min(len(ready) - 1, i + 1)]
        dt = after["frame_s"] - before["frame_s"]
        rate = (after["head_yaw_deg"] - before["head_yaw_deg"]) / dt if dt > 0 else 0.0
        row["head_rate_dps"] = rate
        row["motion"] = "still" if abs(rate) < 1.0 else "turning_right" if rate > 3.0 else \
            "turning_left" if rate < -3.0 else "slow"


def summarize(run: Path, label: str) -> dict[str, Any]:
    """Build the trial summary and evaluate the fixed criteria.

    Args:
        run (Path): Servo-demo output folder.
        label (str): Detector class name.
    Returns:
        dict[str, Any]: Counts, statistics, latency estimate and criteria results.
    """
    rows, counts = detections(run, label)
    classify_motion(rows)
    ready = [r for r in rows if r.get("status") == "ready"]
    trusted = [r for r in ready if not r.get("extrapolated")]
    unknown: dict[str, int] = {}
    for r in rows:
        if r.get("status") != "ready":
            unknown[r.get("reason", "unknown")] = unknown.get(r.get("reason", "unknown"), 0) + 1
    still = [r for r in trusted if r["motion"] == "still"]
    by_motion = {m: stats([r["yaw_deg"] for r in trusted if r["motion"] == m])
                 for m in ("still", "turning_right", "turning_left", "slow")}
    # Receipt time trails exposure: while turning right the paired head yaw is too
    # far right, so bearings shift by about rate x latency in the turn direction.
    latency = None
    if by_motion["turning_right"] and by_motion["turning_left"]:
        rates = [abs(r["head_rate_dps"]) for r in trusted if r["motion"] in ("turning_right", "turning_left")]
        mean_rate = sum(rates) / len(rates)
        latency = 1000 * (by_motion["turning_right"]["median"] - by_motion["turning_left"]["median"]) / (2 * mean_rate)
    # First and last still stretches: does the bearing return after the sweep?
    first = [r["yaw_deg"] for r in still[:5]]
    last = [r["yaw_deg"] for r in still[-5:]]
    head_yaws = [r["head_yaw_deg"] for r in trusted]
    summary = {
        "label": label, "counts": {**counts, "label_results": len(rows), "ready": len(ready),
                                   "ready_not_extrapolated": len(trusted), "unknown_reasons": unknown},
        "bearing_yaw_deg": stats([r["yaw_deg"] for r in trusted]),
        "bearing_pitch_deg": stats([r["pitch_deg"] for r in trusted]),
        "image_yaw_deg_without_gyro": stats([r["image_yaw_deg"] for r in trusted]),
        "head_yaw_deg_while_visible": stats(head_yaws),
        "bearing_yaw_by_motion_deg": by_motion,
        "latency_estimate_ms": latency,
        "orientation_lag_ms": stats([r["orientation_lag_ms"] for r in ready]),
        "first_last_still_yaw_deg": [sum(first) / len(first), sum(last) / len(last)] if first and last else None,
        "criteria": CRITERIA,
    }
    yaw, pitch, still_yaw = summary["bearing_yaw_deg"], summary["bearing_pitch_deg"], by_motion["still"]
    ends = summary["first_last_still_yaw_deg"]
    summary["checks"] = {
        "enough_ready_bearings": len(trusted) >= CRITERIA["min_ready_bearings"],
        "head_moved_enough": bool(head_yaws) and max(head_yaws) - min(head_yaws) >= CRITERIA["min_head_yaw_span_deg"],
        "yaw_stable": bool(yaw) and yaw["spread_p5_p95"] <= CRITERIA["max_yaw_spread_p5_p95_deg"],
        "pitch_stable": bool(pitch) and pitch["spread_p5_p95"] <= CRITERIA["max_pitch_spread_p5_p95_deg"],
        "still_yaw_stable": bool(still_yaw) and still_yaw["spread_p5_p95"] <= CRITERIA["max_still_yaw_spread_p5_p95_deg"],
        "returns_after_sweep": bool(ends) and abs(ends[0] - ends[1]) <= CRITERIA["max_first_last_still_difference_deg"],
    }
    summary["pass"] = all(summary["checks"].values())
    summary["rows"] = rows
    return summary


def main() -> int:
    """Write the summary JSON and print the headline numbers.

    Args: None.
    Returns:
        int: Zero after writing; the pass flag is in the JSON, not the exit code.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    parser.add_argument("--label", default="bottle")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    summary = summarize(args.run, args.label)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(summary, stream, indent=1, allow_nan=False)
        stream.write("\n")
    print(json.dumps({k: v for k, v in summary.items() if k != "rows"}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
