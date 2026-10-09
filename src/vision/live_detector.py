"""Latest-frame CPU detection with bounded storage and explicit result age."""

# Postpone type evaluation so optional drivers/libraries stay optional.
from __future__ import annotations

# Describe data contracts without adding third-party runtime dependencies.
from typing import Any, Callable, TYPE_CHECKING

# Resolve documentation-only types for editors; this block does not run in production.
if TYPE_CHECKING:
    # Reuse the documented frame, sensor and report vocabulary for type checking.
    from _contracts import Frame, Record

    # Reuse app.live_preview helpers rather than duplicating their behavior here.
    from app.live_preview import State


# Keep bounded timestamp/diagnostic histories with deque.
from collections import deque

# Work with explicit filesystem paths rather than shell expansions.
from pathlib import Path

# Coordinate independent workers using threads, locks, conditions and events.
import threading

# Measure host intervals and provide bounded polling pauses.
import time

# Reuse vision.detect_image helpers rather than duplicating their behavior here.
from vision.detect_image import infer_once, parse_detections

# Retain the 1280-by-720 detector source separately from the small motion image.
SOURCE_WIDTH, SOURCE_HEIGHT = 1280, 720
# Hide detector predictions once their source receipt is older than 1.5 seconds.
MAX_AGE = 1.5


class DetectionState:
    def __init__(self, enabled: bool = False) -> None:
        """Initialize a single latest detector result and bounded completion history.

        Args:
            enabled (bool): Whether this optional live subsystem is requested.

        Returns:
            None: does not load a model or start inference.
        """
        # Remember whether the user requested this optional subsystem.
        self.enabled = enabled
        # Protect this subsystem while capture, workers and HTTP requests run concurrently.
        self.lock = threading.Lock()
        # Remember monotonic startup time for no-data timeout checks.
        self.started = time.monotonic()
        # Keep one published result instead of an ever-growing result history.
        self.result = None
        # Retain the failure message for subsequent status snapshots.
        self.error = None
        # Bound detector completion history for its recent update-rate calculation.
        self.finished = deque(maxlen=20)

    def publish(
        self, frame: Frame, boxes: list[Record], cost_ms: float, finished: float
    ) -> None:
        """Store detections together with their source frame time and elapsed compute.

        Args:
            frame (Frame): Sequence integer, monotonic receipt seconds, and immutable gray
                bytes.
            boxes (list[Record]): Detection dictionaries; box_xyxy coordinates refer to the
                full source image.
            cost_ms (float): Elapsed detector call duration in milliseconds, excluding
                loading/display.
            finished (float): Host monotonic completion time in seconds for rate
                measurement.

        Returns:
            None: replaces older detections and records a completion for the rate estimate.
        """
        # Hold the shared-state lock only while reading or replacing shared values.
        with self.lock:
            # Keep one published result instead of an ever-growing result history.
            self.result = dict(
                sequence=frame[0], captured=frame[1], boxes=boxes, compute_ms=cost_ms
            )
            # Retain this item/chunk for the current calculation or bounded history.
            self.finished.append(finished)

    def fail(self, error: Exception | str) -> None:
        """Isolate a detector failure from camera and IMU workers.

        Args:
            error (Exception | str): Exception or explanatory message for this subsystem.

        Returns:
            None: the next snapshot hides boxes and exposes this message.
        """
        # Hold the shared-state lock only while reading or replacing shared values.
        with self.lock:
            # Retain the failure message for subsequent status snapshots.
            self.error = str(error)

    def snapshot(self, now: float, camera_live: bool = True) -> Record:
        """Report latest detections with source age and hide unavailable predictions.

        Args:
            now (float): Host monotonic seconds used to calculate age; None selects the
                clock now.
            camera_live (bool): Whether current camera state allows drawing possibly older
                boxes.

        Returns:
            Record: JSON-ready detector state; an empty ready box list is a valid result.
        """
        # Hold the shared-state lock only while reading or replacing shared values.
        with self.lock:
            # Copy the stored result before adding age/status, leaving published state intact.
            result = dict(self.result) if self.result else {}
            # Measure age from the observation/source time, not from when its result was
            # published.
            age = now - result.pop("captured") if result else None
            # Choose the visible state from enablement, errors, startup and freshness.
            status = (
                "off"
                if not self.enabled
                else "error"
                if self.error
                else (
                    "unavailable"
                    if not camera_live
                    else "starting"
                    if age is None
                    else "stale"
                    if age > MAX_AGE
                    else "ready"
                )
            )
            # Apply the freshness/status policy before exposing values to the user.
            if status == "starting" and now - self.started > 10:
                # Choose the visible state from enablement, errors, startup and freshness.
                status = "stale"
            # Select detector completions within the recent five-second rate window.
            times = [t for t in self.finished if now - t < 5]
            # Measure recent completed detections per second rather than assuming the target was
            # met.
            hz = (
                (len(times) - 1) / (times[-1] - times[0])
                if len(times) > 1 and times[-1] > times[0]
                else None
            )
            # Add the fields produced by this step while preserving the other report fields.
            result.update(
                status=status,
                error=self.error,
                rate_hz=hz,
                age_ms=age * 1000 if age is not None else None,
                width=SOURCE_WIDTH,
                height=SOURCE_HEIGHT,
            )
            # Apply the freshness/status policy before exposing values to the user.
            if status != "ready":
                # Hide stale or unavailable predictions instead of drawing them as current.
                result["boxes"] = []
            # Return the documented result to the caller without starting another operation.
            return result


class CpuDetector:
    def __init__(self, cv: Any, prototxt: Path, weights: Path) -> None:
        """Load existing Caffe artifacts into OpenCV's CPU inference backend.

        Args:
            cv (Any): OpenCV module or test double; Any is intentional for this optional
                native API.
            prototxt (Path): Existing Caffe graph definition; this operation never downloads
                it.
            weights (Path): Existing pretrained Caffe parameter file, kept outside Git.

        Returns:
            None: raises ValueError for missing files and propagates runtime/model errors.
        """
        # Perform typed array and numerical operations; no sensor access occurs on import.
        import numpy as np

        # Retain the array/runtime APIs on the detector object for subsequent calls.
        self.np, self.cv = np, cv
        # Process each name in the selected collection.
        for name in (prototxt, weights):
            # Reject this invalid input before it can produce misleading output.
            if not Path(name).is_file():
                # Stop this operation with an explicit error rather than publishing invalid
                # data.
                raise ValueError(
                    f"Missing model file: {name}; see docs/DETECTION_BASELINE.md"
                )
        # Load the existing Caffe graph and learned parameters; do not download or train.
        self.net = cv.dnn.readNetFromCaffe(str(prototxt), str(weights))
        # Execute the graph through OpenCV rather than assuming another inference backend.
        self.net.setPreferableBackend(cv.dnn.DNN_BACKEND_OPENCV)
        # Select CPU execution explicitly; no GPU/NPU offload is configured.
        self.net.setPreferableTarget(cv.dnn.DNN_TARGET_CPU)

    def __call__(self, pixels: bytes) -> list[Record]:
        """Detect objects from one full 1280x720 grayscale byte frame.

        Args:
            pixels (bytes): Immutable row-major grayscale bytes; dimensions are specified by
                this stage.

        Returns:
            list[Record]: Parsed source-coordinate boxes at confidence threshold 0.5.
        """
        # Interpret the image as one grayscale intensity per pixel with explicit dimensions.
        gray = self.np.frombuffer(pixels, dtype=self.np.uint8).reshape(
            SOURCE_HEIGHT, SOURCE_WIDTH
        )
        # Use the SSD prediction rows; live scheduling measures the whole call separately.
        rows, *_ = infer_once(self.cv, self.net, gray)
        # Return the documented result to the caller without starting another operation.
        return parse_detections(rows, SOURCE_WIDTH, SOURCE_HEIGHT, 0.5)


def detect_latest(
    state: State,
    factory: Callable[[], Callable[[bytes], list[Record]]],
    clock: Callable[[], float] = time.monotonic,
) -> None:
    """Run sequential latest-frame detection with at least 0.5 seconds between starts.

    Args:
        state (State): Shared live application state, protected by its locks and stop
            event.
        factory (Callable[[], Callable[[bytes], list[Record]]]): Constructs one callable
            detector before the loop begins.
        clock (Callable[[], float]): Zero-argument host clock; units are seconds except
            explicitly named nanosecond stages.

    Returns:
        None: publishes results/errors without queuing frames or catch-up attempts.
    """
    # Keep failure handling alongside the operation so cleanup/status remains explicit.
    try:
        # Construct the detector once in this worker before processing any frames.
        detector = factory()
        # Start with no processed source frame and no initial scheduling delay.
        previous_seq, due = 0, 0.0
        # Repeat until the stop signal, deadline or explicit exit condition is reached.
        while not state.stop.is_set():
            # Check shutdown/failure before starting another unit of worker work.
            if state.stop.wait(max(0, due - clock())):
                # Leave this loop; the enclosing cleanup/status code still runs.
                break
            # Hold the shared-state lock only while reading or replacing shared values.
            with state.condition:

                def detection_frame_ready() -> bool | str:
                    """Wake on shutdown, a nonempty error, or a new eligible source sequence.

                    Args:
                        None; values are captured from the enclosing function.

                    Returns:
                        bool | str: The callback result described above.
                    """
                    # Evaluate the original callback expression only when the caller invokes it.
                    return (
                        state.stop.is_set()
                        or state.error
                        or (
                            state.detection_frame is not None
                            and state.detection_frame[0] != previous_seq
                        )
                    )

                # Wait for new eligible data or shutdown; notification can wake this before the
                # timeout.
                state.condition.wait_for(
                    detection_frame_ready,
                    timeout=0.5,
                )
                # Check shutdown/failure before starting another unit of worker work.
                if state.stop.is_set() or state.error:
                    # Leave this loop; the enclosing cleanup/status code still runs.
                    break
                # Hold a local reference to the latest slot so replacement cannot change this
                # work item.
                frame = state.detection_frame
            # Handle absent data explicitly instead of interpreting it as a valid zero.
            if frame is None or frame[0] == previous_seq:
                # Skip this unusable item and look for the next eligible observation.
                continue
            # Mark this source sequence as attempted so it is not repeatedly inferred.
            previous_seq = frame[0]
            # Read host monotonic time for this stage's timing boundary.
            started = clock()
            # Allow the next inference start after 0.5 seconds, not 0.5 seconds after
            # completion.
            due = started + 0.5
            # Choose the next branch using started - frame[1] > MAX_AGE.
            if started - frame[1] > MAX_AGE:
                # Skip this unusable item and look for the next eligible observation.
                continue
            # Run inference sequentially on the selected immutable source frame.
            boxes = detector(frame[2])
            # Stamp completion separately from the source frame's receipt time.
            finished = clock()
            # Publish completed work through the state object's synchronization boundary.
            state.detector.publish(frame, boxes, (finished - started) * 1000, finished)
    # Handle this failure without losing the error or skipping the enclosing cleanup.
    except Exception as error:
        # Call state.detector.fail for this step; its contract describes the result or side
        # effect.
        state.detector.fail(f"Detector failed: {error}")
