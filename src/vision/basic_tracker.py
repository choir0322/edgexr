"""Match boxes from successive detections, optionally predicting scene shift.

Live input path: camera frame -> CpuDetector.__call__ in live_detector.py ->
infer_once and parse_detections in detect_image.py -> BasicTracker.update here.
parse_detections produces a list of dictionaries with class_id, label,
confidence and box_xyxy. This module does not see image pixels or run the model.
"""

from __future__ import annotations
from typing import Callable, Sequence, TYPE_CHECKING

if TYPE_CHECKING:
    from _contracts import Record

from dataclasses import dataclass
from collections import Counter
from functools import partial
import math
from vision.object_memory import MemoryEntry, RetiredObjectMemory, normalize_descriptor


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
    seen_at: float | None = None
    descriptor: tuple[float, ...] | None = None
    gallery: tuple[tuple[float, ...], ...] = ()
    reference_area: float = 0.0
    pending_until: float | None = None


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
    def __init__(
        self, min_iou: float = 0.3, max_missed: int = 2,
        *, reid_memory: RetiredObjectMemory | None = None,
        reid_min_similarity: float = 0.85, reid_min_margin: float = 0.05,
        reid_retry_seconds: float = 0.0, reid_spatial: bool = False,
    ) -> None:
        """Create empty memory for one sequential stream of detector results.

        Args:
            min_iou (float): Minimum IoU for treating a current box as the same
                track. 0.3 is a first-test choice, not a measured optimum.
            max_missed (int): Consecutive completed detector results without a
                match before forgetting an ID. Two updates are not necessarily
                one second: the detector's target rate can slow down.
            reid_memory (RetiredObjectMemory | None): Optional, experimental
                session-local memory; None preserves the existing behavior.
            reid_min_similarity (float): Provisional appearance score floor.
            reid_min_margin (float): Provisional gap over a lookalike runner-up.
            reid_retry_seconds (float): Optional time for a provisional new ID to
                gather a better appearance after its first failed return.
            reid_spatial (bool): Use reliable image shift as a small positive
                ranking clue between already-strong retired-ID candidates.

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
        if not math.isfinite(reid_retry_seconds) or not 0 <= reid_retry_seconds <= 5:
            raise ValueError("reid_retry_seconds must be in [0, 5]")
        self.min_iou = min_iou
        self.max_missed = max_missed
        self.reid_memory = reid_memory
        self.reid_min_similarity = reid_min_similarity
        self.reid_min_margin = reid_min_margin
        self.reid_retry_seconds = reid_retry_seconds
        self.reid_spatial = reid_spatial
        self._next_id = 1
        self._tracks: dict[int, _Track] = {}
        self._reid_events: Counter[str] = Counter()
        self._last_reid_event: Record | None = None
        self._last_reid_by_class: dict[int, Record] = {}
        self.last_stats = {
            "covered_tracks": 0, "fallback_tracks": 0,
            "motion_matches": 0, "motion_only_matches": 0,
            "reid_restores": 0,
        }

    def _note_reid(self, reason: str, class_id: int, **details: object) -> None:
        """Keep a small, image-free explanation of the most recent memory decision.

        Args:
            reason (str): Stable decision name for browser and telemetry.
            class_id (int): Detector class that triggered the decision.
            **details (object): Numeric score and candidate metadata, never pixels.
        """
        self._reid_events[reason] += 1
        self._last_reid_event = {"reason": reason, "class_id": class_id, **details}
        self._last_reid_by_class[class_id] = self._last_reid_event

    def _learn_appearance(
        self, track: _Track, descriptor: tuple[float, ...] | None,
        confidence: float,
    ) -> str:
        """Retain a few useful views without overwriting them on an exit crop.

        Args:
            track (_Track): Active track after its source box has been updated.
            descriptor (tuple[float, ...] | None): Current normalized crop vector.
            confidence (float): Current detector score, separate from similarity.

        Returns:
            str: Image-free enrollment reason for diagnostics.
        """
        if descriptor is None:
            return "no_descriptor"
        if not math.isfinite(confidence) or confidence < 0.5:
            return "low_confidence"
        area = (track.box[2] - track.box[0]) * (track.box[3] - track.box[1])
        if area < 0.6 * track.reference_area:
            return "shrunken_crop"
        track.reference_area = max(track.reference_area, area)
        # Keep the first eligible view as an anchor. Near-identical subsequent
        # views do not fill the gallery; rotate the other three slots when full.
        if any(sum(a * b for a, b in zip(descriptor, old)) >= 0.98
               for old in track.gallery if len(old) == len(descriptor)):
            return "duplicate_view"
        if track.gallery and len(track.gallery[0]) != len(descriptor):
            return "descriptor_shape_changed"
        views = track.gallery
        if len(views) == 4:
            views = (views[0],) + views[2:]
        track.gallery = views + (descriptor,)
        track.descriptor = descriptor
        return "stored_view"

    def _spatial_support(
        self, entry: MemoryEntry, box: tuple[float, float, float, float],
        now: float, shift_lookup: Callable[[float, float], tuple[float, float] | None],
    ) -> bool | None:
        """Check whether a reliable image shift places an old box near a return.

        Args:
            entry (MemoryEntry): Retired ID with its last observed source box.
            box (tuple[float, float, float, float]): Current source box in pixels.
            now (float): Current detector frame's monotonic receipt seconds.
            shift_lookup (Callable): Returns source-pixel displacement or None.

        Returns:
            bool | None: Spatial support, disagreement, or unavailable evidence.
        """
        if entry.box is None:
            return None
        offset = shift_lookup(entry.seen_at, now)
        if (offset is None or len(offset) != 2 or
                not all(math.isfinite(v) for v in offset) or
                abs(offset[0]) > 320 or abs(offset[1]) > 180):
            return None
        old = entry.box
        predicted_x = (old[0] + old[2]) / 2 + offset[0]
        predicted_y = (old[1] + old[3]) / 2 + offset[1]
        actual_x, actual_y = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
        # Broad tolerance acknowledges independent object motion, box jitter
        # and approximate host timestamps. Disagreement is diagnostic only.
        tolerance_x = max(80.0, (old[2] - old[0] + box[2] - box[0]) / 2)
        tolerance_y = max(60.0, (old[3] - old[1] + box[3] - box[1]) / 2)
        return abs(actual_x - predicted_x) <= tolerance_x and abs(actual_y - predicted_y) <= tolerance_y

    def update(
        self,
        detections: Sequence[Record],
        source_time: float | None = None,
        shift_lookup: Callable[[float, float], tuple[float, float] | None] | None = None,
        *, descriptors: Sequence[Sequence[float] | None] | None = None,
    ) -> list[Record]:
        """Attach IDs to the boxes from one completed detector inference.

        Args:
            detections (Sequence[Record]): Intended output of
                ``CpuDetector.__call__``. It calls ``parse_detections()``, which
                supplies class_id, label, confidence and box_xyxy. Coordinates
                are from the original 1280x720 frame, not the 300x300 network
                input or 320x180 motion preview. An empty list means inference
                finished and found no accepted boxes; it still ages tracks.
            source_time (float | None): This detector frame's monotonic host
                receipt seconds. Required to use shift_lookup.
            shift_lookup (Callable | None): Optional displacement between two
                receipt times, in 1280x720 source pixels. None means unknown;
                ordinary box overlap remains available.
            descriptors (Sequence[Sequence[float] | None] | None): Optional
                appearance vectors aligned to current detections. Used only
                when the experimental retired-ID memory is enabled.

        Returns:
            list[Record]: New dictionaries in the detector's original order,
                each with an added integer track_id. Only current detections
                appear; remembered but missing tracks do not draw boxes.
        """
        # ``detections`` arrives from the preceding inference stage; this method
        # neither generates boxes nor edits that input. Extract each current
        # box as four floats. Validate all boxes before touching saved tracks,
        # so one bad record cannot leave memory half-updated.
        if source_time is not None and not math.isfinite(source_time):
            raise ValueError("source_time must be finite")
        if descriptors is not None and len(descriptors) != len(detections):
            raise ValueError("descriptors must align with detections")
        normalized = (
            [normalize_descriptor(value) if value is not None else None
             for value in descriptors]
            if descriptors is not None else [None] * len(detections)
        )
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
        candidates: list[tuple[float, int, int, bool, bool]] = []
        covered = fallback = 0
        for track_id, track in self._tracks.items():
            offset = None
            if shift_lookup is not None and source_time is not None and track.seen_at is not None:
                offset = shift_lookup(track.seen_at, source_time)
                if offset is not None and (
                    len(offset) != 2
                    or not all(math.isfinite(value) for value in offset)
                    or abs(offset[0]) > 320
                    or abs(offset[1]) > 180
                ):
                    offset = None
                if offset is None:
                    fallback += 1
                else:
                    covered += 1
            for index, detection in enumerate(detections):
                if track.class_id != detection["class_id"]:
                    continue
                raw_overlap = box_iou(track.box, boxes[index])
                predicted_overlap = 0.0
                if offset is not None:
                    predicted = (
                        track.box[0] + offset[0], track.box[1] + offset[1],
                        track.box[2] + offset[0], track.box[3] + offset[1],
                    )
                    predicted_overlap = box_iou(predicted, boxes[index])
                use_motion = predicted_overlap > raw_overlap
                overlap = predicted_overlap if use_motion else raw_overlap
                if overlap >= self.min_iou:
                    candidates.append(
                        (-overlap, track_id, index, use_motion, raw_overlap < self.min_iou)
                    )
        assignments: dict[int, tuple[int, bool, bool]] = {}
        matched_tracks: set[int] = set()
        # ``assignments`` maps a current-list position to an old ID. Accept the
        # strongest available pair first; refuse a pair if either side already
        # won one. On equal overlap, sorting prefers the lower (older) ID and
        # then the earlier current-list position. This is greedy, not a global
        # optimal assignment across all boxes.
        for _, track_id, index, use_motion, motion_only in sorted(candidates):
            if track_id not in matched_tracks and index not in assignments:
                assignments[index] = (track_id, use_motion, motion_only)
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
                if self.reid_memory is not None:
                    if (track.pending_until is not None and source_time is not None
                            and source_time <= track.pending_until):
                        # A provisional duplicate that vanished before the
                        # verdict must not compete with the original old ID.
                        self._note_reid("retry_disappeared", track.class_id)
                    elif track.descriptor is None or track.seen_at is None or source_time is None:
                        self._note_reid("retired_no_descriptor", track.class_id)
                    elif self.reid_memory.remember(
                        track_id, track.class_id, track.descriptor,
                        seen_at=track.seen_at, now=source_time,
                        gallery=track.gallery, reference_area=track.reference_area,
                        box=track.box,
                    ):
                        self._note_reid("retired_stored", track.class_id)
                    else:
                        self._note_reid("retired_expired", track.class_id)
                del self._tracks[track_id]

        # Walk the current detections in their original order. A matched one
        # refreshes its saved box and clears ``missed``; an unmatched one gets
        # ``self._next_id``, which only increases. Return copies with track_id.
        # The detector worker publishes the returned boxes; remembered tracks
        # remain internal when absent from this result.
        identified: list[Record] = []
        reid_restores = 0
        retry_restores = 0
        gallery_updates: Counter[str] = Counter()
        unmatched_class_counts = Counter(
            detection["class_id"] for index, detection in enumerate(detections)
            if index not in assignments
        )
        for index, detection in enumerate(detections):
            assignment = assignments.get(index)
            restored = None
            retried = False
            class_id = detection["class_id"]
            spatial_support = None
            if self.reid_spatial and shift_lookup is not None and source_time is not None:
                spatial_support = partial(
                    self._spatial_support, box=boxes[index], now=source_time,
                    shift_lookup=shift_lookup,
                )
            if assignment is None:
                if self.reid_memory is not None:
                    if normalized[index] is None or source_time is None:
                        self._note_reid("return_no_descriptor", class_id)
                    elif unmatched_class_counts[class_id] != 1:
                        self._note_reid("return_multiple_same_class", class_id)
                    else:
                        restored = self.reid_memory.take_match(
                            class_id, normalized[index], now=source_time,
                            min_similarity=self.reid_min_similarity,
                            min_margin=self.reid_min_margin,
                            spatial_support=spatial_support,
                        )
                        decision = self.reid_memory.last_decision
                        if decision is not None:
                            self._note_reid(decision["reason"], class_id, **{
                                key: value for key, value in decision.items()
                                if key != "reason"
                            })
                if restored is None:
                    track_id = self._next_id
                    self._next_id += 1
                else:
                    track_id = restored[0]
                    reid_restores += 1
                self._tracks[track_id] = _Track(
                    detection["class_id"], boxes[index], seen_at=source_time,
                )
                if (restored is None and self.reid_memory is not None
                        and self.reid_retry_seconds > 0 and source_time is not None
                        and unmatched_class_counts[class_id] == 1
                        and self.reid_memory.eligible_count(class_id, source_time) > 0
                        and not any(t.class_id == class_id and t.pending_until is not None
                                    for key, t in self._tracks.items() if key != track_id)):
                    self._tracks[track_id].pending_until = source_time + self.reid_retry_seconds
                    self._note_reid("retry_pending", class_id)
                if restored is not None:
                    entry = self.reid_memory.last_match_entry
                    self._tracks[track_id].gallery = entry.gallery
                    self._tracks[track_id].descriptor = entry.descriptor
                    self._tracks[track_id].reference_area = entry.reference_area
            else:
                track_id = assignment[0]
                track = self._tracks[track_id]
                track.box = boxes[index]
                track.missed = 0
                track.seen_at = source_time
                if track.pending_until is not None and source_time is not None:
                    if source_time > track.pending_until:
                        track.pending_until = None
                        self._note_reid("retry_expired", class_id)
                    elif (self.reid_memory is not None and normalized[index] is not None
                          and sum(t.class_id == class_id and t.pending_until is not None
                                  for t in self._tracks.values()) == 1):
                        restored = self.reid_memory.take_match(
                            class_id, normalized[index], now=source_time,
                            min_similarity=self.reid_min_similarity,
                            min_margin=self.reid_min_margin,
                            spatial_support=spatial_support,
                        )
                        if restored is not None:
                            old_id = track_id
                            track_id = restored[0]
                            entry = self.reid_memory.last_match_entry
                            track.gallery = entry.gallery
                            track.descriptor = entry.descriptor
                            track.reference_area = entry.reference_area
                            track.pending_until = None
                            self._tracks[track_id] = self._tracks.pop(old_id)
                            retried = True
                            retry_restores += 1
                            reid_restores += 1
                            self._note_reid("retry_restored", class_id,
                                            best_similarity=restored[1], provisional_id=old_id)
                        else:
                            decision = self.reid_memory.last_decision or {}
                            self._note_reid("retry_" + str(decision.get("reason", "unknown")),
                                            class_id, **{
                                                key: value for key, value in decision.items()
                                                if key != "reason"
                                            })
            if self.reid_memory is not None:
                reason = self._learn_appearance(
                    self._tracks[track_id], normalized[index],
                    float(detection.get("confidence", 1.0)),
                )
                gallery_updates[reason] += 1
            identified_box = {**detection, "track_id": track_id}
            if restored is not None:
                identified_box["match_source"] = "appearance_retry" if retried else "appearance"
            elif self._tracks[track_id].pending_until is not None:
                identified_box["identity_status"] = "provisional"
            identified.append(identified_box)
        self.last_stats = {
            "covered_tracks": covered,
            "fallback_tracks": fallback,
            "motion_matches": sum(assignment[1] for assignment in assignments.values()),
            "motion_only_matches": sum(assignment[1] and assignment[2] for assignment in assignments.values()),
            "reid_restores": reid_restores,
            "reid_retry_restores": retry_restores,
            "reid_pending": sum(t.pending_until is not None for t in self._tracks.values()),
        }
        if self.reid_memory is not None:
            self.last_stats.update(
                reid_memory_count=len(self.reid_memory),
                reid_gallery_updates=dict(gallery_updates),
                reid_gallery_sizes={str(key): len(track.gallery)
                                    for key, track in self._tracks.items()},
                reid_expired_total=self.reid_memory.expired_total,
                reid_event_counts=dict(self._reid_events),
                reid_last_event=dict(self._last_reid_event or {}),
                reid_last_by_class={
                    str(class_id): dict(event)
                    for class_id, event in self._last_reid_by_class.items()
                },
            )
        return identified
