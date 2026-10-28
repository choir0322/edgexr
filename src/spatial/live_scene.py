"""Latest-frame scene worker; orientation is context, not fusion or a match gate."""

from __future__ import annotations

import copy
import json
import platform
from pathlib import Path
import threading
import time
from typing import Any

import numpy as np
from spatial.scene_memory import SceneMemory


class LiveScene:
    """Small locked mailbox; SceneMemory itself belongs exclusively to the worker."""

    def __init__(self, enabled: bool = False) -> None:
        """Create an empty mailbox without loading OpenCV.

        Args:
            enabled (bool): Opt-in runtime flag.
        Returns:
            None.
        """
        self.enabled = enabled
        self.lock = threading.Lock()
        self.pending: tuple[str, float] | None = None
        self.next_label = 1
        self.result: dict | None = None
        self.error: str | None = None

    def enroll(self, now: float) -> str:
        """Request one reference from the next fresh frame after this click.

        Args:
            now (float): Host monotonic request time.
        Returns:
            str: Unique session-local label; pending requests cannot accumulate.
        """
        with self.lock:
            if not self.enabled or self.error or self.pending:
                raise ValueError("Scene memory off, failed, or enrollment already pending")
            label = f"View-{self.next_label}"
            self.next_label += 1
            self.pending = (label, now)
            return label

    def take_request(self, captured: float) -> str | None:
        """Consume a request only with a frame newer than the click.

        Args:
            captured (float): Frame host receipt seconds.
        Returns:
            str | None: Explicit enrollment label or ordinary query.
        """
        with self.lock:
            if self.pending and captured > self.pending[1]:
                label = self.pending[0]
                self.pending = None
                return label
        return None

    def snapshot(self, now: float, camera_live: bool) -> dict:
        """Keep aged decisions diagnostic without presenting stale recognition as live.

        Args:
            now (float): Host monotonic seconds.
            camera_live (bool): Current camera/analysis health.
        Returns:
            dict: Independently aged scene status and last decision.
        """
        with self.lock:
            result = copy.deepcopy(self.result)
            age = (now - result["frame_host_s"]) * 1000 if result else None
            status = ("off" if not self.enabled else "error" if self.error else
                      "starting" if result is None else
                      "stale" if not camera_live or age > 2000 else "ready")
            return {"status": status, "error": self.error, "source_age_ms": age,
                    "pending_label": self.pending[0] if self.pending else None,
                    "target_hz": 1, "result": result}


def scene_latest(state: Any, cv: Any, output: Path | None = None) -> None:
    """Process at most one newest frame per second, never queue capture frames.

    Args:
        state (Any): App State, with condition, scene_frame and stop event.
        cv (Any): Existing CPU OpenCV module.
        output (Path | None): New ignored directory for non-image JSONL evidence.
    Returns:
        None: Failures are isolated to scene status; no motor or gyro correction.
    """
    log = None
    try:
        memory = SceneMemory(cv=cv)
        contexts: dict[int, dict] = {}
        if output is not None:
            output.mkdir(parents=True, exist_ok=False)
            from vision.detect_image import git_info
            metadata = {"settings": memory.settings(), "git": git_info(),
                        "opencv": cv.__version__, "target_hz": 1,
                        "host": platform.platform(), "python": platform.python_version(),
                        "started_unix_s": time.time(), "opencv_threads": cv.getNumThreads(),
                        "imu_poll_sleep_ms": state.imu_sleep_ms,
                        "camera_axis_basis": state.imu.camera_axis_basis,
                        "detection_enabled": state.detector.enabled,
                        "input_shape": "1280x720 grayscale; host receipts, not exposure time",
                        "scope": "Host receipt/preceding IMU context; no exposure sync, pose correction or images"}
            (output / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
            log = (output / "updates.jsonl").open("x")
        seen = 0
        while not state.stop.is_set():
            with state.condition:
                frame = state.scene_frame
            if frame is None or frame[0] == seen:
                state.stop.wait(0.05)
                continue
            sequence, captured, pixels, orientation = frame
            seen = sequence
            if time.monotonic() - captured > 0.5:
                continue
            started = time.monotonic()
            label = state.scene.take_request(captured)
            gray = np.frombuffer(pixels, dtype=np.uint8).reshape(720, 1280)
            decision = memory.process(gray, captured, label)
            if decision["state"] == "enrolled":
                contexts[decision["scene_id"]] = orientation
                contexts.pop(decision.get("evicted_id"), None)
            row = {"frame_sequence": sequence, "frame_host_s": captured,
                   "completed_host_s": time.monotonic(),
                   "compute_ms": (time.monotonic() - started) * 1000,
                   "enrollment_requested": label, "decision": decision,
                   "orientation_at_frame": orientation,
                   "reference_orientation": contexts.get(decision["scene_id"])}
            if log is not None:
                log.write(json.dumps(row, allow_nan=False) + "\n")
                log.flush()
            with state.scene.lock:
                state.scene.result = row
            state.stop.wait(max(0, 1 - (time.monotonic() - started)))
    except Exception as error:
        with state.scene.lock:
            state.scene.error = str(error)
    finally:
        if log is not None:
            log.close()
