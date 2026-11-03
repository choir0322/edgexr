"""Bounded view/transition memory; angular context is not position or fusion."""

from __future__ import annotations

import copy
import math

from spatial.relative_orientation import quaternion_product


def orientation_context(context: dict, frame_s: float) -> dict:
    """Validate the preceding host-timed gyro context of one scene observation.

    Args:
        context (dict): Output of LiveImu.orientation_at, possibly unknown.
        frame_s (float): Camera host receipt seconds, not exposure time.
    Returns:
        dict: Finite unit quaternion/epoch/sample time or explicit unknown reason.
    """
    if context.get("status") != "ready":
        return {"status": "unknown", "reason": context.get("reason") or "orientation_unavailable"}
    try:
        q = tuple(float(v) for v in context["quaternion_wxyz"])
        epoch = float(context["reference_monotonic_s"])
        sample = float(context["sample_monotonic_s"])
        if (len(q) != 4 or not all(math.isfinite(v) for v in (*q, epoch, sample)) or
                epoch < 0 or sample < epoch or not 0 <= frame_s - sample <= 0.200000001):
            raise ValueError("Invalid orientation timing or values")
        norm = math.sqrt(sum(v * v for v in q))
        if abs(norm - 1) > 0.001:
            raise ValueError("Non-unit orientation")
        return {"status": "ready", "quaternion_wxyz": [v / norm for v in q],
                "reference_monotonic_s": epoch, "sample_monotonic_s": sample}
    except (KeyError, TypeError, ValueError, OverflowError):
        return {"status": "unknown", "reason": "invalid_or_stale_orientation_context"}


def direction_to_view(current: dict, saved: dict) -> dict:
    """Express a saved lens direction in the current camera's coordinate frame.

    Args:
        current (dict): Validated current orientation context.
        saved (dict): Validated context captured when the view was enrolled.
    Returns:
        dict: Angular estimates or unknown. X right, Y down, Z forward. These
        are directions to remembered viewing rays, not bearings to 3D objects.
    """
    if current["status"] != "ready" or saved["status"] != "ready":
        return {"status": "unknown", "reason": "current_or_enrollment_orientation_unavailable"}
    if current["reference_monotonic_s"] != saved["reference_monotonic_s"]:
        return {"status": "unknown", "reason": "different_orientation_reference"}
    w, x, y, z = current["quaternion_wxyz"]
    relative = quaternion_product((w, -x, -y, -z), saved["quaternion_wxyz"])
    a, b, c, d = relative
    # Rotate the saved camera's forward unit axis, rather than treating the
    # quaternion XYZ components as positions or Euler angles.
    ray = quaternion_product(quaternion_product(relative, (0, 0, 0, 1)),
                             (a, -b, -c, -d))[1:]
    rx, ry, rz = ray
    horizontal = math.hypot(rx, rz)
    return {"status": "ready", "direction_xyz_unit": list(ray),
            "yaw_right_deg": math.degrees(math.atan2(rx, rz)) if horizontal > 1e-9 else None,
            "elevation_up_deg": math.degrees(math.atan2(-ry, horizontal)),
            "pointing_separation_deg": math.degrees(math.acos(max(-1, min(1, rz)))),
            "rotation_difference_deg": math.degrees(2 * math.acos(max(0, min(1, abs(a)))))}


class ViewMap:
    """Scene-worker-owned nodes and bounded directed observation-history edges."""

    def __init__(self, max_views: int = 12) -> None:
        """Start an empty session map tied to the scene memory's capacity.

        Args:
            max_views (int): Maximum enrolled nodes; must agree with SceneMemory.
        Returns: None.
        """
        if not 1 <= max_views <= 30:
            raise ValueError("View-map capacity must be between 1 and 30")
        self.max_views = max_views
        self.nodes: dict[int, dict] = {}
        self.edges: dict[tuple[int, int], dict] = {}
        self.previous: dict | None = None
        self.unknown_since_previous = 0
        self.last_time: float | None = None

    def update(self, decision: dict, orientation: dict, frame_s: float) -> dict:
        """Observe one existing scene decision without changing its outcome.

        Args:
            decision (dict): SceneMemory.process result, including optional eviction.
            orientation (dict): Preceding frame-associated gyro context.
            frame_s (float): Strictly increasing finite host receipt seconds.
        Returns:
            dict: Independent JSON-ready map snapshot; bounded nodes/edges and
            unknowns are preserved even if the optional recorder drops this row.
        """
        if (not math.isfinite(frame_s) or frame_s < 0 or
                (self.last_time is not None and frame_s <= self.last_time)):
            raise ValueError("View-map frame times must increase")
        kind = decision["state"]
        if kind not in {"enrolled", "known", "unknown"}:
            raise ValueError("Unsupported scene decision")
        scene_id = decision.get("scene_id")
        evicted = decision.get("evicted_id")
        if kind == "known" and scene_id not in self.nodes:
            raise ValueError("Known view missing from map")
        if kind == "enrolled" and (scene_id in self.nodes or
                len(self.nodes) - int(evicted in self.nodes) >= self.max_views):
            raise ValueError("Enrollment capacity/ID disagrees with scene memory")
        current = orientation_context(orientation, frame_s)
        self.last_time = frame_s

        # Match SceneMemory's LRU eviction exactly; never retain dangling edges.
        if kind == "enrolled":
            self.nodes.pop(evicted, None)
            self.edges = {key: value for key, value in self.edges.items() if evicted not in key}
            if self.previous and self.previous["scene_id"] == evicted:
                self.previous = None
                self.unknown_since_previous = 0
            self.nodes[scene_id] = {"scene_id": scene_id, "label": decision["label"],
                                    "enrolled_host_s": frame_s, "orientation": current,
                                    "last_seen_host_s": frame_s, "recognized_queries": 0}

        transition = None
        if kind == "unknown":
            if self.previous:
                self.unknown_since_previous += 1
        else:
            node = self.nodes[scene_id]
            node["last_seen_host_s"] = frame_s
            node["recognized_queries"] += int(kind == "known")
            if self.previous and self.previous["scene_id"] != scene_id:
                key = (self.previous["scene_id"], scene_id)
                transition = self.edges.setdefault(key, {
                    "from_scene_id": key[0], "to_scene_id": key[1], "count": 0})
                transition.update(count=transition["count"] + 1, last_observed_host_s=frame_s,
                                  interval_s=frame_s - self.previous["frame_host_s"],
                                  intervening_unknown_observations=self.unknown_since_previous)
            self.previous = {"scene_id": scene_id, "frame_host_s": frame_s}
            self.unknown_since_previous = 0

        # Bearings are contextual comparisons, not new matches or motor commands.
        nodes = []
        for node in self.nodes.values():
            nodes.append({**node, "enrollment_age_s": frame_s - node["enrolled_host_s"],
                          "direction_from_current": direction_to_view(current, node["orientation"])})
        return copy.deepcopy({"schema": 1, "frame_host_s": frame_s,
                              "current_scene_id": scene_id if kind != "unknown" else None,
                              "visual_state": kind, "visual_reason": decision.get("reason"),
                              "orientation_status": current["status"],
                              "orientation_reason": current.get("reason"),
                              "nodes": nodes, "edges": list(self.edges.values()),
                              "latest_transition": transition,
                              "scope": "Session-local viewing directions and observed label changes; gyro drift, no physical position/distance/path or correction"})
