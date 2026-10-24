"""Exercise the real bounded control pipe without servos or an IMU."""
from __future__ import annotations

import os
import unittest
from imu.command_polling import CommandPolling


class CommandPollingTests(unittest.TestCase):
    """Check nonblocking rate selection, transition logging and broken controls."""

    def test_fragmented_requests_switch_only_on_complete_lines(self) -> None:
        """A partial message cannot block acquisition or select the wrong rate.

        Args:
            None.

        Returns:
            None: Checks idle/fast/idle transitions and no-input behavior.
        """
        read_fd,write_fd = os.pipe()
        try:
            policy = CommandPolling(.05,.01)
            policy.poll(read_fd,1.)
            self.assertEqual(policy.interval,.05)
            os.write(write_fd,b'fa')
            policy.poll(read_fd,2.)
            self.assertEqual(policy.interval,.05)
            os.write(write_fd,b'st\n')
            policy.poll(read_fd,2.4)
            self.assertEqual(policy.interval,.01)
            os.write(write_fd,b'fast\nidle\n')
            policy.poll(read_fd,19.6)
            self.assertEqual(policy.interval,.05)
            self.assertEqual([e['mode'] for e in policy.transitions],['idle','fast','idle'])
            self.assertEqual(policy.transitions[1]['host_s'],2.4)
        finally:
            os.close(read_fd)
            os.close(write_fd)

    def test_broken_or_invalid_controls_are_not_silently_accepted(self) -> None:
        """EOF and malformed requests must invalidate the controlled recording.

        Args:
            None.

        Returns:
            None: Checks explicit errors and positive bounded rate selection.
        """
        read_fd,write_fd = os.pipe()
        try:
            policy = CommandPolling(.05,.01)
            os.write(write_fd,b'other\n')
            with self.assertRaisesRegex(ValueError,'Invalid'):
                policy.poll(read_fd,1.)
            os.close(write_fd)
            write_fd = None
            with self.assertRaisesRegex(RuntimeError,'closed'):
                policy.poll(read_fd,2.)
        finally:
            os.close(read_fd)
            if write_fd is not None:
                os.close(write_fd)
        with self.assertRaises(ValueError):
            CommandPolling(.01,.05)
