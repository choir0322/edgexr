from __future__ import annotations
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
import json

from recording.analyze_capture import analyze_stationary, timing, integrate, mean_axes


class CaptureAnalysisTests(unittest.TestCase):
    def test_stationary_report_excludes_startup_and_detects_bias_change(self) -> None:
        """Check one complete synthetic recording with known timing and drift.

        Args:
            None.

        Returns:
            None: Assertions fail if windowing, units or gap reporting changes.
        """
        with TemporaryDirectory() as temporary:
            folder = Path(temporary)
            metadata = dict(
                status="complete", requested_seconds_after_first_frame=30,
                recording_cue_host_s=10, decoded_frames=6, imu_samples=11,
                requested_mode="1280x720 MJPEG 30 fps", imu_sleep_seconds=.05,
            )
            (folder / "metadata.json").write_text(json.dumps(metadata))
            (folder / "frames.csv").write_text(
                "frame_index,camera_pts_s,host_receipt_s\n"
                "0,0,9\n1,1,10\n2,2,11\n3,3,20\n4,4,30\n5,5,39\n"
            )
            (folder / "imu.csv").write_text(
                "host_read_midpoint_s,read_duration_s,ax_g,ay_g,az_g,gx_dps,gy_dps,gz_dps\n"
                "9,.002,0,0,1,99,99,99\n"
                "10,.002,0,0,1,1,2,3\n11,.002,0,0,1,1,2,3\n"
                "12,.002,0,0,1,1,2,3\n13,.002,0,0,1,1,2,3\n"
                "14,.002,0,0,1,1,2,3\n30,.004,0,0,1,3,4,5\n"
                "31,.004,0,0,1,3,4,5\n32,.004,0,0,1,3,4,5\n"
                "38,.006,0,0,1,3,4,5\n39,.006,0,0,1,3,4,5\n"
            )
            report = analyze_stationary(folder, 10)
            self.assertEqual(report["first_gyro_mean_dps"], [1, 2, 3])
            self.assertEqual(report["last_gyro_mean_dps"], [3, 4, 5])
            self.assertEqual(report["gyro_mean_change_dps"], [2, 2, 2])
            self.assertEqual(report["first_still_samples"], 5)
            self.assertEqual(report["imu_long_gap_count"], 2)
            self.assertEqual(report["camera_pts"]["count"], 5)
            self.assertEqual(report["imu_read_duration_ms_p95"], 6)

    def test_timing_preserves_startup_gap_and_nearest_rank_percentile(self) -> None:
        """Verify timing preserves startup gap and nearest rank percentile.

        Args:
            None.

        Returns:
            None: unittest assertions fail if the expected contract is violated.
        """
        # Keep the large startup interval in statistics, then reject invalid clocks.
        result = timing([0, 0.15, 0.18, 0.21])
        self.assertAlmostEqual(result["max_gap_ms"], 150)
        self.assertAlmostEqual(result["median_gap_ms"], 30)
        self.assertAlmostEqual(result["p95_gap_ms"], 150)
        self.assertAlmostEqual(result["rate_hz"], 3 / 0.21)
        for times in ([0], [0, 0], [1, 0], [0, float("nan")]):
            with self.assertRaises(ValueError):
                timing(times)

    def test_irregular_turn_return_cancels_with_independent_bias(self) -> None:
        """Verify irregular turn return cancels with independent bias.

        Args:
            None.

        Returns:
            None: unittest assertions fail if the expected contract is violated.
        """
        # Use unequal sample intervals and a known independent bias; the outward
        # and return areas should cancel without normalizing the gyro rates.
        rows = [
            dict(host_read_midpoint_s=t, gx_dps=2, gy_dps=y + 3, gz_dps=4)
            for t, y in [(0, 0), (1, 10), (3, 0), (5, -10), (6, 0)]
        ]
        path = integrate(rows, [2, 3, 4])
        self.assertEqual(path[-1][1:], [0, 0, 0])
        self.assertEqual(max(r[2] for r in path), 15)

    def test_mean_does_not_normalize_gyro(self) -> None:
        """Verify mean does not normalize gyro.

        Args:
            None.

        Returns:
            None: unittest assertions fail if the expected contract is violated.
        """
        rows = [
            dict(gx_dps=-4, gy_dps=15, gz_dps=-3),
            dict(gx_dps=-6, gy_dps=17, gz_dps=-1),
        ]
        self.assertEqual(mean_axes(rows), [-5, 16, -2])
        with self.assertRaises(ValueError):
            mean_axes(rows[:1])
