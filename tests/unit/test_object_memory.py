"""Hardware-free tests for bounded retired-ID memory and diagnostics."""

from __future__ import annotations

import unittest

from vision.object_memory import (
    RetiredObjectMemory, grayscale_grid_descriptor, normalize_descriptor,
)


class ObjectMemoryTests(unittest.TestCase):
    def test_grayscale_crop_has_fixed_shape_and_rejects_flat_or_tiny_boxes(self) -> None:
        """A source-pixel box yields a coarse descriptor, not stored raw pixels."""
        pixels = bytes([0] * 16 + [255] * 16) * 32
        descriptor = grayscale_grid_descriptor(pixels, 32, 32, [0, 0, 32, 32])
        self.assertIsNotNone(descriptor)
        self.assertEqual(len(descriptor), 64)
        self.assertIsNone(grayscale_grid_descriptor(
            bytes([100] * 1024), 32, 32, [0, 0, 32, 32]
        ))
        self.assertIsNone(grayscale_grid_descriptor(pixels, 32, 32, [0, 0, 8, 32]))
        with self.assertRaisesRegex(ValueError, "complete"):
            grayscale_grid_descriptor(b"short", 32, 32, [0, 0, 32, 32])
    def test_restores_only_a_strong_same_class_return_once(self) -> None:
        """A claimed ID leaves memory; a second detection cannot reuse it."""
        memory = RetiredObjectMemory(capacity=3, retention_s=5)
        self.assertTrue(memory.remember(7, 15, [1, 0], seen_at=1, now=2))
        self.assertIsNone(memory.take_match(
            8, [1, 0], now=2.1, min_similarity=0.9, min_margin=0.1
        ))
        self.assertEqual(memory.take_match(
            15, [2, 0], now=2.2, min_similarity=0.9, min_margin=0.1
        ), (7, 1.0))
        self.assertIsNone(memory.take_match(
            15, [1, 0], now=2.3, min_similarity=0.9, min_margin=0.1
        ))

    def test_ambiguous_lookalikes_and_weak_matches_abstain(self) -> None:
        """Near ties or low scores must not make a confident old-ID claim."""
        memory = RetiredObjectMemory(capacity=3, retention_s=5)
        memory.remember(1, 15, [1, 0], seen_at=1, now=2)
        memory.remember(2, 15, [0.99, 0.01], seen_at=1.1, now=2.1)
        self.assertIsNone(memory.take_match(
            15, [1, 0], now=2.2, min_similarity=0.9, min_margin=0.1
        ))
        self.assertEqual(len(memory), 2)
        self.assertIsNone(memory.take_match(
            15, [0, 1], now=2.3, min_similarity=0.9, min_margin=0.1
        ))
        self.assertEqual(memory.last_decision["reason"], "below_threshold")
        self.assertAlmostEqual(memory.last_decision["best_similarity"], 0.01, places=2)

    def test_diagnostic_distinguishes_expiry_ambiguity_and_success(self) -> None:
        """Publish scores and reasons without changing the original match policy."""
        memory = RetiredObjectMemory(capacity=3, retention_s=2)
        memory.remember(1, 15, [1, 0], seen_at=1, now=1)
        memory.remember(2, 15, [0.99, 0.01], seen_at=1, now=1)
        self.assertIsNone(memory.take_match(
            15, [1, 0], now=2, min_similarity=0.85, min_margin=0.05
        ))
        self.assertEqual(memory.last_decision["reason"], "ambiguous")
        self.assertEqual(memory.last_decision["candidate_count"], 2)
        self.assertIsNotNone(memory.last_decision["runner_up_similarity"])
        self.assertIsNone(memory.take_match(
            15, [1, 0], now=3.1, min_similarity=0.85, min_margin=0.05
        ))
        self.assertEqual(memory.last_decision["reason"], "expired")
        self.assertEqual(memory.expired_total, 2)
        memory.remember(3, 15, [1, 0], seen_at=3.2, now=3.2)
        self.assertEqual(memory.take_match(
            15, [1, 0], now=3.3, min_similarity=0.85, min_margin=0.05
        ), (3, 1.0))
        self.assertEqual(memory.last_decision["reason"], "restored")

    def test_expiry_capacity_and_clock_direction(self) -> None:
        """Last sighting, not retirement time, controls expiry and eviction."""
        memory = RetiredObjectMemory(capacity=2, retention_s=2)
        memory.remember(1, 15, [1, 0], seen_at=0, now=1)
        memory.remember(2, 15, [0, 1], seen_at=1.1, now=1.2)
        memory.remember(3, 7, [1, 1], seen_at=1.3, now=1.4)
        self.assertEqual(len(memory), 2)
        self.assertIsNone(memory.take_match(
            15, [1, 0], now=1.5, min_similarity=0.9, min_margin=0.1
        ))
        self.assertIsNone(memory.take_match(
            15, [0, 1], now=3.2, min_similarity=0.9, min_margin=0.1
        ))
        with self.assertRaisesRegex(ValueError, "backwards"):
            memory.take_match(7, [1, 1], now=3.1,
                              min_similarity=0.9, min_margin=0.1)
        self.assertFalse(memory.remember(4, 7, [1, 0], seen_at=0, now=3.3))

    def test_invalid_descriptors_and_policy_are_rejected(self) -> None:
        """No zero, nonfinite, oversized or shape-incompatible silent match."""
        for descriptor in ([], [0, 0], [float("nan")], [float("inf")],
                           [True], [1] * 257):
            with self.subTest(descriptor=descriptor[:3]):
                with self.assertRaises(ValueError):
                    normalize_descriptor(descriptor)
        memory = RetiredObjectMemory(capacity=1, retention_s=1)
        memory.remember(1, 15, [1, 0], seen_at=0, now=0)
        self.assertIsNone(memory.take_match(
            15, [1, 0, 0], now=0.1, min_similarity=0.9, min_margin=0.1
        ))
        with self.assertRaisesRegex(ValueError, "min_margin"):
            memory.take_match(15, [1, 0], now=0.2,
                              min_similarity=0.9, min_margin=0)


if __name__ == "__main__":
    unittest.main()
