"""Regression checks for bounded appearance learning and repeated returns."""

import unittest

from vision.basic_tracker import BasicTracker
from vision.object_memory import RetiredObjectMemory


def detection(height: float = 100, confidence: float = 0.9) -> dict:
    """Make one person box for a controlled appearance sequence.

    Args:
        height (float): Source box height in pixels.
        confidence (float): Detector score, independent of appearance similarity.

    Returns:
        dict: Detector-shaped input without an assigned ID.
    """
    return {"class_id": 15, "label": "person", "confidence": confidence,
            "box_xyxy": [0, 0, 100, height]}


class GalleryTests(unittest.TestCase):
    def test_retry_restores_only_after_a_better_followup_view(self) -> None:
        """A poor first return stays provisional until a later clear crop passes.

        Args:
            None.
        Returns:
            None: Asserts visible pending state and one-time old-ID claim.
        """
        tracker = BasicTracker(
            reid_memory=RetiredObjectMemory(capacity=3, retention_s=10),
            reid_retry_seconds=2,
        )
        tracker.update([detection()], 0, descriptors=[[1, 0]])
        tracker.update([], 1)
        tracker.update([], 2)
        first = tracker.update([detection()], 3, descriptors=[[0, 1]])
        self.assertEqual(first[0]["track_id"], 2)
        self.assertEqual(first[0]["identity_status"], "provisional")
        second = tracker.update([detection()], 3.5, descriptors=[[1, 0]])
        self.assertEqual(second[0]["track_id"], 1)
        self.assertEqual(second[0]["match_source"], "appearance_retry")
        self.assertEqual(tracker.last_stats["reid_retry_restores"], 1)
        self.assertEqual(len(tracker.reid_memory), 0)

    def test_retry_expires_and_ambiguous_crowd_does_not_claim(self) -> None:
        """A tentative ID becomes new after its deadline; crowded returns abstain.

        Args:
            None.
        Returns:
            None: Asserts no delayed or competing old-ID claim.
        """
        memory = RetiredObjectMemory(capacity=3, retention_s=10)
        tracker = BasicTracker(reid_memory=memory, reid_retry_seconds=1)
        tracker.update([detection()], 0, descriptors=[[1, 0]])
        tracker.update([], 1)
        tracker.update([], 2)
        tracker.update([detection()], 3, descriptors=[[0, 1]])
        expired = tracker.update([detection()], 4.1, descriptors=[[1, 0]])
        self.assertEqual(expired[0]["track_id"], 2)
        self.assertNotIn("identity_status", expired[0])
        self.assertEqual(len(memory), 1)

        crowd = BasicTracker(reid_memory=RetiredObjectMemory(capacity=3, retention_s=10),
                             reid_retry_seconds=2)
        crowd.reid_memory.remember(7, 15, [1, 0], seen_at=0, now=0)
        boxes = [detection(), {**detection(), "box_xyxy": [200, 0, 300, 100]}]
        result = crowd.update(boxes, 1, descriptors=[[0, 1], [0, 1]])
        self.assertTrue(all("identity_status" not in box for box in result))
        self.assertEqual(len(crowd.reid_memory), 1)

    def test_disappearing_provisional_id_does_not_enter_memory(self) -> None:
        """A brief poor return cannot create a second retired identity.

        Args:
            None.
        Returns:
            None: Keeps only the original old ID after a provisional exit.
        """
        memory = RetiredObjectMemory(capacity=3, retention_s=10)
        tracker = BasicTracker(reid_memory=memory, reid_retry_seconds=2)
        tracker.update([detection()], 0, descriptors=[[1, 0]])
        tracker.update([], 1)
        tracker.update([], 2)
        tracker.update([detection()], 3, descriptors=[[0, 1]])
        tracker.update([], 3.25)
        tracker.update([], 3.5)
        self.assertEqual(len(memory), 1)
        self.assertEqual(tracker.last_stats["reid_last_event"]["reason"], "retry_disappeared")

    def test_spatial_support_breaks_only_a_close_appearance_tie(self) -> None:
        """Reliable camera shift ranks strong candidates but never rescues weak ones.

        Args:
            None.
        Returns:
            None: Asserts opt-in spatial coverage, positive ranking and abstention.
        """
        def make_memory() -> RetiredObjectMemory:
            """Create two same-class candidates with nearby appearance scores.

            Args:
                None.
            Returns:
                RetiredObjectMemory: Distinct old source positions.
            """
            memory = RetiredObjectMemory(capacity=3, retention_s=10)
            memory.remember(7, 15, [0.99, 0.141067], seen_at=0, now=0,
                            box=[0, 0, 100, 100])
            memory.remember(8, 15, [0.955, 0.2966], seen_at=0, now=0,
                            box=[600, 0, 700, 100])
            return memory

        plain = BasicTracker(reid_memory=make_memory())
        plain_result = plain.update([detection()], 1, descriptors=[[1, 0]])
        self.assertNotIn("match_source", plain_result[0])
        spatial = BasicTracker(reid_memory=make_memory(), reid_spatial=True)
        result = spatial.update([detection()], 1, lambda start, end: (0, 0),
                                descriptors=[[1, 0]])
        self.assertEqual(result[0]["track_id"], 7)
        self.assertEqual(spatial.last_stats["reid_last_event"]["spatial_covered_candidates"], 2)
        self.assertEqual(spatial.last_stats["reid_last_event"]["spatial_supported_candidates"], 1)
        weak = BasicTracker(reid_memory=make_memory(), reid_spatial=True)
        self.assertNotIn("match_source", weak.update(
            [detection()], 1, lambda start, end: (0, 0), descriptors=[[0, 1]])[0])

    def test_degraded_exit_and_repeated_return_preserve_good_views(self) -> None:
        """A partial final crop cannot erase either of two earlier appearances.

        Args:
            None.
        Returns:
            None: Asserts continuity across two exits and returns.
        """
        tracker = BasicTracker(reid_memory=RetiredObjectMemory(capacity=3, retention_s=10))
        tracker.update([detection()], 0, descriptors=[[1, 0, 0]])
        tracker.update([detection()], 1, descriptors=[[0, 1, 0]])
        tracker.update([detection(50)], 2, descriptors=[[0, 0, 1]])
        self.assertEqual(tracker.last_stats["reid_gallery_updates"], {"shrunken_crop": 1})
        tracker.update([], 3)
        tracker.update([], 4)
        first = tracker.update([detection()], 5, descriptors=[[1, 0, 0]])
        self.assertEqual(first[0]["track_id"], 1)
        self.assertEqual(first[0]["match_source"], "appearance")
        tracker.update([], 6)
        tracker.update([], 7)
        second = tracker.update([detection()], 8, descriptors=[[0, 1, 0]])
        self.assertEqual(second[0]["track_id"], 1)
        self.assertEqual(second[0]["match_source"], "appearance")

    def test_multiple_views_compete_as_one_id_but_lookalike_ids_abstain(self) -> None:
        """Runner-up ambiguity is between identities, never two views of one ID.

        Args:
            None.
        Returns:
            None: Asserts same-ID views and competing identities are distinct.
        """
        memory = RetiredObjectMemory(capacity=3, retention_s=10)
        memory.remember(1, 15, [1, 0], gallery=[[1, 0], [0.99, 0.01]], seen_at=0, now=0)
        self.assertEqual(memory.take_match(15, [1, 0], now=1,
                         min_similarity=0.85, min_margin=0.05), (1, 1.0))
        memory.remember(1, 15, [1, 0], gallery=[[1, 0], [0, 1]], seen_at=1, now=1)
        memory.remember(2, 15, [0, 1], seen_at=1, now=1)
        self.assertIsNone(memory.take_match(15, [0, 1], now=2,
                          min_similarity=0.85, min_margin=0.05))
        self.assertEqual(memory.last_decision["reason"], "ambiguous")

    def test_low_confidence_and_duplicates_do_not_fill_gallery(self) -> None:
        """Weak boxes remain visible but do not teach memory new appearances.

        Args:
            None.
        Returns:
            None: Asserts enrollment filtering and duplicate suppression.
        """
        tracker = BasicTracker(reid_memory=RetiredObjectMemory(capacity=3, retention_s=10))
        first = tracker.update([detection(confidence=0.3)], 0, descriptors=[[1, 0]])
        self.assertEqual(first[0]["track_id"], 1)
        self.assertEqual(tracker.last_stats["reid_gallery_sizes"], {"1": 0})
        tracker.update([detection()], 1, descriptors=[[1, 0]])
        tracker.update([detection()], 2, descriptors=[[1, 0]])
        self.assertEqual(tracker.last_stats["reid_gallery_sizes"], {"1": 1})
        self.assertEqual(tracker.last_stats["reid_gallery_updates"], {"duplicate_view": 1})

    def test_gallery_capacity_anchor_expiry_and_invalid_shapes(self) -> None:
        """Diverse views remain bounded; gallery storage does not extend expiry.

        Args:
            None.
        Returns:
            None: Asserts bounds, retained anchor, validation and expiry.
        """
        memory = RetiredObjectMemory(capacity=3, retention_s=10)
        tracker = BasicTracker(reid_memory=memory)
        for index in range(8):
            vector = [float(i == index) for i in range(8)]
            tracker.update([detection()], index, descriptors=[vector])
        self.assertEqual(tracker.last_stats["reid_gallery_sizes"], {"1": 4})
        tracker.update([], 8)
        tracker.update([], 9)
        self.assertEqual(memory.take_match(15, [1] + [0] * 7, now=10,
                         min_similarity=0.85, min_margin=0.05), (1, 1.0))
        with self.assertRaises(ValueError):
            memory.remember(2, 15, [1, 0], gallery=[[1, 0, 0]], seen_at=10, now=10)
        with self.assertRaises(ValueError):
            memory.remember(2, 15, [1, 0], gallery=[[1, 0]] * 5, seen_at=10, now=10)
        memory.remember(2, 15, [1, 0], gallery=[[1, 0], [0, 1]], seen_at=10, now=10)
        self.assertIsNone(memory.take_match(15, [0, 1], now=21,
                          min_similarity=0.85, min_margin=0.05))


if __name__ == "__main__":
    unittest.main()
