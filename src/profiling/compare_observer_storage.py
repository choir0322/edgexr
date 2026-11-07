"""Read file/RAM spatial-profiler trials; report evidence without causal claims."""

import argparse
from collections import Counter
from collections.abc import Iterator
import json
import math
from pathlib import Path
import statistics


def distribution(values: list[float | None]) -> dict:
    """Summarize available observations using nearest-rank p95.

    Args:
        values (list[float | None]): Finite observations in the caller's units.
    Returns:
        dict: Count/median/p95/max; unavailable values are never converted to zero.
    """
    valid = sorted(v for v in values if v is not None and math.isfinite(v))
    return {"count": len(valid), "median": statistics.median(valid) if valid else None,
            "p95": valid[math.ceil(.95 * len(valid)) - 1] if valid else None,
            "max": max(valid) if valid else None}


def counter(text: str | None, key: str) -> float | None:
    """Extract a numeric procfs field, preserving absence.

    Args:
        text (str | None): Raw status, meminfo or vmstat text.
        key (str): Field name, without an optional trailing colon.
    Returns:
        float | None: Raw numeric value; status/meminfo memory is in KiB.
    """
    for line in (text or "").splitlines():
        fields = line.split()
        if len(fields) > 1 and fields[0].rstrip(":") == key:
            return float(fields[1])
    return None


def rows(path: Path) -> Iterator[dict]:
    """Stream JSONL records instead of retaining a whole measurement file.

    Args:
        path (Path): Required JSONL evidence file.
    Returns:
        Iterator[dict]: Parsed records; invalid or truncated lines raise.
    """
    with path.open() as source:
        for line in source:
            if line.strip():
                yield json.loads(line)


def summarize(folder: Path) -> dict:
    """Summarize one trial without assuming that completion equals acceptance.

    Args:
        folder (Path): Spatial profiler output containing metadata/summary/samples.
    Returns:
        dict: Configuration, timing, resource and continuity evidence with limits.
    """
    metadata = json.loads((folder / "metadata.json").read_text())
    summary = json.loads((folder / "summary.json").read_text())
    metrics = {name: [] for name in ("observer_gap_ms", "preview_cpu_pct_one_core",
               "preview_rss_kib", "observer_rss_kib", "observer_swap_kib",
               "mem_available_kib", "temperature_c", "image_write_ms", "scene_queue_wait_ms")}
    cycles = {}
    for row in rows(folder / "samples.jsonl"):
        metrics["observer_gap_ms"].append(row.get("sample_gap_ms"))
        metrics["preview_cpu_pct_one_core"].append(row.get("preview_cpu_pct_one_core"))
        metrics["preview_rss_kib"].append(counter(row.get("preview", {}).get("status", {}).get("text"), "VmRSS"))
        own = row.get("observer_status", {}).get("text")
        if own is not None:
            metrics["observer_rss_kib"].append(counter(own, "VmRSS"))
            metrics["observer_swap_kib"].append(counter(own, "VmSwap"))
        metrics["mem_available_kib"].append(counter(row.get("system", {}).get("meminfo", {}).get("text"), "MemAvailable"))
        temp = row.get("temperature_millic", {}).get("text")
        if temp is not None:
            metrics["temperature_c"].append(float(temp) / 1000)
        cycle = row.get("previous_observer_cycle")
        if cycle:
            cycles[cycle["sample_index"]] = cycle
    last = summary.get("last_observer_cycle")
    if last:
        cycles[last["sample_index"]] = last
    for key in ("serialize_wall_ms", "serialize_cpu_ms", "write_wall_ms", "write_cpu_ms",
                "wake_late_ms", "work_overrun_ms"):
        metrics[key] = [cycle.get(key) for cycle in cycles.values()]
    orientations = Counter()
    decisions = Counter()
    scene_path = folder / "scene" / "updates.jsonl"
    if scene_path.exists():
        for row in rows(scene_path):
            metrics["image_write_ms"].append(row.get("image_write_ms"))
            metrics["scene_queue_wait_ms"].append(row.get("recording_queue_wait_ms"))
            orientations[row.get("orientation_at_frame", {}).get("status", "missing")] += 1
            decisions[row.get("decision", {}).get("state", "missing")] += 1
    before = metadata.get("vmstat_before", {}).get("text")
    after = summary.get("vmstat_after", {}).get("text")
    final_status = summary.get("observer_final_status", {}).get("text")
    if final_status is not None:
        metrics["observer_rss_kib"].append(counter(final_status, "VmRSS"))
        metrics["observer_swap_kib"].append(counter(final_status, "VmSwap"))
    swap = {}
    for name in ("pswpin", "pswpout"):
        a, b = counter(before, name), counter(after, name)
        swap[name + "_pages_delta"] = b - a if a is not None and b is not None and b >= a else None
    duration = summary.get("elapsed_s", 0)
    cpu = summary.get("observer_cpu_s")
    return {"trial": folder.name, "mode": metadata.get("observer_output_mode", "file_legacy"),
            "revision": metadata.get("revision"),
            "configuration": {key: metadata.get(key) for key in
                ("schema", "requested_scene_seconds", "sample_interval_s", "camera_request", "scene", "power", "cooling")},
            "outcome": summary.get("collector_outcome"), "error": summary.get("error"),
            "preview_returncode": summary.get("preview_returncode"),
            "sample_count": summary.get("samples"), "elapsed_s": duration,
            "observer_cpu_s": cpu,
            "observer_average_cpu_pct_one_core": cpu / duration * 100 if cpu is not None and duration > 0 else None,
            "metrics": {key: distribution(values) for key, values in metrics.items()},
            "scene_recording": summary.get("scene_final", {}).get("recording"),
            "imu_continuity": summary.get("scene_final", {}).get("imu_poll_timing"),
            "orientation_status_counts": dict(orientations), "scene_decision_counts": dict(decisions),
            "scene_updates_available": scene_path.exists(),
            "swap": swap, "sample_sink": summary.get("sample_sink"), "sample_export": summary.get("sample_export"),
            "limits": "Different manual scenes/order/temperature can confound results. Sampled RSS/VmSwap can miss peaks; swap deltas are system-wide, not attribution. RAM write timing is buffer admission, not disk persistence. No automatic accuracy, trace-loss or card-health pass."}


def main() -> None:
    """Print a read-only report for two or more supplied trial directories.

    Args: None; command-line trial paths.
    Returns:
        None: JSON on stdout, no source modification.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folders", type=Path, nargs="+")
    args = parser.parse_args()
    try:
        print(json.dumps({"trials": [summarize(folder) for folder in args.folders]}, indent=2, allow_nan=False))
    except (OSError, ValueError) as error:
        parser.exit(1, f"Comparison failed: {error}\n")


if __name__ == "__main__":
    main()
