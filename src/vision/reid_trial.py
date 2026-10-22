"""Opt-in, local recording of exact detector inputs and re-ID decisions."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import threading
import time
from typing import Any


def current_commit() -> str | None:
    """Return the source revision used for this trial, if available."""
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=False
    )
    return result.stdout.strip() if result.returncode == 0 else None


class ReidTrialRecorder:
    """Save video-adjacent detector frames and JSONL decisions without overwrites."""

    def __init__(
        self, output: Path, seconds: float, notes: str, cv: Any,
        *, width: int = 1280, height: int = 720,
        tracking_modes: dict[str, Any] | None = None,
    ) -> None:
        """Create a new ignored recording directory before opening the camera.

        Args:
            output (Path): New trial directory; existing targets are refused.
            seconds (float): Requested timed trial duration.
            notes (str): User-supplied scene description.
            cv (Any): Existing OpenCV module used only for lossless PNG encoding.
            width (int): Grayscale detector source width.
            height (int): Grayscale detector source height.
            tracking_modes (dict[str, Any] | None): Selected optional matching
                modes and retry duration for reproducible trial comparisons.
        """
        if seconds <= 0 or width <= 0 or height <= 0:
            raise ValueError("Trial duration and dimensions must be positive")
        self.output = Path(output)
        self.output.mkdir(parents=True, exist_ok=False)
        self.frames = self.output / "detector-frames"
        self.frames.mkdir()
        self.stream = (self.output / "updates.jsonl").open("x")
        self.lock = threading.Lock()
        self.cv = cv
        self.width, self.height = width, height
        self.closed = False
        self.metadata = {
            "status": "recording",
            "started_utc": datetime.now(timezone.utc).isoformat(),
            "started_monotonic_s": time.monotonic(),
            "requested_seconds": seconds,
            "notes": notes,
            "git_commit": current_commit(),
            "requested_camera_mode": "1280x720 MJPEG 30 fps",
            "tracking_modes": dict(tracking_modes or {}),
            "video": "camera.mkv; FFmpeg copies incoming MJPEG packets",
            "detector_frames": "Lossless PNG grayscale frames sampled at detector updates, at most about 2 Hz",
            "timing_limit": "Host frame receipt and detector completion are monotonic observations, not exposure synchronization or an exact video-PTS map.",
            "privacy": "Contains camera images of people; ignored by Git. Share only intentionally.",
        }
        self._write_metadata()

    def _write_metadata(self) -> None:
        """Write the small trial manifest, including an explicit completion state."""
        (self.output / "metadata.json").write_text(
            json.dumps(self.metadata, indent=2) + "\n"
        )

    def record(
        self, frame: tuple[int, float, bytes], boxes: list[dict[str, Any]],
        tracking_stats: dict[str, Any], completed_s: float,
    ) -> None:
        """Save the exact grayscale detector input and its completed decision.

        Args:
            frame (tuple[int, float, bytes]): Source sequence, host receipt time,
                and full row-major grayscale pixels from the live detector.
            boxes (list[dict[str, Any]]): Current source-coordinate boxes and IDs.
            tracking_stats (dict[str, Any]): Memory counts/reasons, not descriptors.
            completed_s (float): Host-monotonic detector completion time.
        """
        import numpy as np

        sequence, received_s, pixels = frame
        if len(pixels) != self.width * self.height:
            raise ValueError("Trial frame is not one complete grayscale image")
        gray = np.frombuffer(pixels, dtype=np.uint8).reshape(self.height, self.width)
        ok, encoded = self.cv.imencode(
            ".png", gray, [self.cv.IMWRITE_PNG_COMPRESSION, 3]
        )
        if not ok:
            raise OSError("OpenCV could not encode a trial frame")
        name = f"detector-frames/frame-{sequence:08d}.png"
        sample = {
            "sequence": sequence,
            "source_receipt_monotonic_s": received_s,
            "detector_completed_monotonic_s": completed_s,
            "image": name,
            "boxes": boxes,
            "tracking_stats": tracking_stats,
        }
        with self.lock:
            if self.closed:
                raise RuntimeError("Trial recorder is closed")
            (self.output / name).write_bytes(encoded.tobytes())
            self.stream.write(json.dumps(sample, allow_nan=False) + "\n")
            self.stream.flush()

    def close(self, status: str) -> None:
        """Flush the log and mark the run complete or partial exactly once.

        Args:
            status (str): ``complete`` after the timer, otherwise ``partial``.
        """
        with self.lock:
            if self.closed:
                return
            self.closed = True
            self.stream.close()
            self.metadata["status"] = status
            self.metadata["finished_utc"] = datetime.now(timezone.utc).isoformat()
            self.metadata["elapsed_host_s"] = (
                time.monotonic() - self.metadata["started_monotonic_s"]
            )
            video = self.output / "camera.mkv"
            self.metadata["video_bytes"] = video.stat().st_size if video.exists() else None
            with (self.output / "updates.jsonl").open() as saved:
                self.metadata["saved_detector_updates"] = sum(1 for _ in saved)
            self._write_metadata()
