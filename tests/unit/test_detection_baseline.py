from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import numpy as np

import math
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch
import json
from vision.detect_image import parse_detections, timing_summary, run, infer_once


class DetectionBaselineTests(unittest.TestCase):
    def test_maps_normalized_box_to_full_720p_frame(self) -> None:
        """Verify maps normalized box to full 720p frame.

        Args:
            None.

        Returns:
            None: unittest assertions fail if the expected contract is violated.
        """
        result = parse_detections(
            [[0, 15, 0.8, 0.25, 0.25, 0.75, 0.75]], 1280, 720, 0.5
        )
        self.assertEqual(result[0]["label"], "person")
        self.assertEqual(result[0]["box_xyxy"], [320, 180, 960, 540])

    def test_clips_boxes_and_filters_background_low_scores_and_empty_boxes(
        self,
    ) -> None:
        """Verify clips boxes and filters background low scores and empty boxes.

        Args:
            None.

        Returns:
            None: unittest assertions fail if the expected contract is violated.
        """
        # Combine an out-of-bounds valid box with background, low-score and empty
        # boxes; only the clamped valid prediction should survive.
        rows = [
            [0, 5, 0.5, -0.1, -0.2, 1.1, 1.2],
            [0, 0, 0.9, 0, 0, 1, 1],
            [0, 15, 0.49, 0, 0, 1, 1],
            [0, 9, 0.9, 0.8, 0.1, 0.2, 0.9],
            [0, 9, 0.9, 2, 0, 3, 1],
        ]
        self.assertEqual(
            parse_detections(rows, 100, 50, 0.5),
            [
                dict(
                    class_id=5, label="bottle", confidence=0.5, box_xyxy=[0, 0, 100, 50]
                )
            ],
        )

    def test_empty_and_sentinel_detections_are_valid(self) -> None:
        """Verify empty and sentinel detections are valid.

        Args:
            None.

        Returns:
            None: unittest assertions fail if the expected contract is violated.
        """
        self.assertEqual(parse_detections([], 100, 50, 0.5), [])
        self.assertEqual(parse_detections([[-1] * 7], 100, 50, 0.5), [])

    def test_wrong_model_or_invalid_numbers_fail_clearly(self) -> None:
        """Verify wrong model or invalid numbers fail clearly.

        Args:
            None.

        Returns:
            None: unittest assertions fail if the expected contract is violated.
        """
        # Reject wrong row length, invalid model IDs/batches and nonfinite or
        # out-of-range scores instead of silently misinterpreting a different network.
        for row in (
            [0] * 6,
            [0, 99, 0.8, 0, 0, 1, 1],
            [0, 1.5, 0.8, 0, 0, 1, 1],
            [1, 15, 0.8, 0, 0, 1, 1],
            [0, 15, math.nan, 0, 0, 1, 1],
            [0, 15, 1.2, 0, 0, 1, 1],
        ):
            with self.subTest(row=row), self.assertRaises(ValueError):
                parse_detections([row], 100, 50, 0.5)

    def test_nearest_rank_percentile_and_invalid_timings(self) -> None:
        """Verify nearest rank percentile and invalid timings.

        Args:
            None.

        Returns:
            None: unittest assertions fail if the expected contract is violated.
        """
        stats = timing_summary(list(range(1, 21)))
        self.assertEqual(stats["median_ms"], 10.5)
        self.assertEqual(stats["p95_ms"], 19)
        for values in ([], [-1], [math.inf]):
            with self.assertRaises(ValueError):
                timing_summary(values)

    def test_existing_output_is_preserved_before_loading_runtime_or_inputs(
        self,
    ) -> None:
        """Verify existing output is preserved before loading runtime or inputs.

        Args:
            None.

        Returns:
            None: unittest assertions fail if the expected contract is violated.
        """
        # Place a marker in existing output and confirm rejection happens before
        # loading inputs/runtime or disturbing the existing experiment.
        Path("recordings").mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir="recordings") as folder:
            path = Path(folder)
            marker = path / "keep.txt"
            marker.write_text("keep")
            with self.assertRaises(ValueError):
                run(SimpleNamespace(output=path), None)
            self.assertEqual(marker.read_text(), "keep")

    def test_real_opencv_preprocessing_when_available(self) -> None:
        """Verify real opencv preprocessing when available.

        Args:
            None.

        Returns:
            None: unittest assertions fail if the expected contract is violated.
        """
        try:
            import cv2

            import numpy as np
        except ImportError:
            self.skipTest("OpenCV is optional; actual preprocessing awaits its runtime")

        # Use real OpenCV preprocessing with a fake network so no weights are needed.
        class Net:
            def setInput(self, blob: np.ndarray) -> None:
                """Retain the prepared tensor so the test can inspect its shape and values.

                Args:
                    blob (np.ndarray): Synthetic input used by this test double.

                Returns:
                    None: The declared test-double result; only synthetic state is changed.
                """
                self.blob = blob

            def forward(self) -> np.ndarray:
                """Return a synthetic empty SSD output without loading a model.

                Args:
                    None.

                Returns:
                    np.ndarray: The declared test-double result; only synthetic state is changed.
                """
                return np.zeros((1, 1, 0, 7), dtype=np.float32)

        # White grayscale must become three normalized 300×300 channels; the fake
        # network returns a valid empty detection tensor.
        net = Net()
        rows, *_ = infer_once(cv2, net, np.full((720, 1280), 255, dtype=np.uint8))
        self.assertEqual(net.blob.shape, (1, 3, 300, 300))
        np.testing.assert_allclose(net.blob, (255 - 127.5) * 0.007843, atol=1e-6)
        self.assertEqual(len(rows), 0)

    def test_report_excludes_warmups_and_records_model_and_boxes(self) -> None:
        """Verify report excludes warmups and records model and boxes.

        Args:
            None.

        Returns:
            None: unittest assertions fail if the expected contract is violated.
        """
        try:
            import numpy as np
        except ImportError:
            self.skipTest("Synthetic runtime test needs NumPy")

        # Create temporary input/model stand-ins and a deterministic OpenCV double
        # that returns one known prediction without actual inference.
        Path("recordings").mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir="recordings") as folder:
            root = Path(folder)
            fixture = root / "fixture"
            fixture.write_bytes(b"fake input/model for report testing only")
            cv = MagicMock()
            cv.__version__ = "test-double"
            cv.imread.return_value = np.zeros((720, 1280), dtype=np.uint8)
            cv.getNumThreads.return_value = 2
            cv.imwrite.return_value = True
            net = cv.dnn.readNetFromCaffe.return_value
            net.forward.return_value = np.array(
                [[[[0, 15, 0.9, 0.25, 0.25, 0.75, 0.75]]]]
            )
            args = SimpleNamespace(
                output=root / "result",
                image=fixture,
                prototxt=fixture,
                weights=fixture,
                threads=2,
                warmup=3,
                runs=2,
                threshold=0.5,
                notes="synthetic",
            )

            # Run the saved-image tool with environment probes isolated, then verify
            # warm-up exclusion, box mapping, model identity and timing component totals.
            with patch("vision.detect_image.git_info", return_value={}), patch(
                "vision.detect_image.cpu_temperature", return_value=None
            ), patch("builtins.print"):
                run(args, cv)
            report = json.loads((args.output / "report.json").read_text())
            self.assertEqual(net.forward.call_count, 5)
            self.assertEqual(len(report["samples"]), 2)
            self.assertEqual(report["detections"][0]["box_xyxy"], [320, 180, 960, 540])
            self.assertEqual(len(report["model"]["weights_sha256"]), 64)
            for sample in report["samples"]:
                self.assertAlmostEqual(
                    sample["total_ms"],
                    sample["preprocess_ms"]
                    + sample["inference_ms"]
                    + sample["postprocess_ms"],
                )
