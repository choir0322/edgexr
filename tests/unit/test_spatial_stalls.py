"""Linux accounting fixtures and collector identity/error checks without hardware."""

import io
import json
import argparse
import signal
import subprocess
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, Mock

from profiling.spatial_stalls import cpu_delta, fetch_telemetry, parse_schedstat, parse_stat, read_process, run, stop_child, write_and_wait


def stat_record(pid: int = 42, start: int = 100, cpu: int = 20) -> str:
    """Construct a proc stat fixture with a deliberately awkward task name.

    Args:
        pid (int): Process or task identifier.
        start (int): Identity start ticks.
        cpu (int): User CPU ticks; fixture adds five system ticks.
    Returns:
        str: Linux stat line with state through field 52.
    """
    fields = ["0"] * 50
    fields[0], fields[1] = "S", "10"
    fields[7], fields[9] = "7", "2"
    fields[11], fields[12], fields[19], fields[36] = str(cpu), "5", str(start), "3"
    return f"{pid} (worker (odd) name) " + " ".join(fields)


class SpatialStallTests(unittest.TestCase):
    def test_ram_run_exports_after_collection_and_keeps_scene_path(self) -> None:
        """Exercise collector lifecycle with a fake child and real bounded sink.

        Args: None.
        Returns: None.
        """
        original_exists = Path.exists

        def proc_exists(path: Path) -> bool:
            """Admit the Linux check without requiring Linux on the test host.

            Args: path (Path): Queried file.
            Returns: bool: Real existence except the injected procfs sentinel.
            """
            return str(path) == "/proc/self/stat" or original_exists(path)

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            output = root / "recordings" / "ram"
            args = argparse.Namespace(output=output, device="fake", port=8765,
                seconds=180, interval=.25, scene="fixture", power="unknown", cooling="unknown",
                observer_output="ram", ram_limit_mib=4, ram_export_delay=45)
            child = Mock(pid=42, returncode=0)
            child.poll.side_effect = [None, 0, 0]
            process = {"stat": {"parsed": parse_stat(stat_record())}}
            with patch("profiling.spatial_stalls.Path.cwd", return_value=root), \
                 patch.object(Path, "exists", proc_exists), \
                 patch.object(Path, "is_file", return_value=True), \
                 patch("profiling.spatial_stalls.platform.system", return_value="Linux"), \
                 patch("profiling.spatial_stalls.platform.platform", return_value="Linux fixture"), \
                 patch("profiling.spatial_stalls.shutil.which", return_value="fake"), \
                 patch("profiling.spatial_stalls.socket.socket"), \
                 patch("profiling.spatial_stalls.subprocess.run", return_value=Mock(stdout="fixture")), \
                 patch("profiling.spatial_stalls.subprocess.Popen", return_value=child) as launch, \
                 patch("profiling.spatial_stalls.read_optional", return_value={"text": None, "error": "fixture"}), \
                 patch("profiling.spatial_stalls.read_process", return_value=process), \
                 patch("profiling.spatial_stalls.fetch_telemetry", return_value={"error": "fixture"}), \
                 patch("profiling.spatial_stalls.time.sleep") as sleep, \
                 patch("builtins.print"):
                result = run(args)
            self.assertEqual(result["collector_outcome"], "child_exited")
            self.assertEqual(result["sample_sink"]["mode"], "ram")
            self.assertEqual(result["sample_export"]["status"], "complete")
            self.assertEqual(result["samples"], 1)
            self.assertGreaterEqual(result["sample_export"]["started_host_s"], result["collection_ended_host_s"])
            sleep.assert_any_call(45)
            self.assertTrue((output / "samples.jsonl").is_file())
            self.assertIn(str((output / "scene").resolve()), launch.call_args.args[0])
            self.assertTrue((output / "preview.log").is_file())

    def test_observer_phases_and_previous_cycle_are_separate(self) -> None:
        """Separate serialization, write, sleep and oversleep with a fake clock.

        Args: None.
        Returns: None.
        """
        log = io.StringIO()
        row = {"sample_index": 1, "started_host_s": 10.0,
               "previous_observer_cycle": {"sample_index": 0}}
        timing = {}
        with patch("profiling.spatial_stalls.time.monotonic", side_effect=[10.02, 10.03, 10.04, 10.09, 10.10, 10.27]), patch("profiling.spatial_stalls.time.process_time", side_effect=[0, .005, .005, .006]), patch("profiling.spatial_stalls.time.sleep") as sleep:
            write_and_wait(log, row, .25, timing)
        self.assertAlmostEqual(timing["serialize_wall_ms"], 10)
        self.assertAlmostEqual(timing["write_wall_ms"], 50)
        self.assertAlmostEqual(timing["write_cpu_ms"], 1)
        self.assertAlmostEqual(timing["wake_late_ms"], 20)
        self.assertAlmostEqual(sleep.call_args.args[0], .15)
        self.assertEqual(timing["work_overrun_ms"], 0)
        self.assertEqual(json.loads(log.getvalue()), row)
        self.assertEqual(timing["phase"], "complete")

    def test_overrun_is_not_reported_as_oversleep(self) -> None:
        """A slow write consumes the budget; interrupted phases remain explicit.

        Args: None.
        Returns: None.
        """
        timing = {}
        with patch("profiling.spatial_stalls.time.monotonic", side_effect=[0, .01, .01, 2, 2, 2.001]), patch("profiling.spatial_stalls.time.sleep") as sleep:
            write_and_wait(io.StringIO(), {"sample_index": 0, "started_host_s": 0}, .25, timing)
        sleep.assert_called_once_with(0.0)
        self.assertAlmostEqual(timing["work_overrun_ms"], 1750)
        self.assertAlmostEqual(timing["wake_late_ms"], 1)
        failed = {}
        with self.assertRaises(OSError):
            write_and_wait(Mock(write=Mock(side_effect=OSError("disk"))),
                           {"sample_index": 0, "started_host_s": 0}, .25, failed)
        self.assertEqual(failed["phase"], "write")
        self.assertIn("write_finished_host_s", failed)
        self.assertNotIn("write_completed", failed)
        self.assertNotIn("sleep_started_host_s", failed)

    def test_existing_output_is_preserved_before_launch(self) -> None:
        """Reject a previous evidence folder before starting any hardware process.

        Args: None.
        Returns: None.
        """
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            output = root / "recordings" / "existing"
            output.mkdir(parents=True)
            marker = output / "metadata.json"
            marker.write_text("original evidence")
            with patch("profiling.spatial_stalls.Path.cwd", return_value=root), patch("profiling.spatial_stalls.subprocess.Popen") as launch:
                with self.assertRaises(ValueError):
                    run(argparse.Namespace(output=output))
                launch.assert_not_called()
            self.assertEqual(marker.read_text(), "original evidence")

    def test_cleanup_uses_only_owned_process_and_escalates_on_timeout(self) -> None:
        """Allow graceful draining before killing the owned session on timeout.

        Args: None.
        Returns: None.
        """
        child = Mock(pid=123)
        child.poll.return_value = None
        child.wait.side_effect = [subprocess.TimeoutExpired("preview", 10), 0]
        with patch("profiling.spatial_stalls.os.killpg") as kill:
            stop_child(child)
            child.send_signal.assert_called_once_with(signal.SIGINT)
            kill.assert_called_once_with(123, signal.SIGKILL)
        child = Mock()
        child.poll.return_value = 0
        stop_child(child)
        child.send_signal.assert_not_called()

    def test_stat_and_identity_checked_cpu_delta(self) -> None:
        """Keep correct fields despite parentheses and reject reused task IDs.

        Args: None.
        Returns: None.
        """
        old = parse_stat(stat_record())
        new = parse_stat(stat_record(cpu=45))
        self.assertEqual(old["comm"], "worker (odd) name")
        self.assertEqual((old["minor_faults"], old["major_faults"], old["last_cpu"]), (7, 2, 3))
        self.assertEqual(cpu_delta(old, new, 0.5, 100), 50)
        self.assertIsNone(cpu_delta(old, parse_stat(stat_record(start=200)), 1, 100))
        self.assertIsNone(cpu_delta(new, old, 1, 100))
        self.assertIsNone(cpu_delta(old, new, 0, 100))
        with self.assertRaises(ValueError):
            parse_stat("42 (short) S 1")

    def test_schedstat_units_and_absence(self) -> None:
        """Read ns counters without reinterpreting missing/disabled data as wait.

        Args: None.
        Returns: None.
        """
        value = parse_schedstat("123000000 45000000 17")
        self.assertEqual(value, {"runtime_ns": 123000000, "runqueue_ns": 45000000, "timeslices": 17})
        with self.assertRaises(ValueError):
            parse_schedstat("1 2")
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            process = root / "42"
            task = process / "task" / "43"
            task.mkdir(parents=True)
            (process / "stat").write_text(stat_record())
            (task / "stat").write_text(stat_record(pid=43))
            (task / "schedstat").write_text("0 0 0")
            result = read_process(42, root)
            self.assertEqual(result["tasks"]["43"]["stat"]["parsed"]["id"], 43)
            self.assertEqual(result["tasks"]["43"]["schedstat"]["parsed"]["runqueue_ns"], 0)
            self.assertIsNone(result["io"]["text"])
            self.assertIsNotNone(result["io"]["error"])
            self.assertIsNone(result["schedstat"]["text"])

    def test_telemetry_wrong_pid_and_timeout_do_not_reuse_data(self) -> None:
        """Never associate another app or a previous response with this sample.

        Args: None.
        Returns: None.
        """
        with patch("profiling.spatial_stalls.urlopen", return_value=io.BytesIO(json.dumps({"preview_pid": 8}).encode())):
            rejected = fetch_telemetry(8765, 9)
        self.assertIn("PID", rejected["error"])
        self.assertNotIn("snapshot", rejected)
        with patch("profiling.spatial_stalls.urlopen", side_effect=TimeoutError("late")):
            timed_out = fetch_telemetry(8765, 9)
        self.assertIn("error", timed_out)
        self.assertNotIn("snapshot", timed_out)
        with patch("profiling.spatial_stalls.urlopen", return_value=io.BytesIO(json.dumps({"preview_pid": 9}).encode())):
            accepted = fetch_telemetry(8765, 9)
        self.assertEqual(accepted["snapshot"]["preview_pid"], 9)
        self.assertGreaterEqual(accepted["finished_host_s"], accepted["started_host_s"])


if __name__ == "__main__":
    unittest.main()
