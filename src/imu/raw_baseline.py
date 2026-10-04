"""Read-only baseline for the SunFounder SH3001 motion sensor.

The library's read_raw() skips saved user calibration, but still converts
register values to g and degrees/second. This tool never writes corrections.
"""

import argparse
import math
import statistics
import struct
import sys
import time


def summarize(samples, elapsed_seconds):
    """Summarize stationary (acceleration_g, gyro_dps) sample pairs."""
    if elapsed_seconds <= 0 or len(samples) < 2:
        raise ValueError("Need at least two samples and positive elapsed time")

    acceleration = []
    gyroscope = []
    for accel, gyro in samples:
        if len(accel) != 3 or len(gyro) != 3:
            raise ValueError("Each sensor reading must have three axes")
        if not all(math.isfinite(value) for value in (*accel, *gyro)):
            raise ValueError("Sensor readings must be finite")
        acceleration.append(accel)
        gyroscope.append(gyro)

    def axis_stats(readings):
        axes = list(zip(*readings))
        return (
            tuple(statistics.mean(axis) for axis in axes),
            tuple(statistics.pstdev(axis) for axis in axes),
        )

    accel_mean, accel_std = axis_stats(acceleration)
    gyro_mean, gyro_std = axis_stats(gyroscope)
    magnitudes = [math.sqrt(sum(value * value for value in a)) for a in acceleration]
    return {
        "samples": len(samples),
        "elapsed_seconds": elapsed_seconds,
        "sample_rate_hz": len(samples) / elapsed_seconds,
        "accel_mean_g": accel_mean,
        "accel_std_g": accel_std,
        "accel_magnitude_mean_g": statistics.mean(magnitudes),
        "accel_magnitude_std_g": statistics.pstdev(magnitudes),
        "gyro_mean_dps": gyro_mean,
        "gyro_std_dps": gyro_std,
        "gyro_offset_estimate_dps": gyro_mean,
    }


def collect(sensor, seconds, interval):
    """Collect samples without changing sensor or calibration settings."""
    if seconds <= 0 or interval <= 0:
        raise ValueError("Seconds and interval must be positive")
    samples = []
    start = time.monotonic()
    while True:
        accel, gyro, _temperature = sensor.read_raw()
        samples.append((tuple(accel), tuple(gyro)))
        remaining = seconds - (time.monotonic() - start)
        if remaining <= 0:
            break
        time.sleep(min(interval, remaining))
    return samples, time.monotonic() - start


def format_report(result):
    def axes(values):
        return ", ".join(f"{name}={value:+.3f}" for name, value in zip("XYZ", values))

    return "\n".join([
        f"Samples: {result['samples']} in {result['elapsed_seconds']:.2f} s "
        f"({result['sample_rate_hz']:.1f} samples/s)",
        f"Acceleration mean (g): {axes(result['accel_mean_g'])}",
        f"Acceleration stddev (g): {axes(result['accel_std_g'])}",
        f"Acceleration magnitude: {result['accel_magnitude_mean_g']:.3f} g "
        f"(stddev {result['accel_magnitude_std_g']:.3f} g)",
        f"Gyro mean (deg/s): {axes(result['gyro_mean_dps'])}",
        f"Gyro stddev (deg/s): {axes(result['gyro_std_dps'])}",
        "Stationary gyro offset estimate = gyro mean above; "
        "valid only if the board stayed still.",
        "Read-only: no calibration was applied or saved.",
    ])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seconds", type=float, default=10.0)
    parser.add_argument("--interval", type=float, default=0.1)
    args = parser.parse_args(argv)
    if args.seconds <= 0 or args.interval <= 0:
        parser.error("--seconds and --interval must be positive")

    try:
        from sunfounder_imu import IMU
    except ImportError:
        print("The SunFounder IMU library is required on the Pi.", file=sys.stderr)
        return 2

    try:
        sensor = IMU().accel_gyro
        samples, elapsed = collect(sensor, args.seconds, args.interval)
        print(format_report(summarize(samples, elapsed)))
    except (OSError, ValueError, struct.error) as error:
        print(f"IMU baseline failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
