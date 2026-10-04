"""Read-only, timestamped SH3001 gyro rotation experiment.

First estimate gyro offset while still. Then integrate a separate timed
rotation window. Angles are in sensor axes, not yet camera or world axes.
"""

import argparse
import math
import statistics
import struct
import sys
import time


def collect_timed_gyro(sensor, seconds, interval):
    """Return (monotonic_seconds, gyro_dps) without changing sensor settings."""
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


def check_samples(samples):
    if len(samples) < 2:
        raise ValueError("At least two timed gyro samples are required")
    for timestamp, gyro in samples:
        if not math.isfinite(timestamp) or len(gyro) != 3:
            raise ValueError("Each sample needs a finite time and three axes")
        if not all(math.isfinite(value) for value in gyro):
            raise ValueError("Gyro readings must be finite")
    if any(b[0] <= a[0] for a, b in zip(samples, samples[1:])):
        raise ValueError("Sample timestamps must increase")


def estimate_stationary_offset(samples):
    """Mean gyro rate from a separate still window, in degrees/second."""
    check_samples(samples)
    return tuple(statistics.mean(gyro[axis] for _, gyro in samples) for axis in range(3))


def integrate_rotation(samples, offset_dps):
    """Trapezoidal integral of offset-corrected gyro rates in degrees."""
    check_samples(samples)
    if len(offset_dps) != 3 or not all(math.isfinite(v) for v in offset_dps):
        raise ValueError("Offset must contain three finite values")
    angles = [0.0, 0.0, 0.0]
    intervals = []
    for (first_time, first_gyro), (next_time, next_gyro) in zip(
        samples, samples[1:]
    ):
        delta = next_time - first_time
        intervals.append(delta)
        for axis in range(3):
            mean_rate = (first_gyro[axis] + next_gyro[axis]) / 2
            angles[axis] += (mean_rate - offset_dps[axis]) * delta
    return {
        "samples": len(samples),
        "span_seconds": samples[-1][0] - samples[0][0],
        "median_interval_ms": statistics.median(intervals) * 1000,
        "max_interval_ms": max(intervals) * 1000,
        "angle_degrees": tuple(angles),
    }


def format_report(offset_dps, result):
    def axes(values):
        return ", ".join(f"{name}={value:+.2f}" for name, value in zip("XYZ", values))

    return "\n".join([
        f"Stationary gyro offset (deg/s): {axes(offset_dps)}",
        f"Rotation samples: {result['samples']} over {result['span_seconds']:.2f} s",
        f"Sample interval: median {result['median_interval_ms']:.1f} ms, "
        f"maximum {result['max_interval_ms']:.1f} ms",
        f"Integrated sensor-axis angle (deg): {axes(result['angle_degrees'])}",
        "This is relative rotation in IMU axes, not compass heading or camera pose.",
        "Read-only: no calibration or raw log was saved.",
    ])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--still-seconds", type=float, default=10.0)
    parser.add_argument("--rotate-seconds", type=float, default=5.0)
    parser.add_argument("--interval", type=float, default=0.05)
    args = parser.parse_args(argv)
    if min(args.still_seconds, args.rotate_seconds, args.interval) <= 0:
        parser.error("Durations and interval must be positive")

    try:
        from sunfounder_imu import IMU
    except ImportError:
        print("The SunFounder IMU library is required on the Pi.", file=sys.stderr)
        return 2

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
    except (OSError, ValueError, struct.error, EOFError) as error:
        print(f"Rotation test failed: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nStopped; no calibration was changed.", file=sys.stderr)
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
