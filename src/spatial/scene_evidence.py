"""Bounded source-matched diagnostic images, separate from numeric telemetry."""

import base64
from typing import Any
import numpy as np
from spatial.scene_memory import SceneMemory, prepare_gray


def render_evidence(cv: Any, memory: SceneMemory, gray: np.ndarray, decision: dict) -> dict:
    """Draw verified inliers on the actual query and stored reference.

    Args:
        cv (Any): OpenCV module already loaded by the scene worker.
        memory (SceneMemory): Worker-owned bounded references.
        gray (np.ndarray): Exact selected source grayscale image.
        decision (dict): Recognition and foreground diagnostics for that source.
    Returns:
        dict: JPEG data URL and legend metadata; not an image of the newest preview.
    """
    query = cv.cvtColor(prepare_gray(cv, gray), cv.COLOR_GRAY2BGR)
    reference = np.zeros_like(query)
    for view in memory.views:
        if view.scene_id == decision["scene_id"] and view.image is not None:
            reference = cv.cvtColor(view.image, cv.COLOR_GRAY2BGR)
    # Amber identifies unavailable evidence, not a detected object's silhouette.
    for left, top, right, bottom in decision.get("foreground", {}).get("excluded_boxes_xyxy_640x360", []):
        region = query[top:bottom, left:right]
        region[:] = (region.astype(np.float32) * 0.55 + np.array([0, 170, 255]) * 0.45).astype(np.uint8)
    pairs = decision.get("evidence_pairs", {}) if decision["state"] == "known" else {}
    for panel, key in ((reference, "reference_xy"), (query, "query_xy")):
        for x, y in pairs.get(key, []):
            cv.circle(panel, (round(x), round(y)), 3, (80, 240, 80), 1, cv.LINE_AA)
    ok, encoded = cv.imencode(".jpg", np.hstack((reference, query)), [cv.IMWRITE_JPEG_QUALITY, 75])
    if not ok:
        raise ValueError("Could not encode scene evidence")
    return {"image_url": "data:image/jpeg;base64," + base64.b64encode(encoded).decode("ascii"),
            "points_shown": len(pairs.get("query_xy", [])),
            "reference_label": decision.get("label"),
            "layout": "reference_left_query_right"}
