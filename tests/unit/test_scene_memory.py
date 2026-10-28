"""Real OpenCV scene-revisit checks using synthetic, nonprivate images."""

from __future__ import annotations

import unittest
import numpy as np

from spatial.scene_memory import MemoryConfig, SceneMemory, spatial_support

try:
    import cv2 as cv
except ImportError:
    cv = None


@unittest.skipIf(cv is None, "OpenCV required for real feature/geometry tests")
class SceneMemoryTests(unittest.TestCase):
    def setUp(self) -> None:
        """Build two independently textured scenes with distributed features.

        Args:
            None.
        Returns:
            None: Only synthetic images and an empty memory are created.
        """
        cv.setNumThreads(1)
        cv.setRNGSeed(0)
        rng = np.random.default_rng(42)
        self.a = cv.GaussianBlur(rng.integers(0, 256, (360, 640), dtype=np.uint8), (3, 3), 0)
        self.b = cv.GaussianBlur(rng.integers(0, 256, (360, 640), dtype=np.uint8), (3, 3), 0)
        self.memory = SceneMemory(cv=cv)

    def test_return_after_unrelated_view_retains_scene_id(self) -> None:
        """A translated return retrieves A after an unknown B observation.

        Args:
            None.
        Returns:
            None: Assertions check recognition and query non-enrollment.
        """
        enrolled = self.memory.process(self.a, 0, "A")
        other = self.memory.process(self.b, 1)
        shifted = cv.warpAffine(self.a, np.float32([[1, 0, 12], [0, 1, -7]]), (640, 360))
        returned = self.memory.process(shifted, 2)
        self.assertEqual(enrolled["state"], "enrolled")
        self.assertEqual(other["state"], "unknown")
        self.assertEqual(returned["state"], "known")
        self.assertEqual(returned["scene_id"], enrolled["scene_id"])
        self.assertEqual(len(self.memory.views), 1)

    def test_blank_and_local_foreground_do_not_prove_revisit(self) -> None:
        """Shared detail confined to a small image region cannot validate the view.

        Args:
            None.
        Returns:
            None: Assertions reject low texture and concentrated matching evidence.
        """
        self.memory.process(self.a, 0, "A")
        self.assertEqual(self.memory.process(np.zeros_like(self.a), 1)["reason"], "weak_image")
        foreground = self.b.copy()
        foreground[120:230, 240:400] = self.a[120:230, 240:400]
        self.assertEqual(self.memory.process(foreground, 2)["state"], "unknown")
        coverage, cells = spatial_support(cv, np.float32([[250, 140], [350, 140], [350, 220], [250, 220]]))
        self.assertLess(coverage, self.memory.config.min_coverage)
        self.assertLess(cells, self.memory.config.min_cells)

    def test_small_rotation_and_scale_preserve_view_recognition(self) -> None:
        """Geometric verification accepts distributed features after a 2D warp.

        Args:
            None.
        Returns:
            None: The stored scene is recovered despite changed pixel coordinates.
        """
        self.memory.process(self.a, 0, "A")
        transform = cv.getRotationMatrix2D((320, 180), 4, 0.98)
        rotated = cv.warpAffine(self.a, transform, (640, 360))
        self.assertEqual(self.memory.process(rotated, 1)["label"], "A")

    def test_duplicate_references_abstain_without_refreshing_either(self) -> None:
        """Two equally supported scene labels must not produce an arbitrary identity.

        Args:
            None.
        Returns:
            None: Ambiguous query keeps both reference recencies unchanged.
        """
        self.memory.process(self.a, 0, "A")
        self.memory.process(self.a, 1, "A-lookalike")
        result = self.memory.process(self.a, 2)
        self.assertEqual(result["reason"], "ambiguous_views")
        self.assertIsNone(result["scene_id"])
        self.assertEqual([view.last_used_s for view in self.memory.views], [0, 1])

    def test_capacity_recency_and_reset_do_not_reuse_ids(self) -> None:
        """Confirmed use protects A from LRU eviction; reset clears views, not IDs.

        Args:
            None.
        Returns:
            None: Memory remains bounded and expired IDs are never reassigned.
        """
        memory = SceneMemory(MemoryConfig(max_views=2), cv)
        first = memory.process(self.a, 0, "A")
        second = memory.process(self.b, 1, "B")
        memory.process(self.a, 2)
        third = memory.process(self.b, 3, "C")
        self.assertEqual(third["evicted_id"], second["scene_id"])
        self.assertIn(first["scene_id"], [view.scene_id for view in memory.views])
        self.assertEqual(len(memory.views), 2)
        memory.reset()
        self.assertEqual(len(memory.views), 0)
        self.assertGreater(memory.process(self.a, 0, "A")["scene_id"], third["scene_id"])

    def test_invalid_time_shape_and_duplicate_label_are_rejected(self) -> None:
        """Input contract failures cannot silently alter a reference set.

        Args:
            None.
        Returns:
            None: Invalid observations raise ValueError.
        """
        self.memory.process(self.a, 1, "A")
        for timestamp in (0, 1, float("nan"), float("inf")):
            with self.assertRaises(ValueError):
                self.memory.process(self.a, timestamp)
        with self.assertRaises(ValueError):
            self.memory.process(self.a, 2, "A")
        with self.assertRaises(ValueError):
            self.memory.process(np.zeros((300, 300), dtype=np.uint8), 2)
        self.assertEqual(len(self.memory.views), 1)


if __name__ == "__main__":
    unittest.main()
