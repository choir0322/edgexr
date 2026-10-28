"""Offline scene replay input integrity and a small real video round trip."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import numpy as np

from spatial.scene_revisit import parse_events, run

try:
    import cv2 as cv
except ImportError:
    cv = None


class SceneReplayTests(unittest.TestCase):
    def test_event_order_never_teaches_future_views_early(self) -> None:
        """Earlier queries remain earlier than a later reference enrollment.

        Args:
            None.
        Returns:
            None: Timeline ordering and invalid-time checks are asserted.
        """
        events = parse_events(["A=2", "B=6"], [7, 1, 4])
        self.assertEqual([event["requested_s"] for event in events], [1, 2, 4, 6, 7])
        for references, queries in [(["A=2"], [2]), (["A=nan"], [3]),
                                    (["A=0", "A=1"], [3]), (["A=0"], [-1])]:
            with self.assertRaises(ValueError):
                parse_events(references, queries)

    def test_existing_output_is_preserved(self) -> None:
        """No runtime import or output overwrite occurs when the folder exists.

        Args:
            None.
        Returns:
            None: An unrelated marker remains unchanged.
        """
        with TemporaryDirectory() as directory:
            output = Path(directory)
            marker = output / "keep.txt"
            marker.write_text("keep")
            with self.assertRaises(ValueError):
                run(argparse.Namespace(output=output))
            self.assertEqual(marker.read_text(), "keep")

    @unittest.skipIf(cv is None, "OpenCV required for real local-video replay")
    def test_video_aba_and_partial_output(self) -> None:
        """Decode a synthetic A/B/A clip and preserve diagnostics for an EOF request.

        Args:
            None.
        Returns:
            None: Known/unknown decisions and partial-report status are checked.
        """
        Path("recordings").mkdir(exist_ok=True)
        with TemporaryDirectory(dir="recordings") as directory:
            folder = Path(directory)
            rng = np.random.default_rng(42)
            a = cv.GaussianBlur(rng.integers(0, 256, (360, 640), dtype=np.uint8), (3, 3), 0)
            b = cv.GaussianBlur(rng.integers(0, 256, (360, 640), dtype=np.uint8), (3, 3), 0)
            video = folder / "test.avi"
            writer = cv.VideoWriter(str(video), cv.VideoWriter_fourcc(*"MJPG"), 10, (640, 360))
            self.assertTrue(writer.isOpened())
            for index in range(10):
                writer.write(cv.cvtColor(b if 4 <= index < 7 else a, cv.COLOR_GRAY2BGR))
            writer.release()
            args = argparse.Namespace(video=video, reference=["A=0"], query=[0.4, 0.8],
                                      max_views=12, output=folder / "complete")
            report = run(args, cv)
            self.assertEqual(report["status"], "complete")
            self.assertEqual([row["decision"]["state"] for row in report["events"]],
                             ["enrolled", "unknown", "known"])
            self.assertTrue((args.output / "event-003.png").is_file())
            args.output = folder / "partial"
            args.query = [5.0]
            report = run(args, cv)
            self.assertEqual(report["status"], "partial")
            saved = json.loads((args.output / "report.json").read_text())
            self.assertIsNotNone(saved["error"])


if __name__ == "__main__":
    unittest.main()
