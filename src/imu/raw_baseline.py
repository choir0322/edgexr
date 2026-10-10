"""Read-only baseline for the SunFounder SH3001 motion sensor.

The library's read_raw() skips saved user calibration, but still converts
register values to g and degrees/second. This tool never writes corrections.
"""

from __future__ import annotations
from typing import Sequence, TYPE_CHECKING

if TYPE_CHECKING:
    from _contracts import Axes, Record, Sensor, SensorSample


import argparse
import math
import statistics
import struct
import sys
import time


def summarize(samples: Sequence[SensorSample], elapsed_seconds: float) -> Record:
    """Summarize driver-unit acceleration and gyro samples from a still window.

    Args:
        samples (Sequence[SensorSample]): Sequence of (XYZ acceleration g, XYZ gyro
            degrees/s) pairs.
        elapsed_seconds (float): Measured duration used for the sample-rate estimate.

    Returns:
        Record: Means/stddevs, acceleration magnitude and a gyro offset estimate; no
            correction is saved.
    """
    # Require enough samples, then separate and validate raw accelerometer/gyro axes
    # without applying saved calibration or changing the sensor coordinate system.
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

    def axis_stats(readings: Sequence[Axes]) -> tuple[Axes, Axes]:
        """Transpose XYZ readings to calculate independent axis means and spreads.

        Args:
            readings (Sequence[Axes]): Sequence of XYZ vectors, retaining the input physical
                units.

        Returns:
            tuple[Axes, Axes]: XYZ means and population standard deviations in the input
                units.
        """
        # Transpose samples into per-axis series and report their means and population
        # standard deviations in the original driver units.
        axes = list(zip(*readings))
        return (
            tuple(statistics.mean(axis) for axis in axes),
            tuple(statistics.pstdev(axis) for axis in axes),
        )

    # Summarize raw axes and acceleration magnitude separately. The gyro mean is
    # an offset estimate only if the board actually stayed still during acquisition.
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


def collect(
    sensor: Sensor, seconds: float, interval: float
) -> tuple[list[SensorSample], float]:
    """Collect acceleration/gyro pairs for a requested duration without changing hardware settings.

    Args:
        sensor (Sensor): Read-only object implementing read_raw: acceleration g, gyro
            degrees/s, temperature C.
        seconds (float): Requested positive collection duration in host seconds.
        interval (float): Positive pause after each read, in seconds; not the complete
            sample period.

    Returns:
        tuple[list[SensorSample], float]: Sample list and actual elapsed host seconds,
            including read/wait overhead.
    """
    # Read until the monotonic duration expires, pausing after each read.
    # Preserve actual elapsed time rather than assuming a requested sample rate.
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


def format_report(result: Record) -> str:
    """Format a raw stationary baseline for the terminal with explicit physical units.

    Args:
        result (Record): Report dictionary produced by the corresponding calculation
            function.

    Returns:
        str: Multi-line report; result must come from summarize.
    """

    def axes(values: Sequence[float]) -> str:
        """Label a three-axis vector for the baseline report.

        Args:
            values (Sequence[float]): Numeric values in the units and shape described by
                this function.

        Returns:
            str: Signed XYZ values formatted to three decimal places.
        """
        return ", ".join(f"{name}={value:+.3f}" for name, value in zip("XYZ", values))

    return "\n".join(
        [
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
        ]
    )


def validate_gyro_offset(baseline: Record, verification: Record) -> Record:
    """Check one window's gyro offset on a separate stationary window.

    Args:
        baseline (Record): Summary of the first, physically stationary gyro window.
        verification (Record): Summary of a separately collected stationary window.

    Returns:
        Record: Raw/corrected verification means and unchanged spread; neither input is
            mutated.
    """
    # Apply the first window mean to a separate verification window. Subtracting
    # a constant changes its mean but not its standard deviation.
    offset = baseline["gyro_mean_dps"]
    raw_mean = verification["gyro_mean_dps"]
    return {
        "offset_dps": offset,
        "verification_raw_mean_dps": raw_mean,
        "verification_corrected_mean_dps": tuple(
            raw - bias for raw, bias in zip(raw_mean, offset)
        ),
        "verification_corrected_std_dps": verification["gyro_std_dps"],
    }


def format_gyro_validation(result: Record) -> str:
    """Explain the independent-window correction and its stationary-only scope.

    Args:
        result (Record): Report dictionary produced by the corresponding calculation
            function.

    Returns:
        str: Multi-line verification report from validate_gyro_offset fields.
    """

    def axes(values: Sequence[float]) -> str:
        """Label a three-axis vector for the verification report.

        Args:
            values (Sequence[float]): Numeric values in the units and shape described by
                this function.

        Returns:
            str: Signed XYZ values formatted to three decimal places.
        """
        return ", ".join(f"{name}={value:+.3f}" for name, value in zip("XYZ", values))

    return "\n".join(
        [
            f"Estimated gyro offset (deg/s): {axes(result['offset_dps'])}",
            f"Second-window raw gyro mean (deg/s): "
            f"{axes(result['verification_raw_mean_dps'])}",
            f"Second-window corrected gyro mean (deg/s): "
            f"{axes(result['verification_corrected_mean_dps'])}",
            f"Second-window gyro stddev (deg/s): "
            f"{axes(result['verification_corrected_std_dps'])}",
            "Correction is valid only while the board stayed still in both windows.",
            "Read-only: correction was not saved or applied to live tracking.",
        ]
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Run one stationary baseline or a separate-window gyro verification.

    Args:
        argv (Sequence[str] | None): Command-line tokens, or None to parse the current
            process arguments.

    Returns:
        int: Exit code 0 on success, 1 on read/validation failure, or 2 when the driver
            is missing.
    """
    # Parse acquisition and optional verification timing, then validate durations.
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seconds", type=float, default=10.0)
    parser.add_argument("--interval", type=float, default=0.1)
    parser.add_argument(
        "--verify-gyro",
        action="store_true",
        help="use a second, separate stationary window to check the gyro offset",
    )
    parser.add_argument(
        "--settle-seconds",
        type=float,
        default=2.0,
        help="pause between baseline and verification windows (default: 2)",
    )
    args = parser.parse_args(argv)
    if args.seconds <= 0 or args.interval <= 0:
        parser.error("--seconds and --interval must be positive")
    if args.settle_seconds < 0:
        parser.error("--settle-seconds cannot be negative")

    # Import the Pi-only driver lazily so this module can be tested on a Mac.
    try:
        from sunfounder_imu import IMU
    except ImportError:
        print("The SunFounder IMU library is required on the Pi.", file=sys.stderr)
        return 2

    # Collect and report the first raw window without writing calibration.
    try:
        sensor = IMU().accel_gyro
        samples, elapsed = collect(sensor, args.seconds, args.interval)
        baseline = summarize(samples, elapsed)
        print(format_report(baseline))

        # If requested, settle and measure a second still window independently;
        # report the residual after correction rather than reusing baseline samples.
        if args.verify_gyro:
            print(
                f"Keep the board still. Waiting {args.settle_seconds:g} s "
                "before a separate verification window.",
                flush=True,
            )
            time.sleep(args.settle_seconds)
            verification_samples, verification_elapsed = collect(
                sensor, args.seconds, args.interval
            )
            verification = summarize(verification_samples, verification_elapsed)
            print(format_gyro_validation(validate_gyro_offset(baseline, verification)))
    except (OSError, ValueError, struct.error) as error:
        print(f"IMU baseline failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
