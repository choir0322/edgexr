"""Compare four controlled image-motion trials without altering live tracking.

Run visual_motion on each combined recording first. This report uses its
per-frame-pair CSV, including rejected pairs; it does not inspect raw images.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from statistics import median


SCENARIOS = ("still", "slow_turn", "fast_turn", "moving_person")
NOTICEABLE_SHIFT_PX = 1.0  # Reporting threshold only; not an algorithm gate.


def number(row: dict[str, str], key: str) -> float | None:
    """Parse an optional numeric CSV field; blank means missing, not zero.

    Args:
        row (dict[str, str]): One visual_motion motion.csv record.
        key (str): Field name to read from that record.

    Returns:
        float | None: A finite value or None when the field is blank.
    """
    value = row[key]
    if value == "":
        return None
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ValueError(f"Nonfinite {key} in motion.csv")
    return parsed


def percentile(values: list[float], percentage: float) -> float | None:
    """Find a linearly interpolated percentile for a nonempty list.

    Args:
        values (list[float]): Finite observations, possibly empty.
        percentage (float): Percentile in the closed interval from 0 to 100.

    Returns:
        float | None: Requested percentile, or None for no observations.
    """
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * percentage / 100
    low = math.floor(position)
    weight = position - low
    return ordered[low] * (1 - weight) + ordered[min(low + 1, len(ordered) - 1)] * weight


def summarize(rows: list[dict[str, str]], scenario: str) -> dict[str, object]:
    """Report availability and displacement without treating rejection as zero.

    Args:
        rows (list[dict[str, str]]): All frame-pair records from visual_motion.
        scenario (str): Named trial condition; only still/person imply fixed camera.

    Returns:
        dict[str, object]: Counts, rates and per-second summaries with nulls for
            unavailable measurements.
    """
    if scenario not in SCENARIOS or not rows:
        raise ValueError("Expected a named scenario with at least one motion row")
    visual = []
    gyro_count = paired_count = noticeable_count = 0
    by_second: dict[int, list[tuple[float, float, float | None]]] = {}
    for row in rows:
        elapsed = number(row, "host_after_cue_s")
        dx, dy = number(row, "dx_pixels"), number(row, "dy_pixels")
        gyro_y = number(row, "gy_dps")
        if elapsed is None or elapsed < 0 or (dx is None) != (dy is None):
            raise ValueError("Invalid time or incomplete visual shift in motion.csv")
        gyro_count += gyro_y is not None
        paired_count += dx is not None and gyro_y is not None
        if dx is None:
            continue
        visual.append((dx, dy))
        noticeable_count += math.hypot(dx, dy) > NOTICEABLE_SHIFT_PX
        by_second.setdefault(int(elapsed), []).append((dx, dy, gyro_y))

    magnitudes = [math.hypot(dx, dy) for dx, dy in visual]
    per_second = [
        dict(
            second=second,
            visual_pairs=len(part),
            median_dx_pixels=median(x for x, _, _ in part),
            median_dy_pixels=median(y for _, y, _ in part),
            median_gyro_y_dps=median(gy for _, _, gy in part if gy is not None)
            if any(gy is not None for _, _, gy in part)
            else None,
        )
        for second, part in sorted(by_second.items())
    ]
    return dict(
        scenario=scenario,
        total_pairs=len(rows),
        visual_pairs=len(visual),
        visual_coverage=len(visual) / len(rows),
        gyro_covered_pairs=gyro_count,
        paired_pairs=paired_count,
        median_shift_pixels=median(magnitudes) if magnitudes else None,
        p95_shift_pixels=percentile(magnitudes, 95),
        noticeable_shift_pairs=noticeable_count,
        noticeable_shift_fraction_of_visual=noticeable_count / len(visual)
        if visual
        else None,
        per_second=per_second,
    )


def main() -> None:
    """Read four existing analyses and save a small, rerunnable JSON comparison.

    Args:
        None.

    Returns:
        None: CLI exits with a helpful message on invalid or missing input.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    for scenario in SCENARIOS:
        parser.add_argument(f"--{scenario.replace('_', '-')}", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or not args.output.resolve().is_relative_to(
        Path("recordings").resolve()
    ):
        parser.error("choose a new output directory under recordings/, from repo root")
    try:
        reports = []
        for scenario in SCENARIOS:
            folder = getattr(args, scenario)
            with (folder / "motion.csv").open(newline="") as handle:
                reports.append(summarize(list(csv.DictReader(handle)), scenario))
        result = {
            "noticeable_shift_threshold_pixels_per_pair": NOTICEABLE_SHIFT_PX,
            "scope": "320x180 image displacement per consecutive pair; no ground-truth rotation or synchronization",
            "trials": reports,
        }
        args.output.mkdir(parents=True, exist_ok=False)
        (args.output / "comparison.json").write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result, indent=2))
    except (OSError, ValueError, KeyError) as error:
        parser.exit(1, f"Motion-quality comparison failed: {error}\n")


if __name__ == "__main__":
    main()
