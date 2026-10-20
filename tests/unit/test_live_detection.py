from __future__ import annotations
from typing import Callable, NoReturn, TYPE_CHECKING

if TYPE_CHECKING:
    from _contracts import Record

import unittest
from unittest.mock import patch

try:
    import numpy as np
except ImportError:
    np = None

from vision.live_detector import DetectionState, detect_latest

if np is not None:
    from app.live_preview import State, camera_command


class DetectionStateTests(unittest.TestCase):
    def test_age_stale_error_camera_failure_and_empty_detection(self) -> None:
        """Verify age stale error camera failure and empty detection.

        Args:
            None.

        Returns:
            None: unittest assertions fail if the expected contract is violated.
        """
        # Exercise startup, source-age expiry and camera availability independently
        # from a valid empty prediction and an explicit model failure.
        state = DetectionState(True)
        self.assertEqual(state.snapshot(state.started)["status"], "starting")
        self.assertEqual(state.snapshot(state.started + 11)["status"], "stale")
        state.publish((1, 10, b""), [{"label": "chair"}], 200, 10.2)
        self.assertAlmostEqual(state.snapshot(10.3)["age_ms"], 300)
        self.assertEqual(state.snapshot(10.3)["status"], "ready")
        self.assertEqual(state.snapshot(12)["boxes"], [])
        self.assertEqual(state.snapshot(10.3, False)["boxes"], [])
        state.publish((2, 10.5, b""), [], 201, 10.7)
        self.assertEqual(state.snapshot(10.8)["status"], "ready")
        self.assertAlmostEqual(state.snapshot(10.8)["rate_hz"], 2)
        state.fail("bad model")
        self.assertEqual(state.snapshot(10.8)["status"], "error")
        self.assertEqual(state.snapshot(10.8)["boxes"], [])
        self.assertEqual(DetectionState().snapshot(1)["status"], "off")


@unittest.skipIf(np is None, "NumPy required for preview")
class LiveDetectionTests(unittest.TestCase):
    def test_opt_in_worker_restores_a_retired_id_without_changing_default(self) -> None:
        """A four-inference sequence exercises the live memory handoff."""
        clock = [100.0]

        class Stop:
            """Advance synthetic time while the detector respects its cadence."""

            stopped = False

            def is_set(self) -> bool:
                """Return whether the synthetic worker should exit."""
                return self.stopped

            def set(self) -> None:
                """Stop the worker after the returning detection."""
                self.stopped = True

            def wait(self, seconds: float) -> bool:
                """Advance the fake clock without sleeping."""
                clock[0] += seconds
                return self.stopped

        state = State(detection_enabled=True, reidentify=True)
        state.stop = Stop()
        state.publish_frame(b"", clock[0], b"frame1")
        published: list[list[Record]] = []
        real_publish = state.detector.publish

        def publish(frame: tuple[int, float, bytes], boxes: list[Record],
                    cost_ms: float, finished: float,
                    tracking_stats: Record | None = None) -> None:
            """Record the published IDs and retain the real status update."""
            published.append(boxes)
            real_publish(frame, boxes, cost_ms, finished, tracking_stats)

        state.detector.publish = publish

        def detect(pixels: bytes) -> list[Record]:
            """Send one box, two empty results, then a displaced return."""
            index = len(published)
            clock[0] += 0.1
            if index < 3:
                state.publish_frame(b"", clock[0], f"frame{index + 2}".encode())
            else:
                state.stop.set()
            if index in (1, 2):
                return []
            box = [100, 0, 200, 100] if index == 0 else [400, 0, 500, 100]
            return [{"class_id": 15, "label": "person", "confidence": 0.9,
                     "box_xyxy": box}]

        with patch("vision.live_detector.grayscale_grid_descriptor", return_value=(1.0, 0.0)):
            detect_latest(state, lambda: detect, lambda: clock[0])
        self.assertEqual([len(group) for group in published], [1, 0, 0, 1])
        self.assertEqual(published[0][0]["track_id"], 1)
        self.assertEqual(published[-1][0]["track_id"], 1)
        self.assertEqual(published[-1][0]["match_source"], "appearance")
        self.assertEqual(state.detector.snapshot(clock[0])["tracking_stats"]["reid_restores"], 1)
        self.assertIsNone(state.detector.error)

    def test_worker_uses_scaled_motion_and_reports_motion_only_id_hold(self) -> None:
        """Join 320×180 pair shifts to 1280×720 detector boxes by receipt time.

        Args:
            None.

        Returns:
            None: Assertions check a motion-only ID hold and diagnostic counts.
        """
        clock = [100.0]

        class Stop:
            """Advance synthetic time without sleeping."""

            stopped = False

            def is_set(self) -> bool:
                """Return the test worker's stop flag.

                Args:
                    None.

                Returns:
                    bool: Whether synthetic work has stopped.
                """
                return self.stopped

            def set(self) -> None:
                """Stop after the second inference.

                Args:
                    None.

                Returns:
                    None: Marks this test worker stopped.
                """
                self.stopped = True

            def wait(self, seconds: float) -> bool:
                """Advance the fake clock by the requested seconds.

                Args:
                    seconds (float): Synthetic wait duration.

                Returns:
                    bool: Whether the test worker has stopped.
                """
                clock[0] += seconds
                return self.stopped

        state = State(detection_enabled=True, motion_aware_tracking=True)
        state.stop = Stop()
        state.publish_frame(b"", 100.0, b"first")
        calls = [0]

        def detect(pixels: bytes) -> list[Record]:
            """Offer a second frame after reliable motion has been recorded.

            Args:
                pixels (bytes): Selected source frame bytes, unused by this fake.

            Returns:
                list[Record]: Synthetic person box for the chosen source time.
            """
            calls[0] += 1
            clock[0] += 0.2
            if calls[0] == 1:
                for index in range(1, 11):
                    timestamp = 100.0 + index * 0.05
                    state.publish_frame(b"", timestamp, b"latest")
                    state.motion_history.add(
                        index, 100.0 + (index - 1) * 0.05,
                        index + 1, timestamp, (5.0, 0.0),
                    )
                return [{"class_id": 15, "label": "person", "box_xyxy": [100, 0, 200, 100]}]
            state.stop.set()
            return [{"class_id": 15, "label": "person", "box_xyxy": [300, 0, 400, 100]}]

        def factory() -> Callable[[bytes], list[Record]]:
            """Build the synthetic detector only once.

            Args:
                None.

            Returns:
                Callable: Fake detector accepting source bytes.
            """
            return detect

        def fake_clock() -> float:
            """Read synthetic monotonic seconds.

            Args:
                None.

            Returns:
                float: Synthetic monotonic seconds.
            """
            return clock[0]

        detect_latest(state, factory, fake_clock)
        result = state.detector.snapshot(clock[0])
        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["boxes"][0]["track_id"], 1)
        self.assertEqual(result["tracking_mode"], "motion-aware")
        self.assertEqual(result["tracking_stats"]["covered_tracks"], 1)
        self.assertEqual(result["tracking_stats"]["motion_only_matches"], 1)
        self.assertIsNone(state.error)

    def test_full_frame_is_separate_from_motion_and_latest_replaces_older(self) -> None:
        """Verify full frame is separate from motion and latest replaces older.

        Args:
            None.

        Returns:
            None: unittest assertions fail if the expected contract is violated.
        """
        # Replace both frame slots, then verify source-size separation, detector
        # availability and unchanged FFmpeg scaling choices.
        state = State(detection_enabled=True)
        state.publish_frame(b"small1", 1, b"full1")
        state.publish_frame(b"small2", 2, b"full2")
        self.assertEqual(state.latest, (2, 2, b"small2"))
        self.assertEqual(state.detection_frame, (2, 2, b"full2"))
        state.publish_result(state.latest, 1, None, 1, 2.01)
        state.detector.publish(state.detection_frame, [], 200, 2.2)
        self.assertEqual(state.snapshot(2.3)["detector"]["status"], "ready")
        state.fail("camera gone")
        self.assertEqual(state.snapshot(2.3)["detector"]["status"], "unavailable")
        self.assertIn("scale=1280:720", camera_command("/dev/video0", detection=True))
        self.assertIn("scale=320:180", camera_command("/dev/video0"))

    def test_worker_rate_limits_and_skips_backlog_even_when_slow(self) -> None:
        """Verify worker rate limits and skips backlog even when slow.

        Args:
            None.

        Returns:
            None: unittest assertions fail if the expected contract is violated.
        """
        # Simulate both fast and slow inference with a controllable clock/event;
        # no real model or half-second sleeps are needed.
        for duration in (0.2, 0.8):
            with self.subTest(duration=duration):
                clock = [100.0]

                class Stop:
                    stopped = False

                    def is_set(self) -> bool:
                        """Report whether the fake stop event has been triggered.

                        Args:
                            None.

                        Returns:
                            bool: The declared test-double result; only synthetic state is changed.
                        """
                        return self.stopped

                    def set(self) -> None:
                        """Trigger the fake stop event so the worker exits predictably.

                        Args:
                            None.

                        Returns:
                            None: The declared test-double result; only synthetic state is changed.
                        """
                        self.stopped = True

                    def wait(self, seconds: float) -> bool:
                        """Simulate waiting using the enclosing test state rather than real hardware.

                        Args:
                            seconds (float): Requested positive collection duration in host seconds.

                        Returns:
                            bool: The declared test-double result; only synthetic state is changed.
                        """
                        clock[0] += seconds
                        return self.stopped

                state = State(detection_enabled=True)
                state.stop = Stop()
                state.publish_frame(b"", clock[0], b"one")
                calls = []

                def detector(pixels: bytes) -> list[Record]:
                    """Simulate inference cost and publish newer frames during that computation.

                    Args:
                        pixels (bytes): Immutable row-major grayscale bytes; dimensions are specified by
                            this stage.

                    Returns:
                        list[Record]: The declared test-double result; only synthetic state is changed.
                    """
                    # Advance fake compute time and publish two arrivals during the first call.
                    # Only the newest should be used next; stop after the second inference.
                    calls.append((clock[0], pixels))
                    clock[0] += duration
                    if len(calls) == 1:
                        state.publish_frame(b"", clock[0], b"two")
                        state.publish_frame(b"", clock[0], b"three")
                    else:
                        state.stop.set()
                    return []

                def fake_detector_factory() -> Callable[[bytes], list[Record]]:
                    """Reuse the fake detector that advances the enclosing simulated clock.

                    Args:
                        None; values are captured from the enclosing function.

                    Returns:
                        Callable[[bytes], list[Record]]: The callback result described above.
                    """
                    return detector

                def read_fake_clock() -> float:
                    """Read simulated monotonic seconds without advancing real time.

                    Args:
                        None; values are captured from the enclosing function.

                    Returns:
                        float: The callback result described above.
                    """
                    return clock[0]

                # Verify bounded sampling and the slower of the target cadence or compute
                # duration, while camera state remains healthy.
                detect_latest(state, fake_detector_factory, read_fake_clock)
                self.assertEqual([c[1] for c in calls], [b"one", b"three"])
                self.assertAlmostEqual(calls[1][0] - calls[0][0], max(0.5, duration))
                self.assertIsNone(state.error)

    def test_detector_failure_does_not_fail_camera(self) -> None:
        """Verify detector failure does not fail camera.

        Args:
            None.

        Returns:
            None: unittest assertions fail if the expected contract is violated.
        """
        state = State(detection_enabled=True)

        def broken() -> NoReturn:
            """Inject a model-construction failure to verify subsystem isolation.

            Args:
                None.

            Returns:
                NoReturn: The declared test-double result; only synthetic state is changed.
            """
            raise ValueError("invalid model")

        # A model-construction exception must affect only detector status, not stop capture.
        detect_latest(state, broken)
        self.assertIsNone(state.error)
        self.assertIn("invalid model", state.detector.snapshot(1)["error"])
        self.assertFalse(state.stop.is_set())

    def test_worker_attaches_ids_before_publication_and_ages_empty_updates(self) -> None:
        """Verify ordered detector results receive IDs before any API publication.

        Args:
            None.

        Returns:
            None: unittest assertions fail if the live handoff is incorrect.
        """
        # Advance a synthetic clock and replace the newest source frame after each
        # inference. A valid empty result counts as one missed detector update.
        clock = [100.0]

        class Stop:
            stopped = False

            def is_set(self) -> bool:
                """Report whether this synthetic worker has completed its four calls.

                Args:
                    None.

                Returns:
                    bool: Current synthetic stop state.
                """
                return self.stopped

            def set(self) -> None:
                """Stop the synthetic worker after the fourth inference.

                Args:
                    None.

                Returns:
                    None: Updates only the test stop state.
                """
                self.stopped = True

            def wait(self, seconds: float) -> bool:
                """Advance synthetic time by a requested worker wait.

                Args:
                    seconds (float): Requested host seconds.

                Returns:
                    bool: Current synthetic stop state.
                """
                clock[0] += seconds
                return self.stopped

        def chair(box: list[int]) -> Record:
            """Build one source-coordinate test detection without an ID.

            Args:
                box (list[int]): XYXY image coordinates.

            Returns:
                Record: Synthetic detector output.
            """
            return {"class_id": 9, "label": "chair", "confidence": 0.9,
                    "box_xyxy": box}

        outputs = [
            [chair([100, 100, 200, 200])],
            [chair([105, 100, 205, 200]), chair([400, 100, 500, 200])],
            [],
            [chair([110, 100, 210, 200])],
        ]
        state = State(detection_enabled=True)
        state.stop = Stop()
        published: list[list[Record]] = []
        original_publish = state.detector.publish

        def record_publish(
            frame: tuple[int, float, bytes], boxes: list[Record],
            cost_ms: float, finished: float, tracking_stats: Record | None = None
        ) -> None:
            """Observe ID-bearing payloads at the real publication boundary.

            Args:
                frame (tuple[int, float, bytes]): Source sequence, receipt time, pixels.
                boxes (list[Record]): ID-bearing current detections.
                cost_ms (float): Inference milliseconds.
                finished (float): Synthetic monotonic completion seconds.
                tracking_stats (Record | None): Tracker's latest coverage counts.

            Returns:
                None: Records the payload and calls the real publisher.
            """
            published.append(boxes)
            original_publish(frame, boxes, cost_ms, finished, tracking_stats)

        state.detector.publish = record_publish
        state.publish_frame(b"", clock[0], b"frame1")

        def fake_detector(pixels: bytes) -> list[Record]:
            """Return the next complete result while another frame arrives.

            Args:
                pixels (bytes): Synthetic latest source-frame bytes.

            Returns:
                list[Record]: Next completed detector output without IDs.
            """
            index = len(published)
            clock[0] += 0.1
            if index < len(outputs) - 1:
                state.publish_frame(b"", clock[0], f"frame{index + 2}".encode())
            else:
                state.stop.set()
            return outputs[index]

        def fake_factory() -> Callable[[bytes], list[Record]]:
            """Provide the synthetic detector to the worker.

            Args:
                None.

            Returns:
                Callable[[bytes], list[Record]]: Synthetic inference function.
            """
            return fake_detector

        def fake_clock() -> float:
            """Read synthetic monotonic time without advancing it.

            Args:
                None.

            Returns:
                float: Synthetic host seconds.
            """
            return clock[0]

        detect_latest(state, fake_factory, fake_clock)
        self.assertEqual([[box["track_id"] for box in group] for group in published],
                         [[1], [1, 2], [], [1]])
        self.assertEqual([box.get("track_id") for box in outputs[1]], [None, None])
        self.assertEqual(state.detector.snapshot(clock[0])["boxes"][0]["track_id"], 1)
        self.assertIsNone(state.error)
