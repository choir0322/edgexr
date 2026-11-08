"""Latest-frame scene worker; orientation is context, not fusion or a match gate."""

from __future__ import annotations

import copy
import platform
from pathlib import Path
import threading
import time
from typing import Any

import numpy as np
from spatial.scene_memory import SceneMemory
from spatial.scene_recorder import SceneRecorder
from spatial.view_map import ViewMap
from spatial.foreground import person_mask


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
        self.recorder: SceneRecorder | None = None

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
                    "recording": self.recorder.snapshot() if self.recorder else None,
                    "target_hz": 1, "result": result}


def scene_latest(state: Any, cv: Any, output: Path | None = None,
                 save_images: bool = False, exclude_people: bool = False) -> None:
    """Process at most one newest frame per second, never queue capture frames.

    Args:
        state (Any): App State, with condition, scene_frame and stop event.
        cv (Any): Existing CPU OpenCV module.
        output (Path | None): New ignored directory for non-image JSONL evidence.
        save_images (bool): Opt-in canonical PNGs; bounded recording may drop queries.
        exclude_people (bool): Require fresh detector evidence and mask person features.
    Returns:
        None: Failures are isolated to scene status; no motor or gyro correction.
    """
    recorder = None
    try:
        if save_images and output is None:
            raise ValueError("Scene images require a new output directory")
        memory = SceneMemory(cv=cv)
        view_map = ViewMap(memory.config.max_views)
        contexts: dict[int, dict] = {}
        reference_images: dict[int, str] = {}
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
                        "foreground_policy": "person_boxes_v1" if exclude_people else "off",
                        "foreground_max_source_lag_s": 0.5 if exclude_people else None,
                        "input_shape": "1280x720 grayscale; host receipts, not exposure time",
                        "save_images": save_images,
                        "timing_schema": 2,
                        "view_map_schema": 1,
                        "recording_policy": "FIFO background writer; four waiting plus one in-flight record; drop new queries when full; defer enrollment until admission available",
                        "completion_rule": "Require timing-final.json recording status; missing final file means incomplete",
                        "timing_scope": "Host wall intervals plus scene-thread/process CPU; CPU clocks do not measure other OpenCV threads individually. IMU keeps 64 slow events and cumulative maxima. No OS scheduler/storage attribution.",
                        "image_shape": "640x360 grayscale PNG" if save_images else None,
                        "scope": "Host receipt/preceding IMU context; no exposure sync or pose correction. Images only when explicitly enabled."}
            recorder = SceneRecorder(output, cv, metadata)
            with state.scene.lock:
                state.scene.recorder = recorder
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
            thread_started = time.thread_time()
            process_started = time.process_time()
            # Leave explicit enrollment pending if its evidence cannot be admitted.
            # Only this worker produces records: capacity cannot shrink meanwhile.
            mask, foreground = (person_mask(state.detector.scene_evidence(), captured)
                                if exclude_people else (None, {"status": "off"}))
            usable = not exclude_people or mask is not None
            label = (state.scene.take_request(captured)
                     if usable and (recorder is None or recorder.can_enroll()) else None)
            gray = np.frombuffer(pixels, dtype=np.uint8).reshape(720, 1280)
            if usable:
                decision = memory.process(gray, captured, label, feature_mask=mask)
            else:
                decision = {"timestamp_s": captured, "state": "unknown", "scene_id": None,
                            "label": None, "reason": "foreground_evidence_unavailable",
                            "features": 0, "candidates": [], "stored_views": len(memory.views)}
            decision["foreground"] = foreground
            if decision["state"] == "enrolled":
                contexts[decision["scene_id"]] = orientation
                contexts.pop(decision.get("evicted_id"), None)
            row = {"frame_sequence": sequence, "frame_host_s": captured,
                   "completed_host_s": time.monotonic(),
                   "compute_ms": (time.monotonic() - started) * 1000,
                   "compute_started_host_s": started,
                   "scene_thread_cpu_ms": (time.thread_time() - thread_started) * 1000,
                   "process_cpu_during_compute_ms": (time.process_time() - process_started) * 1000,
                   "enrollment_requested": label, "decision": decision,
                   "orientation_at_frame": orientation,
                   "reference_orientation": contexts.get(decision["scene_id"])}
            map_started = time.monotonic()
            row["view_map"] = view_map.update(decision, orientation, captured)
            row["view_map_update_ms"] = (time.monotonic() - map_started) * 1000
            if recorder is not None:
                # Queue immutable source bytes, not a future camera frame. The
                # writer owns resizing/encoding/disk I/O and its own row copy.
                if save_images:
                    image_name = f"frame-{sequence:08d}.png"
                    if decision["state"] == "enrolled":
                        reference_images[decision["scene_id"]] = image_name
                        reference_images.pop(decision.get("evicted_id"), None)
                    row.update(image=image_name,
                               reference_images=dict(reference_images))
                row["imu_poll_timing"] = state.imu.timing_snapshot()
                row["recording_accepted"] = recorder.submit(row, pixels if save_images else None)
            with state.scene.lock:
                state.scene.result = row
            state.stop.wait(max(0, 1 - (time.monotonic() - started)))
    except Exception as error:
        with state.scene.lock:
            state.scene.error = str(error)
    finally:
        if recorder is not None:
            status = recorder.close({"imu_poll_timing": state.imu.timing_snapshot(),
                                     "scene_error": state.scene.error})
            print(f"Scene recording: {status['status']}; {status['written']} written, "
                  f"{status['dropped']} dropped, {status['accepted_not_written']} pending/failed. "
                  f"{status['error'] or ''}", flush=True)
