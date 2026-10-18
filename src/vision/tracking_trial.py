"""Record lightweight preview telemetry for a two-mode tracking comparison.

Run in a second Pi SSH terminal while one live preview is already running.
Only JSON metrics and detector boxes are saved; camera image bytes are omitted.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import platform
import statistics
import subprocess
import time
from typing import Any, Callable
from urllib.parse import urlsplit
from urllib.request import urlopen


Record = dict[str, Any]
URL = "http://127.0.0.1:8765/api/telemetry"


def fetch_snapshot(url: str) -> Record:
    """Read one small loopback snapshot without accessing the camera directly.

    Args:
        url (str): Local HTTP telemetry endpoint of the running preview.

    Returns:
        Record: JSON camera, detector and IMU state with no image bytes.
    """
    with urlopen(url, timeout=2) as response:
        snapshot = json.load(response)
    if not isinstance(snapshot, dict) or "detector" not in snapshot:
        raise ValueError("Preview returned no detector telemetry")
    if "pixels_b64" in snapshot:
        raise ValueError("Refusing an endpoint that returns camera image bytes")
    return snapshot


def compact_sample(snapshot: Record, observed_s: float) -> Record:
    """Keep the metrics and box identities needed for later comparison.

    Args:
        snapshot (Record): One live `/api/telemetry` response.
        observed_s (float): Recorder monotonic seconds relative to trial start.

    Returns:
        Record: Small serializable record; no image pixels or model data.
    """
    detector = snapshot.get("detector") or {}
    imu = snapshot.get("imu") or {}
    gyro = imu.get("gyro_dps")
    return {
        "observed_s": round(observed_s, 4),
        "camera_status": snapshot.get("status"),
        "received": snapshot.get("received"),
        "analyzed": snapshot.get("analyzed"),
        "skipped": snapshot.get("skipped"),
        "capture_fps": snapshot.get("capture_fps"),
        "analysis_fps": snapshot.get("analysis_fps"),
        "analysis_ms": snapshot.get("analysis_ms"),
        "motion": snapshot.get("motion"),
        "dx_small_px": snapshot.get("dx"),
        "dy_small_px": snapshot.get("dy"),
        "imu_status": imu.get("status"),
        "imu_rate_hz": imu.get("rate_hz"),
        "gyro_y_dps": gyro[1] if isinstance(gyro, (list, tuple)) and len(gyro) == 3 else None,
        "detector_status": detector.get("status"),
        "tracking_mode": detector.get("tracking_mode"),
        "detector_sequence": detector.get("sequence"),
        "detector_rate_hz": detector.get("rate_hz"),
        "detector_compute_ms": detector.get("compute_ms"),
        "box_source_age_ms": detector.get("age_ms"),
        "tracking_stats": detector.get("tracking_stats") or {},
        "boxes": [
            {
                "label": box.get("label"),
                "track_id": box.get("track_id"),
                "confidence": box.get("confidence"),
                "box_xyxy": box.get("box_xyxy"),
            }
            for box in detector.get("boxes", [])
        ],
    }


def phase_at(elapsed_s: float, total_s: float) -> str:
    """Divide a trial into still, turn/return, and final still windows.

    Args:
        elapsed_s (float): Recorder time since the first trial poll.
        total_s (float): Requested trial duration.

    Returns:
        str: Phase label based on sixths of the requested duration.
    """
    if elapsed_s < total_s / 6:
        return "start_still"
    if elapsed_s < total_s * 5 / 6:
        return "turn_and_return"
    return "end_still"


def median_and_p95(values: list[float]) -> Record:
    """Summarize observed values without assuming a normal distribution.

    Args:
        values (list[float]): Finite observed rates, ages or durations.

    Returns:
        Record: Sample count, median and nearest-rank p95, or null estimates.
    """
    ordered = sorted(values)
    if not ordered:
        return {"count": 0, "median": None, "p95": None}
    rank = max(0, (95 * len(ordered) + 99) // 100 - 1)
    return {"count": len(ordered), "median": statistics.median(ordered), "p95": ordered[rank]}


class TrialSummary:
    """Summarize distinct detector updates, not repeated HTTP polls."""

    def __init__(self, mode: str, target_label: str) -> None:
        """Prepare counters for one recorder run.

        Args:
            mode (str): Expected `basic` or `motion-aware` preview mode.
            target_label (str): Category that should appear at most once per update.

        Returns:
            None: Creates empty counters without starting hardware.
        """
        self.mode = mode
        self.target_label = target_label
        self.statuses: Counter[str] = Counter()
        self.last_sequence: int | None = None
        self.last_unique_id: int | None = None
        self.updates = 0
        self.target_visible_updates = 0
        self.target_missing_updates = 0
        self.target_ambiguous_updates = 0
        self.continuous_id_changes = 0
        self.phase_updates: Counter[str] = Counter()
        self.phase_id_changes: Counter[str] = Counter()
        self.phase_motion_only: Counter[str] = Counter()
        self.gyro_y_by_phase: dict[str, list[float]] = {}
        self.stats: Counter[str] = Counter()
        self.analysis_rates: list[float] = []
        self.detector_costs: list[float] = []
        self.source_ages: list[float] = []
        self.first_skipped: int | None = None
        self.last_skipped: int | None = None

    def add(self, sample: Record) -> bool:
        """Account for one poll and identify whether it saw a new detector result.

        Args:
            sample (Record): Compact telemetry from one HTTP response.

        Returns:
            bool: True only for the first observation of a ready detector sequence.
        """
        self.statuses[str(sample["detector_status"])] += 1
        rate = sample.get("analysis_fps")
        if isinstance(rate, (int, float)):
            self.analysis_rates.append(float(rate))
        skipped = sample.get("skipped")
        if isinstance(skipped, int):
            if self.first_skipped is None:
                self.first_skipped = skipped
            self.last_skipped = skipped
        gyro_y = sample.get("gyro_y_dps")
        if isinstance(gyro_y, (int, float)):
            phase = str(sample.get("phase", "unlabelled"))
            self.gyro_y_by_phase.setdefault(phase, []).append(abs(float(gyro_y)))

        sequence = sample.get("detector_sequence")
        if sample.get("detector_status") != "ready" or not isinstance(sequence, int):
            self.last_unique_id = None
            return False
        if sequence == self.last_sequence:
            return False
        self.last_sequence = sequence
        self.updates += 1
        phase = str(sample.get("phase", "unlabelled"))
        self.phase_updates[phase] += 1
        for key in ("covered_tracks", "fallback_tracks", "motion_matches", "motion_only_matches"):
            self.stats[key] += int(sample["tracking_stats"].get(key, 0))
        self.phase_motion_only[phase] += int(sample["tracking_stats"].get("motion_only_matches", 0))
        for value, destination in (
            (sample.get("detector_compute_ms"), self.detector_costs),
            (sample.get("box_source_age_ms"), self.source_ages),
        ):
            if isinstance(value, (int, float)):
                destination.append(float(value))

        # A single target-class box permits an observed ID-transition count.
        # Missing or multiple such boxes break continuity rather than guessing
        # which physical object a track_id belongs to.
        targets = [box for box in sample["boxes"] if box["label"] == self.target_label]
        if len(targets) != 1 or not isinstance(targets[0].get("track_id"), int):
            if not targets:
                self.target_missing_updates += 1
            else:
                self.target_ambiguous_updates += 1
            self.last_unique_id = None
        else:
            current_id = targets[0]["track_id"]
            self.target_visible_updates += 1
            if self.last_unique_id is not None and current_id != self.last_unique_id:
                self.continuous_id_changes += 1
                self.phase_id_changes[phase] += 1
            self.last_unique_id = current_id
        return True

    def report(self, elapsed_s: float, poll_errors: int) -> Record:
        """Produce a comparison-ready summary with explicit interpretation limits.

        Args:
            elapsed_s (float): Actual monotonic trial duration.
            poll_errors (int): HTTP/JSON read failures during this trial.

        Returns:
            Record: Counts and observed distributions, not accuracy ground truth.
        """
        opportunities = self.stats["covered_tracks"] + self.stats["fallback_tracks"]
        return {
            "mode": self.mode,
            "target_label": self.target_label,
            "elapsed_s": elapsed_s,
            "poll_errors": poll_errors,
            "detector_status_polls": dict(self.statuses),
            "detector_updates_observed": self.updates,
            "observed_updates_per_s": self.updates / elapsed_s if elapsed_s > 0 else None,
            "target_visible_updates": self.target_visible_updates,
            "target_missing_updates": self.target_missing_updates,
            "target_ambiguous_updates": self.target_ambiguous_updates,
            "continuous_target_id_changes": self.continuous_id_changes,
            "detector_updates_by_phase": dict(self.phase_updates),
            "target_id_changes_by_phase": dict(self.phase_id_changes),
            "motion_only_matches_by_phase": dict(self.phase_motion_only),
            "absolute_gyro_y_dps_by_phase": {
                phase: median_and_p95(values)
                for phase, values in self.gyro_y_by_phase.items()
            },
            "tracking_counts_across_observed_updates": dict(self.stats),
            "motion_coverage_fraction": self.stats["covered_tracks"] / opportunities if opportunities else None,
            "motion_analysis_fps": median_and_p95(self.analysis_rates),
            "detector_compute_ms": median_and_p95(self.detector_costs),
            "box_source_age_ms_at_first_poll": median_and_p95(self.source_ages),
            "skipped_decoded_frames_increase": (
                self.last_skipped - self.first_skipped
                if self.first_skipped is not None and self.last_skipped is not None else None
            ),
            "interpretation": "ID changes are observed transitions for one unique target label, not ground-truth identity errors; false holds require human review.",
        }


def git_commit() -> str | None:
    """Read the local commit identifier without changing Git state.

    Args:
        None.

    Returns:
        str | None: Current commit hash, or unknown outside a repository.
    """
    result = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=False)
    return result.stdout.strip() if result.returncode == 0 else None


def run_trial(
    url: str, mode: str, target_label: str, seconds: float, interval: float,
    output: Path, notes: str, fetch: Callable[[str], Record] = fetch_snapshot,
) -> Record:
    """Poll a running preview for a fixed interval and save a reproducible trial.

    Args:
        url (str): Local telemetry endpoint.
        mode (str): Expected tracker mode, checked before creating files.
        target_label (str): Unique category to watch for ID transitions.
        seconds (float): Requested monotonic recording duration.
        interval (float): Delay between poll starts, in seconds.
        output (Path): New directory for metadata, JSONL samples and summary.
        notes (str): User description of scene and movement.
        fetch (Callable): Injectable snapshot reader for hardware-free tests.

    Returns:
        Record: Summary also written to output/summary.json.
    """
    first = fetch(url)
    actual_mode = first["detector"].get("tracking_mode")
    if actual_mode != mode:
        raise ValueError(f"Preview mode is {actual_mode!r}, expected {mode!r}; restart preview first")
    if first["detector"].get("status") == "off":
        raise ValueError("Detector is off; start the preview with --detect")
    output.mkdir(parents=True, exist_ok=False)
    metadata = {
        "status": "recording", "expected_mode": mode, "target_label": target_label,
        "requested_seconds": seconds, "poll_interval_seconds": interval,
        "notes": notes, "started_utc": datetime.now(timezone.utc).isoformat(),
        "host": platform.platform(), "git_commit": git_commit(), "endpoint": url,
        "camera_request": "1280x720 MJPEG 30 fps in live preview; verify actual Pi mode separately",
        "scope": "HTTP host-observation metrics and detector boxes; no frames, ground-truth IDs or exposure timestamps",
    }
    (output / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
    summary = TrialSummary(mode, target_label)
    errors = 0
    started = time.monotonic()
    next_poll = started
    last_phase = None
    with (output / "samples.jsonl").open("x") as stream:
        while True:
            now = time.monotonic()
            if now - started >= seconds:
                break
            if now < next_poll:
                time.sleep(min(next_poll - now, seconds - (now - started)))
                continue
            next_poll = now + interval
            try:
                snapshot = first if summary.statuses == Counter() else fetch(url)
                sample = compact_sample(snapshot, now - started)
                sample["phase"] = phase_at(now - started, seconds)
                if sample["phase"] != last_phase:
                    last_phase = sample["phase"]
                    if seconds >= 5:
                        print(f"{last_phase}: {'keep the rig still' if last_phase != 'turn_and_return' else 'gently turn and return while keeping the target visible'}", flush=True)
                if sample["tracking_mode"] != mode:
                    raise ValueError("Preview changed tracking mode during the trial")
                stream.write(json.dumps(sample, allow_nan=False) + "\n")
                summary.add(sample)
            except (OSError, ValueError, KeyError, TypeError) as error:
                errors += 1
                if errors >= 5 and summary.updates == 0:
                    raise RuntimeError("No usable preview telemetry; check the Pi preview") from error
    report = summary.report(time.monotonic() - started, errors)
    (output / "summary.json").write_text(json.dumps(report, indent=2) + "\n")
    metadata["status"] = "complete"
    metadata["finished_utc"] = datetime.now(timezone.utc).isoformat()
    (output / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
    return report


def main() -> None:
    """Parse one Pi trial request and print the resulting concise summary.

    Args:
        None; values come from the user's command line.

    Returns:
        None: Writes trial files or exits with a readable usage error.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("basic", "motion-aware"), required=True)
    parser.add_argument("--target-label", default="person")
    parser.add_argument("--seconds", type=float, default=60.0)
    parser.add_argument("--interval", type=float, default=0.1)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--notes", default="")
    parser.add_argument("--url", default=URL)
    args = parser.parse_args()
    parsed = urlsplit(args.url)
    if parsed.scheme != "http" or parsed.hostname not in ("127.0.0.1", "localhost") or parsed.path != "/api/telemetry":
        parser.error("--url must be a loopback http://.../api/telemetry endpoint")
    if not 0 < args.seconds <= 3600 or not 0.05 <= args.interval <= 5:
        parser.error("seconds must be (0, 3600] and interval must be [0.05, 5]")
    if not args.target_label.strip():
        parser.error("target label must not be empty")
    try:
        report = run_trial(
            args.url, args.mode, args.target_label.strip(), args.seconds,
            args.interval, args.output, args.notes,
        )
    except (OSError, ValueError, RuntimeError) as error:
        parser.exit(1, f"Trial failed: {error}\n")
    print(json.dumps(report, indent=2))
    print(f"Saved metrics (no images) to {args.output}")


if __name__ == "__main__":
    main()
