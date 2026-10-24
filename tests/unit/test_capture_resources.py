"""Synthetic CPU accounting and failure tests, requiring no Pi or /proc."""
from __future__ import annotations

import unittest
from profiling.ap_baseline import ProcessReading
from profiling.capture_resources import CaptureResources


class CaptureResourceTests(unittest.TestCase):
    """Check cumulative work, observation cadence and invalid process histories."""

    def make_monitor(self) -> tuple[CaptureResources, list[float], list[int]]:
        """Create a monitor with a controlled clock and known process counters.

        Args:
            None.

        Returns:
            tuple: Monitor, mutable seconds and log of process reads.
        """
        now, calls = [0.], []

        def read(pid: int) -> ProcessReading:
            """Return CPU ticks that grow 20/35 ticks per second by process.

            Args:
                pid (int): Fake recorder 1 or FFmpeg 2.

            Returns:
                ProcessReading: Fixed process identity and synthetic RSS/counters.
            """
            calls.append(pid)
            return ProcessReading(pid, 0, 10, 100+int(now[0]*(20 if pid == 1 else 35)),
                                  1024*pid)

        monitor = CaptureResources(1,2,clock=lambda:now[0],reader=read,
                                   temperature=lambda:45., throttle=lambda:'0x0',
                                   ticks_per_second=100)
        return monitor,now,calls

    def test_cpu_seconds_and_one_core_percent_use_endpoint_deltas(self) -> None:
        """Equal elapsed time gives known CPU work independent of intermediate polls.

        Args:
            None.

        Returns:
            None: Checks separate counters, combined totals and sampled memory.
        """
        monitor,now,calls = self.make_monitor()
        now[0] = .4
        monitor.poll()
        self.assertEqual(len(calls),2)
        now[0] = 1.
        monitor.poll()
        now[0] = 2.
        report = monitor.finish(complete=True)
        self.assertEqual(report['status'],'complete')
        summary = report['summary']
        self.assertAlmostEqual(summary['recorder_cpu_seconds'],.4)
        self.assertAlmostEqual(summary['ffmpeg_cpu_seconds'],.7)
        self.assertAlmostEqual(summary['combined_cpu_seconds'],1.1)
        self.assertAlmostEqual(summary['recorder_mean_cpu_pct_one_core'],20.)
        self.assertAlmostEqual(summary['combined_mean_cpu_pct_one_core'],55.)
        self.assertEqual(summary['ffmpeg_max_sampled_rss_mib'],2.)
        self.assertEqual(summary['observation_count'],3)

    def test_process_identity_change_or_missing_data_invalidates_totals(self) -> None:
        """A replaced or inaccessible process must not produce trusted CPU totals.

        Args:
            None.

        Returns:
            None: Checks reports have an error and no usable summary.
        """
        monitor,now,_ = self.make_monitor()
        now[0] = 2.
        monitor.reader = lambda pid: ProcessReading(pid,0,99,200,1024)
        report = monitor.finish(complete=True)
        self.assertIn('identity',report['error'])
        self.assertNotIn('summary',report)
        monitor,now,_ = self.make_monitor()

        def missing(pid: int) -> ProcessReading:
            """Simulate a process exiting before its final observation.

            Args:
                pid (int): Process requested by the monitor.

            Returns:
                ProcessReading: Never returns; raises OSError.
            """
            raise OSError('process gone')

        monitor.reader = missing
        now[0] = 2.
        report = monitor.finish(complete=True)
        self.assertEqual(report['error'],'process gone')
        self.assertNotIn('summary',report)
        monitor,now,_ = self.make_monitor()
        monitor.reader = lambda pid: ProcessReading(pid,0,10,0,1024)
        now[0] = 2.
        report = monitor.finish(complete=True)
        self.assertIn('counter',report['error'])
        self.assertNotIn('summary',report)

    def test_incomplete_capture_does_not_claim_complete_measurement(self) -> None:
        """Partial recordings retain observations without complete-window totals.

        Args:
            None.

        Returns:
            None: Checks the incomplete flag and absence of summary.
        """
        monitor,now,_ = self.make_monitor()
        now[0] = 1.
        report = monitor.finish(complete=False)
        self.assertEqual(report['status'],'incomplete')
        self.assertNotIn('summary',report)
