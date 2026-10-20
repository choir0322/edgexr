"""Hardware-free checks for an opt-in, image-containing re-ID trial directory."""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import numpy as np

from vision.reid_trial import ReidTrialRecorder


class FakeCv:
    """Return known PNG-shaped bytes without loading OpenCV or a camera."""

    IMWRITE_PNG_COMPRESSION = 1

    def imencode(self, suffix: str, gray: np.ndarray, options: list[int]):
        """Confirm the recorder passes the exact grayscale input dimensions."""
        assert suffix == ".png" and gray.shape == (2, 2) and options == [1, 3]
        return True, np.frombuffer(b"PNG", dtype=np.uint8)


class ReidTrialTests(unittest.TestCase):
    def test_records_exact_detector_update_and_refuses_overwrite(self) -> None:
        """One image and one decision line share a frame sequence without raw descriptors."""
        with TemporaryDirectory() as temporary:
            output = Path(temporary) / "trial"
            recorder = ReidTrialRecorder(output, 20, "person and bottle", FakeCv(),
                                         width=2, height=2)
            with self.assertRaises(FileExistsError):
                ReidTrialRecorder(output, 20, "", FakeCv(), width=2, height=2)
            recorder.record((7, 10.1, bytes([1, 2, 3, 4])),
                            [{"class_id": 15, "track_id": 2, "box_xyxy": [0, 0, 2, 2]}],
                            {"reid_last_by_class": {"15": {"reason": "below_threshold"}}},
                            10.4)
            recorder.close("complete")
            recorder.close("partial")
            self.assertEqual((output / "detector-frames/frame-00000007.png").read_bytes(), b"PNG")
            row = json.loads((output / "updates.jsonl").read_text().strip())
            self.assertEqual(row["sequence"], 7)
            self.assertEqual(row["boxes"][0]["track_id"], 2)
            self.assertEqual(row["tracking_stats"]["reid_last_by_class"]["15"]["reason"],
                             "below_threshold")
            metadata = json.loads((output / "metadata.json").read_text())
            self.assertEqual(metadata["status"], "complete")
            self.assertEqual(metadata["saved_detector_updates"], 1)

    def test_rejects_incomplete_source_frame(self) -> None:
        """An invalid source cannot create a misleading frame/decision pair."""
        with TemporaryDirectory() as temporary:
            output = Path(temporary) / "trial"
            recorder = ReidTrialRecorder(output, 5, "", FakeCv(), width=2, height=2)
            with self.assertRaisesRegex(ValueError, "complete grayscale"):
                recorder.record((1, 0.0, b"x"), [], {}, 0.1)
            recorder.close("partial")
            self.assertEqual((output / "updates.jsonl").read_text(), "")


if __name__ == "__main__":
    unittest.main()
