"""Source-pairing, bounded enrollment and partial-background safety checks."""

import threading
import time
import unittest
import numpy as np
from app.live_preview import State
from spatial.live_scene import LiveScene, scene_latest
from spatial.scene_memory import SceneMemory
from vision.live_detector import DetectionState

try:
    import cv2 as cv
except ImportError:
    cv = None


class SceneOcclusionTests(unittest.TestCase):
    def test_pair_is_immutable_and_not_in_detector_telemetry(self) -> None:
        """Retain exact pixels/context until a newer completed result replaces it.

        Args: None.
        Returns: None.
        """
        state = DetectionState(True)
        state.publish((4, 10., b"old-source"), [], 250, 10.25,
                      orientation={"status": "ready", "sample": 9.99})
        source, orientation, evidence = state.paired_scene()
        self.assertEqual(source, (4, 10., b"old-source"))
        orientation["sample"] = 100
        evidence["boxes"].append({})
        self.assertEqual(state.paired_scene()[1]["sample"], 9.99)
        self.assertEqual(state.paired_scene()[2]["boxes"], [])
        self.assertNotIn("pixels", state.snapshot(10.3))
        state.fail("lost")
        self.assertIsNone(state.paired_scene())

    def test_timeout_without_frames_and_no_late_store(self) -> None:
        """A missing-source request expires and cannot consume a later frame.

        Args: None.
        Returns: None.
        """
        scene = LiveScene(True)
        scene.enroll(10)
        self.assertIsNone(scene.take_request(10))
        snapshot = scene.snapshot(18, True)
        self.assertEqual(snapshot["enrollments"][-1]["status"], "expired")
        self.assertIsNone(snapshot["pending_label"])
        self.assertIsNone(scene.take_request(19))
        self.assertEqual(scene.enroll(20), "View-2")

    @unittest.skipIf(cv is None, "OpenCV required")
    def test_stale_pair_expires_without_processing_or_browser(self) -> None:
        """An old detector package cannot enroll; worker deadlines need no browser.

        Args: None.
        Returns: None.
        """
        state = State(scene_memory=True, detection_enabled=True)
        now = time.monotonic()
        state.scene.enroll(now - 8)
        state.detector.publish((1, now - 3, bytes(720 * 1280)), [], 250, now - 2.75)
        worker = threading.Thread(target=scene_latest, args=(state, cv, None, False, True))
        worker.start()
        try:
            deadline = time.monotonic() + 2
            while state.scene.pending and time.monotonic() < deadline:
                time.sleep(.01)
            self.assertIsNone(state.scene.pending)
            self.assertIsNone(state.scene.result)
            self.assertEqual(state.scene.enrollments[-1]["reason"], "enrollment_wait_timeout")
        finally:
            state.stop.set()
            worker.join(5)

    @unittest.skipIf(cv is None, "OpenCV required")
    def test_partial_background_and_rejection_controls(self) -> None:
        """Match visible background; reject tiny, unrelated and ambiguous evidence.

        Args: None.
        Returns: None.
        """
        cv.setNumThreads(1)
        cv.setRNGSeed(0)
        image = np.random.default_rng(40).integers(0, 256, (360, 640), dtype=np.uint8)
        memory = SceneMemory(cv=cv)
        self.assertEqual(memory.process(image, 0, "clear")["state"], "enrolled")
        reference = memory.views[0].image.copy()
        mask = np.full_like(image, 255)
        mask[:, :400] = 0
        query = image.copy()
        query[:, :400] = 0
        result = memory.process(query, 1, feature_mask=mask)
        self.assertEqual(result["state"], "known")
        self.assertLessEqual(len(result["evidence_pairs"]["query_xy"]), 128)
        self.assertTrue(all(x >= 400 for x, y in result["evidence_pairs"]["query_xy"]))
        # Only one of the original three grid columns remains: v1's four-cell
        # whole-frame rule would reject this, despite consistent visible geometry.
        self.assertEqual(result["candidates"][0]["query_cells"], 3)
        np.testing.assert_array_equal(reference, memory.views[0].image)
        mask[:, :600] = 0
        self.assertEqual(memory.process(image, 2, feature_mask=mask)["reason"], "insufficient_visible_background")
        mask[:, :] = 255
        mask[:, :400] = 0
        unrelated = np.random.default_rng(99).integers(0, 256, image.shape, dtype=np.uint8)
        self.assertEqual(memory.process(unrelated, 3, feature_mask=mask)["state"], "unknown")
        memory.process(image, 4, "duplicate")
        self.assertEqual(memory.process(query, 5, feature_mask=mask)["reason"], "ambiguous_views")

    @unittest.skipIf(cv is None, "OpenCV required")
    def test_worker_uses_older_exact_pair_not_new_camera_frame(self) -> None:
        """A 600ms old paired source is usable and keeps its original orientation.

        Args: None.
        Returns: None.
        """
        state = State(scene_memory=True, detection_enabled=True)
        now = time.monotonic()
        state.scene.enroll(now - 1)
        pixels = np.random.default_rng(7).integers(0, 256, (720, 1280), dtype=np.uint8).tobytes()
        state.publish_frame(bytes(320 * 180), now, bytes(720 * 1280))
        state.detector.publish((40, now - .6, pixels), [], 250, now - .35,
                               orientation={"status": "unknown", "reason": "source-marker"})
        worker = threading.Thread(target=scene_latest, args=(state, cv, None, False, True))
        worker.start()
        try:
            deadline = time.monotonic() + 3
            while state.scene.result is None and not state.scene.error and time.monotonic() < deadline:
                time.sleep(.01)
            self.assertIsNone(state.scene.error)
            row = state.scene.result
            self.assertEqual(row["frame_sequence"], 40)
            self.assertEqual(row["orientation_at_frame"]["reason"], "source-marker")
            self.assertEqual(row["decision"]["state"], "enrolled")
            self.assertEqual(row["decision"]["foreground"]["source_age_ms"], 0)
            self.assertTrue(state.scene.evidence["image_url"].startswith("data:image/jpeg;base64,"))
            self.assertNotIn("evidence", state.snapshot()["scene"])
        finally:
            state.stop.set()
            worker.join(5)
