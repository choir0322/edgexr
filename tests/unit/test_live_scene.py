"""Hardware-free checks for scene mailbox, timing association and live worker."""

import json
from pathlib import Path
import tempfile
import threading
import time
import unittest

import numpy as np
from app.live_preview import State, make_server
from imu.live_reader import LiveImu
from spatial.live_scene import LiveScene, scene_latest
from spatial.scene_memory import prepare_gray
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from unittest.mock import patch
from functools import partial
from spatial.scene_recorder import SceneRecorder


class LiveSceneTests(unittest.TestCase):
    def test_recognition_continues_during_image_write(self) -> None:
        """Publish another real ORB result while the first PNG save is blocked.

        Args: None.
        Returns: None.
        """
        try:
            import cv2 as cv
        except ImportError:
            self.skipTest("OpenCV required")
        entered, release = threading.Event(), threading.Event()
        original = cv.imwrite

        def delayed(path: str, image: np.ndarray) -> bool:
            """Simulate slow encoding/storage without blocking the producer.

            Args:
                path (str): Target PNG path.
                image (np.ndarray): Canonical selected pixels.
            Returns:
                bool: Real OpenCV write result after release.
            """
            entered.set()
            release.wait(5)
            return original(path, image)

        state = State(scene_memory=True)
        now = time.monotonic()
        state.scene.enroll(now - 0.1)
        pixels = np.random.default_rng(17).integers(0, 256, (720, 1280), dtype=np.uint8).tobytes()
        state.publish_frame(bytes(320 * 180), now, pixels)
        with tempfile.TemporaryDirectory() as folder, patch.object(cv, "imwrite", delayed), \
                patch("spatial.live_scene.SceneRecorder", partial(SceneRecorder, capacity=1)):
            worker = threading.Thread(target=scene_latest,
                                      args=(state, cv, Path(folder) / "trial", True))
            worker.start()
            try:
                self.assertTrue(entered.wait(3))
                deadline = time.monotonic() + 2.5
                # Keep the latest source fresh until the target-1Hz worker selects it.
                while time.monotonic() < deadline:
                    state.publish_frame(bytes(320 * 180), time.monotonic(), pixels)
                    if state.scene.result and state.scene.result["decision"]["state"] == "known":
                        break
                    time.sleep(0.02)
                self.assertEqual(state.scene.result["decision"]["state"], "known")
                self.assertEqual(state.scene.recorder.snapshot()["written"], 0)
                self.assertIsNone(state.scene.error)
                self.assertEqual(state.scene.recorder.snapshot()["queued"], 1)
                label = state.scene.enroll(time.monotonic())
                deadline = time.monotonic() + 1.5
                while time.monotonic() < deadline:
                    state.publish_frame(bytes(320 * 180), time.monotonic(), pixels)
                    if state.scene.recorder.snapshot()["dropped"]:
                        break
                    time.sleep(0.02)
                self.assertGreater(state.scene.recorder.snapshot()["dropped"], 0)
                self.assertEqual(state.scene.snapshot(time.monotonic(), True)["pending_label"], label)
                release.set()
                deadline = time.monotonic() + 2
                while time.monotonic() < deadline:
                    state.publish_frame(bytes(320 * 180), time.monotonic(), pixels)
                    if state.scene.result.get("enrollment_requested") == label:
                        break
                    time.sleep(0.02)
                self.assertEqual(state.scene.result["decision"]["state"], "enrolled")
                self.assertEqual(state.scene.result["decision"]["label"], label)
            finally:
                state.stop.set()
                release.set()
                worker.join(5)
            rows = [json.loads(line) for line in (Path(folder) / "trial" / "updates.jsonl").read_text().splitlines()]
            self.assertGreaterEqual(len(rows), 2)
            self.assertEqual(rows[1]["reference_images"]["1"], rows[0]["image"])
            last = rows[-1]
            self.assertEqual(last["reference_images"]["2"], last["image"])
            self.assertTrue((Path(folder) / "trial" / last["image"]).is_file())

    def test_opt_in_image_matches_source(self) -> None:
        """Recorded query and reference point to the selected canonical image.

        Args: None.
        Returns: None.
        """
        try:
            import cv2 as cv
        except ImportError:
            self.skipTest("OpenCV required")
        state = State(scene_memory=True)
        now = time.monotonic()
        state.scene.enroll(now - 0.1)
        gray = np.random.default_rng(7).integers(0, 256, (720, 1280), dtype=np.uint8)
        state.publish_frame(bytes(320 * 180), now, gray.tobytes())
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "trial"
            worker = threading.Thread(target=scene_latest, args=(state, cv, output, True))
            worker.start()
            deadline = time.monotonic() + 5
            while state.scene.result is None and not state.scene.error and time.monotonic() < deadline:
                time.sleep(0.01)
            state.stop.set()
            worker.join(5)
            self.assertIsNone(state.scene.error)
            row = json.loads((output / "updates.jsonl").read_text().splitlines()[0])
            self.assertEqual(row["reference_images"]["1"], row["image"])
            self.assertEqual(row["view_map"]["current_scene_id"], 1)
            self.assertEqual(len(row["view_map"]["nodes"]), 1)
            self.assertGreaterEqual(row["view_map_update_ms"], 0)
            saved = cv.imread(str(output / row["image"]), cv.IMREAD_GRAYSCALE)
            np.testing.assert_array_equal(saved, prepare_gray(cv, gray))
            self.assertGreaterEqual(row["image_write_ms"], 0)
            self.assertTrue(json.loads((output / "metadata.json").read_text())["save_images"])

    def test_existing_output_is_preserved(self) -> None:
        """A recording path collision fails scene startup without overwriting evidence.

        Args: None.
        Returns: None.
        """
        try:
            import cv2 as cv
        except ImportError:
            self.skipTest("OpenCV required")
        state = State(scene_memory=True)
        with tempfile.TemporaryDirectory() as folder:
            marker = Path(folder) / "metadata.json"
            marker.write_text("existing evidence")
            scene_latest(state, cv, Path(folder))
            self.assertIsNotNone(state.scene.error)
            self.assertEqual(marker.read_text(), "existing evidence")

    def test_mailbox_and_freshness(self) -> None:
        """Consume a click once, only on a newer frame; age independently.

        Args: None.
        Returns: None.
        """
        scene = LiveScene(True)
        self.assertEqual(scene.enroll(10), "View-1")
        with self.assertRaises(ValueError):
            scene.enroll(11)
        self.assertIsNone(scene.take_request(9))
        self.assertEqual(scene.take_request(11), "View-1")
        self.assertIsNone(scene.take_request(12))
        scene.result = {"frame_host_s": 11, "decision": {"state": "known"}}
        self.assertEqual(scene.snapshot(12, True)["status"], "ready")
        self.assertEqual(scene.snapshot(14, True)["status"], "stale")
        self.assertEqual(scene.snapshot(12, False)["status"], "stale")

    def test_preceding_orientation_only(self) -> None:
        """No future or old orientation may masquerade as frame context.

        Args: None.
        Returns: None.
        """
        imu = LiveImu(True, [[1, 0, 0], [0, 1, 0], [0, 0, 1]], True)
        imu.offset = (0, 0, 0)
        imu.publish(10, (0, 0, 0))
        imu.publish(10.1, (0, 1, 0))
        self.assertEqual(imu.orientation_at(10.05)["sample_monotonic_s"], 10)
        self.assertEqual(imu.orientation_at(9)["status"], "unknown")
        self.assertEqual(imu.orientation_at(11)["status"], "unknown")
        imu.fail("lost sensor")
        self.assertEqual(imu.orientation_at(10.15)["status"], "unknown")

    def test_worker_records_enrollment(self) -> None:
        """Use real ORB, preserving timestamps and writing no image payload.

        Args: None.
        Returns: None.
        """
        try:
            import cv2 as cv
        except ImportError:
            self.skipTest("OpenCV required")
        state = State(scene_memory=True)
        now = time.monotonic()
        state.scene.enroll(now - 0.1)
        pixels = np.random.default_rng(4).integers(0, 256, (720, 1280), dtype=np.uint8).tobytes()
        state.publish_frame(bytes(320 * 180), now, pixels)
        self.assertIsNone(state.detection_frame)
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "trial"
            worker = threading.Thread(target=scene_latest, args=(state, cv, output))
            worker.start()
            deadline = time.monotonic() + 5
            while state.scene.result is None and not state.scene.error and time.monotonic() < deadline:
                time.sleep(0.01)
            state.stop.set()
            worker.join(5)
            self.assertFalse(worker.is_alive())
            self.assertIsNone(state.scene.error)
            row = json.loads((output / "updates.jsonl").read_text().splitlines()[0])
            self.assertEqual(row["decision"]["state"], "enrolled")
            self.assertEqual(row["frame_host_s"], now)
            self.assertEqual(row["orientation_at_frame"]["status"], "unknown")
            self.assertEqual(set(p.name for p in output.iterdir()), {"metadata.json", "updates.jsonl", "timing-final.json"})
            self.assertIn("scene_thread_cpu_ms", row)
            self.assertIn("imu_poll_timing", row)

    def test_enrollment_http_origin(self) -> None:
        """Mutation requires the exact local origin; GET cannot enroll.

        Args: None.
        Returns: None.
        """
        state = State(scene_memory=True)
        server = make_server(state, 0)
        host = f"http://127.0.0.1:{server.server_port}"
        thread = threading.Thread(target=server.serve_forever)
        thread.start()
        try:
            with self.assertRaises(HTTPError) as error:
                urlopen(Request(host + "/api/scene/enroll", method="POST"))
            self.assertEqual(error.exception.code, 403)
            request = Request(host + "/api/scene/enroll", method="POST", headers={"Origin": host})
            with urlopen(request) as response:
                self.assertEqual(response.status, 202)
            with self.assertRaises(HTTPError) as error:
                urlopen(host + "/api/scene/enroll")
            self.assertEqual(error.exception.code, 404)
        finally:
            server.shutdown()
            thread.join()
            server.server_close()
