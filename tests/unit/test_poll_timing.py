"""Deterministic timing attribution without hardware or sleeping."""
import unittest
from imu.live_reader import LiveImu


class PollTimingTests(unittest.TestCase):
    def test_stage_durations_and_bounded_events(self) -> None:
        """Separate read, publication and late-wake wall intervals.

        Args: None.
        Returns: None.
        """
        imu = LiveImu(True)
        imu.record_poll_timing(1, 1.03, 1.07, .7, .9)
        result = imu.timing_snapshot()
        self.assertEqual(result['gaps_over_200ms'], 1)
        for key, expected in [('read_ms', 30), ('publish_ms', 40), ('wake_late_ms', 100), ('midpoint_gap_ms', 315)]:
            self.assertAlmostEqual(result['max_ms'][key], expected)
        for i in range(100):
            imu.record_poll_timing(i + 2, i + 2.03, i + 2.04, None, None)
        self.assertEqual(len(imu.timing_snapshot()['recent_slow_polls']), 64)
        self.assertEqual(imu.timing_snapshot()['polls'], 101)

    def test_fast_poll_and_missing_previous_sample(self) -> None:
        """A normal first read creates no fabricated gap or slow event.

        Args: None.
        Returns: None.
        """
        imu = LiveImu(True)
        imu.record_poll_timing(1, 1.002, 1.003, None, None)
        result = imu.timing_snapshot()
        self.assertEqual(result['gaps_over_200ms'], 0)
        self.assertEqual(result['recent_slow_polls'], [])
