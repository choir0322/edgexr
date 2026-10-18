"""Check offline explanations against the unchanged motion-estimator decisions."""

from __future__ import annotations

import unittest
from pathlib import Path

try:
    import numpy as np
except ImportError:
    np = None

if np is not None:
    from recording.patch_diagnostics import diagnose_pair, recording_name_for_video
    from recording.visual_motion import (
        PATCH_HEIGHT,
        PATCH_WIDTH,
        PATCH_ORIGINS,
        image_shift,
        patch_shift,
    )


@unittest.skipIf(np is None, "Optional NumPy required for patch diagnostics")
class PatchDiagnosticTests(unittest.TestCase):
    def test_video_name_works_for_original_and_copied_recordings(self) -> None:
        """The servo run's camera.mkv keeps its recording-directory identity."""
        self.assertEqual(recording_name_for_video(Path("recordings/run-01/camera.mkv")), "run-01")
        self.assertEqual(recording_name_for_video(Path("recordings/run-01.mkv")), "run-01")

    def test_patch_check_reasons_and_original_returns(self) -> None:
        """Detail records distinguish texture, weak peak and over-limit shifts."""
        rng = np.random.default_rng(7)
        textured = rng.normal(120, 30, (56, 80))
        cases = (
            (np.zeros((56, 80)), np.zeros((56, 80)), "low_texture"),
            (textured, rng.normal(120, 30, (56, 80)), "weak_peak"),
            (textured, np.roll(textured, 25, axis=1), "large_horizontal_shift"),
        )
        for first, second, expected in cases:
            with self.subTest(expected=expected):
                detail = {}
                self.assertIsNone(patch_shift(first, second, diagnostics=detail))
                self.assertIsNone(patch_shift(first, second))
                self.assertIn(expected, detail["failed_checks"])
                self.assertFalse(detail["accepted"])

        detail = {}
        original = patch_shift(textured, np.roll(textured, 3, axis=1))
        explained = patch_shift(textured, np.roll(textured, 3, axis=1), diagnostics=detail)
        self.assertEqual(original, explained)
        self.assertTrue(detail["accepted"])
        self.assertEqual(detail["failed_checks"], [])

    def test_pair_reports_insufficient_valid_patches(self) -> None:
        """A flat image has nine texture failures, not a fabricated zero shift."""
        first = np.zeros((180, 320), dtype=np.uint8)
        result = diagnose_pair(first, first)
        self.assertIsNone(image_shift(first, first))
        self.assertEqual(result["pair_status"], "too_few_valid_patches")
        self.assertEqual(result["valid_patches"], 0)
        self.assertEqual(len(result["patches"]), 9)

    def test_pair_reports_disagreement_and_matches_acceptance(self) -> None:
        """Three groups of competing shifts cannot create four agreeing patches."""
        rng = np.random.default_rng(29)
        first = np.zeros((180, 320), dtype=np.uint8)
        second = np.zeros_like(first)
        for patch_index, (x, y) in enumerate(PATCH_ORIGINS):
            region = rng.integers(20, 230, (PATCH_HEIGHT, PATCH_WIDTH), dtype=np.uint8)
            first[y : y + PATCH_HEIGHT, x : x + PATCH_WIDTH] = region
            second[y : y + PATCH_HEIGHT, x : x + PATCH_WIDTH] = np.roll(
                region, (patch_index // 3) * 4, axis=1
            )
        result = diagnose_pair(first, second)
        self.assertIsNone(image_shift(first, second))
        self.assertEqual(result["pair_status"], "patches_disagree")
        self.assertEqual(result["valid_patches"], 9)
        self.assertLess(result["agreeing_patches"], 4)

        accepted = diagnose_pair(first, first)
        self.assertIsNotNone(image_shift(first, first))
        self.assertEqual(accepted["pair_status"], "accepted")
