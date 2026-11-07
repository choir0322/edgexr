"""Capture a bounded private ftrace I/O instance; export only after tracing stops."""

from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import platform
import re
import signal
import subprocess
import threading
import time
import uuid
from typing import BinaryIO

from profiling.spatial_stalls import read_optional


# Keep kernel workers and completion events: an application-PID filter loses them.
EVENTS = (
    "block:block_rq_insert", "block:block_rq_issue", "block:block_rq_complete",
    "block:block_rq_requeue", "mmc:mmc_request_start", "mmc:mmc_request_done",
    "jbd2:jbd2_lock_buffer_stall", "jbd2:jbd2_start_commit",
    "jbd2:jbd2_end_commit", "jbd2:jbd2_commit_flushing", "jbd2:jbd2_commit_logging",
    "ext4:ext4_da_write_begin", "ext4:ext4_da_write_end",
    "ext4:ext4_write_begin", "ext4:ext4_write_end",
    "ext4:ext4_writepages", "ext4:ext4_writepages_result",
    "writeback:balance_dirty_pages",
)
TRACE_ROOT = Path("/sys/kernel/tracing")
EXPORT_LIMIT = 64 * 1024 * 1024


def select_events(available: str) -> tuple[list[str], list[str]]:
    """Select known events and require basic block and journal visibility.

    Args:
        available (str): Kernel available_events text.
    Returns:
        tuple[list[str], list[str]]: Supported and missing requested event names.
    """
    names = set(available.split())
    required = {"block:block_rq_issue", "block:block_rq_complete",
                "jbd2:jbd2_lock_buffer_stall"}
    if not required <= names:
        raise ValueError(f"Required trace events missing: {sorted(required - names)}")
    return ([name for name in EVENTS if name in names],
            [name for name in EVENTS if name not in names])


def loss_counts(text: str) -> dict:
    """Retain explicit loss counters from a per-CPU ftrace stats file.

    Args:
        text (str): Kernel per_cpu/cpuN/stats contents.
    Returns:
        dict: Available counters and availability flag; missing is not zero loss.
    """
    counters = {}
    for line in text.splitlines():
        key, separator, value = line.partition(":")
        if separator and key.strip() in ("overrun", "commit overrun", "dropped events"):
            counters[key.strip()] = int(value.strip())
    return {"counters": counters, "all_available": len(counters) == 3}


def export_trace(source: BinaryIO, target: BinaryIO, limit: int = EXPORT_LIMIT) -> dict:
    """Stream a stopped text trace to disk with a hard output-size cap.

    Args:
        source (BinaryIO): Read-only stopped-instance trace stream.
        target (BinaryIO): Newly created trace.txt output stream.
        limit (int): Maximum exported bytes, default 64 MiB.
    Returns:
        dict: Byte count and explicit truncation flag, never silent clipping.
    """
    written = 0
    while written < limit:
        block = source.read(min(65536, limit - written))
        if not block:
            return {"bytes": written, "truncated": False}
        target.write(block)
        written += len(block)
    return {"bytes": written, "truncated": bool(source.read(1))}


def configure_instance(instance: Path, events: list[str], buffer_kb: int,
                       mmc_host: str | None = None) -> dict:
    """Configure only a newly owned instance and preserve event field layouts.

    Args:
        instance (Path): Fresh directory under tracefs/instances, created by caller.
        events (list[str]): Supported exact event names.
        buffer_kb (int): KiB per CPU; caller checks total CPUs before allocation.
        mmc_host (str | None): Exact MMC host to retain, or all hosts when None.
    Returns:
        dict: Actual buffer size, clock and event formats before collection.
    """
    (instance / "tracing_on").write_text("0\n")
    (instance / "events/enable").write_text("0\n")
    clocks = (instance / "trace_clock").read_text().replace("[", "").replace("]", "").split()
    if "mono" not in clocks:
        raise ValueError("Instance lacks mono clock for host-timestamp correlation")
    (instance / "trace_clock").write_text("mono\n")
    (instance / "buffer_size_kb").write_text(f"{buffer_kb}\n")
    total = int((instance / "buffer_total_size_kb").read_text().strip())
    if total > 32768:
        raise ValueError("Actual kernel ring allocation exceeds 32 MiB bound")
    formats = {}
    filters = {}
    if mmc_host is not None:
        if not re.fullmatch(r"mmc[0-9]+", mmc_host):
            raise ValueError("MMC host must be an exact name such as mmc0")
        if not {"mmc:mmc_request_start", "mmc:mmc_request_done"} <= set(events):
            raise ValueError("Filtered capture requires both MMC start and done events")
    for event in events:
        group, name = event.split(":")
        folder = instance / "events" / group / name
        formats[event] = (folder / "format").read_text()
        if mmc_host is not None and group == "mmc":
            if not re.search(r"field:__data_loc char\[\] name;", formats[event]):
                raise ValueError(f"{event} lacks the expected MMC host string field")
            expression = f'name == "{mmc_host}"'
            (folder / "filter").write_text(expression + "\n")
            actual = (folder / "filter").read_text().strip()
            filters[event] = actual
            if actual != expression:
                raise ValueError(f"MMC filter readback mismatch for {event}: {actual}")
        (folder / "enable").write_text("1\n")
    return {"buffer_total_kb": total, "clock": (instance / "trace_clock").read_text().strip(),
            "trace_options": read_optional(instance / "trace_options"),
            "event_formats": formats, "event_filters": filters}


def run(args: argparse.Namespace) -> dict:
    """Collect root-only tracing without launching or modifying the camera app.

    Args:
        args (argparse.Namespace): Duration and new output folder under recordings/.
    Returns:
        dict: Trace/export/loss/cleanup status and host times; not an I/O diagnosis.
    """
    output = args.output.resolve()
    recordings = (Path.cwd() / "recordings").resolve()
    if output == recordings or not output.is_relative_to(recordings) or output.exists():
        raise ValueError("Output must be a new directory under recordings/")
    if platform.system() != "Linux" or os.geteuid() != 0:
        raise ValueError("Run on the Pi with sudo; only this trace helper needs root")
    events, missing = select_events((TRACE_ROOT / "available_events").read_text())
    instances = TRACE_ROOT / "instances"
    # Count all exposed CPU buffers before allocation, including offline CPUs.
    cpus = list((TRACE_ROOT / "per_cpu").glob("cpu[0-9]*"))
    if not cpus or len(cpus) * 2048 > 32768:
        raise ValueError("CPU count does not fit bounded 2 MiB-per-CPU trace profile")
    if not instances.is_dir():
        raise ValueError("Kernel trace instances unavailable")
    output.mkdir(parents=True, exist_ok=False)
    instance = instances / f"edgexr-io-{uuid.uuid4().hex[:12]}"
    # Scope Git's root/user ownership exception to this one read-only invocation.
    try:
        revision = subprocess.run(
            ["git", "-c", f"safe.directory={Path.cwd().resolve()}", "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=5)
        provenance = {"revision": revision.stdout.strip() if revision.returncode == 0 else None,
                      "error": revision.stderr.strip() or None}
    except (OSError, subprocess.TimeoutExpired) as error:
        provenance = {"revision": None, "error": str(error)}
    mmc_host = getattr(args, "mmc_host", None)
    metadata = {"schema": 2, "host": platform.platform(), "python": platform.python_version(),
                "mmc_host_filter": mmc_host,
                "git": provenance,
                "requested_seconds": args.seconds, "events": events, "missing_events": missing,
                "instance": str(instance), "requested_buffer_kb_per_cpu": 2048,
                "export_limit_bytes": EXPORT_LIMIT,
                "root_tracer_before": read_optional(TRACE_ROOT / "current_tracer"),
                "root_tracing_on_before": read_optional(TRACE_ROOT / "tracing_on"),
                "mounts": read_optional(Path("/proc/mounts")),
                "scope": "System-wide selected I/O events, private ring. Optional exact MMC-host filter; other events remain unfiltered. No PID filter. Trace exported only after stop; tracing adds overhead."}
    summary = {"status": "error", "error": None, "cleanup_errors": [],
               "trace_export": None, "per_cpu_stats": {}}
    stop = threading.Event()
    old_handlers = {}
    created = False

    def request_stop(signum: int, frame: object) -> None:
        """Request normal stop/export after Ctrl+C or SIGTERM.

        Args:
            signum (int): Received POSIX signal number.
            frame (object): Python signal frame, unused.
        Returns:
            None: Main thread wakes from timed wait.
        """
        stop.set()

    try:
        (output / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
        instance.mkdir()
        created = True
        metadata.update(configure_instance(instance, events, 2048, mmc_host))
        (output / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
        for signum in (signal.SIGINT, signal.SIGTERM):
            old_handlers[signum] = signal.signal(signum, request_stop)
        # No diagnostic files are written during this timed interval.
        summary["start_before_enable_host_s"] = time.monotonic()
        (instance / "tracing_on").write_text("1\n")
        summary["start_after_enable_host_s"] = time.monotonic()
        (instance / "trace_marker").write_text(f"EDGEXR_IO_START host_s={time.monotonic():.9f}\n")
        print(f"TRACING for {args.seconds:g} s; start the app in another Pi terminal now.\nPrivate instance: {instance}", flush=True)
        deadline = summary["start_after_enable_host_s"] + args.seconds
        while not stop.is_set() and time.monotonic() < deadline:
            stop.wait(min(1.0, max(0.0, deadline - time.monotonic())))
        summary["status"] = "interrupted" if stop.is_set() else "complete"
    except KeyboardInterrupt:
        summary["status"] = "interrupted"
    except (OSError, ValueError) as error:
        summary["error"] = str(error)
    finally:
        if created:
            try:
                summary["stop_before_disable_host_s"] = time.monotonic()
                (instance / "tracing_on").write_text("0\n")
                summary["stop_after_disable_host_s"] = time.monotonic()
                for cpu in sorted((instance / "per_cpu").glob("cpu[0-9]*")):
                    observation = read_optional(cpu / "stats")
                    if observation["text"] is not None:
                        observation.update(loss_counts(observation["text"]))
                    summary["per_cpu_stats"][cpu.name] = observation
                with (instance / "trace").open("rb") as source, (output / "trace.txt").open("xb") as target:
                    summary["trace_export"] = export_trace(source, target)
            except (OSError, ValueError) as error:
                summary["error"] = summary["error"] or str(error)
                summary["status"] = "error"
            # Disable all events in only the owned instance before removing it.
            for name, value in (("tracing_on", "0\n"), ("events/enable", "0\n")):
                try:
                    (instance / name).write_text(value)
                except OSError as error:
                    summary["cleanup_errors"].append(str(error))
            try:
                instance.rmdir()
            except OSError as error:
                summary["cleanup_errors"].append(str(error))
        for signum, handler in old_handlers.items():
            signal.signal(signum, handler)
    summary["root_tracer_after"] = read_optional(TRACE_ROOT / "current_tracer")
    summary["root_tracing_on_after"] = read_optional(TRACE_ROOT / "tracing_on")
    stats = list(summary["per_cpu_stats"].values())
    summary["loss_accounting_complete"] = bool(stats) and all(v.get("all_available", False) for v in stats)
    summary["buffer_loss_detected"] = any(
        count > 0 for value in stats for count in value.get("counters", {}).values())
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    # Only newly created evidence files are handed back to the invoking sudo user.
    if os.environ.get("SUDO_UID", "").isdigit() and os.environ.get("SUDO_GID", "").isdigit():
        uid, gid = int(os.environ["SUDO_UID"]), int(os.environ["SUDO_GID"])
        for path in output.iterdir():
            os.chown(path, uid, gid, follow_symlinks=False)
        os.chown(output, uid, gid, follow_symlinks=False)
    print(json.dumps(summary, indent=2), flush=True)
    print(f"Saved {output}. Include this folder and the separate app recording in SCP.", flush=True)
    return summary


def main() -> None:
    """Parse the bounded trace command and expose failures through exit status.

    Args: None; settings come from command-line arguments.
    Returns:
        None: Exits nonzero for setup/export/cleanup failure or truncated export.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seconds", type=float, default=210)
    parser.add_argument("--mmc-host", help="Retain only this MMC host, e.g. mmc0; other event groups unchanged")
    args = parser.parse_args()
    if not math.isfinite(args.seconds) or not 10 <= args.seconds <= 300:
        parser.error("Require seconds 10–300")
    try:
        result = run(args)
    except (OSError, ValueError) as error:
        parser.exit(1, f"Kernel trace failed: {error}\n")
    if (result["status"] != "complete" or result["error"] or result["cleanup_errors"] or
            not result["trace_export"] or result["trace_export"]["truncated"] or
            result["buffer_loss_detected"] or not result["loss_accounting_complete"]):
        parser.exit(1, "Trace partial or failed; inspect summary.json.\n")


if __name__ == "__main__":
    main()
