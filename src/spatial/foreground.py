"""Conservative, host-timestamped person masks for scene feature extraction."""

from __future__ import annotations

import math
import numpy as np

from spatial.scene_memory import WIDTH, HEIGHT

MAX_SOURCE_LAG_S = 0.5


def person_mask(detection: dict | None, frame_s: float) -> tuple[np.ndarray | None, dict]:
    """Return a canonical allowed-feature mask or explicit unavailable evidence.

    Args:
        detection (dict | None): Atomic detector result with captured host seconds,
            sequence and boxes in 1280×720 source pixels; None means unavailable.
        frame_s (float): Scene source host receipt time, not processing completion.
    Returns:
        tuple[np.ndarray | None, dict]: 360×640 uint8 mask (255 allowed) and diagnostics.
            None forbids masked-mode recognition/enrollment for this query.
    """
    info = {"policy": "person_boxes_v1", "max_source_lag_s": MAX_SOURCE_LAG_S,
            "status": "unavailable", "reason": "missing_detection",
            "source_sequence": None, "source_host_s": None,
            "source_age_ms": None, "person_boxes": 0, "excluded_fraction": None,
            "excluded_boxes_xyxy_640x360": []}
    if detection is None:
        return None, info
    source = detection.get("captured")
    if (not isinstance(source, (int, float)) or not math.isfinite(source) or
            not math.isfinite(frame_s)):
        info["reason"] = "invalid_timestamp"
        return None, info
    lag = frame_s - source
    info.update(source_sequence=detection.get("sequence"), source_host_s=source,
                source_age_ms=lag * 1000)
    if lag < 0 or lag > MAX_SOURCE_LAG_S:
        info["reason"] = "future_detection" if lag < 0 else "stale_detection"
        return None, info

    # SSD boxes refer to the full camera image, whereas ORB uses the canonical
    # half-size image. Round outwards and clip; never alter the source image.
    mask = np.full((HEIGHT, WIDTH), 255, dtype=np.uint8)
    for box in detection.get("boxes", []):
        if box.get("class_id") != 15:
            continue
        coords = box.get("box_xyxy", [])
        if len(coords) != 4 or not all(isinstance(v, (int, float)) and math.isfinite(v) for v in coords):
            info["reason"] = "invalid_person_box"
            return None, info
        x1, y1, x2, y2 = coords
        if x2 <= x1 or y2 <= y1:
            info["reason"] = "invalid_person_box"
            return None, info
        left, top = max(0, min(WIDTH, math.floor(x1 / 2))), max(0, min(HEIGHT, math.floor(y1 / 2)))
        right, bottom = max(0, min(WIDTH, math.ceil(x2 / 2))), max(0, min(HEIGHT, math.ceil(y2 / 2)))
        mask[top:bottom, left:right] = 0
        info["person_boxes"] += 1
        info["excluded_boxes_xyxy_640x360"].append([left, top, right, bottom])
    info.update(status="ready", reason="fresh_detector_result",
                excluded_fraction=float(np.count_nonzero(mask == 0)) / mask.size)
    return mask, info
