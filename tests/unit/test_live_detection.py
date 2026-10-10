from __future__ import annotations
from typing import Callable, NoReturn, TYPE_CHECKING

if TYPE_CHECKING:
    from _contracts import Record

import unittest

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
