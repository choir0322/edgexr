"""Receive IMU polling-rate requests from the servo controller's stdin pipe."""
from __future__ import annotations

import math
import os
import select


class CommandPolling:
    """Use slow reads at rest and fast reads when the controller requests them."""

    def __init__(self, idle_seconds: float, active_seconds: float) -> None:
        """Initialize the explicit two-rate policy; do not touch the IMU hardware.

        Args:
            idle_seconds (float): Post-read sleep at rest, in seconds.
            active_seconds (float): Post-read sleep during motion; at most idle sleep.

        Returns:
            None: Holds observed transitions and whole-recording sample counts.
        """
        if (not all(math.isfinite(x) and x > 0 for x in (idle_seconds,active_seconds))
                or active_seconds > idle_seconds):
            raise ValueError('Active sleep must be positive and no longer than idle sleep')
        self.intervals = {'idle':idle_seconds,'fast':active_seconds}
        self.mode = 'idle'
        self.pending = b''
        self.transitions = [dict(host_s=0.,mode='idle',sleep_seconds=idle_seconds)]
        self.counts = {'idle':0,'fast':0}

    @property
    def interval(self) -> float:
        """Return the current post-read sleep in seconds.

        Args:
            None.

        Returns:
            float: Selected idle or active interval.
        """
        return self.intervals[self.mode]

    def poll(self, fd: int, host_s: float) -> None:
        """Consume available complete control lines without waiting for input.

        Args:
            fd (int): Pipe descriptor carrying only fast/idle newline-delimited requests.
            host_s (float): Current recorder host time relative to its monotonic origin.

        Returns:
            None: Applies/logs requests; broken, malformed or oversized input fails.
        """
        if not select.select([fd],[],[],0)[0]:
            return
        data = os.read(fd,256)
        if not data:
            raise RuntimeError('IMU control pipe closed before recording completed')
        self.pending += data
        if len(self.pending) > 256:
            raise ValueError('IMU control message exceeds bounded input size')
        # A pipe may deliver part of a line. Preserve that fragment until a later
        # poll rather than block the acquisition loop waiting for its newline.
        while b'\n' in self.pending:
            line,self.pending = self.pending.split(b'\n',1)
            if line not in (b'fast',b'idle'):
                raise ValueError('Invalid IMU control request')
            mode = line.decode('ascii')
            if mode != self.mode:
                self.mode = mode
                self.transitions.append(dict(host_s=host_s,mode=mode,
                                             sleep_seconds=self.interval))
