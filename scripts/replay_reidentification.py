"""Replay saved detector inputs through current memory without opening hardware."""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path

from vision.basic_tracker import BasicTracker
from vision.object_memory import RetiredObjectMemory, grayscale_grid_descriptor


def replay(directory: Path, class_id: int = 15, retry_seconds: float = 0.0) -> dict:
    """Compare recorded and current IDs at first-return frames.

    Args:
        directory (Path): Private trial with updates.jsonl and detector PNGs.
        class_id (int): Detector class to inspect; 15 is person.
        retry_seconds (float): Optional provisional return window for replay.

    Returns:
        dict: Aggregate enrollment diagnostics and per-return continuity.
            This uses recorded boxes, so it does not re-run the detector.
    """
    from PIL import Image

    rows = [json.loads(line) for line in (directory / "updates.jsonl").read_text().splitlines()]
    tracker = BasicTracker(reid_memory=RetiredObjectMemory(capacity=32, retention_s=10),
                           reid_retry_seconds=retry_seconds)
    origin = rows[0]["source_receipt_monotonic_s"]
    previous = None
    events = []
    enrollment = Counter()
    retry_events = []
    for index, row in enumerate(rows):
        with Image.open(directory / row["image"]) as image:
            gray = image.convert("L")
            pixels = gray.tobytes()
            descriptors = [grayscale_grid_descriptor(
                pixels, gray.width, gray.height, box["box_xyxy"]
            ) for box in row["boxes"]]
        boxes = [{key: value for key, value in box.items()
                  if key not in ("track_id", "match_source", "identity_status")}
                 for box in row["boxes"]]
        current = tracker.update(boxes, row["source_receipt_monotonic_s"], descriptors=descriptors)
        for box in current:
            if box.get("match_source") == "appearance_retry":
                retry_events.append({
                    "row": index, "seconds_from_first_input": row["source_receipt_monotonic_s"] - origin,
                    "restored_id": box["track_id"], "class_id": box["class_id"],
                    "decision": tracker.last_stats["reid_last_by_class"].get(str(box["class_id"])),
                })
        enrollment.update(tracker.last_stats["reid_gallery_updates"])
        targets = [i for i, box in enumerate(boxes) if box["class_id"] == class_id]
        if len(targets) > 1:
            previous = None  # A single-target continuity label would be ambiguous.
        if len(targets) != 1:
            continue
        target = targets[0]
        observed = row["boxes"][target]["track_id"]
        actual = current[target]["track_id"]
        if previous is not None and index - previous[0] > 1:
            events.append({
                "row": index, "seconds_from_first_input": row["source_receipt_monotonic_s"] - origin,
                "recorded_ids": [previous[1], observed],
                "current_ids": [previous[2], actual],
                "recorded_continuity": observed == previous[1],
                "current_continuity": actual == previous[2],
                "decision": tracker.last_stats["reid_last_by_class"].get(str(class_id)),
            })
        previous = (index, observed, actual)
    return {"updates": len(rows), "returns": events, "retry_restores": retry_events,
            "recorded_continuity_count": sum(event["recorded_continuity"] for event in events),
            "current_continuity_count": sum(event["current_continuity"] for event in events),
            "gallery_enrollment": dict(enrollment),
            "limits": "Existing development trial; no held-out lookalikes or Pi runtime measurement. IDs may renumber after earlier restorations."}


def main() -> None:
    """Read a private trial directory and print an image-free JSON summary.

    Args:
        None: Options come from the command line.
    Returns:
        None: Writes only to standard output; does not alter the trial.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--class-id", type=int, default=15)
    parser.add_argument("--retry-seconds", type=float, default=0.0)
    args = parser.parse_args()
    print(json.dumps(replay(args.directory, args.class_id, args.retry_seconds), indent=2))


if __name__ == "__main__":
    main()
