"""Check reconstruction against known synthetic geometry and degeneracy."""

import unittest
import json
import tempfile
from pathlib import Path
from unittest.mock import patch
import numpy as np
import cv2 as cv
from spatial.sparse_reconstruction import reconstruct, run


class SparseReconstructionTests(unittest.TestCase):
    """Use a nonplanar scene with known translation and fixed camera intrinsics."""

    def test_rejected_pair_saves_evidence_and_refuses_overwrite(self) -> None:
        """Exercise descriptor matching, rejection reports and output ownership.

        Args: None.
        Returns: None.
        """
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            video, calibration, output = root / "video.mkv", root / "calibration.json", root / "result"
            video.touch()
            calibration.write_text(json.dumps({"camera_matrix": [[733, 0, 670], [0, 733, 331], [0, 0, 1]],
                "distortion_coefficients": [0] * 5, "image_size_wh": [1280, 720], "status": "needs_review"}))
            gray = np.random.default_rng(5).integers(0, 256, (720, 1280), dtype=np.uint8)
            with patch("spatial.sparse_reconstruction.extract_frame", return_value=gray):
                report = run(video, calibration, output, 5, 15)
            self.assertEqual(report["status"], "rejected")
            self.assertGreater(report["descriptor_matches"], 30)
            self.assertTrue((output / "report.json").is_file())
            self.assertTrue((output / "view-1.png").is_file())
            self.assertFalse((output / "points.ply").exists())
            with self.assertRaises(FileExistsError):
                run(video, calibration, output, 5, 15)

    def test_recovers_translated_scene(self) -> None:
        """Recover known points up to the normalized baseline.

        Args: None.
        Returns: None.
        """
        rng = np.random.default_rng(17)
        points = rng.uniform([-1, -0.6, 3], [1, 0.6, 7], (180, 3))
        matrix = np.array([[733., 0, 670], [0, 733, 331], [0, 0, 1]])
        distortion = np.array([0.08, -0.06, 0.0005, -0.0002, -0.07])
        a, _ = cv.projectPoints(points, np.zeros(3), np.zeros(3), matrix, distortion)
        b, _ = cv.projectPoints(points, np.zeros(3), np.array([-0.3, 0., 0.]), matrix, distortion)
        cloud, report = reconstruct(a.reshape(-1, 2), b.reshape(-1, 2), matrix, distortion)
        self.assertEqual(report["status"], "candidate_needs_review")
        self.assertEqual(len(cloud), len(points))
        np.testing.assert_allclose(cloud, points / 0.3, atol=0.01)
        np.testing.assert_allclose(report["camera_2_center"], [1, 0, 0], atol=0.001)

    def test_rejects_background_only_support(self) -> None:
        """A scene with all features above the optical center lacks broad coverage.

        Args: None.
        Returns: None.
        """
        rng = np.random.default_rng(23)
        points = rng.uniform([-1, -1.5, 3], [1, -0.7, 7], (180, 3))
        matrix = np.array([[733., 0, 670], [0, 733, 331], [0, 0, 1]])
        a, _ = cv.projectPoints(points, np.zeros(3), np.zeros(3), matrix, None)
        b, _ = cv.projectPoints(points, np.zeros(3), np.array([-0.3, 0., 0.]), matrix, None)
        _, report = reconstruct(a.reshape(-1, 2), b.reshape(-1, 2), matrix, np.zeros(5))
        self.assertEqual(report["status"], "rejected")
        self.assertEqual(report["reason"], "Insufficient vertical point coverage in the scene")

    def test_identical_views_do_not_make_a_cloud(self) -> None:
        """A stationary pair must not become an accepted 3D map.

        Args: None.
        Returns: None.
        """
        rng = np.random.default_rng(12)
        pixels = rng.uniform([100, 100], [1100, 600], (100, 2))
        matrix = np.array([[733., 0, 670], [0, 733, 331], [0, 0, 1]])
        try:
            _, report = reconstruct(pixels, pixels, matrix, np.zeros(5))
        except ValueError:
            return
        self.assertEqual(report["status"], "rejected")

    def test_rejects_pure_rotation(self) -> None:
        """Changing view direction without translation cannot establish depth.

        Args: None.
        Returns: None.
        """
        rng = np.random.default_rng(13)
        points = rng.uniform([-1, -1, 3], [1, 1, 7], (120, 3))
        matrix = np.array([[733., 0, 670], [0, 733, 331], [0, 0, 1]])
        a, _ = cv.projectPoints(points, np.zeros(3), np.zeros(3), matrix, None)
        b, _ = cv.projectPoints(points, np.array([0., 0.1, 0.]), np.zeros(3), matrix, None)
        try:
            _, report = reconstruct(a.reshape(-1, 2), b.reshape(-1, 2), matrix, np.zeros(5))
        except ValueError:
            return
        self.assertEqual(report["status"], "rejected")

    def test_rejects_bad_correspondences(self) -> None:
        """Reject insufficient, mismatched or nonfinite input coordinates.

        Args: None.
        Returns: None.
        """
        for a, b in [(np.zeros((10, 2)), np.zeros((10, 2))),
                     (np.zeros((30, 2)), np.zeros((31, 2))),
                     (np.full((30, 2), np.nan), np.zeros((30, 2)))]:
            with self.assertRaises(ValueError):
                reconstruct(a, b, np.eye(3), np.zeros(5))


if __name__ == "__main__":
    unittest.main()
