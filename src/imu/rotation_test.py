"""Read-only, timestamped SH3001 gyro rotation experiment.

First estimate gyro offset while still. Then integrate a separate timed
rotation window. Angles are in sensor axes, not yet camera or world axes.
"""

from __future__ import annotations
from typing import Sequence, TYPE_CHECKING

if TYPE_CHECKING:
    from _contracts import Axes, Record, Sensor, TimedGyro


import argparse
import math
import statistics
import struct
import sys
import time


def collect_timed_gyro(
    sensor: Sensor, seconds: float, interval: float
) -> list[TimedGyro]:
    """Collect read-midpoint timestamps and uncorrected gyro vectors during a timed window.

    Args:
        sensor (Sensor): Read-only object implementing read_raw: acceleration g, gyro
            degrees/s, temperature C.
        seconds (float): Requested positive collection duration in host seconds.
        interval (float): Positive pause after each read, in seconds; not the complete
            sample period.

    Returns:
        list[TimedGyro]: Ordered host-seconds/XYZ-degrees-per-second pairs; no sensor
            settings change.
    """
    # Collect raw gyro with host read-midpoint timestamps until the deadline.
    # The pause follows each read, so integration must use measured intervals.
    if seconds <= 0 or interval <= 0:
        raise ValueError("Seconds and interval must be positive")
    samples = []
    start = time.monotonic()
    while True:
        before = time.monotonic()
        _accel, gyro, _temperature = sensor.read_raw()
        after = time.monotonic()
        samples.append(((before + after) / 2, tuple(gyro)))
        remaining = seconds - (after - start)
        if remaining <= 0:
            break
        time.sleep(min(interval, remaining))
    return samples


def check_samples(samples: Sequence[TimedGyro]) -> None:
    """Require finite three-axis samples and strictly increasing observation times.

    Args:
        samples (Sequence[TimedGyro]): Sequence of (host monotonic seconds, XYZ gyro
            degrees/s) pairs.

    Returns:
        None: None if valid; raises ValueError otherwise.
    """
    # Require finite three-axis samples and strictly increasing timestamps
    # before averaging or numerical integration.
    if len(samples) < 2:
        raise ValueError("At least two timed gyro samples are required")
    for timestamp, gyro in samples:
        if not math.isfinite(timestamp) or len(gyro) != 3:
            raise ValueError("Each sample needs a finite time and three axes")
        if not all(math.isfinite(value) for value in gyro):
            raise ValueError("Gyro readings must be finite")
    if any(b[0] <= a[0] for a, b in zip(samples, samples[1:])):
        raise ValueError("Sample timestamps must increase")


def estimate_stationary_offset(samples: Sequence[TimedGyro]) -> Axes:
    """Average a physically stationary window to estimate raw gyro bias.

    Args:
        samples (Sequence[TimedGyro]): Sequence of (host monotonic seconds, XYZ gyro
            degrees/s) pairs.

    Returns:
        Axes: XYZ mean degrees/s; this older tool assumes stillness rather than testing
            its spread.
    """
    check_samples(samples)
    return tuple(
        statistics.mean(gyro[axis] for _, gyro in samples) for axis in range(3)
    )


def integrate_rotation(samples: Sequence[TimedGyro], offset_dps: Axes) -> Record:
    """Integrate bias-corrected rates using each actual adjacent timestamp interval.

    Args:
        samples (Sequence[TimedGyro]): Sequence of (host monotonic seconds, XYZ gyro
            degrees/s) pairs.
        offset_dps (Axes): Three stationary gyro biases in XYZ degrees/second.

    Returns:
        Record: Sensor-axis angle integrals and timing summary, not a full 3D
            orientation.
    """
    # Validate samples and bias, then integrate each sensor axis with the
    # trapezoidal rule: average adjacent rates, subtract bias, multiply by elapsed time.
    check_samples(samples)
    if len(offset_dps) != 3 or not all(math.isfinite(v) for v in offset_dps):
        raise ValueError("Offset must contain three finite values")
    angles = [0.0, 0.0, 0.0]
    intervals = []
    for (first_time, first_gyro), (next_time, next_gyro) in zip(samples, samples[1:]):
        delta = next_time - first_time
        intervals.append(delta)
        for axis in range(3):
            mean_rate = (first_gyro[axis] + next_gyro[axis]) / 2
            angles[axis] += (mean_rate - offset_dps[axis]) * delta

    # Report the observed interval distribution alongside relative angles.
    # Independent axis integrals are not a general 3D orientation solution.
    return {
        "samples": len(samples),
        "span_seconds": samples[-1][0] - samples[0][0],
        "median_interval_ms": statistics.median(intervals) * 1000,
        "max_interval_ms": max(intervals) * 1000,
        "angle_degrees": tuple(angles),
    }


def format_report(offset_dps: Axes, result: Record) -> str:
    """Format offset, interval statistics and the controlled-rotation integral.

    Args:
        offset_dps (Axes): Three stationary gyro biases in XYZ degrees/second.
        result (Record): Report dictionary produced by the corresponding calculation
            function.

    Returns:
        str: Multi-line terminal report with units and measurement limitations.
    """

    def axes(values: Sequence[float]) -> str:
        """Format a sensor-axis vector for the rotation report.

        Args:
            values (Sequence[float]): Numeric values in the units and shape described by
                this function.

        Returns:
            str: Signed XYZ values at two decimal places.
        """
        return ", ".join(f"{name}={value:+.2f}" for name, value in zip("XYZ", values))

    return "\n".join(
        [
            f"Stationary gyro offset (deg/s): {axes(offset_dps)}",
            f"Rotation samples: {result['samples']} over {result['span_seconds']:.2f} s",
            f"Sample interval: median {result['median_interval_ms']:.1f} ms, "
            f"maximum {result['max_interval_ms']:.1f} ms",
            f"Integrated sensor-axis angle (deg): {axes(result['angle_degrees'])}",
            "This is relative rotation in IMU axes, not compass heading or camera pose.",
            "Read-only: no calibration or raw log was saved.",
        ]
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Guide the user through a still window and a separate safe rotation window.

    Args:
        argv (Sequence[str] | None): Command-line tokens, or None to parse the current
            process arguments.

    Returns:
        int: Exit code; prints results but saves no raw log or calibration.
    """
    # Parse and validate the still/turn durations and polling pause.
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--still-seconds", type=float, default=10.0)
    parser.add_argument("--rotate-seconds", type=float, default=5.0)
    parser.add_argument("--interval", type=float, default=0.05)
    args = parser.parse_args(argv)
    if min(args.still_seconds, args.rotate_seconds, args.interval) <= 0:
        parser.error("Durations and interval must be positive")

    # Load the optional hardware driver only when running the experiment.
    try:
        from sunfounder_imu import IMU
    except ImportError:
        print("The SunFounder IMU library is required on the Pi.", file=sys.stderr)
        return 2

    # Estimate bias during a still window, then wait for the user to position
    # the wiring safely before starting the separate timed rotation window.
    try:
        sensor = IMU().accel_gyro
        print(f"Keep the board still for {args.still_seconds:g} seconds.", flush=True)
        still = collect_timed_gyro(sensor, args.still_seconds, args.interval)
        offset = estimate_stationary_offset(still)
        print("Still period complete. Keep wiring slack and avoid pulling the HAT.")
        input(
            "When safe and ready, press Enter; then rotate the board about "
            "90 degrees while keeping it level, and stop within the timed window. "
        )
        print(f"Recording rotation for {args.rotate_seconds:g} seconds.", flush=True)
        turning = collect_timed_gyro(sensor, args.rotate_seconds, args.interval)
        print(format_report(offset, integrate_rotation(turning, offset)))

    # Report interrupted or failed experiments without saving sensor calibration.
    except (OSError, ValueError, struct.error, EOFError) as error:
        print(f"Rotation test failed: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nStopped; no calibration was changed.", file=sys.stderr)
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
