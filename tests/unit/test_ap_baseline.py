"""Hardware-free checks for the read-only AP baseline collector."""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from profiling.ap_baseline import (
    ProcessReading,
    model_paths,
    parse_proc_stat,
    parse_proc_status,
    parse_system_cpu,
    process_cpu_percent,
    read_counters,
    summarize,
    system_cpu_percent,
    validate_preview,
)


def stat_line(pid: int, parent: int, user: int, system: int, start: int) -> str:
    """Build a fixture with the relevant Linux stat fields in their real positions.

    Args:
        pid (int): Process ID used in the fixture.
        parent (int): Parent ID, represented in status rather than stat here.
        user (int): Cumulative user CPU ticks.
        system (int): Cumulative system CPU ticks.
        start (int): Process start ticks since boot.

    Returns:
        str: Minimal stat line whose comm contains spaces and parentheses.
    """
    fields = ["0"] * 22
    fields[0] = "S"
    fields[1] = str(parent)
    fields[11] = str(user)
    fields[12] = str(system)
    fields[19] = str(start)
    return f"{pid} (edge (preview) process) " + " ".join(fields)


class ApBaselineTests(unittest.TestCase):
    """Protect process identity, mode selection and non-duplicated summaries."""

    def test_parses_process_and_host_counters(self) -> None:
        """Read Linux fields and calculate CPU usage in the documented units.

        Args:
            None.

        Returns:
            None: Asserts fixture interpretations.
        """
        self.assertEqual(parse_proc_stat(stat_line(123, 1, 50, 25, 999), 123), (75, 999))
        self.assertEqual(parse_proc_status("Name:\ttest\nPPid:\t1\nVmRSS:\t2048 kB\n"), (1, 2048))
        self.assertEqual(parse_system_cpu("cpu  100 0 20 80 5 0 0\n"), (205, 85))
        old = ProcessReading(123, 1, 999, 75, 2048)
        new = ProcessReading(123, 1, 999, 125, 3072)
        self.assertEqual(process_cpu_percent(old, new, 1, 100), 50)
        self.assertEqual(system_cpu_percent((205, 85), (305, 105)), 80)
        with self.assertRaisesRegex(ValueError, "identity"):
            process_cpu_percent(old, ProcessReading(123, 1, 1000, 125, 3072), 1, 100)

    def test_rejects_wrong_mode_or_missing_pid(self) -> None:
        """A running motion-aware trial is not silently accepted as basic mode.

        Args:
            None.

        Returns:
            None: Checks explicit preflight failures.
        """
        snapshot = {
            "status": "live", "preview_pid": 100, "ffmpeg_pid": 101,
            "detector": {"status": "ready", "tracking_mode": "motion-aware"},
            "imu": {"status": "ready", "camera_axis_mode": "off",
                    "camera_axis_conversions": 0},
        }
        with self.assertRaisesRegex(ValueError, "without --motion-aware-tracking"):
            validate_preview(snapshot)
        snapshot["detector"]["tracking_mode"] = "basic"
        self.assertEqual(validate_preview(snapshot), (100, 101))
        with self.assertRaisesRegex(ValueError, "Camera-axis mode"):
            validate_preview(snapshot, "on")
        snapshot["imu"].update(camera_axis_mode="on", camera_axis_conversions=12)
        self.assertEqual(validate_preview(snapshot, "on"), (100, 101))
        snapshot["imu"].update(camera_axis_mode="off", camera_axis_conversions=0)
        snapshot["ffmpeg_pid"] = None
        with self.assertRaisesRegex(ValueError, "process IDs"):
            validate_preview(snapshot)

    def test_reads_exact_child_process(self) -> None:
        """Reject an unrelated FFmpeg process while reading fake proc files.

        Args:
            None.

        Returns:
            None: Verifies parent-child matching.
        """
        with TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            for pid, parent in ((100, 1), (101, 100)):
                folder = root / str(pid)
                folder.mkdir()
                (folder / "stat").write_text(stat_line(pid, parent, 10, 5, pid * 10))
                (folder / "status").write_text(f"PPid:\t{parent}\nVmRSS:\t1024 kB\n")
            (root / "stat").write_text("cpu 1 2 3 4 5 6 7\n")
            readings = read_counters(100, 101, root)
            self.assertEqual(readings[0].rss_kib, 1024)
            self.assertEqual(readings[1].parent_pid, 100)
            (root / "101" / "status").write_text("PPid:\t999\nVmRSS:\t1024 kB\n")
            with self.assertRaisesRegex(ValueError, "not a child"):
                read_counters(100, 101, root)

    def test_model_paths_follow_preview_arguments(self) -> None:
        """Resolve default and explicit model paths from the running process.

        Args:
            None.

        Returns:
            None: Checks lookup without loading model files.
        """
        with TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            folder = root / "100"
            folder.mkdir()
            (folder / "cwd").symlink_to(root)
            (folder / "cmdline").write_bytes(b"python3\0-m\0app.live_preview\0")
            graph, weights = model_paths(100, root)
            self.assertEqual(graph, root / "models/mobilenet-ssd/deploy.prototxt")
            self.assertEqual(weights, root / "models/mobilenet-ssd/mobilenet_iter_73000.caffemodel")
            (folder / "cmdline").write_bytes(b"python3\0--prototxt\0other/graph.prototxt\0--weights\0/tmp/model.bin\0")
            self.assertEqual(model_paths(100, root), (root / "other/graph.prototxt", Path("/tmp/model.bin")))

    def test_summarizes_distinct_detector_results(self) -> None:
        """Repeated HTTP polls do not multiply the compute-time sample count.

        Args:
            None.

        Returns:
            None: Checks distributions, skipped delta and thermal windows.
        """
        samples = []
        for index, sequence in enumerate((3, 3, 4)):
            samples.append({
                "observed_s": (10, 20, 290)[index],
                "camera_status": "live", "imu_status": "ready", "detector_status": "ready",
                "throttle_flag_raw": "0x0", "detector_sequence": sequence,
                "detector_compute_ms_latest": (200, 200, 240)[index],
                "box_source_age_ms": (300, 400, 500)[index],
                "temperature_c_thermal_zone0": (50, 51, 60)[index],
                "skipped_decoded_frames_total": (4, 4, 7)[index],
                "capture_fps": 30, "analysis_fps": 25,
                "camera_axis_conversions_total": (0, 10, 20)[index],
            })
        report = summarize(samples, 300)
        self.assertEqual(report["distinct_detector_updates_observed"], 2)
        self.assertEqual(report["detector_compute_ms_distinct"]["median"], 220)
        self.assertEqual(report["skipped_decoded_frames_increase"], 3)
        self.assertEqual(report["camera_axis_conversions_increase"], 20)
        self.assertEqual(report["temperature_first_minute_c"]["median"], 50.5)
        self.assertEqual(report["temperature_last_minute_c"]["median"], 60)
        json.dumps(report, allow_nan=False)


if __name__ == "__main__":
    unittest.main()
