"""Query explicitly taught scene views in a local video; no live camera or motors."""

from __future__ import annotations

import argparse
from collections import Counter
import json
import math
from pathlib import Path
import platform
import time
from typing import Any

from spatial.scene_memory import MemoryConfig, SceneMemory, prepare_gray
from vision.detect_image import git_info, sha256


def parse_events(references: list[str], queries: list[float]) -> list[dict]:
    """Merge explicit reference/query requests into chronological video order.

    Args:
        references (list[str]): LABEL=SECONDS strings, with unique short labels.
        queries (list[float]): Query seconds relative to decoded video start.
    Returns:
        list[dict]: Up to 128 events with unique finite nonnegative times.
    """
    events = []
    labels = set()
    for specification in references:
        label, separator, seconds = specification.rpartition("=")
        if not separator or not label.strip() or len(label) > 80 or label in labels:
            raise ValueError("References need unique LABEL=SECONDS names (maximum 80 characters)")
        labels.add(label)
        events.append({"requested_s": float(seconds), "reference_label": label})
    events.extend({"requested_s": float(seconds), "reference_label": None} for seconds in queries)
    if not references or not queries or len(events) > 128:
        raise ValueError("Need references and queries, at most 128 selected frames")
    times = [event["requested_s"] for event in events]
    if any(not math.isfinite(t) or t < 0 for t in times) or len(set(times)) != len(times):
        raise ValueError("Selected times must be unique, finite and nonnegative")
    return sorted(events, key=event_time)


def event_time(event: dict) -> float:
    """Read requested time for chronological ordering.

    Args:
        event (dict): Parsed reference or query request.
    Returns:
        float: Requested seconds from decoded video start.
    """
    return event["requested_s"]


def run(args: argparse.Namespace, cv: Any = None) -> dict:
    """Replay selected frames, retaining decisions and image evidence in new output.

    Args:
        args (argparse.Namespace): Local video, reference/query times, memory limit and output.
        cv (Any): Optional OpenCV module; loaded lazily after path/argument validation.
    Returns:
        dict: Complete or partial report; partial output is retained after decoding errors.
    """
    root = (Path.cwd() / "recordings").resolve()
    output = args.output.resolve()
    if output == root or not output.is_relative_to(root) or output.exists():
        raise ValueError("Output must be a new directory under recordings/")
    video = args.video.resolve()
    if not video.is_file():
        raise ValueError("Input must be an existing local video file")
    events = parse_events(args.reference, args.query)
    if cv is None:
        import cv2 as cv
    memory = SceneMemory(MemoryConfig(max_views=args.max_views), cv)
    cv.setNumThreads(2)
    cv.setRNGSeed(0)
    capture = cv.VideoCapture(str(video))
    if not capture.isOpened():
        capture.release()
        raise ValueError("OpenCV could not open the input video")

    report = {"status": "partial", "error": None, "source": str(video),
              "source_sha256": None, "settings": memory.settings(),
              "opencv": cv.__version__, "opencv_threads": cv.getNumThreads(),
              "python": platform.python_version(), "host": platform.platform(),
              "git": git_info(), "events": [], "decoded_frames": 0,
              "scope": "Offline visual scene recognition; no IMU association, camera pose, depth or accuracy ground truth. Compute excludes video decoding and report/image I/O."}
    created_output = False
    try:
        output.mkdir(parents=True)
        created_output = True
        report["source_sha256"] = sha256(video)
        event_index = 0
        origin_s = None
        previous_s = None
        while event_index < len(events):
            success, frame = capture.read()
            if not success:
                raise ValueError("Video ended or decoding failed before all requested times")
            raw_s = float(capture.get(cv.CAP_PROP_POS_MSEC)) / 1000
            if not math.isfinite(raw_s) or (previous_s is not None and raw_s <= previous_s):
                raise ValueError("Decoder timestamps are missing or non-increasing")
            previous_s = raw_s
            if origin_s is None:
                origin_s = raw_s
                report["decoder_origin_s"] = origin_s
            timestamp_s = raw_s - origin_s
            report["decoded_frames"] += 1
            event = events[event_index]
            if timestamp_s + 1e-9 < event["requested_s"]:
                continue

            # Sequential decoding avoids future-reference leakage and retains the
            # actual selected time; close requests must not silently share a frame.
            if event_index + 1 < len(events) and events[event_index + 1]["requested_s"] <= timestamp_s:
                raise ValueError("Requested events share a decoded frame; separate their times")
            gray = cv.cvtColor(frame, cv.COLOR_BGR2GRAY)
            started = time.perf_counter()
            decision = memory.process(gray, timestamp_s, event["reference_label"])
            compute_ms = (time.perf_counter() - started) * 1000
            image_name = f"event-{event_index + 1:03d}.png"
            if not cv.imwrite(str(output / image_name), prepare_gray(cv, gray)):
                raise OSError("Could not save selected-frame evidence")
            row = {**event, "actual_video_s": timestamp_s, "image": image_name,
                   "compute_ms": compute_ms, "decision": decision}
            report["events"].append(row)
            print(f"{timestamp_s:.3f}s: {decision['state']} "
                  f"{decision['label'] or '-'} ({decision['reason']})", flush=True)
            event_index += 1
        report["status"] = "complete"
    except (ValueError, OSError, cv.error) as error:
        report["error"] = str(error)
    finally:
        capture.release()
        if created_output:
            report["state_counts"] = dict(Counter(row["decision"]["state"] for row in report["events"]))
            (output / "report.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    return report


def main() -> int:
    """Parse an offline trial without touching the live preview or hardware.

    Args:
        None; arguments come from the command line.
    Returns:
        int: Zero on complete replay, one on partial or invalid input.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video", type=Path)
    parser.add_argument("--reference", action="append", required=True, metavar="LABEL=SECONDS")
    parser.add_argument("--query", action="append", required=True, type=float, metavar="SECONDS")
    parser.add_argument("--max-views", type=int, default=12)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = run(args)
    except (ImportError, ValueError, OSError) as error:
        print(f"Scene replay failed: {error}")
        return 1
    print(f"{report['status']}: {args.output / 'report.json'}")
    if report["error"]:
        print(report["error"])
    return 0 if report["status"] == "complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
