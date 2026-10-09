# Postpone type evaluation so optional drivers/libraries stay optional.
from __future__ import annotations

# Describe data contracts without adding third-party runtime dependencies.
from typing import TYPE_CHECKING

# Resolve documentation-only types for editors; this block does not run in production.
if TYPE_CHECKING:
    # Perform typed array and numerical operations; no sensor access occurs on import.
    import numpy as np

# Validate finite numbers and perform scalar numerical calculations.
import math

# Work with explicit filesystem paths rather than shell expansions.
from pathlib import Path

# Create isolated temporary test outputs that are cleaned up afterwards.
import tempfile

# Build lightweight fake runtime objects for unit tests.
from types import SimpleNamespace

# Express hardware-independent behavior as executable checks.
import unittest

# Replace external effects with controlled test fixtures.
from unittest.mock import MagicMock, patch

# Read or serialize metadata and browser/report payloads.
import json

# Reuse vision.detect_image helpers rather than duplicating their behavior here.
from vision.detect_image import parse_detections, timing_summary, run, infer_once


class DetectionBaselineTests(unittest.TestCase):
    def test_maps_normalized_box_to_full_720p_frame(self) -> None:
        """Verify maps normalized box to full 720p frame.

        Args:
            None.

        Returns:
            None: unittest assertions fail if the expected contract is violated.
        """
        # Prepare or exercise parse_detections with the controlled test inputs.
        result = parse_detections(
            [[0, 15, 0.8, 0.25, 0.25, 0.75, 0.75]], 1280, 720, 0.5
        )
        # Check the expected Equal relationship for this case.
        self.assertEqual(result[0]["label"], "person")
        # Check the expected Equal relationship for this case.
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
        # Set up rows for this independent test scenario.
        rows = [
            [0, 5, 0.5, -0.1, -0.2, 1.1, 1.2],
            [0, 0, 0.9, 0, 0, 1, 1],
            [0, 15, 0.49, 0, 0, 1, 1],
            [0, 9, 0.9, 0.8, 0.1, 0.2, 0.9],
            [0, 9, 0.9, 2, 0, 3, 1],
        ]
        # Check the expected Equal relationship for this case.
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
        # Check the expected Equal relationship for this case.
        self.assertEqual(parse_detections([], 100, 50, 0.5), [])
        # Check the expected Equal relationship for this case.
        self.assertEqual(parse_detections([[-1] * 7], 100, 50, 0.5), [])

    def test_wrong_model_or_invalid_numbers_fail_clearly(self) -> None:
        """Verify wrong model or invalid numbers fail clearly.

        Args:
            None.

        Returns:
            None: unittest assertions fail if the expected contract is violated.
        """
        # Exercise each fixture or edge case independently.
        for row in (
            [0] * 6,
            [0, 99, 0.8, 0, 0, 1, 1],
            [0, 1.5, 0.8, 0, 0, 1, 1],
            [1, 15, 0.8, 0, 0, 1, 1],
            [0, 15, math.nan, 0, 0, 1, 1],
            [0, 15, 1.2, 0, 0, 1, 1],
        ):
            # Require this invalid case to fail with the expected exception.
            with self.subTest(row=row), self.assertRaises(ValueError):
                # Call parse_detections for this step; its contract describes the result or side
                # effect.
                parse_detections([row], 100, 50, 0.5)

    def test_nearest_rank_percentile_and_invalid_timings(self) -> None:
        """Verify nearest rank percentile and invalid timings.

        Args:
            None.

        Returns:
            None: unittest assertions fail if the expected contract is violated.
        """
        # Prepare or exercise timing_summary with the controlled test inputs.
        stats = timing_summary(list(range(1, 21)))
        # Check the expected Equal relationship for this case.
        self.assertEqual(stats["median_ms"], 10.5)
        # Check the expected Equal relationship for this case.
        self.assertEqual(stats["p95_ms"], 19)
        # Exercise each fixture or edge case independently.
        for values in ([], [-1], [math.inf]):
            # Require this invalid case to fail with the expected exception.
            with self.assertRaises(ValueError):
                # Call timing_summary for this step; its contract describes the result or side
                # effect.
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
        # Create the explicit output/test directory using the existing overwrite policy.
        Path("recordings").mkdir(exist_ok=True)
        # Keep these resources scoped so they are released even if the operation fails.
        with tempfile.TemporaryDirectory(dir="recordings") as folder:
            # Prepare or exercise Path with the controlled test inputs.
            path = Path(folder)
            # Set up marker for this independent test scenario.
            marker = path / "keep.txt"
            # Persist this explicitly requested local output; raw artifacts stay outside Git.
            marker.write_text("keep")
            # Require this invalid case to fail with the expected exception.
            with self.assertRaises(ValueError):
                # Call run for this step; its contract describes the result or side effect.
                run(SimpleNamespace(output=path), None)
            # Check the expected Equal relationship for this case.
            self.assertEqual(marker.read_text(), "keep")

    def test_real_opencv_preprocessing_when_available(self) -> None:
        """Verify real opencv preprocessing when available.

        Args:
            None.

        Returns:
            None: unittest assertions fail if the expected contract is violated.
        """
        # Keep failure handling alongside the operation so cleanup/status remains explicit.
        try:
            # Load optional OpenCV only for detection or its explicit runtime test.
            import cv2

            # Perform typed array and numerical operations; no sensor access occurs on import.
            import numpy as np
        # Handle this failure without losing the error or skipping the enclosing cleanup.
        except ImportError:
            # Call self.skipTest for this step; its contract describes the result or side
            # effect.
            self.skipTest("OpenCV is optional; actual preprocessing awaits its runtime")

        class Net:
            def setInput(self, blob: np.ndarray) -> None:
                """Retain the prepared tensor so the test can inspect its shape and values.

                Args:
                    blob (np.ndarray): Synthetic input used by this test double.

                Returns:
                    None: The declared test-double result; only synthetic state is changed.
                """
                # Set up self.blob for this independent test scenario.
                self.blob = blob

            def forward(self) -> np.ndarray:
                """Return a synthetic empty SSD output without loading a model.

                Args:
                    None.

                Returns:
                    np.ndarray: The declared test-double result; only synthetic state is changed.
                """
                # Return the documented result to the caller without starting another operation.
                return np.zeros((1, 1, 0, 7), dtype=np.float32)

        # Prepare or exercise Net with the controlled test inputs.
        net = Net()
        # Prepare or exercise infer_once with the controlled test inputs.
        rows, *_ = infer_once(cv2, net, np.full((720, 1280), 255, dtype=np.uint8))
        # Check the expected Equal relationship for this case.
        self.assertEqual(net.blob.shape, (1, 3, 300, 300))
        # Check the expected _allclose relationship for this case.
        np.testing.assert_allclose(net.blob, (255 - 127.5) * 0.007843, atol=1e-6)
        # Check the expected Equal relationship for this case.
        self.assertEqual(len(rows), 0)

    def test_report_excludes_warmups_and_records_model_and_boxes(self) -> None:
        """Verify report excludes warmups and records model and boxes.

        Args:
            None.

        Returns:
            None: unittest assertions fail if the expected contract is violated.
        """
        # Keep failure handling alongside the operation so cleanup/status remains explicit.
        try:
            # Perform typed array and numerical operations; no sensor access occurs on import.
            import numpy as np
        # Handle this failure without losing the error or skipping the enclosing cleanup.
        except ImportError:
            # Call self.skipTest for this step; its contract describes the result or side
            # effect.
            self.skipTest("Synthetic runtime test needs NumPy")
        # Create the explicit output/test directory using the existing overwrite policy.
        Path("recordings").mkdir(exist_ok=True)
        # Keep these resources scoped so they are released even if the operation fails.
        with tempfile.TemporaryDirectory(dir="recordings") as folder:
            # Prepare or exercise Path with the controlled test inputs.
            root = Path(folder)
            # Set up fixture for this independent test scenario.
            fixture = root / "fixture"
            # Persist this explicitly requested local output; raw artifacts stay outside Git.
            fixture.write_bytes(b"fake input/model for report testing only")
            # Prepare or exercise MagicMock with the controlled test inputs.
            cv = MagicMock()
            # Set up cv.__version__ for this independent test scenario.
            cv.__version__ = "test-double"
            # Prepare or exercise np.zeros with the controlled test inputs.
            cv.imread.return_value = np.zeros((720, 1280), dtype=np.uint8)
            # Set up cv.getNumThreads.return_value for this independent test scenario.
            cv.getNumThreads.return_value = 2
            # Set up cv.imwrite.return_value for this independent test scenario.
            cv.imwrite.return_value = True
            # Set up net for this independent test scenario.
            net = cv.dnn.readNetFromCaffe.return_value
            # Prepare or exercise np.array with the controlled test inputs.
            net.forward.return_value = np.array(
                [[[[0, 15, 0.9, 0.25, 0.25, 0.75, 0.75]]]]
            )
            # Prepare or exercise SimpleNamespace with the controlled test inputs.
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
            # Replace external effects only within this controlled test scope.
            with patch("vision.detect_image.git_info", return_value={}), patch(
                "vision.detect_image.cpu_temperature", return_value=None
            ), patch("builtins.print"):
                # Call run for this step; its contract describes the result or side effect.
                run(args, cv)
            # Prepare or exercise json.loads with the controlled test inputs.
            report = json.loads((args.output / "report.json").read_text())
            # Check the expected Equal relationship for this case.
            self.assertEqual(net.forward.call_count, 5)
            # Check the expected Equal relationship for this case.
            self.assertEqual(len(report["samples"]), 2)
            # Check the expected Equal relationship for this case.
            self.assertEqual(report["detections"][0]["box_xyxy"], [320, 180, 960, 540])
            # Check the expected Equal relationship for this case.
            self.assertEqual(len(report["model"]["weights_sha256"]), 64)
            # Exercise each fixture or edge case independently.
            for sample in report["samples"]:
                # Check the expected AlmostEqual relationship for this case.
                self.assertAlmostEqual(
                    sample["total_ms"],
                    sample["preprocess_ms"]
                    + sample["inference_ms"]
                    + sample["postprocess_ms"],
                )
