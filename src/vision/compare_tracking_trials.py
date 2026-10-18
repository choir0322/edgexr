"""Compare two saved EdgeXR tracking-trial summaries without claiming ground truth."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


Record = dict[str, Any]


def load_report(folder: Path, expected_mode: str) -> Record:
    """Read one completed trial and guard against mode-label mistakes.

    Args:
        folder (Path): Directory produced by vision.tracking_trial.
        expected_mode (str): Required mode for this side of the comparison.

    Returns:
        Record: Summary fields, or raises for missing/incomplete/wrong-mode data.
    """
    metadata = json.loads((folder / "metadata.json").read_text())
    report = json.loads((folder / "summary.json").read_text())
    if metadata.get("status") != "complete" or report.get("mode") != expected_mode:
        raise ValueError(f"{folder} is not a complete {expected_mode} trial")
    if metadata.get("expected_mode") != expected_mode:
        raise ValueError(f"{folder} metadata does not match {expected_mode}")
    report["trial_metadata"] = metadata
    return report


def comparison(basic: Record, aware: Record) -> Record:
    """Place comparable observed metrics side by side without inventing accuracy.

    Args:
        basic (Record): Completed baseline summary.
        aware (Record): Completed motion-aware summary.

    Returns:
        Record: Parallel metrics and interpretation cautions.
    """
    if basic.get("target_label") != aware.get("target_label"):
        raise ValueError("Trials must use the same target label")
    fields = (
        "elapsed_s", "detector_updates_observed", "observed_updates_per_s",
        "target_visible_updates", "target_missing_updates", "target_ambiguous_updates",
        "continuous_target_id_changes", "target_id_changes_by_phase",
        "detector_updates_by_phase", "motion_only_matches_by_phase",
        "absolute_gyro_y_dps_by_phase",
        "skipped_decoded_frames_increase",
    )
    sides = {key: {"basic": basic.get(key), "motion_aware": aware.get(key)} for key in fields}
    for metric in ("motion_analysis_fps", "detector_compute_ms", "box_source_age_ms_at_first_poll"):
        sides[metric] = {
            "basic": basic.get(metric), "motion_aware": aware.get(metric)
        }
    sides["aware_matching"] = aware.get("tracking_counts_across_observed_updates", {})
    sides["aware_coverage_fraction"] = aware.get("motion_coverage_fraction")
    sides["run_context"] = {
        mode: {
            key: report.get("trial_metadata", {}).get(key)
            for key in ("git_commit", "host", "notes", "requested_seconds", "camera_request")
        }
        for mode, report in (("basic", basic), ("motion_aware", aware))
    }
    return {
        "target_label": basic["target_label"], "metrics": sides,
        "warning": (
            "This is an observation of two separate runs, not paired frames or ground-truth identity accuracy. "
            "Compare scene, lighting, movement, duration, software commit and missed detections; "
            "review false ID holds by eye. Zero motion-only matches can be expected when raw IoU already suffices."
        ),
    }


def main() -> None:
    """Read the two Pi trial folders and print a JSON comparison.

    Args:
        None; trial paths come from the command line.

    Returns:
        None: Prints a comparison or exits with a readable error.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("basic", type=Path, help="Output directory of --mode basic")
    parser.add_argument("motion_aware", type=Path, help="Output directory of --mode motion-aware")
    args = parser.parse_args()
    try:
        basic = load_report(args.basic, "basic")
        aware = load_report(args.motion_aware, "motion-aware")
        result = comparison(basic, aware)
    except (OSError, ValueError, KeyError) as error:
        parser.exit(1, f"Comparison failed: {error}\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
