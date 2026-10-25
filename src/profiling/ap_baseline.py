"""Measure a verified live Pi workload without opening camera or model files."""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import time
from typing import Any
from urllib.parse import urlsplit

from vision.tracking_trial import fetch_snapshot, median_and_p95


Record = dict[str, Any]
DEFAULT_URL = "http://127.0.0.1:8765/api/telemetry"
DEFAULT_GRAPH = Path("models/mobilenet-ssd/deploy.prototxt")
DEFAULT_WEIGHTS = Path("models/mobilenet-ssd/mobilenet_iter_73000.caffemodel")


@dataclass(frozen=True)
class ProcessReading:
    """One Linux process observation, with identity and cumulative CPU ticks."""

    pid: int
    parent_pid: int | None
    start_ticks: int
    cpu_ticks: int
    rss_kib: int | None


def parse_proc_stat(text: str, pid: int) -> tuple[int, int]:
    """Extract CPU ticks and process start ticks despite spaces in command names.

    Args:
        text (str): Linux `/proc/PID/stat` line; fields before `)` include comm.
        pid (int): Expected numeric process ID.

    Returns:
        tuple[int, int]: User+system CPU ticks and boot-relative start ticks.
    """
    close = text.rfind(")")
    if close < 0 or not text.startswith(f"{pid} ("):
        raise ValueError(f"Malformed /proc/{pid}/stat identity")
    fields = text[close + 1:].split()  # Begins at field 3 (process state).
    if len(fields) < 22:
        raise ValueError(f"Incomplete /proc/{pid}/stat")
    return int(fields[11]) + int(fields[12]), int(fields[19])


def parse_proc_status(text: str) -> tuple[int | None, int | None]:
    """Extract parent PID and resident memory from a Linux status record.

    Args:
        text (str): Linux `/proc/PID/status` text.

    Returns:
        tuple[int | None, int | None]: Parent PID and resident KiB, if present.
    """
    parent = rss = None
    for line in text.splitlines():
        if line.startswith("PPid:"):
            parent = int(line.split()[1])
        elif line.startswith("VmRSS:"):
            parts = line.split()
            if len(parts) != 3 or parts[2] != "kB":
                raise ValueError("Expected VmRSS in kB")
            rss = int(parts[1])
    return parent, rss


def read_process(pid: int, proc_root: Path = Path("/proc")) -> ProcessReading:
    """Read one process's identity, CPU time and memory without controlling it.

    Args:
        pid (int): PID supplied by the live preview telemetry.
        proc_root (Path): Linux proc filesystem or a test fixture directory.

    Returns:
        ProcessReading: Snapshot of counters and RSS; read failure propagates.
    """
    if pid <= 0:
        raise ValueError("Process PID must be positive")
    folder = proc_root / str(pid)
    cpu_ticks, start_ticks = parse_proc_stat((folder / "stat").read_text(), pid)
    parent_pid, rss_kib = parse_proc_status((folder / "status").read_text())
    return ProcessReading(pid, parent_pid, start_ticks, cpu_ticks, rss_kib)


def parse_system_cpu(text: str) -> tuple[int, int]:
    """Extract aggregate CPU tick totals and idle-plus-iowait ticks.

    Args:
        text (str): `/proc/stat` contents starting with the aggregate `cpu` row.

    Returns:
        tuple[int, int]: All-core cumulative ticks and idle ticks.
    """
    fields = text.splitlines()[0].split()
    if fields[0] != "cpu" or len(fields) < 5:
        raise ValueError("Missing aggregate /proc/stat CPU row")
    values = [int(value) for value in fields[1:]]
    return sum(values), values[3] + (values[4] if len(values) > 4 else 0)


def process_cpu_percent(
    old: ProcessReading, new: ProcessReading, elapsed_s: float, ticks_per_s: int
) -> float:
    """Convert process CPU-tick growth to percent of one logical CPU.

    Args:
        old (ProcessReading): Earlier reading of one process.
        new (ProcessReading): Later reading of that same process.
        elapsed_s (float): Monotonic seconds separating observations.
        ticks_per_s (int): Linux clock ticks per second from `SC_CLK_TCK`.

    Returns:
        float: Percent where 100 means one fully used logical CPU; may exceed 100.
    """
    if (old.pid, old.start_ticks) != (new.pid, new.start_ticks):
        raise ValueError("Process identity changed during the benchmark")
    if elapsed_s <= 0 or ticks_per_s <= 0 or new.cpu_ticks < old.cpu_ticks:
        raise ValueError("Invalid CPU sampling interval or counter")
    return 100 * (new.cpu_ticks - old.cpu_ticks) / ticks_per_s / elapsed_s


def system_cpu_percent(old: tuple[int, int], new: tuple[int, int]) -> float:
    """Calculate aggregate busy fraction across all logical CPUs.

    Args:
        old (tuple[int, int]): Previous total and idle tick counts.
        new (tuple[int, int]): Current total and idle tick counts.

    Returns:
        float: Busy percent of aggregate CPU capacity, from zero to 100.
    """
    total_delta = new[0] - old[0]
    idle_delta = new[1] - old[1]
    if total_delta <= 0 or idle_delta < 0 or idle_delta > total_delta:
        raise ValueError("Invalid aggregate CPU counter change")
    return 100 * (total_delta - idle_delta) / total_delta


def read_temperature(path: Path = Path("/sys/class/thermal/thermal_zone0/temp")) -> float | None:
    """Read the conventional Pi thermal zone if exposed by this OS image.

    Args:
        path (Path): Millidegree-Celsius thermal-zone file or a test fixture.

    Returns:
        float | None: Degrees Celsius, or unavailable if the file cannot be read.
    """
    try:
        return int(path.read_text().strip()) / 1000
    except (OSError, ValueError):
        return None


def read_throttle_flag() -> str | None:
    """Read the Pi firmware's raw throttling flag without changing settings.

    Args:
        None.

    Returns:
        str | None: Hex flag from `vcgencmd get_throttled`, or unavailable.
    """
    if shutil.which("vcgencmd") is None:
        return None
    try:
        result = subprocess.run(
            ["vcgencmd", "get_throttled"], capture_output=True, text=True,
            timeout=2, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    match = re.fullmatch(r"throttled=(0x[0-9a-fA-F]+)", result.stdout.strip())
    return match.group(1).lower() if result.returncode == 0 and match else None


def sha256_file(path: Path) -> str | None:
    """Hash a local model artifact once for reproducibility, without loading it.

    Args:
        path (Path): Existing graph or weight file from the preview's default mode.

    Returns:
        str | None: SHA-256 hex digest, or unavailable for an unreadable file.
    """
    try:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            while True:
                chunk = stream.read(1024 * 1024)
                if not chunk:
                    break
                digest.update(chunk)
        return digest.hexdigest()
    except OSError:
        return None


def git_commit() -> str | None:
    """Read the checkout commit identifier without modifying Git.

    Args:
        None.

    Returns:
        str | None: Current commit hash, or unavailable outside Git.
    """
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def validate_preview(snapshot: Record, camera_axis_mode: str = "off") -> tuple[int, int]:
    """Require the agreed basic-tracking workload and camera-axis mode.

    Args:
        snapshot (Record): Metrics-only response from the running preview.
        camera_axis_mode (str): Expected conversion mode, ``off`` or ``on``.

    Returns:
        tuple[int, int]: Python preview PID and its FFmpeg child PID.
    """
    detector = snapshot.get("detector") or {}
    imu = snapshot.get("imu") or {}
    if snapshot.get("status") != "live":
        raise ValueError("Camera preview is not live")
    if detector.get("status") != "ready" or detector.get("tracking_mode") != "basic":
        raise ValueError("Run --detect without --motion-aware-tracking for this baseline")
    if imu.get("status") != "ready":
        raise ValueError("IMU is not ready; run the preview with --imu and wait for startup")
    if camera_axis_mode not in ("off", "on") or imu.get("camera_axis_mode") != camera_axis_mode:
        raise ValueError("Camera-axis mode differs from the requested A/B condition")
    if camera_axis_mode == "on" and (not isinstance(imu.get("camera_axis_conversions"), int)
                                     or imu["camera_axis_conversions"] < 1):
        raise ValueError("Camera-axis conversion count is unavailable")
    preview_pid, ffmpeg_pid = snapshot.get("preview_pid"), snapshot.get("ffmpeg_pid")
    if not all(type(pid) is int and pid > 0 for pid in (preview_pid, ffmpeg_pid)):
        raise ValueError("Telemetry has no process IDs; update and restart the Pi preview")
    return preview_pid, ffmpeg_pid


def read_counters(
    preview_pid: int, ffmpeg_pid: int, proc_root: Path = Path("/proc")
) -> tuple[ProcessReading, ProcessReading, tuple[int, int]]:
    """Read exact preview/FFmpeg processes and aggregate host CPU counters.

    Args:
        preview_pid (int): Live Python preview PID from local telemetry.
        ffmpeg_pid (int): Live decoder child PID from local telemetry.
        proc_root (Path): Linux proc filesystem or test fixture.

    Returns:
        tuple[ProcessReading, ProcessReading, tuple[int, int]]: Process and host
            counters; rejects a decoder that is not the preview's child.
    """
    preview = read_process(preview_pid, proc_root)
    ffmpeg = read_process(ffmpeg_pid, proc_root)
    if ffmpeg.parent_pid != preview_pid:
        raise ValueError("FFmpeg PID is not a child of the preview process")
    host = parse_system_cpu((proc_root / "stat").read_text())
    return preview, ffmpeg, host


def one_sample(
    snapshot: Record, observed_s: float, previous: tuple[ProcessReading, ProcessReading, tuple[int, int]],
    current: tuple[ProcessReading, ProcessReading, tuple[int, int]],
    elapsed_s: float, ticks_per_s: int,
) -> Record:
    """Join separately timed app, process, thermal and throttle observations.

    Args:
        snapshot (Record): Latest application telemetry without image pixels.
        observed_s (float): Collector monotonic time since measurement began.
        previous (tuple): Previous Python, FFmpeg and host CPU counters.
        current (tuple): New counters for the same processes and host.
        elapsed_s (float): Monotonic seconds between CPU counter reads.
        ticks_per_s (int): Linux process clock ticks per second.

    Returns:
        Record: One JSON-ready row with distinct units and measurement scopes.
    """
    detector = snapshot.get("detector") or {}
    imu = snapshot.get("imu") or {}
    return {
        "observed_s": round(observed_s, 3),
        "camera_status": snapshot.get("status"),
        "capture_fps": snapshot.get("capture_fps"),
        "analysis_fps": snapshot.get("analysis_fps"),
        "analysis_ms_latest": snapshot.get("analysis_ms"),
        "skipped_decoded_frames_total": snapshot.get("skipped"),
        "preview_cpu_pct_one_core": process_cpu_percent(previous[0], current[0], elapsed_s, ticks_per_s),
        "ffmpeg_cpu_pct_one_core": process_cpu_percent(previous[1], current[1], elapsed_s, ticks_per_s),
        "system_cpu_busy_pct_all_cores": system_cpu_percent(previous[2], current[2]),
        "preview_rss_mib": current[0].rss_kib / 1024 if current[0].rss_kib is not None else None,
        "ffmpeg_rss_mib": current[1].rss_kib / 1024 if current[1].rss_kib is not None else None,
        "temperature_c_thermal_zone0": read_temperature(),
        "throttle_flag_raw": read_throttle_flag(),
        "detector_status": detector.get("status"),
        "detector_sequence": detector.get("sequence"),
        "detector_rate_hz": detector.get("rate_hz"),
        "detector_compute_ms_latest": detector.get("compute_ms"),
        "box_source_age_ms": detector.get("age_ms"),
        "imu_status": imu.get("status"),
        "imu_rate_hz": imu.get("rate_hz"),
        "camera_axis_conversions_total": imu.get("camera_axis_conversions"),
    }


def summarize(samples: list[Record], elapsed_s: float) -> Record:
    """Summarize fixed-window samples without counting repeated detector results.

    Args:
        samples (list[Record]): Bounded one-second-or-slower observations.
        elapsed_s (float): Actual monotonic measurement duration.

    Returns:
        Record: Distribution and drift context with missing metrics left null.
    """
    fields = (
        "capture_fps", "analysis_fps", "analysis_ms_latest",
        "preview_cpu_pct_one_core", "ffmpeg_cpu_pct_one_core",
        "system_cpu_busy_pct_all_cores", "preview_rss_mib", "ffmpeg_rss_mib",
        "temperature_c_thermal_zone0", "detector_rate_hz", "imu_rate_hz",
    )
    result: Record = {"elapsed_s": elapsed_s, "sample_count": len(samples)}
    for key in fields:
        result[key] = median_and_p95([
            float(sample[key]) for sample in samples
            if isinstance(sample.get(key), (int, float))
        ])

    # Detector compute is a property of a completed result; count a source
    # sequence only once. Box age at first observation has the same rule.
    seen: set[int] = set()
    compute: list[float] = []
    ages: list[float] = []
    for sample in samples:
        sequence = sample.get("detector_sequence")
        if sample.get("detector_status") != "ready" or not isinstance(sequence, int) or sequence in seen:
            continue
        seen.add(sequence)
        if isinstance(sample.get("detector_compute_ms_latest"), (int, float)):
            compute.append(float(sample["detector_compute_ms_latest"]))
        if isinstance(sample.get("box_source_age_ms"), (int, float)):
            ages.append(float(sample["box_source_age_ms"]))
    result["distinct_detector_updates_observed"] = len(seen)
    result["detector_compute_ms_distinct"] = median_and_p95(compute)
    result["box_source_age_ms_at_first_poll"] = median_and_p95(ages)
    result["camera_status_counts"] = dict(Counter(str(s["camera_status"]) for s in samples))
    result["imu_status_counts"] = dict(Counter(str(s["imu_status"]) for s in samples))
    result["detector_status_counts"] = dict(Counter(str(s["detector_status"]) for s in samples))
    result["throttle_flag_counts"] = dict(Counter(str(s["throttle_flag_raw"]) for s in samples))
    skipped = [s["skipped_decoded_frames_total"] for s in samples if isinstance(s.get("skipped_decoded_frames_total"), int)]
    result["skipped_decoded_frames_increase"] = skipped[-1] - skipped[0] if len(skipped) >= 2 else None
    converted = [s["camera_axis_conversions_total"] for s in samples
                 if isinstance(s.get("camera_axis_conversions_total"), int)]
    result["camera_axis_conversions_increase"] = (converted[-1] - converted[0]
                                                  if len(converted) >= 2 else None)
    first = [s["temperature_c_thermal_zone0"] for s in samples if s["observed_s"] < 60 and s["temperature_c_thermal_zone0"] is not None]
    last = [s["temperature_c_thermal_zone0"] for s in samples if s["observed_s"] >= max(0, elapsed_s - 60) and s["temperature_c_thermal_zone0"] is not None]
    result["temperature_first_minute_c"] = median_and_p95(first)
    result["temperature_last_minute_c"] = median_and_p95(last)
    result["limits"] = (
        "CPU percent uses one logical CPU as 100% per process; system busy uses all-core capacity as 100%. "
        "HTTP, /proc, thermal and firmware reads are sequential host observations, not synchronized exposure or power measurements."
    )
    return result


def model_paths(preview_pid: int, proc_root: Path = Path("/proc")) -> tuple[Path, Path]:
    """Resolve the model files actually requested by the preview command line.

    Args:
        preview_pid (int): Running preview process from local telemetry.
        proc_root (Path): Linux proc filesystem or a test fixture.

    Returns:
        tuple[Path, Path]: Absolute graph and weight artifact paths.
    """
    folder = proc_root / str(preview_pid)
    arguments = [part.decode(errors="replace") for part in (folder / "cmdline").read_bytes().split(b"\0") if part]
    graph, weights = DEFAULT_GRAPH, DEFAULT_WEIGHTS
    for flag, default in (("--prototxt", DEFAULT_GRAPH), ("--weights", DEFAULT_WEIGHTS)):
        if flag in arguments:
            index = arguments.index(flag)
            if index + 1 >= len(arguments):
                raise ValueError(f"Preview {flag} has no path")
            value = Path(arguments[index + 1])
        else:
            value = default
        if flag == "--prototxt":
            graph = value
        else:
            weights = value
    cwd = folder.joinpath("cwd").resolve()
    return (
        graph if graph.is_absolute() else cwd / graph,
        weights if weights.is_absolute() else cwd / weights,
    )


def run_baseline(
    url: str, output: Path, warmup_s: float, seconds: float, interval_s: float,
    scene: str, power: str, cooling: str, camera_axis_mode: str = "off",
) -> Record:
    """Warm up the selected workload and collect one bounded AP measurement.

    Args:
        url (str): Local `/api/telemetry` endpoint of the running preview.
        output (Path): New ignored directory for metadata, samples and summary.
        warmup_s (float): Unmeasured stabilization period in seconds.
        seconds (float): Measured monotonic duration in seconds.
        interval_s (float): Seconds between sample starts, at least 0.5.
        scene (str): User description of the fixed, well-lit scene.
        power (str): User description of Pi supply or explicit unknown.
        cooling (str): User description of cooling or explicit unknown.
        camera_axis_mode (str): Required live conversion mode for this run.

    Returns:
        Record: Summary saved with the raw time series under the output path.
    """
    initial = fetch_snapshot(url)
    preview_pid, ffmpeg_pid = validate_preview(initial, camera_axis_mode)
    baseline = read_counters(preview_pid, ffmpeg_pid)
    graph, weights = model_paths(preview_pid)
    metadata: Record = {
        "status": "warming_up", "started_utc": datetime.now(timezone.utc).isoformat(),
        "host": platform.platform(), "git_commit": git_commit(),
        "preview_pid": preview_pid, "ffmpeg_pid": ffmpeg_pid,
        "tracking_mode": "basic", "detector_target_hz": 2,
        "camera_axis_mode": camera_axis_mode,
        "camera_axis_basis": (initial.get("imu") or {}).get("camera_axis_basis"),
        "camera_request": "1280x720 MJPEG 30 fps; negotiated mode not measured here",
        "motion_analysis_shape": "320x180 grayscale", "opencv_internal_threads": 2,
        "model_graph_path": str(graph), "model_graph_sha256": sha256_file(graph),
        "model_weights_path": str(weights), "model_weights_sha256": sha256_file(weights),
        "warmup_seconds": warmup_s, "requested_seconds": seconds,
        "sample_interval_seconds": interval_s,
        "scene": scene, "power": power, "cooling": cooling,
        "scope": "Read-only host observations; no camera images or exposure timestamps saved",
    }
    output.mkdir(parents=True, exist_ok=False)
    (output / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")

    # Warm up after verifying the exact workload. A later status check prevents
    # a failed or restarted preview from quietly becoming the measured run.
    if warmup_s:
        print(f"Warming up for {warmup_s:g} seconds; keep the scene stable.", flush=True)
    warmup_started = time.monotonic()
    while time.monotonic() - warmup_started < warmup_s:
        remaining = warmup_s - (time.monotonic() - warmup_started)
        time.sleep(min(5.0, remaining))
    ready = fetch_snapshot(url)
    if validate_preview(ready, camera_axis_mode) != (preview_pid, ffmpeg_pid):
        raise ValueError("Preview process changed during warm-up")
    previous = read_counters(preview_pid, ffmpeg_pid)
    if (previous[0].start_ticks, previous[1].start_ticks) != (baseline[0].start_ticks, baseline[1].start_ticks):
        raise ValueError("Preview or FFmpeg restarted during warm-up")

    metadata["status"] = "recording"
    metadata["measurement_started_utc"] = datetime.now(timezone.utc).isoformat()
    (output / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
    print(f"MEASURING for {seconds:g} seconds; keep the scene stable.", flush=True)
    ticks_per_s = os.sysconf("SC_CLK_TCK")
    samples: list[Record] = []
    started = previous_at = time.monotonic()
    deadline = started + seconds
    next_sample = min(started + interval_s, deadline)
    with (output / "samples.jsonl").open("x") as stream:
        while True:
            now = time.monotonic()
            time.sleep(max(0.0, next_sample - now))
            now = time.monotonic()
            snapshot = fetch_snapshot(url)
            if validate_preview(snapshot, camera_axis_mode) != (preview_pid, ffmpeg_pid):
                raise ValueError("Preview process changed during measurement")
            current = read_counters(preview_pid, ffmpeg_pid)
            sample = one_sample(snapshot, now - started, previous, current, now - previous_at, ticks_per_s)
            samples.append(sample)
            stream.write(json.dumps(sample, allow_nan=False) + "\n")
            previous, previous_at = current, now
            if next_sample >= deadline:
                break
            # Start spacing follows the actual prior poll; a slow read never
            # creates a catch-up burst of tightly spaced samples.
            next_sample = min(time.monotonic() + interval_s, deadline)

    report = summarize(samples, time.monotonic() - started)
    (output / "summary.json").write_text(json.dumps(report, indent=2) + "\n")
    metadata["status"] = "complete"
    metadata["finished_utc"] = datetime.now(timezone.utc).isoformat()
    (output / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
    return report


def main() -> None:
    """Parse Pi-only options and report a mode-verified AP measurement.

    Args:
        None; values come from the user's command line.

    Returns:
        None: Writes ignored measurement files or exits with a readable error.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--warmup-seconds", type=float, default=120.0)
    parser.add_argument("--seconds", type=float, default=300.0)
    parser.add_argument("--interval", type=float, default=1.0)
    parser.add_argument("--scene", required=True)
    parser.add_argument("--power", required=True)
    parser.add_argument("--cooling", required=True)
    parser.add_argument("--camera-axis-mode", choices=("off", "on"), default="off",
                        help="require matching live camera-axis conversion mode")
    args = parser.parse_args()
    parsed = urlsplit(args.url)
    if parsed.scheme != "http" or parsed.hostname not in ("127.0.0.1", "localhost") or parsed.path != "/api/telemetry":
        parser.error("--url must be a loopback http://.../api/telemetry endpoint")
    if not 0 <= args.warmup_seconds <= 1800 or not 1 <= args.seconds <= 3600 or not .5 <= args.interval <= 10:
        parser.error("warm-up must be 0–1800 s, measurement 1–3600 s, interval 0.5–10 s")
    if any(not value.strip() for value in (args.scene, args.power, args.cooling)):
        parser.error("scene, power and cooling must be described (use 'unknown' if needed)")
    try:
        result = run_baseline(
            args.url, args.output, args.warmup_seconds, args.seconds,
            args.interval, args.scene.strip(), args.power.strip(), args.cooling.strip(),
            args.camera_axis_mode,
        )
    except (OSError, ValueError, RuntimeError) as error:
        parser.exit(1, f"Baseline failed: {error}\n")
    print(json.dumps(result, indent=2))
    print(f"Saved metrics (no images) to {args.output}")


if __name__ == "__main__":
    main()
