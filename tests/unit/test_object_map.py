"""Object memory on simulated head sweeps: stay, removed, moved, false sightings."""

import importlib.util
import math
from pathlib import Path
import tempfile
import unittest

from spatial.bearing import attach_bearings, distort, load_camera_model, max_ideal_radius, rotate
from spatial.object_map import ObjectMap, separation

MODEL = load_camera_model(Path(__file__).resolve().parents[2] / "configs" / "camera_calibration.json")


def orientation(pan: float, t: float) -> dict:
    """Orientation context for a head panned by ``pan`` degrees.

    Args:
        pan (float): Head yaw, right positive.
        t (float): Frame time (sample 5 ms earlier).
    Returns:
        dict: Ready orientation_at-shaped record.
    """
    a = math.radians(pan) / 2
    return {"status": "ready", "quaternion_wxyz": [math.cos(a), 0, math.sin(a), 0],
            "reference_monotonic_s": 0.0, "sample_monotonic_s": t - 0.005}


def boxes(objects: list[tuple[str, float, float]], pan: float, t: float) -> list[dict]:
    """Detections (with bearings) for objects visible from a head pan.

    Args:
        objects (list[tuple[str, float, float]]): (label, yaw, pitch) in the start frame.
        pan (float): Head yaw.
        t (float): Frame time.
    Returns:
        list[dict]: Boxes inside the image, as the detector worker would publish them.
    """
    a = math.radians(pan) / 2
    q = [math.cos(a), 0, math.sin(a), 0]
    out = []
    for label, yaw, pitch in objects:
        ya, pa = math.radians(yaw), math.radians(pitch)
        x, y, z = rotate([q[0], 0, -q[2], 0], (math.sin(ya) * math.cos(pa), -math.sin(pa), math.cos(ya) * math.cos(pa)))
        if z <= 0 or math.hypot(x / z, y / z) >= max_ideal_radius(MODEL):
            continue
        u, v = distort(MODEL, x / z, y / z)
        if 60 <= u <= 1220 and 80 <= v <= 640:
            out.append({"label": label, "confidence": 0.9, "box_xyxy": [u - 40, v - 70, u + 40, v + 70]})
    return attach_bearings(out, MODEL, orientation(pan, t), t)


def run(memory: ObjectMap, phases: list[tuple[float, int, list]]) -> list[dict]:
    """Feed 2 Hz detector results through phases of (pan, updates, objects).

    Args:
        memory (ObjectMap): Map under test.
        phases (list[tuple[float, int, list]]): Head pan, number of updates, visible-world objects.
    Returns:
        list[dict]: All events in order.
    """
    events, t = [], 1.0
    for pan, count, objects in phases:
        for _ in range(count):
            events += memory.update(boxes(objects, pan, t), orientation(pan, t), t)
            t += 0.5
    return events


BOTTLE = ("bottle", -32.0, 0.0)
LOOK_AWAY = (20.0, 8, [BOTTLE])     # head far right: the bottle is outside the view


class ObjectMapTests(unittest.TestCase):
    """Expected event sequences for the three trial cases plus robustness checks."""

    def test_bottle_stays_confirmed_on_return(self) -> None:
        """Seen, out of view, then confirmed where predicted; never missing.

        Args: None.
        Returns: None.
        """
        memory = ObjectMap(MODEL)
        events = run(memory, [(0.0, 4, [BOTTLE]), LOOK_AWAY, (0.0, 4, [BOTTLE])])
        kinds = [e["event"] for e in events]
        self.assertEqual(kinds, ["new", "confirmed_return"])
        self.assertLess(events[1]["prediction_error_px"], 1.0)
        self.assertEqual(memory.snapshot(20)["objects"][0]["state"], "seen")

    def test_removed_bottle_reported_missing(self) -> None:
        """Expected in view after the return but absent for three updates.

        Args: None.
        Returns: None.
        """
        memory = ObjectMap(MODEL)
        events = run(memory, [(0.0, 4, [BOTTLE]), (20.0, 8, []), (0.0, 5, [])])
        self.assertEqual([e["event"] for e in events], ["new", "missing"])
        self.assertAlmostEqual(events[1]["yaw_deg"], -32, delta=0.5)

    def test_moved_out_of_sight_keeps_identity(self) -> None:
        """Moved to a spot the turned head cannot see: missing, then confirmed elsewhere.

        Args: None.
        Returns: None.
        """
        memory = ObjectMap(MODEL)
        moved = ("bottle", -24.0, 0.0)   # outside the view of the head turned +20°
        self.assertEqual(boxes([moved], 20.0, 1.0), [])
        events = run(memory, [(0.0, 4, [BOTTLE]), (20.0, 8, [moved]), (0.0, 6, [moved])])
        self.assertEqual([e["event"] for e in events], ["new", "missing", "moved"])
        self.assertEqual(events[0]["id"], events[2]["id"])
        self.assertAlmostEqual(events[2]["moved_deg"], 8, delta=0.5)
        self.assertEqual(len(memory.snapshot(20)["objects"]), 1)

    def test_moved_into_view_of_turned_head_is_merged(self) -> None:
        """Moved where the turned head sees it: a new sighting, merged when the old goes missing.

        Args: None.
        Returns: None.
        """
        memory = ObjectMap(MODEL)
        moved = ("bottle", -10.0, 0.0)
        events = run(memory, [(0.0, 4, [BOTTLE]), (20.0, 8, [moved]), (0.0, 6, [moved])])
        self.assertEqual([e["event"] for e in events], ["new", "new", "moved"])
        self.assertEqual(events[2]["id"], events[0]["id"])
        self.assertEqual(events[2]["merged_id"], events[1]["id"])
        self.assertAlmostEqual(events[2]["moved_deg"], 22, delta=0.5)
        objects = memory.snapshot(20)["objects"]
        self.assertEqual([(o["id"], round(o["yaw_deg"])) for o in objects], [(events[0]["id"], -10)])

    def test_one_off_false_detection_never_becomes_an_object(self) -> None:
        """A single far-away 'bottle' stays tentative and is forgotten.

        Args: None.
        Returns: None.
        """
        memory = ObjectMap(MODEL)
        run(memory, [(0.0, 3, [BOTTLE]), (0.0, 1, [BOTTLE, ("bottle", 10.0, 5.0)]), (0.0, 10, [BOTTLE])])
        states = [(o["yaw_deg"] > 0, o["state"]) for o in memory.snapshot(20)["objects"]]
        self.assertEqual(states, [(False, "seen")])

    def test_oversized_boxes_and_unknown_orientation_are_ignored(self) -> None:
        """Whole-frame boxes are dropped; no orientation means no update.

        Args: None.
        Returns: None.
        """
        memory = ObjectMap(MODEL)
        big = attach_bearings([{"label": "bottle", "box_xyxy": [0, 0, 1280, 718]}], MODEL, orientation(0, 1), 1)
        self.assertEqual(memory.update(big + big, orientation(0, 1), 1), [])
        self.assertEqual(memory.update(big, orientation(0, 1.5), 1.5), [])
        self.assertEqual(memory.snapshot(2)["objects"], [])
        self.assertEqual(memory.update(boxes([BOTTLE], 0, 2), {"status": "unknown"}, 2), [])
        self.assertEqual(memory.snapshot(2)["status"], "orientation_unknown")

    def test_bounded_and_timed(self) -> None:
        """Memory never exceeds its limit and records update cost.

        Args: None.
        Returns: None.
        """
        memory = ObjectMap(MODEL, max_entries=3)
        objects = [("bottle", -30 + 8 * i, 0.0) for i in range(6)]
        run(memory, [(0.0, 3, objects)])
        snap = memory.snapshot(5)
        self.assertLessEqual(len(snap["objects"]), 3)
        self.assertIsNotNone(snap["update_ms_mean"])
        self.assertAlmostEqual(separation((0, 0), (90, 0)), 90, places=9)

    def test_far_off_axis_directions_are_not_predicted_in_view(self) -> None:
        """61° off-axis would fold back into the image; prediction must say out of view.

        Args: None.
        Returns: None.
        """
        memory = ObjectMap(MODEL)
        entry_box = boxes([BOTTLE], 0.0, 1.0)
        memory.update(entry_box, orientation(0.0, 1.0), 1.0)
        memory.update(boxes([BOTTLE], 0.0, 1.5), orientation(0.0, 1.5), 1.5)
        entry = next(iter(memory.entries.values()))
        entry.yaw = -41.0
        a = math.radians(20.0) / 2
        self.assertEqual(memory.predict(entry, [math.cos(a), 0, math.sin(a), 0]), (False, None))


@unittest.skipUnless(importlib.util.find_spec("cv2"), "OpenCV not installed")
class DuplicateEvidenceTests(unittest.TestCase):
    """Frames with two boxes of one class are saved, up to the limit."""

    def test_saves_only_duplicate_class_frames_up_to_limit(self) -> None:
        """One label twice → saved; distinct labels → not; limit respected.

        Args: None.
        Returns: None.
        """
        from vision.live_detector import save_duplicate_evidence
        with tempfile.TemporaryDirectory() as folder:
            evidence = {"folder": Path(folder), "saved": 0, "limit": 1}
            frame = (7, 1.0, bytes(1280 * 720))
            single = [{"label": "bottle"}, {"label": "chair"}]
            double = [{"label": "bottle", "box_xyxy": [0, 0, 1, 1]}, {"label": "bottle", "box_xyxy": [2, 2, 3, 3]}]
            self.assertFalse(save_duplicate_evidence(evidence, frame, single))
            self.assertTrue(save_duplicate_evidence(evidence, frame, double))
            self.assertFalse(save_duplicate_evidence(evidence, (8, 1.5, bytes(1280 * 720)), double))
            self.assertEqual(sorted(p.name for p in Path(folder).iterdir()), ["frame-00000007.json", "frame-00000007.png"])


if __name__ == "__main__":
    unittest.main()
