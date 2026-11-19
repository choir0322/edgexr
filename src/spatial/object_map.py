"""Session memory of objects by direction, with in-view prediction (step 2).

Each remembered object has a detector class and a start-frame bearing (from
spatial.bearing). On every detector result the map predicts, from the head
orientation paired with that frame, which remembered objects should be in view
and at which pixel; then matches detections to memory by class and angular
distance. It reports events: new, confirmed_return (reappeared where predicted
after being out of view), missing (expected in view but unseen), seen_again and
moved. "Same object" means same class near the same direction; two identical
objects swapped in place are indistinguishable. Bearings share the gyro's slowly
drifting reference, so the matching gate must exceed the drift over a session.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
import math
import threading
import time
from typing import Any

from spatial.bearing import CameraModel, distort, max_ideal_radius, rotate
from spatial.view_map import orientation_context


@dataclass
class Entry:
    """One remembered object; angles in degrees in the start frame, times in host seconds."""

    id: int
    label: str
    yaw: float
    pitch: float
    first_s: float
    last_s: float
    sightings: int = 1
    state: str = "tentative"        # tentative, seen, out_of_view, expected, missing
    misses: int = 0                 # consecutive in-view updates without a match
    away: bool = False              # has been out of view since it was last seen
    predicted_px: list[float] | None = None
    in_view: bool = True
    replaces: int | None = None     # tentative sighting that may be a missing object, moved
    history: list[str] = field(default_factory=list)


def direction(yaw: float, pitch: float) -> tuple[float, float, float]:
    """Unit vector for a bearing (x right, y down, z forward).

    Args:
        yaw (float): Degrees, right positive.
        pitch (float): Degrees, up positive.
    Returns:
        tuple[float, float, float]: Unit direction.
    """
    a, b = math.radians(yaw), math.radians(pitch)
    return math.sin(a) * math.cos(b), -math.sin(b), math.cos(a) * math.cos(b)


def separation(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Angle between two bearings.

    Args:
        a (tuple[float, float]): Yaw, pitch in degrees.
        b (tuple[float, float]): Yaw, pitch in degrees.
    Returns:
        float: Angular separation in degrees.
    """
    u, v = direction(*a), direction(*b)
    return math.degrees(math.acos(max(-1.0, min(1.0, sum(p * q for p, q in zip(u, v))))))


class ObjectMap:
    """Bounded, thread-safe object memory updated by the detector worker."""

    def __init__(self, model: CameraModel, gate_deg: float = 6.0, confirm_sightings: int = 2,
                 tentative_s: float = 3.0, miss_updates: int = 3, max_entries: int = 32,
                 max_width_fraction: float = 0.4, edge_margin_px: float = 30.0) -> None:
        """Create an empty map.

        Args:
            model (CameraModel): Calibration used to predict pixels.
            gate_deg (float): Largest angular distance for "same object" (≥ expected drift).
            confirm_sightings (int): Matches needed before a tentative object becomes real.
            tentative_s (float): Unconfirmed objects are forgotten after this long unseen.
            miss_updates (int): Consecutive in-view detector results without a match
                before "missing" (3 ≈ 1.5 s at 2 Hz).
            max_entries (int): Least-recently-seen objects are evicted beyond this.
            max_width_fraction (float): Boxes wider than this image fraction are ignored
                (the detector's whole-frame false positives).
            edge_margin_px (float): Predicted positions this close to an edge count as out of view.
        Returns:
            None: Empty memory; settings validated.
        """
        if not (0 < gate_deg <= 30 and confirm_sightings >= 1 and miss_updates >= 1 and max_entries >= 1):
            raise ValueError("Invalid object map settings")
        self.model, self.gate_deg = model, gate_deg
        self.max_radius = max_ideal_radius(model)
        self.confirm_sightings, self.tentative_s = confirm_sightings, tentative_s
        self.miss_updates, self.max_entries = miss_updates, max_entries
        self.max_width_fraction, self.edge_margin_px = max_width_fraction, edge_margin_px
        self.entries: dict[int, Entry] = {}
        self.events: deque[dict[str, Any]] = deque(maxlen=64)
        self.next_id = 1
        self.lock = threading.Lock()
        self.updates = 0
        self.update_ms: deque[float] = deque(maxlen=256)
        self.status = "waiting"

    def predict(self, entry: Entry, quaternion: list[float]) -> tuple[bool, list[float] | None]:
        """Where a remembered direction should appear for the current head orientation.

        Args:
            entry (Entry): Remembered object.
            quaternion (list[float]): Head orientation (w, x, y, z) for this frame.
        Returns:
            tuple[bool, list[float] | None]: In view flag and predicted pixel (u, v).
        """
        w, x, y, z = quaternion
        cx, cy, cz = rotate((w, -x, -y, -z), direction(entry.yaw, entry.pitch))
        # Behind the lens, or beyond where the lens polynomial folds back: not in view.
        if cz <= 0 or math.hypot(cx / cz, cy / cz) >= self.max_radius:
            return False, None
        u, v = distort(self.model, cx / cz, cy / cz)
        m = self.edge_margin_px
        inside = m <= u <= self.model.width - m and m <= v <= self.model.height - m
        return inside, [u, v]

    def _event(self, kind: str, entry: Entry, frame_s: float, **extra: Any) -> None:
        """Record an event and append it to the entry's short history.

        Args:
            kind (str): Event name.
            entry (Entry): Object concerned.
            frame_s (float): Frame receipt time.
            **extra (Any): Event details (angles, pixels).
        Returns:
            None: Appends to the bounded event list.
        """
        self.events.append({"frame_s": frame_s, "event": kind, "id": entry.id, "label": entry.label,
                            "yaw_deg": entry.yaw, "pitch_deg": entry.pitch, **extra})
        entry.history = (entry.history + [kind])[-8:]

    def update(self, boxes: list[dict[str, Any]], orientation: dict | None, frame_s: float) -> list[dict[str, Any]]:
        """Predict, match and update memory for one detector result.

        Args:
            boxes (list[dict[str, Any]]): Detections carrying ``bearing`` records.
            orientation (dict | None): Orientation context paired with the frame.
            frame_s (float): Frame receipt seconds.
        Returns:
            list[dict[str, Any]]: Events produced by this update.
        """
        started = time.perf_counter()
        context = orientation_context(orientation or {}, frame_s)
        with self.lock:
            before = len(self.events)
            if context["status"] != "ready":
                self.status = "orientation_unknown"
                return []
            self.status = "ready"
            q = context["quaternion_wxyz"]
            detections = [b for b in boxes
                          if b.get("bearing", {}).get("status") == "ready"
                          and b["box_xyxy"][2] - b["box_xyxy"][0] <= self.max_width_fraction * self.model.width]
            for entry in self.entries.values():
                entry.in_view, entry.predicted_px = self.predict(entry, q)

            # Closest same-class pairs first; each object and detection used once.
            pairs = []
            for entry in self.entries.values():
                for j, box in enumerate(detections):
                    if box["label"] == entry.label:
                        d = separation((entry.yaw, entry.pitch), (box["bearing"]["yaw_deg"], box["bearing"]["pitch_deg"]))
                        if d <= self.gate_deg:
                            pairs.append((d, entry.id, j))
            matched_entries, matched_boxes = set(), set()
            for d, entry_id, j in sorted(pairs):
                if entry_id in matched_entries or j in matched_boxes:
                    continue
                matched_entries.add(entry_id)
                matched_boxes.add(j)
                self._matched(self.entries[entry_id], detections[j], d, frame_s)

            # Remembered objects not seen this time: out of view, or expected and missed.
            for entry in list(self.entries.values()):
                if entry.id in matched_entries or entry.last_s == frame_s:
                    continue   # matched, or moved/confirmed during this update
                if entry.state == "tentative":
                    if frame_s - entry.last_s > self.tentative_s:
                        del self.entries[entry.id]
                    continue
                if not entry.in_view:
                    if entry.state in ("seen", "expected"):
                        entry.state, entry.misses = "out_of_view", 0
                    entry.away = True
                    continue
                if entry.state == "missing":
                    continue
                entry.misses += 1
                entry.state = "expected"
                if entry.misses >= self.miss_updates:
                    entry.state = "missing"
                    # A same-class object that first appeared after this one was last
                    # seen is most likely this object, moved while the head looked away.
                    later = [e for e in self.entries.values() if e.label == entry.label and e.id != entry.id
                             and e.state != "tentative" and e.first_s > entry.last_s]
                    if later:
                        self._merge_moved(entry, max(later, key=self._last_seen), frame_s)
                    else:
                        self._event("missing", entry, frame_s, predicted_px=entry.predicted_px)

            # Unmatched detections: a missing object reappearing elsewhere has moved;
            # while a same-class object is merely late, wait; otherwise start tentative.
            for j, box in enumerate(detections):
                if j in matched_boxes:
                    continue
                bearing = box["bearing"]
                if bearing.get("extrapolated"):
                    continue
                if any(e.label == box["label"] and e.state == "expected" for e in self.entries.values()):
                    continue
                missing = [e for e in self.entries.values() if e.label == box["label"] and e.state == "missing"]
                entry = Entry(self.next_id, box["label"], bearing["yaw_deg"], bearing["pitch_deg"], frame_s, frame_s,
                              replaces=max(missing, key=self._last_seen).id if missing else None)
                self.next_id += 1
                self.entries[entry.id] = entry
                if self.confirm_sightings <= 1:
                    self._confirm(entry, frame_s)

            # Bound memory: forget the least recently seen objects first.
            while len(self.entries) > self.max_entries:
                del self.entries[min(self.entries.values(), key=self._last_seen).id]
            self.updates += 1
            produced = list(self.events)[before:] if len(self.events) > before else []
            self.update_ms.append((time.perf_counter() - started) * 1000)
            return produced

    @staticmethod
    def _last_seen(entry: Entry) -> float:
        """Sort key: when an object was last matched.

        Args:
            entry (Entry): Remembered object.
        Returns:
            float: Host seconds.
        """
        return entry.last_s

    def _matched(self, entry: Entry, box: dict[str, Any], distance: float, frame_s: float) -> None:
        """Update one object from its matching detection and emit state events.

        Args:
            entry (Entry): Remembered object.
            box (dict[str, Any]): Matching detection with bearing.
            distance (float): Angular distance between them, degrees.
            frame_s (float): Frame receipt time.
        Returns:
            None: Updates the entry in place.
        """
        bearing = box["bearing"]
        u, v = bearing["pixel"]
        error = math.dist(entry.predicted_px, (u, v)) if entry.predicted_px else None
        if entry.state == "tentative":
            entry.sightings += 1
            entry.last_s = frame_s
            if entry.sightings >= self.confirm_sightings:
                self._confirm(entry, frame_s)
            return
        if entry.state == "missing":
            self._event("seen_again", entry, frame_s, distance_deg=distance)
        elif entry.away:
            self._event("confirmed_return", entry, frame_s, distance_deg=distance,
                        predicted_px=entry.predicted_px, observed_px=[u, v], prediction_error_px=error)
        entry.state = "seen"
        entry.sightings += 1
        # Smooth the remembered direction a little; detector boxes jitter by ~1°.
        entry.yaw += 0.3 * (bearing["yaw_deg"] - entry.yaw)
        entry.pitch += 0.3 * (bearing["pitch_deg"] - entry.pitch)
        entry.misses, entry.away, entry.last_s = 0, False, frame_s

    def _merge_moved(self, old: Entry, new: Entry, frame_s: float) -> None:
        """Keep the old identity at the newer object's direction and drop the newer entry.

        Args:
            old (Entry): Object now missing from its remembered direction.
            new (Entry): Same-class object first seen after ``old`` was last seen.
            frame_s (float): Frame receipt time.
        Returns:
            None: Removes ``new`` and emits a moved event.
        """
        start = (old.yaw, old.pitch)
        old.yaw, old.pitch, old.state, old.misses = new.yaw, new.pitch, new.state, 0
        old.away, old.in_view, old.predicted_px = new.away, new.in_view, new.predicted_px
        old.last_s, old.sightings = new.last_s, old.sightings + new.sightings
        del self.entries[new.id]
        self._event("moved", old, frame_s, from_yaw_deg=start[0], from_pitch_deg=start[1],
                    moved_deg=separation(start, (old.yaw, old.pitch)), merged_id=new.id)

    def _confirm(self, entry: Entry, frame_s: float) -> None:
        """Promote a confirmed tentative sighting: a moved object or a new one.

        Args:
            entry (Entry): Tentative entry with enough sightings.
            frame_s (float): Frame receipt time.
        Returns:
            None: Emits a new or moved event.
        """
        old = self.entries.get(entry.replaces) if entry.replaces is not None else None
        if old is not None and old.state == "missing":
            # Keep the original identity and move it to the new direction.
            start = (old.yaw, old.pitch)
            old.yaw, old.pitch, old.state, old.misses, old.away = entry.yaw, entry.pitch, "seen", 0, False
            old.last_s, old.sightings = frame_s, old.sightings + entry.sightings
            del self.entries[entry.id]
            self._event("moved", old, frame_s, from_yaw_deg=start[0], from_pitch_deg=start[1],
                        moved_deg=separation(start, (old.yaw, old.pitch)))
            return
        entry.state, entry.replaces = "seen", None
        self._event("new", entry, frame_s)

    def snapshot(self, now: float) -> dict[str, Any]:
        """JSON-ready view of remembered objects, recent events and update cost.

        Args:
            now (float): Host seconds for ages.
        Returns:
            dict[str, Any]: Status, objects, last 12 events and update timing.
        """
        with self.lock:
            objects = [{"id": e.id, "label": e.label, "yaw_deg": e.yaw, "pitch_deg": e.pitch,
                        "state": e.state, "in_view": e.in_view, "predicted_px": e.predicted_px,
                        "sightings": e.sightings, "unseen_s": now - e.last_s}
                       for e in sorted(self.entries.values(), key=self._last_seen, reverse=True)]
            timings = list(self.update_ms)
            return {"status": self.status, "objects": objects, "events": list(self.events)[-12:],
                    "updates": self.updates, "gate_deg": self.gate_deg,
                    "update_ms_last": timings[-1] if timings else None,
                    "update_ms_max": max(timings) if timings else None,
                    "update_ms_mean": sum(timings) / len(timings) if timings else None}
