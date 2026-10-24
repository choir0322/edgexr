"""Opt-in Linux process observations during the camera/IMU recording window."""

from __future__ import annotations

from dataclasses import asdict
import os
import time
from typing import Any, Callable

from profiling.ap_baseline import (
    ProcessReading, process_cpu_percent, read_process, read_temperature,
    read_throttle_flag,
)


class CaptureResources:
    """Collect cumulative CPU counters at the cue, roughly 1 Hz, and capture end."""

    def __init__(self, recorder_pid: int, ffmpeg_pid: int, *,
                 clock: Callable[[], float] = time.monotonic,
                 reader: Callable[[int], ProcessReading] = read_process,
                 temperature: Callable[[], float | None] = read_temperature,
                 throttle: Callable[[], str | None] = read_throttle_flag,
                 ticks_per_second: int | None = None) -> None:
        """Start observations after camera startup, at the recording cue.

        Args:
            recorder_pid (int): Camera/IMU Python process, including its log thread.
            ffmpeg_pid (int): Owned camera subprocess, still alive at final observation.
            clock (Callable[[], float]): Monotonic seconds; injectable for tests.
            reader (Callable[[int], ProcessReading]): Linux counters or synthetic fixture.
            temperature (Callable[[], float | None]): Thermal reading or unavailable.
            throttle (Callable[[], str | None]): Adjacent firmware flags or unavailable.
            ticks_per_second (int | None): Kernel clock tick rate; default SC_CLK_TCK.

        Returns:
            None: Stores observations in memory; no extra polling thread is created.
        """
        self.pids = (recorder_pid, ffmpeg_pid)
        self.clock, self.reader, self.temperature = clock, reader, temperature
        self.throttle = throttle
        self.ticks = ticks_per_second or int(os.sysconf('SC_CLK_TCK'))
        self.samples: list[dict[str, Any]] = []
        self.error: str | None = None
        self.throttle_start = throttle()
        self.poll(force=True)

    def poll(self, *, force: bool = False) -> None:
        """Observe both processes if at least one second has elapsed.

        Args:
            force (bool): Request an endpoint observation regardless of elapsed time.

        Returns:
            None: Saves raw counters, or records an error that invalidates CPU totals.
        """
        if self.error:
            return
        now = self.clock()
        if not force and self.samples and now-self.samples[-1]['monotonic_s'] < 1:
            return
        try:
            recorder, ffmpeg = (self.reader(pid) for pid in self.pids)
            self.samples.append(dict(monotonic_s=self.clock(),
                                     recorder=asdict(recorder), ffmpeg=asdict(ffmpeg),
                                     temperature_c=self.temperature()))
        except (OSError, ValueError) as error:
            self.error = str(error)

    def finish(self, *, complete: bool) -> dict[str, Any]:
        """Take the final counters before camera shutdown and summarize CPU work.

        Args:
            complete (bool): Whether the normal requested recording end was reached.

        Returns:
            dict[str, Any]: Raw observations and summary, or explicit failure status.
        """
        self.poll(force=True)
        result: dict[str, Any] = dict(
            status='incomplete', error=self.error, samples=self.samples,
            ticks_per_second=self.ticks,
            throttle_before=self.throttle_start, throttle_after=self.throttle(),
            scope=('Recording cue to pre-shutdown host observations. Recorder '
                   'CPU includes IMU reads, CSV writes, camera-log thread and '
                   'this observer. FFmpeg CPU is separate. Servo parent, startup, '
                   'shutdown, offline analysis and electrical energy are excluded. '
                   '100% CPU means one logical CPU. RSS is sampled, not a peak '
                   'allocation or unique physical-memory measurement.'),
        )
        if not complete or self.error or len(self.samples) < 2:
            result['error'] = self.error or 'Recording window did not complete'
            return result
        first, last = self.samples[0], self.samples[-1]
        elapsed = last['monotonic_s']-first['monotonic_s']
        summary: dict[str, Any] = dict(measured_seconds=elapsed,
                                       observation_count=len(self.samples))
        try:
            # Validate every identity/counter interval, then use cumulative
            # endpoint differences for total CPU work, independent of poll count.
            for name in ('recorder', 'ffmpeg'):
                for a,b in zip(self.samples,self.samples[1:]):
                    process_cpu_percent(ProcessReading(**a[name]),
                                        ProcessReading(**b[name]),
                                        b['monotonic_s']-a['monotonic_s'],self.ticks)
                seconds = (last[name]['cpu_ticks']-first[name]['cpu_ticks'])/self.ticks
                summary[f'{name}_cpu_seconds'] = seconds
                summary[f'{name}_mean_cpu_pct_one_core'] = 100*seconds/elapsed
                memory = [s[name]['rss_kib'] for s in self.samples
                          if s[name]['rss_kib'] is not None]
                summary[f'{name}_max_sampled_rss_mib'] = max(memory)/1024 if memory else None
        except ValueError as error:
            result['error'] = str(error)
            return result
        summary['combined_cpu_seconds'] = sum(summary[f'{n}_cpu_seconds']
                                              for n in ('recorder','ffmpeg'))
        summary['combined_mean_cpu_pct_one_core'] = 100*summary['combined_cpu_seconds']/elapsed
        summary['temperature_first_c'] = first['temperature_c']
        summary['temperature_last_c'] = last['temperature_c']
        result.update(status='complete', summary=summary)
        return result
