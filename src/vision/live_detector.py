"""Latest-frame CPU detection with bounded storage and explicit result age."""

from __future__ import annotations
from typing import Any, Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from _contracts import Frame, Record

    from app.live_preview import State


from collections import deque
from pathlib import Path
import threading
import time
from vision.basic_tracker import BasicTracker
from vision.detect_image import infer_once, parse_detections

# Keep detector source dimensions and the source-age cutoff separate from
# the small motion/display image and the target inference cadence.
SOURCE_WIDTH, SOURCE_HEIGHT = 1280, 720
MAX_AGE = 1.5


class DetectionState:
    def __init__(self, enabled: bool = False, motion_aware: bool = False) -> None:
        """Initialize a single latest detector result and bounded completion history.

        Args:
            enabled (bool): Whether this optional live subsystem is requested.
            motion_aware (bool): Whether box matching may use recent image shifts.

        Returns:
            None: does not load a model or start inference.
        """
        # Protect a single result and a bounded completion history shared with HTTP
        # readers; startup time is used to detect a detector that never produces data.
        self.enabled = enabled
        self.motion_aware = motion_aware
        self.lock = threading.Lock()
        self.started = time.monotonic()
        self.result = None
        self.error = None
        self.finished = deque(maxlen=20)

    def publish(
        self, frame: Frame, boxes: list[Record], cost_ms: float, finished: float,
        tracking_stats: Record | None = None,
    ) -> None:
        """Store detections together with their source frame time and elapsed compute.

        Args:
            frame (Frame): Sequence integer, monotonic receipt seconds, and immutable gray
                bytes.
            boxes (list[Record]): Current detection dictionaries with session-local
                track_id; box_xyxy coordinates refer to the full source image.
            cost_ms (float): Elapsed detector call duration in milliseconds, excluding
                loading/display.
            finished (float): Host monotonic completion time in seconds for rate
                measurement.
            tracking_stats (Record | None): Counts from the sequential tracker
                update; no inference time is added to cost_ms.

        Returns:
            None: replaces older detections and records a completion for the rate estimate.
        """
        # Publish source identity, boxes and compute time atomically with completion
        # history. Frame receipt time—not inference completion—defines box freshness.
        with self.lock:
            self.result = dict(
                sequence=frame[0], captured=frame[1], boxes=boxes, compute_ms=cost_ms,
                tracking_stats=dict(tracking_stats or {}),
            )
            self.finished.append(finished)

    def fail(self, error: Exception | str) -> None:
        """Isolate a detector failure from camera and IMU workers.

        Args:
            error (Exception | str): Exception or explanatory message for this subsystem.

        Returns:
            None: the next snapshot hides boxes and exposes this message.
        """
        with self.lock:
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
        # Copy the stored prediction and derive availability from camera state,
        # detector errors and source age without mutating the published record.
        with self.lock:
            result = dict(self.result) if self.result else {}
            age = now - result.pop("captured") if result else None
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
            if status == "starting" and now - self.started > 10:
                status = "stale"

            # Measure achieved update rate over recent completions and attach display
            # metadata. Hide boxes whenever their status is not ready.
            times = [t for t in self.finished if now - t < 5]
            hz = (
                (len(times) - 1) / (times[-1] - times[0])
                if len(times) > 1 and times[-1] > times[0]
                else None
            )
            result.update(
                status=status,
                error=self.error,
                rate_hz=hz,
                age_ms=age * 1000 if age is not None else None,
                width=SOURCE_WIDTH,
                height=SOURCE_HEIGHT,
                tracking_mode="motion-aware" if self.motion_aware else "basic",
            )
            if status != "ready":
                result["boxes"] = []
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
        # Load only existing model files and explicitly select the OpenCV CPU backend;
        # this worker does not download weights or choose a hardware accelerator.
        import numpy as np

        self.np, self.cv = np, cv
        for name in (prototxt, weights):
            if not Path(name).is_file():
                raise ValueError(
                    f"Missing model file: {name}; see docs/DETECTION_BASELINE.md"
                )
        self.net = cv.dnn.readNetFromCaffe(str(prototxt), str(weights))
        self.net.setPreferableBackend(cv.dnn.DNN_BACKEND_OPENCV)
        self.net.setPreferableTarget(cv.dnn.DNN_TARGET_CPU)

    def __call__(self, pixels: bytes) -> list[Record]:
        """Detect objects from one full 1280x720 grayscale byte frame.

        Args:
            pixels (bytes): Immutable row-major grayscale bytes; dimensions are specified by
                this stage.

        Returns:
            list[Record]: Parsed source-coordinate boxes at confidence threshold 0.5.
        """
        # Reinterpret the full gray source, run shared 300×300 preprocessing/inference,
        # then map accepted boxes back to source pixels using the baseline 0.5 threshold.
        gray = self.np.frombuffer(pixels, dtype=self.np.uint8).reshape(
            SOURCE_HEIGHT, SOURCE_WIDTH
        )
        rows, *_ = infer_once(self.cv, self.net, gray)
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
        None: assigns session-local IDs and publishes results/errors without
            queuing frames or catch-up attempts.
    """
    # Load the model once and keep one tracker beside it in this sequential
    # worker. Both see completed detector results in order; no camera-frame
    # queue or tracker access from another thread is needed.
    try:
        detector = factory()
        tracker = BasicTracker()

        def source_shift(start: float, end: float) -> tuple[float, float] | None:
            """Scale reliable scene displacement to full detector-image pixels.

            Args:
                start (float): Old track's last matched source receipt seconds.
                end (float): Current detector source receipt seconds.

            Returns:
                tuple[float, float] | None: Source dx/dy pixels, or unknown.
            """
            small = state.motion_between(start, end)
            if small is None:
                return None
            return small[0] * (SOURCE_WIDTH / 320), small[1] * (SOURCE_HEIGHT / 180)

        previous_seq, due = 0, 0.0
        while not state.stop.is_set():
            if state.stop.wait(max(0, due - clock())):
                break

            # Select a new latest frame under the condition lock, then release the lock
            # before expensive inference so capture and motion can continue.
            with state.condition:

                def detection_frame_ready() -> bool | str:
                    """Wake on shutdown, a nonempty error, or a new eligible source sequence.

                    Args:
                        None; values are captured from the enclosing function.

                    Returns:
                        bool | str: The callback result described above.
                    """
                    return (
                        state.stop.is_set()
                        or state.error
                        or (
                            state.detection_frame is not None
                            and state.detection_frame[0] != previous_seq
                        )
                    )

                state.condition.wait_for(
                    detection_frame_ready,
                    timeout=0.5,
                )
                if state.stop.is_set() or state.error:
                    break
                frame = state.detection_frame
            if frame is None or frame[0] == previous_seq:
                continue

            # Space attempts by at least 0.5 seconds (target 2 Hz) and reject old input.
            # Slow inference can lower the achieved rate; skipped sources are intentional.
            previous_seq = frame[0]
            started = clock()
            due = started + 0.5
            if started - frame[1] > MAX_AGE:
                continue

            # Measure inference separately from ID matching, then attach IDs before
            # publishing. Source frame identity and receipt time remain unchanged.
            # An empty valid result still ages remembered tracks by one update.
            boxes = detector(frame[2])
            finished = clock()
            identified = tracker.update(
                boxes, frame[1], source_shift if state.motion_aware_tracking else None
            )
            state.detector.publish(
                frame, identified, (finished - started) * 1000, finished,
                tracker.last_stats,
            )
    except Exception as error:
        state.detector.fail(f"Detector failed: {error}")
