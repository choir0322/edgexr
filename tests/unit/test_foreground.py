"""Person-mask timing, coordinate and scene-evidence contracts."""

import unittest
import numpy as np
from spatial.foreground import person_mask
from spatial.scene_memory import SceneMemory
from vision.live_detector import DetectionState

try:
    import cv2 as cv
except ImportError:
    cv = None


class ForegroundTests(unittest.TestCase):
    def test_time_gates(self) -> None:
        """Reject unavailable, future, stale and nonfinite source evidence.

        Args: None.
        Returns: None.
        """
        for evidence, reason in [(None, "missing_detection"),
                                 ({"captured": 2}, "future_detection"),
                                 ({"captured": 0}, "stale_detection"),
                                 ({"captured": float("nan")}, "invalid_timestamp")]:
            mask, info = person_mask(evidence, 1)
            self.assertIsNone(mask)
            self.assertEqual(info["reason"], reason)
        mask, info = person_mask({"captured": 0.5, "boxes": []}, 1)
        self.assertTrue(np.all(mask == 255))
        self.assertEqual(info["source_age_ms"], 500)

    def test_person_scaling_clipping_and_other_classes(self) -> None:
        """Only VOC person 15 excludes pixels, rounding box edges outwards.

        Args: None.
        Returns: None.
        """
        mask, info = person_mask({"captured": 1, "sequence": 7, "boxes": [
            {"class_id": 15, "box_xyxy": [-5, 0, 641, 720]},
            {"class_id": 9, "box_xyxy": [0, 0, 1280, 720]}]}, 1.2)
        self.assertEqual(mask.shape, (360, 640))
        self.assertTrue(np.all(mask[:, :321] == 0))
        self.assertTrue(np.all(mask[:, 321:] == 255))
        self.assertEqual(info["person_boxes"], 1)
        self.assertEqual(info["source_sequence"], 7)

    def test_invalid_person_box_does_not_silently_disable_mask(self) -> None:
        """Malformed person geometry makes evidence unavailable.

        Args: None.
        Returns: None.
        """
        for coords in ([0, 0, float("nan"), 1], [4, 0, 2, 3], [1]):
            mask, info = person_mask({"captured": 1, "boxes": [
                {"class_id": 15, "box_xyxy": coords}]}, 1)
            self.assertIsNone(mask)
            self.assertEqual(info["reason"], "invalid_person_box")

    def test_mailbox_copy_and_failure(self) -> None:
        """Scene consumers cannot mutate published detections or use failed data.

        Args: None.
        Returns: None.
        """
        state = DetectionState(True)
        state.publish((1, 1.0, b""), [{"class_id": 15, "box_xyxy": [0, 0, 20, 20]}], 5, 1.1)
        copy = state.scene_evidence()
        copy["boxes"][0]["box_xyxy"][0] = 100
        self.assertEqual(state.scene_evidence()["boxes"][0]["box_xyxy"][0], 0)
        state.fail("test")
        self.assertIsNone(state.scene_evidence())

    @unittest.skipIf(cv is None, "OpenCV required")
    def test_masked_enrollment_and_query(self) -> None:
        """Masking leaves input intact, preserves background and rejects no evidence.

        Args: None.
        Returns: None.
        """
        cv.setNumThreads(1)
        cv.setRNGSeed(0)
        image = np.random.default_rng(22).integers(0, 256, (360, 640), dtype=np.uint8)
        original = image.copy()
        mask = np.full_like(image, 255)
        mask[140:220, 280:360] = 0
        memory = SceneMemory(cv=cv)
        rejected = memory.process(image, 0, "background", feature_mask=mask)
        self.assertEqual(rejected["reason"], "clear_background_required")
        result = memory.process(image, 0.1, "background")
        self.assertEqual(result["state"], "enrolled")
        self.assertTrue(np.array_equal(image, original))
        self.assertEqual(memory.process(image, 1, feature_mask=mask)["state"], "known")
        self.assertEqual(memory.process(image, 2, feature_mask=np.zeros_like(mask))["state"], "unknown")
        with self.assertRaises(ValueError):
            memory.process(image, 3, feature_mask=np.ones((10, 10), dtype=np.uint8))
