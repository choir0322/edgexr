"""Hardware-free checks for the first, deliberately modest box tracker."""

from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from _contracts import Record

import unittest

from vision.basic_tracker import BasicTracker, box_iou


def detection(class_id: int, box: list[int]) -> Record:
    """Make one minimal box record in source-image pixel coordinates.

    Args:
        class_id (int): Detector category identity.
        box (list[int]): Left, top, right, bottom pixel coordinates.

    Returns:
        Record: A detector-shaped dictionary for a synthetic update.
    """
    return {"class_id": class_id, "label": f"class-{class_id}", "box_xyxy": box}


def shift_right(start: float, end: float) -> tuple[float, float]:
    """Supply a known rightward scene shift for a synthetic interval.

    Args:
        start (float): Old source receipt time, unused in this fixed fixture.
        end (float): New source receipt time, unused in this fixed fixture.

    Returns:
        tuple[float, float]: Source-pixel dx/dy.
    """
    return (200.0, 0.0)


def shift_left(start: float, end: float) -> tuple[float, float]:
    """Supply a known leftward scene shift for a synthetic interval.

    Args:
        start (float): Old source receipt time, unused in this fixed fixture.
        end (float): New source receipt time, unused in this fixed fixture.

    Returns:
        tuple[float, float]: Source-pixel dx/dy.
    """
    return (-200.0, 0.0)


def shift_missing(start: float, end: float) -> None:
    """Represent an interval with no reliable image-motion estimate.

    Args:
        start (float): Old source receipt time, unused in this fixed fixture.
        end (float): New source receipt time, unused in this fixed fixture.

    Returns:
        None: Unknown shift, not a measured zero.
    """
    return None


def shift_zero(start: float, end: float) -> tuple[float, float]:
    """Supply measured zero displacement after the old track has retired.

    Args:
        start (float): Old source receipt time, unused in this fixed fixture.
        end (float): New source receipt time, unused in this fixed fixture.

    Returns:
        tuple[float, float]: Zero source-pixel dx/dy.
    """
    return (0.0, 0.0)


def shift_implausible(start: float, end: float) -> tuple[float, float]:
    """Supply a shift beyond the tracker's source-width safety bound.

    Args:
        start (float): Old source receipt time, unused in this fixed fixture.
        end (float): New source receipt time, unused in this fixed fixture.

    Returns:
        tuple[float, float]: An intentionally implausible source-pixel shift.
    """
    return (1000.0, 0.0)


class BasicTrackerTests(unittest.TestCase):
    def test_motion_prediction_holds_an_id_that_raw_overlap_would_lose(self) -> None:
        """Use source-pixel scene shift; changing direction changes the sign.

        Args:
            None.

        Returns:
            None: Assertions check ID continuity in both directions.
        """
        tracker = BasicTracker()
        tracker.update([detection(15, [100, 0, 200, 100])], 1.0)
        moved = tracker.update(
            [detection(15, [300, 0, 400, 100])], 1.5,
            shift_right,
        )
        self.assertEqual(moved[0]["track_id"], 1)
        self.assertEqual(tracker.last_stats["motion_only_matches"], 1)
        returned = tracker.update(
            [detection(15, [100, 0, 200, 100])], 2.0,
            shift_left,
        )
        self.assertEqual(returned[0]["track_id"], 1)

    def test_raw_overlap_remains_available_for_independent_object_motion(self) -> None:
        """A stationary person's box keeps its ID despite moving background.

        Args:
            None.

        Returns:
            None: Assertions check the raw-overlap path.
        """
        tracker = BasicTracker()
        tracker.update([detection(15, [100, 0, 200, 100])], 1.0)
        result = tracker.update(
            [detection(15, [101, 0, 201, 100])], 1.5,
            shift_right,
        )
        self.assertEqual(result[0]["track_id"], 1)
        self.assertEqual(tracker.last_stats["motion_only_matches"], 0)

    def test_unknown_motion_miss_and_retirement_keep_baseline_rules(self) -> None:
        """Fallback, one missed result and two missed results remain distinct.

        Args:
            None.

        Returns:
            None: Assertions check fallback, survival and retirement.
        """
        tracker = BasicTracker()
        tracker.update([detection(15, [100, 0, 200, 100])], 1.0)
        tracker.update([], 1.5, shift_missing)
        self.assertEqual(tracker.last_stats["fallback_tracks"], 1)
        self.assertEqual(
            tracker.update([detection(15, [300, 0, 400, 100])], 2.0,
                           shift_right)[0]["track_id"], 1
        )
        tracker.update([], 2.5)
        tracker.update([], 3.0)
        self.assertEqual(
            tracker.update([detection(15, [300, 0, 400, 100])], 3.5,
                           shift_zero)[0]["track_id"], 2
        )

    def test_implausible_prediction_and_competing_boxes(self) -> None:
        """Reject enormous motion and never assign one old ID to two boxes.

        Args:
            None.

        Returns:
            None: Assertions check safety and one-to-one claims.
        """
        tracker = BasicTracker()
        tracker.update([detection(15, [100, 0, 200, 100])], 1.0)
        first = tracker.update([detection(15, [100, 0, 200, 100])], 1.5,
                               shift_implausible)
        self.assertEqual(first[0]["track_id"], 1)
        self.assertEqual(tracker.last_stats["fallback_tracks"], 1)
        contenders = tracker.update(
            [detection(15, [300, 0, 400, 100]), detection(15, [305, 0, 405, 100])],
            2.0, shift_right,
        )
        self.assertEqual([box["track_id"] for box in contenders], [1, 2])

    def test_learning_page_examples_match_real_tracker(self) -> None:
        """Verify the page's competition and miss fixtures use real algorithm IDs.

        Args:
            None.

        Returns:
            None: Assertions fail if the page's expected sequence drifts.
        """
        # The page draws illustrative boxes on the user's saved scene. Check
        # their exact order and geometry through the real Python implementation.
        competition = BasicTracker()
        first = competition.update(
            [
                detection(9, [690, 320, 1000, 570]),
                detection(11, [100, 500, 1250, 720]),
            ]
        )
        second = competition.update(
            [
                detection(9, [700, 325, 1010, 575]),
                detection(9, [755, 330, 1065, 580]),
                detection(11, [100, 505, 1250, 720]),
            ]
        )
        self.assertEqual([item["track_id"] for item in first], [1, 2])
        self.assertEqual([item["track_id"] for item in second], [1, 3, 2])

        missing = BasicTracker()
        ids = []
        for boxes in (
            [detection(9, [690, 320, 1000, 570])],
            [],
            [detection(9, [700, 325, 1010, 575])],
            [],
            [],
            [detection(9, [700, 325, 1010, 575])],
        ):
            ids.append([item["track_id"] for item in missing.update(boxes)])
        self.assertEqual(ids, [[1], [], [1], [], [], [2]])

    def test_iou_geometry_and_stable_id_without_input_mutation(self) -> None:
        """Verify overlap arithmetic and an ID retained across a modest box shift.

        Args:
            None.

        Returns:
            None: Assertions fail if geometry, matching or copying is wrong.
        """
        self.assertAlmostEqual(box_iou((0, 0, 10, 10), (5, 0, 15, 10)), 1 / 3)
        self.assertEqual(box_iou((0, 0, 10, 10), (10, 0, 20, 10)), 0)
        tracker = BasicTracker()
        first = detection(15, [0, 0, 100, 100])
        self.assertEqual(tracker.update([first])[0]["track_id"], 1)
        self.assertNotIn("track_id", first)
        self.assertEqual(
            tracker.update([detection(15, [10, 0, 110, 100])])[0]["track_id"], 1
        )

    def test_class_separation_and_one_to_one_competing_matches(self) -> None:
        """Verify category boundaries and unique assignments for competing boxes.

        Args:
            None.

        Returns:
            None: Assertions fail if IDs cross categories or duplicate.
        """
        tracker = BasicTracker()
        first = tracker.update(
            [detection(15, [0, 0, 100, 100]), detection(9, [200, 0, 300, 100])]
        )
        self.assertEqual([item["track_id"] for item in first], [1, 2])
        second = tracker.update(
            [
                detection(15, [5, 0, 105, 100]),
                detection(15, [10, 0, 110, 100]),
                detection(9, [205, 0, 305, 100]),
            ]
        )
        self.assertEqual([item["track_id"] for item in second], [1, 3, 2])
        self.assertEqual(
            tracker.update([detection(9, [5, 0, 105, 100])])[0]["track_id"], 4
        )

    def test_deterministic_tie_and_output_order(self) -> None:
        """Verify that equal-overlap contenders prefer the older track ID.

        Args:
            None.

        Returns:
            None: Assertions fail if association is non-deterministic.
        """
        tracker = BasicTracker()
        tracker.update([detection(15, [0, 0, 100, 100]), detection(15, [0, 0, 100, 100])])
        result = tracker.update([detection(15, [0, 0, 100, 100])])
        self.assertEqual([item["track_id"] for item in result], [1])

    def test_empty_updates_hide_boxes_and_expire_without_reusing_ids(self) -> None:
        """Verify a one-update miss can recover and a second miss retires the ID.

        Args:
            None.

        Returns:
            None: Assertions fail if expiry or re-entry identity is wrong.
        """
        tracker = BasicTracker(max_missed=2)
        self.assertEqual(tracker.update([detection(15, [0, 0, 100, 100])])[0]["track_id"], 1)
        self.assertEqual(tracker.update([]), [])
        self.assertEqual(
            tracker.update([detection(15, [0, 0, 100, 100])])[0]["track_id"], 1
        )
        self.assertEqual(tracker.update([]), [])
        self.assertEqual(tracker.update([]), [])
        self.assertEqual(
            tracker.update([detection(15, [0, 0, 100, 100])])[0]["track_id"], 2
        )

    def test_large_camera_shift_causes_new_id_not_false_certainty(self) -> None:
        """Verify an IoU-only tracker cannot bridge a non-overlapping camera turn.

        Args:
            None.

        Returns:
            None: Assertions fail if a distant box inherits the prior ID.
        """
        tracker = BasicTracker()
        tracker.update([detection(15, [0, 0, 100, 100])])
        self.assertEqual(
            tracker.update([detection(15, [300, 0, 400, 100])])[0]["track_id"], 2
        )

    def test_invalid_update_is_rejected_without_changing_tracks(self) -> None:
        """Verify malformed geometry cannot partially age a valid prior track.

        Args:
            None.

        Returns:
            None: Assertions fail if bad input mutates tracker state.
        """
        tracker = BasicTracker(max_missed=1)
        tracker.update([detection(15, [0, 0, 100, 100])])
        with self.assertRaises(ValueError):
            tracker.update([detection(15, [0, 0, 100, 100]), detection(9, [1, 1, 1, 5])])
        self.assertEqual(
            tracker.update([detection(15, [0, 0, 100, 100])])[0]["track_id"], 1
        )

    def test_configuration_requires_finite_threshold_and_positive_lifetime(self) -> None:
        """Verify thresholds reject nonsensical values before tracking starts.

        Args:
            None.

        Returns:
            None: Assertions fail if invalid configuration is accepted.
        """
        for threshold in (0, float("nan"), 1.1):
            with self.subTest(threshold=threshold), self.assertRaises(ValueError):
                BasicTracker(min_iou=threshold)
        with self.assertRaises(ValueError):
            BasicTracker(max_missed=0)
