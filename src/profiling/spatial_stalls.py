"""Launch a timed spatial workload and observe Linux task/resource counters."""

from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import platform
import shutil
import signal
import socket
import subprocess
import sys
import time
from urllib.request import urlopen


def read_optional(path: Path) -> dict:
    """Read an accounting file without requiring it to exist or be permitted.

    Args:
        path (Path): Small procfs/sysfs text file.
    Returns:
        dict: Text or explicit error; absence is never a zero counter.
    """
    try:
        return {"text": path.read_text().strip(), "error": None}
    except OSError as error:
        return {"text": None, "error": str(error)}


def parse_stat(text: str) -> dict:
    """Extract Linux stat identity and cumulative CPU/fault counters.

    Args:
        text (str): /proc/PID/stat or task/TID/stat; comm may contain parentheses.
    Returns:
        dict: CPU ticks, start ticks, faults, sampled state and last CPU.
    """
    left, right = text.find("("), text.rfind(")")
    fields = text[right + 1:].split()
    if left < 0 or right <= left or len(fields) < 37:
        raise ValueError("Incomplete Linux stat record")
    return {"id": int(text[:left]), "comm": text[left + 1:right],
            "state": fields[0], "ppid": int(fields[1]),
            "minor_faults": int(fields[7]), "major_faults": int(fields[9]),
            "cpu_ticks": int(fields[11]) + int(fields[12]),
            "start_ticks": int(fields[19]), "last_cpu": int(fields[36])}


def parse_schedstat(text: str) -> dict:
    """Decode cumulative kernel scheduling accounting, if enabled.

    Args:
        text (str): Three whitespace-separated /proc/task/schedstat counters.
    Returns:
        dict: On-CPU ns, runnable-wait ns and timeslices; zeros may be disabled.
    """
    values = [int(value) for value in text.split()]
    if len(values) != 3 or min(values) < 0:
        raise ValueError("Invalid schedstat counters")
    return dict(zip(("runtime_ns", "runqueue_ns", "timeslices"), values))


def cpu_delta(old: dict | None, new: dict, elapsed: float, ticks: int) -> float | None:
    """Calculate one-core CPU percent only for the same process/task lifetime.

    Args:
        old (dict | None): Previous parsed stat counters.
        new (dict): Current parsed counters.
        elapsed (float): Seconds between these observations.
        ticks (int): Linux SC_CLK_TCK value.
    Returns:
        float | None: Percent, or unavailable after reuse/reset/invalid interval.
    """
    if (old is None or elapsed <= 0 or ticks <= 0 or
            (old["id"], old["start_ticks"]) != (new["id"], new["start_ticks"]) or
            new["cpu_ticks"] < old["cpu_ticks"]):
        return None
    return (new["cpu_ticks"] - old["cpu_ticks"]) / ticks / elapsed * 100


def read_task(folder: Path) -> dict:
    """Read one task; tolerate exit races and unavailable kernel accounting.

    Args:
        folder (Path): /proc/PID or /proc/PID/task/TID.
    Returns:
        dict: Separately timed raw observations and parsed identity/counters.
    """
    result = {"read_started_host_s": time.monotonic()}
    for name in ("stat", "status", "schedstat", "wchan", "io"):
        result[name] = read_optional(folder / name)
    for name, parser in (("stat", parse_stat), ("schedstat", parse_schedstat)):
        value = result[name]
        if value["text"] is not None:
            try:
                value["parsed"] = parser(value["text"])
            except ValueError as error:
                value["error"] = str(error)
    result["read_finished_host_s"] = time.monotonic()
    return result


def read_process(pid: int, proc_root: Path = Path("/proc")) -> dict:
    """Sample process and native-thread accounting with bounded task enumeration.

    Args:
        pid (int): Owned preview or verified direct FFmpeg child PID.
        proc_root (Path): Linux procfs root, injectable for tests.
    Returns:
        dict: Process RSS/status/I/O and up to 256 task snapshots.
    """
    folder = proc_root / str(pid)
    result = read_task(folder)
    try:
        tasks = sorted((folder / "task").iterdir())
        result["tasks_truncated"] = len(tasks) > 256
        result["tasks"] = {p.name: read_task(p) for p in tasks[:256]}
    except OSError as error:
        result.update(tasks={}, tasks_error=str(error))
    return result


def fetch_telemetry(port: int, expected_pid: int) -> dict:
    """Poll local app with a short timeout; reject another preview's data.

    Args:
        port (int): Selected loopback preview port.
        expected_pid (int): Exact child launched by this observer.
    Returns:
        dict: Snapshot plus timing, or explicit timeout/error without stale reuse.
    """
    result = {"started_host_s": time.monotonic()}
    try:
        with urlopen(f"http://127.0.0.1:{port}/api/telemetry", timeout=0.15) as response:
            value = json.load(response)
        if value.get("preview_pid") != expected_pid:
            raise ValueError("Telemetry PID does not match launched preview")
        result["snapshot"] = value
    except (OSError, ValueError) as error:
        result["error"] = str(error)
    result["finished_host_s"] = time.monotonic()
    return result


def stop_child(child: subprocess.Popen, grace: float = 10.0) -> None:
    """Stop only our launched process session after interruption/watchdog expiry.

    Args:
        child (subprocess.Popen): Preview started with its own session.
        grace (float): Seconds allowed for app/recorder shutdown before termination.
    Returns:
        None: Owned process is reaped; forced shutdown may leave incomplete logs.
    """
    if child.poll() is not None:
        return
    child.send_signal(signal.SIGINT)
    try:
        child.wait(timeout=grace)
    except subprocess.TimeoutExpired:
        os.killpg(child.pid, signal.SIGKILL)
        child.wait()


def run(args: argparse.Namespace) -> dict:
    """Launch one fixed profile and save bounded-time Linux observations.

    Args:
        args (argparse.Namespace): Validated CLI settings; output must be new.
    Returns:
        dict: Collector outcome and separate scene-recorder outcome, not accuracy.
    """
    output = args.output.resolve()
    root = (Path.cwd() / "recordings").resolve()
    if output == root or not output.is_relative_to(root) or output.exists():
        raise ValueError("Output must be a new directory under recordings/")
    if platform.system() != "Linux" or not Path("/proc/self/stat").exists():
        raise ValueError("Run this observer on the Linux Pi")
    basis = Path("configs/camera_axes_neutral.json")
    if not basis.is_file() or not shutil.which("ffmpeg"):
        raise ValueError("Run in the repo with existing axis basis and FFmpeg")
    # Check the port before creating an evidence folder or launching hardware.
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", args.port))
    output.mkdir(parents=True, exist_ok=False)
    command = [sys.executable, "-m", "app.live_preview", "--device", args.device,
               "--port", str(args.port), "--imu", "--imu-sleep-ms", "10",
               "--camera-axis-basis", str(basis), "--relative-orientation",
               "--scene-memory", "--scene-output", str(output / "scene"),
               "--scene-save-images", "--scene-seconds", str(args.seconds)]
    status = subprocess.run(["git", "status", "--short"], capture_output=True, text=True)
    revision = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True)
    started, cpu_started = time.monotonic(), time.process_time()
    ticks = os.sysconf("SC_CLK_TCK")
    metadata = {"schema": 1, "started_host_s": started, "started_unix_s": time.time(),
                "command": command, "revision": revision.stdout.strip(),
                "git_status": status.stdout, "host": platform.platform(),
                "python": platform.python_version(), "ticks_per_second": ticks,
                "requested_scene_seconds": args.seconds, "sample_interval_s": args.interval,
                "telemetry_interval_s": 1.0, "telemetry_timeout_s": 0.15,
                "scene": args.scene, "power": args.power, "cooling": args.cooling,
                "camera_request": "1280x720 MJPEG 30 fps; negotiated mode not measured",
                "sched_schedstats": read_optional(Path("/proc/sys/kernel/sched_schedstats")),
                "task_delayacct": read_optional(Path("/proc/sys/kernel/task_delayacct")),
                "perf_event_paranoid": read_optional(Path("/proc/sys/kernel/perf_event_paranoid")),
                "available_tools": {name: shutil.which(name) for name in ("perf", "trace-cmd", "pidstat")},
                "scope": "Sequential host observations; schedstat runqueue wait is not GIL/lock wait. State/wchan are sampled. No kernel setting changed, no exposure sync or power measurement."}
    (output / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
    count = 0
    previous = None
    previous_at = None
    max_gap = max_collection = 0.0
    telemetry_errors = 0
    reason = "child_exited"
    child = None
    next_http = started
    error = None
    print(f"Preview: http://127.0.0.1:{args.port}; saving profiling and scene images to {output}", flush=True)
    print(f"Remain still at startup. Enroll/revisit three views in browser; app timer is {args.seconds:g} s. No servo commands.", flush=True)
    try:
        with (output / "preview.log").open("x") as app_log, (output / "samples.jsonl").open("x") as log:
            child = subprocess.Popen(command, stdout=app_log, stderr=subprocess.STDOUT,
                                     start_new_session=True)
            while child.poll() is None:
                now = time.monotonic()
                if now - started > args.seconds + 40:
                    reason = "watchdog_expired"
                    break
                row = {"started_host_s": now, "observer_cpu_s": time.process_time() - cpu_started}
                process = read_process(child.pid)
                current = process["stat"].get("parsed")
                if previous_at is not None:
                    max_gap = max(max_gap, now - previous_at)
                row["preview_cpu_pct_one_core"] = (cpu_delta(previous, current, now - previous_at, ticks)
                    if current is not None and previous_at is not None else None)
                if current is not None:
                    previous, previous_at = current, now
                row["preview"] = process
                # Find only direct children of the launched app, even if HTTP stalls.
                children = read_optional(Path(f"/proc/{child.pid}/task/{child.pid}/children"))
                row["children"] = children
                row["child_processes"] = {}
                for pid in (children["text"] or "").split()[:16]:
                    observation = read_process(int(pid))
                    if observation["stat"].get("parsed", {}).get("ppid") == child.pid:
                        row["child_processes"][pid] = observation
                if now >= next_http:
                    row["telemetry"] = fetch_telemetry(args.port, child.pid)
                    telemetry_errors += int("error" in row["telemetry"])
                    row["system"] = {name: read_optional(Path("/proc") / name) for name in
                                     ("stat", "meminfo", "vmstat", "diskstats", "pressure/cpu", "pressure/io", "pressure/memory")}
                    row["temperature_millic"] = read_optional(Path("/sys/class/thermal/thermal_zone0/temp"))
                    row["cpu0_frequency_khz"] = read_optional(Path("/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq"))
                    next_http = time.monotonic() + 1.0
                row["finished_host_s"] = time.monotonic()
                row["collection_ms"] = (row["finished_host_s"] - now) * 1000
                max_collection = max(max_collection, row["collection_ms"])
                # Buffered JSONL writes can themselves stall; next sample gap records it.
                log.write(json.dumps(row, allow_nan=False) + "\n")
                count += 1
                time.sleep(max(0, args.interval - (time.monotonic() - now)))
    except KeyboardInterrupt:
        reason = "interrupted"
    except Exception as failure:
        reason, error = "collector_error", str(failure)
    finally:
        if child is not None:
            stop_child(child)
    final_file = output / "scene" / "timing-final.json"
    final = read_optional(final_file)
    if final["text"] is not None:
        try:
            final = json.loads(final["text"])
        except ValueError as failure:
            final = {"error": str(failure)}
    elapsed = time.monotonic() - started
    summary = {"collector_outcome": reason, "error": error,
               "preview_returncode": child.returncode if child else None,
               "samples": count, "elapsed_s": elapsed,
               "observer_cpu_s": time.process_time() - cpu_started,
               "max_sample_gap_s": max_gap, "max_collection_ms": max_collection,
               "telemetry_errors_including_startup_shutdown": telemetry_errors,
               "scene_final": final,
               "limits": "Collector completion does not mean application acceptance. Missing/disabled counters are not zero delay. Observer polling/HTTP/JSON I/O perturbs workload; no event-by-event scheduler trace or causal attribution."}
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2), flush=True)
    print(f"Saved {output}; inspect preview.log if startup failed.", flush=True)
    return summary


def main() -> None:
    """Parse bounded run settings and return nonzero on collector/preview failure.

    Args: None; settings come from command-line arguments.
    Returns:
        None: SystemExit reports usage or runtime failure.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seconds", type=float, default=180)
    parser.add_argument("--interval", type=float, default=0.25)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--scene", required=True)
    parser.add_argument("--power", default="unknown")
    parser.add_argument("--cooling", default="unknown")
    args = parser.parse_args()
    if (not math.isfinite(args.seconds) or not 10 <= args.seconds <= 600 or
            not math.isfinite(args.interval) or not 0.1 <= args.interval <= 2 or
            not 1024 <= args.port <= 65535):
        parser.error("Require seconds 10–600, interval 0.1–2, port 1024–65535")
    try:
        summary = run(args)
    except (OSError, ValueError) as error:
        parser.exit(1, f"Profiler failed: {error}\n")
    if summary["collector_outcome"] != "child_exited" or summary["preview_returncode"] != 0:
        parser.exit(1, "Collector/preview did not finish normally; inspect saved evidence.\n")


if __name__ == "__main__":
    main()
