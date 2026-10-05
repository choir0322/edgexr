"""Latest-frame CPU detection with bounded storage and explicit result age."""

from collections import deque
from pathlib import Path
import threading
import time

from vision.detect_image import infer_once, parse_detections

SOURCE_WIDTH, SOURCE_HEIGHT = 1280, 720
MAX_AGE = 1.5


class DetectionState:
    def __init__(self, enabled=False):
        self.enabled = enabled
        self.lock = threading.Lock()
        self.started = time.monotonic()
        self.result = None
        self.error = None
        self.finished = deque(maxlen=20)

    def publish(self, frame, boxes, cost_ms, finished):
        with self.lock:
            self.result = dict(sequence=frame[0], captured=frame[1], boxes=boxes,
                               compute_ms=cost_ms)
            self.finished.append(finished)

    def fail(self, error):
        with self.lock:
            self.error = str(error)

    def snapshot(self, now, camera_live=True):
        with self.lock:
            result = dict(self.result) if self.result else {}
            age = now-result.pop('captured') if result else None
            status = 'off' if not self.enabled else 'error' if self.error else (
                'unavailable' if not camera_live else 'starting' if age is None else
                'stale' if age > MAX_AGE else 'ready')
            if status == 'starting' and now-self.started > 10:
                status = 'stale'
            times = [t for t in self.finished if now-t < 5]
            hz = (len(times)-1)/(times[-1]-times[0]) if len(times)>1 and times[-1]>times[0] else None
            result.update(status=status, error=self.error, rate_hz=hz,
                          age_ms=age*1000 if age is not None else None,
                          width=SOURCE_WIDTH, height=SOURCE_HEIGHT)
            if status != 'ready':
                result['boxes'] = []
            return result


class CpuDetector:
    def __init__(self, cv, prototxt, weights):
        import numpy as np
        self.np, self.cv = np, cv
        for name in (prototxt, weights):
            if not Path(name).is_file():
                raise ValueError(f'Missing model file: {name}; see docs/DETECTION_BASELINE.md')
        self.net = cv.dnn.readNetFromCaffe(str(prototxt), str(weights))
        self.net.setPreferableBackend(cv.dnn.DNN_BACKEND_OPENCV)
        self.net.setPreferableTarget(cv.dnn.DNN_TARGET_CPU)

    def __call__(self, pixels):
        gray = self.np.frombuffer(pixels, dtype=self.np.uint8).reshape(SOURCE_HEIGHT, SOURCE_WIDTH)
        rows, *_ = infer_once(self.cv, self.net, gray)
        return parse_detections(rows, SOURCE_WIDTH, SOURCE_HEIGHT, .5)


def detect_latest(state, factory, clock=time.monotonic):
    """One result per attempt; no catch-up bursts when inference is slow."""
    try:
        detector = factory()
        previous_seq, due = 0, 0.0
        while not state.stop.is_set():
            if state.stop.wait(max(0, due-clock())):
                break
            with state.condition:
                state.condition.wait_for(lambda: state.stop.is_set() or state.error or
                    (state.detection_frame is not None and state.detection_frame[0] != previous_seq), timeout=.5)
                if state.stop.is_set() or state.error:
                    break
                frame = state.detection_frame
            if frame is None or frame[0] == previous_seq:
                continue
            previous_seq = frame[0]
            started = clock()
            due = started+.5
            if started-frame[1] > MAX_AGE:
                continue
            boxes = detector(frame[2])
            finished = clock()
            state.detector.publish(frame, boxes, (finished-started)*1000, finished)
    except Exception as error:
        state.detector.fail(f'Detector failed: {error}')
