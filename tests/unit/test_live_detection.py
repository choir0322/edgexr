# Postpone type evaluation so optional drivers/libraries stay optional.
from __future__ import annotations

# Describe data contracts without adding third-party runtime dependencies.
from typing import Callable, NoReturn, TYPE_CHECKING

# Resolve documentation-only types for editors; this block does not run in production.
if TYPE_CHECKING:
    # Reuse the documented frame, sensor and report vocabulary for type checking.
    from _contracts import Record

# Express hardware-independent behavior as executable checks.
import unittest

# Keep failure handling alongside the operation so cleanup/status remains explicit.
try:
    # Perform typed array and numerical operations; no sensor access occurs on import.
    import numpy as np
# Handle this failure without losing the error or skipping the enclosing cleanup.
except ImportError:
    # Set up np for this independent test scenario.
    np = None

# Reuse vision.live_detector helpers rather than duplicating their behavior here.
from vision.live_detector import DetectionState, detect_latest

# Choose the next branch using np is not None.
if np is not None:
    # Reuse app.live_preview helpers rather than duplicating their behavior here.
    from app.live_preview import State, camera_command


class DetectionStateTests(unittest.TestCase):
    def test_age_stale_error_camera_failure_and_empty_detection(self) -> None:
        """Verify age stale error camera failure and empty detection.

        Args:
            None.

        Returns:
            None: unittest assertions fail if the expected contract is violated.
        """
        # Prepare or exercise DetectionState with the controlled test inputs.
        state = DetectionState(True)
        # Check the expected Equal relationship for this case.
        self.assertEqual(state.snapshot(state.started)["status"], "starting")
        # Check the expected Equal relationship for this case.
        self.assertEqual(state.snapshot(state.started + 11)["status"], "stale")
        # Publish completed work through the state object's synchronization boundary.
        state.publish((1, 10, b""), [{"label": "chair"}], 200, 10.2)
        # Check the expected AlmostEqual relationship for this case.
        self.assertAlmostEqual(state.snapshot(10.3)["age_ms"], 300)
        # Check the expected Equal relationship for this case.
        self.assertEqual(state.snapshot(10.3)["status"], "ready")
        # Check the expected Equal relationship for this case.
        self.assertEqual(state.snapshot(12)["boxes"], [])
        # Check the expected Equal relationship for this case.
        self.assertEqual(state.snapshot(10.3, False)["boxes"], [])
        # Publish completed work through the state object's synchronization boundary.
        state.publish((2, 10.5, b""), [], 201, 10.7)
        # Check the expected Equal relationship for this case.
        self.assertEqual(state.snapshot(10.8)["status"], "ready")
        # Check the expected AlmostEqual relationship for this case.
        self.assertAlmostEqual(state.snapshot(10.8)["rate_hz"], 2)
        # Call state.fail for this step; its contract describes the result or side effect.
        state.fail("bad model")
        # Check the expected Equal relationship for this case.
        self.assertEqual(state.snapshot(10.8)["status"], "error")
        # Check the expected Equal relationship for this case.
        self.assertEqual(state.snapshot(10.8)["boxes"], [])
        # Check the expected Equal relationship for this case.
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
        # Prepare or exercise State with the controlled test inputs.
        state = State(detection_enabled=True)
        # Publish completed work through the state object's synchronization boundary.
        state.publish_frame(b"small1", 1, b"full1")
        # Publish completed work through the state object's synchronization boundary.
        state.publish_frame(b"small2", 2, b"full2")
        # Check the expected Equal relationship for this case.
        self.assertEqual(state.latest, (2, 2, b"small2"))
        # Check the expected Equal relationship for this case.
        self.assertEqual(state.detection_frame, (2, 2, b"full2"))
        # Publish completed work through the state object's synchronization boundary.
        state.publish_result(state.latest, 1, None, 1, 2.01)
        # Publish completed work through the state object's synchronization boundary.
        state.detector.publish(state.detection_frame, [], 200, 2.2)
        # Check the expected Equal relationship for this case.
        self.assertEqual(state.snapshot(2.3)["detector"]["status"], "ready")
        # Call state.fail for this step; its contract describes the result or side effect.
        state.fail("camera gone")
        # Check the expected Equal relationship for this case.
        self.assertEqual(state.snapshot(2.3)["detector"]["status"], "unavailable")
        # Check the expected In relationship for this case.
        self.assertIn("scale=1280:720", camera_command("/dev/video0", detection=True))
        # Check the expected In relationship for this case.
        self.assertIn("scale=320:180", camera_command("/dev/video0"))

    def test_worker_rate_limits_and_skips_backlog_even_when_slow(self) -> None:
        """Verify worker rate limits and skips backlog even when slow.

        Args:
            None.

        Returns:
            None: unittest assertions fail if the expected contract is violated.
        """
        # Exercise each fixture or edge case independently.
        for duration in (0.2, 0.8):
            # Keep these resources scoped so they are released even if the operation fails.
            with self.subTest(duration=duration):
                # Set up clock for this independent test scenario.
                clock = [100.0]

                class Stop:
                    # Set up stopped for this independent test scenario.
                    stopped = False

                    def is_set(self) -> bool:
                        """Report whether the fake stop event has been triggered.

                        Args:
                            None.

                        Returns:
                            bool: The declared test-double result; only synthetic state is changed.
                        """
                        # Return the documented result to the caller without starting another
                        # operation.
                        return self.stopped

                    def set(self) -> None:
                        """Trigger the fake stop event so the worker exits predictably.

                        Args:
                            None.

                        Returns:
                            None: The declared test-double result; only synthetic state is changed.
                        """
                        # Set up self.stopped for this independent test scenario.
                        self.stopped = True

                    def wait(self, seconds: float) -> bool:
                        """Simulate waiting using the enclosing test state rather than real hardware.

                        Args:
                            seconds (float): Requested positive collection duration in host seconds.

                        Returns:
                            bool: The declared test-double result; only synthetic state is changed.
                        """
                        # Update clock[0] with this step's contribution.
                        clock[0] += seconds
                        # Return the documented result to the caller without starting another
                        # operation.
                        return self.stopped

                # Prepare or exercise State with the controlled test inputs.
                state = State(detection_enabled=True)
                # Prepare or exercise Stop with the controlled test inputs.
                state.stop = Stop()
                # Publish completed work through the state object's synchronization boundary.
                state.publish_frame(b"", clock[0], b"one")
                # Set up calls for this independent test scenario.
                calls = []

                def detector(pixels: bytes) -> list[Record]:
                    """Simulate inference cost and publish newer frames during that computation.

                    Args:
                        pixels (bytes): Immutable row-major grayscale bytes; dimensions are specified by
                            this stage.

                    Returns:
                        list[Record]: The declared test-double result; only synthetic state is changed.
                    """
                    # Retain this item/chunk for the current calculation or bounded history.
                    calls.append((clock[0], pixels))
                    # Update clock[0] with this step's contribution.
                    clock[0] += duration
                    # Choose the next branch using len(calls) == 1.
                    if len(calls) == 1:
                        # Publish completed work through the state object's synchronization
                        # boundary.
                        state.publish_frame(b"", clock[0], b"two")
                        # Publish completed work through the state object's synchronization
                        # boundary.
                        state.publish_frame(b"", clock[0], b"three")
                    else:
                        # Signal waiting work through the shared event rather than a busy loop.
                        state.stop.set()
                    # Return the documented result to the caller without starting another
                    # operation.
                    return []

                def fake_detector_factory() -> Callable[[bytes], list[Record]]:
                    """Reuse the fake detector that advances the enclosing simulated clock.

                    Args:
                        None; values are captured from the enclosing function.

                    Returns:
                        Callable[[bytes], list[Record]]: The callback result described above.
                    """
                    # Evaluate the original callback expression only when the caller invokes it.
                    return detector

                def read_fake_clock() -> float:
                    """Read simulated monotonic seconds without advancing real time.

                    Args:
                        None; values are captured from the enclosing function.

                    Returns:
                        float: The callback result described above.
                    """
                    # Evaluate the original callback expression only when the caller invokes it.
                    return clock[0]

                # Call detect_latest for this step; its contract describes the result or side
                # effect.
                detect_latest(state, fake_detector_factory, read_fake_clock)
                # Check the expected Equal relationship for this case.
                self.assertEqual([c[1] for c in calls], [b"one", b"three"])
                # Check the expected AlmostEqual relationship for this case.
                self.assertAlmostEqual(calls[1][0] - calls[0][0], max(0.5, duration))
                # Check the expected IsNone relationship for this case.
                self.assertIsNone(state.error)

    def test_detector_failure_does_not_fail_camera(self) -> None:
        """Verify detector failure does not fail camera.

        Args:
            None.

        Returns:
            None: unittest assertions fail if the expected contract is violated.
        """
        # Prepare or exercise State with the controlled test inputs.
        state = State(detection_enabled=True)

        def broken() -> NoReturn:
            """Inject a model-construction failure to verify subsystem isolation.

            Args:
                None.

            Returns:
                NoReturn: The declared test-double result; only synthetic state is changed.
            """
            # Stop this operation with an explicit error rather than publishing invalid data.
            raise ValueError("invalid model")

        # Call detect_latest for this step; its contract describes the result or side effect.
        detect_latest(state, broken)
        # Check the expected IsNone relationship for this case.
        self.assertIsNone(state.error)
        # Check the expected In relationship for this case.
        self.assertIn("invalid model", state.detector.snapshot(1)["error"])
        # Check the expected False relationship for this case.
        self.assertFalse(state.stop.is_set())
