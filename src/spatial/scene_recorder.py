"""Bounded, single-writer diagnostic recording independent of scene recognition."""

from __future__ import annotations

import copy
import json
from pathlib import Path
import queue
import threading
import time
from typing import Any

import numpy as np
from spatial.scene_memory import prepare_gray


class SceneRecorder:
    """One producer, four waiting records and one in-flight disk operation."""

    def __init__(self, output: Path, cv: Any, metadata: dict,
                 capacity: int = 4) -> None:
        """Start recording into an already-created fresh directory.

        Args:
            output (Path): Directory owned by this run.
            cv (Any): Existing OpenCV module; no global settings changed here.
            metadata (dict): Immutable run provenance copied for the writer.
            capacity (int): Maximum waiting records, excluding the active write.
        Returns:
            None.
        """
        if capacity < 1:
            raise ValueError("Recorder capacity must be positive")
        self.output, self.cv = output, cv
        self.metadata = copy.deepcopy(metadata)
        self.queue: queue.Queue = queue.Queue(maxsize=capacity)
        self.lock = threading.Lock()
        self.stopping = threading.Event()
        self.accepted = self.written = self.dropped = 0
        self.high_water = 0
        self.error: str | None = None
        self.finished = False
        self.final_context: dict = {}
        self.previous_write: dict | None = None
        self.thread = threading.Thread(target=self._run, name="scene-recorder", daemon=True)
        self.thread.start()

    def can_enroll(self) -> bool:
        """Check admission before consuming an explicit enrollment request.

        Args: None.
        Returns:
            bool: A slot is available and recording is healthy. Only the scene
            worker submits, so a free slot cannot fill before its own submission.
        """
        with self.lock:
            return not self.error and not self.stopping.is_set() and not self.queue.full()

    def submit(self, row: dict, pixels: bytes | None) -> bool:
        """Offer evidence without waiting for disk or queue capacity.

        Args:
            row (dict): Scene-owned result, deep copied to prevent writer mutation.
            pixels (bytes | None): Immutable 720x1280 gray source, only if saving PNG.
        Returns:
            bool: Accepted; otherwise a counted recording drop, not a scene drop.
        """
        with self.lock:
            if self.error or self.stopping.is_set() or self.queue.full():
                self.dropped += 1
                return False
            item = (copy.deepcopy(row), pixels, time.monotonic())
            self.queue.put_nowait(item)
            self.accepted += 1
            self.high_water = max(self.high_water, self.queue.qsize())
            return True

    def snapshot(self) -> dict:
        """Expose recording health separately from recognition health.

        Args: None.
        Returns:
            dict: Counts, bounded queue depth and explicit error/status.
        """
        with self.lock:
            status = ("error" if self.error else "complete" if self.finished else
                      "draining" if self.stopping.is_set() else "recording")
            if self.finished and self.dropped and not self.error:
                status = "partial"
            return {"status": status, "error": self.error,
                    "accepted": self.accepted, "written": self.written,
                    "dropped": self.dropped, "queued": self.queue.qsize(),
                    "capacity": self.queue.maxsize, "high_water": self.high_water,
                    "accepted_not_written": self.accepted - self.written}

    def close(self, context: dict, timeout: float = 5.0) -> dict:
        """Drain accepted records within a bounded shutdown wait.

        Args:
            context (dict): Final IMU counters and scene error from the producer.
            timeout (float): Maximum seconds to wait, not an I/O cancellation.
        Returns:
            dict: Recording status. A stuck daemon writer may leave no final file;
            that recording must be treated as incomplete, never silently complete.
        """
        self.final_context = copy.deepcopy(context)
        self.stopping.set()
        self.thread.join(timeout)
        if self.thread.is_alive():
            with self.lock:
                self.error = self.error or "Recorder shutdown timed out; evidence incomplete"
        return self.snapshot()

    def _write(self, log: Any, row: dict, pixels: bytes | None,
               enqueued: float) -> None:
        """Write one ordered record and optional exact-source canonical PNG.

        Args:
            log (Any): Writer-owned text stream.
            row (dict): Private copy of the scene result.
            pixels (bytes | None): Immutable full gray frame, or no image request.
            enqueued (float): Host monotonic enqueue time.
        Returns:
            None: Errors propagate to the recorder, not to recognition.
        """
        row["recording_queue_wait_ms"] = (time.monotonic() - enqueued) * 1000
        row["previous_log_write"] = self.previous_write
        if pixels is not None:
            started = time.monotonic()
            gray = np.frombuffer(pixels, dtype=np.uint8).reshape(720, 1280)
            if not self.cv.imwrite(str(self.output / row["image"]), prepare_gray(self.cv, gray)):
                raise OSError("Could not save scene diagnostic image")
            finished = time.monotonic()
            row.update(image_write_started_host_s=started,
                       image_write_finished_host_s=finished,
                       image_write_ms=(finished - started) * 1000)
        started = time.monotonic()
        log.write(json.dumps(row, allow_nan=False) + "\n")
        log.flush()
        finished = time.monotonic()
        self.previous_write = {"frame_sequence": row["frame_sequence"],
                               "started_host_s": started, "finished_host_s": finished,
                               "wall_ms": (finished - started) * 1000}

    def _run(self) -> None:
        """Own all file writes and preserve FIFO reference-before-query ordering.

        Args: None.
        Returns:
            None: Failures retain counters; final-file absence means incomplete.
        """
        try:
            (self.output / "metadata.json").write_text(json.dumps(self.metadata, indent=2) + "\n")
            with (self.output / "updates.jsonl").open("x") as log:
                while not self.stopping.is_set() or not self.queue.empty():
                    try:
                        row, pixels, enqueued = self.queue.get(timeout=0.05)
                    except queue.Empty:
                        continue
                    self._write(log, row, pixels, enqueued)
                    with self.lock:
                        self.written += 1
        except Exception as error:
            with self.lock:
                self.error = str(error)
            # Producer keeps recognition alive and supplies final counters at stop.
            self.stopping.wait()
        finally:
            with self.lock:
                self.finished = True
            final = dict(self.final_context, last_log_write=self.previous_write,
                         recording=self.snapshot())
            try:
                (self.output / "timing-final.json").write_text(json.dumps(final, indent=2) + "\n")
            except Exception as error:
                with self.lock:
                    self.error = f"Final timing record failed: {error}"
