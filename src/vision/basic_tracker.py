"""Match boxes from successive detections; not yet connected to the live worker.

Planned input path: camera frame -> CpuDetector.__call__ in live_detector.py ->
infer_once and parse_detections in detect_image.py -> BasicTracker.update here.
parse_detections produces a list of dictionaries with class_id, label,
confidence and box_xyxy. This module does not see image pixels or run the model.
"""

from __future__ import annotations
from typing import Sequence, TYPE_CHECKING

if TYPE_CHECKING:
    from _contracts import Record

from dataclasses import dataclass
import math


@dataclass
class _Track:
    """Remember one earlier detection for comparison with the next update.

    BasicTracker creates this record after assigning an ID. ``box`` starts as
    that detection's box and is replaced when a later detection matches it.
    ``missed`` counts completed detector results in which it did not match.
    No old camera frame or full list of past boxes is stored here.
    """

    class_id: int
    box: tuple[float, float, float, float]
    missed: int = 0


def box_iou(first: Sequence[float], second: Sequence[float]) -> float:
    """Measure how much an earlier box and a current box overlap.

    Args:
        first (Sequence[float]): Usually ``_Track.box`` from an earlier detector
            update: left, top, right, bottom in 1280x720 source-image pixels.
        second (Sequence[float]): Current detection's ``box_xyxy`` after update()
            converts its numbers to floats, in those same pixel coordinates.

    Returns:
        float: Shared area divided by the area covered by either box. Zero
            means no shared pixels; one means identical rectangles.
    """
    # The intersection is the rectangle covered by both boxes. If their edges
    # do not overlap, either width or height becomes zero. The union counts
    # shared area once: old area + new area - their shared area.
    width = max(0.0, min(first[2], second[2]) - max(first[0], second[0]))
    height = max(0.0, min(first[3], second[3]) - max(first[1], second[1]))
    intersection = width * height
    first_area = (first[2] - first[0]) * (first[3] - first[1])
    second_area = (second[2] - second[0]) * (second[3] - second[1])
    return intersection / (first_area + second_area - intersection)


class BasicTracker:
    def __init__(self, min_iou: float = 0.3, max_missed: int = 2) -> None:
        """Create empty memory for one sequential stream of detector results.

        Args:
            min_iou (float): Minimum IoU for treating a current box as the same
                track. 0.3 is a first-test choice, not a measured optimum.
            max_missed (int): Consecutive completed detector results without a
                match before forgetting an ID. Two updates are not necessarily
                one second: the detector's target rate can slow down.

        Returns:
            None: Creates an empty ID-to-_Track dictionary and next ID one.
        """
        # Configuration comes from these constructor arguments, not from an IMU,
        # camera clock or model score. Each new tracker instance starts a new
        # session, so IDs from a previous program run are not recovered.
        if not math.isfinite(min_iou) or not 0 < min_iou <= 1:
            raise ValueError("min_iou must be finite and in (0, 1]")
        if isinstance(max_missed, bool) or not isinstance(max_missed, int) or max_missed < 1:
            raise ValueError("max_missed must be a positive integer")
        self.min_iou = min_iou
        self.max_missed = max_missed
        self._next_id = 1
        self._tracks: dict[int, _Track] = {}

    def update(self, detections: Sequence[Record]) -> list[Record]:
        """Attach IDs to the boxes from one completed detector inference.

        Args:
            detections (Sequence[Record]): Intended output of
                ``CpuDetector.__call__``. It calls ``parse_detections()``, which
                supplies class_id, label, confidence and box_xyxy. Coordinates
                are from the original 1280x720 frame, not the 300x300 network
                input or 320x180 motion preview. An empty list means inference
                finished and found no accepted boxes; it still ages tracks.

        Returns:
            list[Record]: New dictionaries in the detector's original order,
                each with an added integer track_id. Only current detections
                appear; remembered but missing tracks do not draw boxes.
        """
        # ``detections`` arrives from the preceding inference stage; this method
        # neither generates boxes nor edits that input. Extract each current
        # box as four floats. Validate all boxes before touching saved tracks,
        # so one bad record cannot leave memory half-updated.
        boxes: list[tuple[float, float, float, float]] = []
        for detection in detections:
            class_id = detection.get("class_id")
            raw = detection.get("box_xyxy")
            if isinstance(class_id, bool) or not isinstance(class_id, int):
                raise ValueError("Detection class_id must be an integer")
            if not isinstance(raw, (list, tuple)) or len(raw) != 4:
                raise ValueError("Detection box_xyxy must have four coordinates")
            try:
                box = tuple(float(value) for value in raw)
            except (TypeError, ValueError) as error:
                raise ValueError("Detection box_xyxy must be numeric") from error
            if (
                not all(math.isfinite(value) for value in box)
                or box[2] <= box[0]
                or box[3] <= box[1]
            ):
                raise ValueError("Detection box_xyxy must be finite and positive-area")
            boxes.append(box)

        # ``self._tracks`` contains boxes remembered from prior update() calls;
        # ``boxes`` contains the current result just validated above. For each
        # old/new pair of the same class, compute overlap. ``candidates`` holds
        # (-IoU, old ID, current-list position); the minus sign makes sorting
        # put the largest overlap first. Below-threshold pairs are not matches.
        candidates: list[tuple[float, int, int]] = []
        for track_id, track in self._tracks.items():
            for index, detection in enumerate(detections):
                if track.class_id != detection["class_id"]:
                    continue
                overlap = box_iou(track.box, boxes[index])
                if overlap >= self.min_iou:
                    candidates.append((-overlap, track_id, index))
        assignments: dict[int, int] = {}
        matched_tracks: set[int] = set()
        # ``assignments`` maps a current-list position to an old ID. Accept the
        # strongest available pair first; refuse a pair if either side already
        # won one. On equal overlap, sorting prefers the lower (older) ID and
        # then the earlier current-list position. This is greedy, not a global
        # optimal assignment across all boxes.
        for _, track_id, index in sorted(candidates):
            if track_id not in matched_tracks and index not in assignments:
                assignments[index] = track_id
                matched_tracks.add(track_id)

        # Each old ID not chosen above missed this completed inference result.
        # One missed update leaves it in memory for a possible later match, but
        # it will not be returned as a visible box. At two misses by default,
        # forget it. Camera frames skipped between detector runs do not count.
        for track_id in list(self._tracks):
            if track_id in matched_tracks:
                continue
            track = self._tracks[track_id]
            track.missed += 1
            if track.missed >= self.max_missed:
                del self._tracks[track_id]

        # Walk the current detections in their original order. A matched one
        # refreshes its saved box and clears ``missed``; an unmatched one gets
        # ``self._next_id``, which only increases. Return copies with track_id.
        # This does not publish to DetectionState or the browser yet: step 2
        # will call update() from the live detector worker.
        identified: list[Record] = []
        for index, detection in enumerate(detections):
            track_id = assignments.get(index)
            if track_id is None:
                track_id = self._next_id
                self._next_id += 1
                self._tracks[track_id] = _Track(detection["class_id"], boxes[index])
            else:
                track = self._tracks[track_id]
                track.box = boxes[index]
                track.missed = 0
            identified.append({**detection, "track_id": track_id})
        return identified
