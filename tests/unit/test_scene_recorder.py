"""Deterministic slow-write, admission, ownership and shutdown checks."""

import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from typing import Any

from spatial.scene_recorder import SceneRecorder


class SceneRecorderTests(unittest.TestCase):
    def test_bounded_queue_defers_enrollment_and_preserves_fifo(self) -> None:
        """A blocked write cannot grow the queue or silently consume enrollment.

        Args: None.
        Returns: None.
        """
        entered, release = threading.Event(), threading.Event()
        original = SceneRecorder._write

        def delayed(writer: SceneRecorder, log: Any, row: dict,
                    pixels: bytes | None, enqueued: float) -> None:
            """Hold disk processing while the producer fills the queue.

            Args:
                writer (SceneRecorder): Test writer.
                log (Any): Text output stream.
                row (dict): Private record.
                pixels (bytes | None): Optional image bytes.
                enqueued (float): Monotonic submission time.
            Returns: None.
            """
            entered.set()
            release.wait(5)
            original(writer, log, row, pixels, enqueued)

        with tempfile.TemporaryDirectory() as folder, patch.object(SceneRecorder, "_write", delayed):
            writer = SceneRecorder(Path(folder), None, {}, capacity=1)
            try:
                row = {"frame_sequence": 1, "decision": {"state": "enrolled"}}
                self.assertTrue(writer.submit(row, None))
                self.assertTrue(entered.wait(2))
                row["decision"]["state"] = "mutated"
                self.assertTrue(writer.submit({"frame_sequence": 2}, None))
                self.assertFalse(writer.can_enroll())
                self.assertFalse(writer.submit({"frame_sequence": 3}, None))
                self.assertEqual(writer.snapshot()["queued"], 1)
                self.assertEqual(writer.snapshot()["dropped"], 1)
            finally:
                release.set()
                status = writer.close({"imu_poll_timing": {"polls": 7}})
            self.assertEqual(status["status"], "partial")
            self.assertEqual(status["written"], 2)
            rows = [json.loads(line) for line in (Path(folder) / "updates.jsonl").read_text().splitlines()]
            self.assertEqual([r["frame_sequence"] for r in rows], [1, 2])
            self.assertEqual(rows[0]["decision"]["state"], "enrolled")
            self.assertNotIn("previous_log_write", row)
            self.assertEqual(rows[1]["previous_log_write"]["frame_sequence"], 1)
            final = json.loads((Path(folder) / "timing-final.json").read_text())
            self.assertEqual(final["recording"]["dropped"], 1)
            self.assertEqual(final["last_log_write"]["frame_sequence"], 2)
            self.assertEqual(final["imu_poll_timing"]["polls"], 7)

    def test_error_is_explicit_and_does_not_accept_more_evidence(self) -> None:
        """Failed serialization is recording failure, not successful evidence.

        Args: None.
        Returns: None.
        """
        with tempfile.TemporaryDirectory() as folder:
            writer = SceneRecorder(Path(folder), None, {})
            writer.submit({"frame_sequence": 1, "bad": float("nan")}, None)
            status = writer.close({})
            self.assertEqual(status["status"], "error")
            self.assertEqual(status["written"], 0)
            self.assertEqual(status["accepted_not_written"], 1)
            self.assertFalse(writer.can_enroll())
            self.assertFalse(writer.submit({"frame_sequence": 2}, None))
            self.assertEqual(writer.snapshot()["dropped"], 1)

    def test_shutdown_timeout_is_incomplete(self) -> None:
        """A blocked disk operation does not permit a successful shutdown claim.

        Args: None.
        Returns: None.
        """
        entered, release = threading.Event(), threading.Event()

        def stalled(writer: SceneRecorder, log: Any, row: dict,
                    pixels: bytes | None, enqueued: float) -> None:
            """Hold one write until explicitly released by the test.

            Args:
                writer (SceneRecorder): Recorder under test.
                log (Any): Stream.
                row (dict): Record.
                pixels (bytes | None): Image payload.
                enqueued (float): Submission time.
            Returns: None.
            """
            entered.set()
            release.wait(5)

        with tempfile.TemporaryDirectory() as folder, patch.object(SceneRecorder, "_write", stalled):
            writer = SceneRecorder(Path(folder), None, {})
            try:
                writer.submit({"frame_sequence": 1}, None)
                self.assertTrue(entered.wait(2))
                status = writer.close({}, timeout=0.01)
                self.assertIn("timed out", status["error"])
            finally:
                release.set()
                writer.thread.join(2)
            final = json.loads((Path(folder) / "timing-final.json").read_text())
            self.assertEqual(final["recording"]["status"], "error")

    def test_empty_recording_drains(self) -> None:
        """No-frame shutdown still records provenance and final status.

        Args: None.
        Returns: None.
        """
        with tempfile.TemporaryDirectory() as folder:
            writer = SceneRecorder(Path(folder), None, {"timing_schema": 2})
            self.assertEqual(writer.close({})["status"], "complete")
            self.assertEqual((Path(folder) / "updates.jsonl").read_text(), "")
