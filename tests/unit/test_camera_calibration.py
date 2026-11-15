"""Hardware-free calibration geometry and error-handling checks."""

import math
from pathlib import Path
import tempfile
import unittest
import numpy as np

try:
    import cv2 as cv
except ImportError:
    cv = None


@unittest.skipIf(cv is None, "OpenCV required")
class CameraCalibrationTests(unittest.TestCase):
    def test_known_camera_from_distinct_board_poses(self) -> None:
        """Recover a synthetic focal length and keep fixed-intrinsics held-out views.

        Args: None.
        Returns: None.
        """
        from spatial.camera_calibration import board_points, fit_observations
        camera = np.array([[820., 0., 640.], [0., 810., 360.], [0., 0., 1.]])
        records = []
        for i in range(20):
            rotation = np.array([0.20 * math.sin(i), 0.23 * math.cos(i * .7), 0.03 * i])
            translation = np.array([-4 + (i % 5) * 1.2, -2.5 + (i % 4), 13. + (i % 3)])
            corners, _ = cv.projectPoints(board_points(), rotation, translation, camera, None)
            records.append({"sample_index": i, "time_s": i * 2., "corners": corners})
        report = fit_observations(records, (1280, 720))
        self.assertEqual(len(report["training_views"]), 16)
        self.assertEqual(len(report["heldout_views"]), 4)
        self.assertAlmostEqual(report["camera_matrix"][0][0], 820., delta=2.)
        self.assertLess(max(item["rms_px"] for item in report["heldout_views"]), .01)
        self.assertEqual(report["status"], "needs_review")

    def test_no_overwrite_and_too_few_views(self) -> None:
        """Reject insufficient evidence and preserve existing reports.

        Args: None.
        Returns: None.
        """
        from spatial.camera_calibration import analyze_video, fit_observations
        with self.assertRaisesRegex(ValueError, "at least 15"):
            fit_observations([], (1280, 720))
        with tempfile.TemporaryDirectory() as folder:
            video = Path(folder) / "source.mkv"
            output = Path(folder) / "result.json"
            video.touch()
            output.write_text("keep", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "already exists"):
                analyze_video(video, output, 2.)
            self.assertEqual(output.read_text(encoding="utf-8"), "keep")


if __name__ == "__main__":
    unittest.main()
