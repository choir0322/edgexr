"""Read-only baseline for the SunFounder SH3001 motion sensor.

The library's read_raw() skips saved user calibration, but still converts
register values to g and degrees/second. This tool never writes corrections.
"""

# Postpone type evaluation so optional drivers/libraries stay optional.
from __future__ import annotations

# Describe data contracts without adding third-party runtime dependencies.
from typing import Sequence, TYPE_CHECKING

# Resolve documentation-only types for editors; this block does not run in production.
if TYPE_CHECKING:
    # Reuse the documented frame, sensor and report vocabulary for type checking.
    from _contracts import Axes, Record, Sensor, SensorSample


# Parse and validate explicit command-line options.
import argparse

# Validate finite numbers and perform scalar numerical calculations.
import math

# Compute means, spreads and medians from collected measurements.
import statistics

# Recognize binary-driver decode errors without changing vendor code.
import struct

# Report failures on stderr and handle command-line exit behavior.
import sys

# Measure host intervals and provide bounded polling pauses.
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
    # Reject this invalid input before it can produce misleading output.
    if elapsed_seconds <= 0 or len(samples) < 2:
        # Stop this operation with an explicit error rather than publishing invalid data.
        raise ValueError("Need at least two samples and positive elapsed time")

    # Collect raw driver acceleration vectors without applying the suspect saved calibration.
    acceleration = []
    # Collect raw driver angular-rate vectors for an independent offset estimate.
    gyroscope = []
    # Process each (accel, gyro) in the selected collection.
    for accel, gyro in samples:
        # Reject this invalid input before it can produce misleading output.
        if len(accel) != 3 or len(gyro) != 3:
            # Stop this operation with an explicit error rather than publishing invalid data.
            raise ValueError("Each sensor reading must have three axes")
        # Reject this invalid input before it can produce misleading output.
        if not all(math.isfinite(value) for value in (*accel, *gyro)):
            # Stop this operation with an explicit error rather than publishing invalid data.
            raise ValueError("Sensor readings must be finite")
        # Retain this item/chunk for the current calculation or bounded history.
        acceleration.append(accel)
        # Retain this item/chunk for the current calculation or bounded history.
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
        # Transpose readings so each sequence contains observations of one physical axis.
        axes = list(zip(*readings))
        # Return the documented result to the caller without starting another operation.
        return (
            tuple(statistics.mean(axis) for axis in axes),
            tuple(statistics.pstdev(axis) for axis in axes),
        )

    # Summarize each acceleration axis independently in g.
    accel_mean, accel_std = axis_stats(acceleration)
    # Summarize each angular-rate axis independently in degrees/second.
    gyro_mean, gyro_std = axis_stats(gyroscope)
    # Compute acceleration-vector lengths in g without changing the raw axes.
    magnitudes = [math.sqrt(sum(value * value for value in a)) for a in acceleration]
    # Return the documented result to the caller without starting another operation.
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
    # Reject this invalid input before it can produce misleading output.
    if seconds <= 0 or interval <= 0:
        # Stop this operation with an explicit error rather than publishing invalid data.
        raise ValueError("Seconds and interval must be positive")
    # Prepare samples for the next step using the values calculated so far.
    samples = []
    # Read host monotonic time for this stage's timing boundary.
    start = time.monotonic()
    # Repeat until the stop signal, deadline or explicit exit condition is reached.
    while True:
        # Read acceleration and angular rate; temperature is not recorded here.
        accel, gyro, _temperature = sensor.read_raw()
        # Retain this item/chunk for the current calculation or bounded history.
        samples.append((tuple(accel), tuple(gyro)))
        # Compute time left using actual elapsed duration rather than sample count.
        remaining = seconds - (time.monotonic() - start)
        # Choose the next branch using remaining <= 0.
        if remaining <= 0:
            # Leave this loop; the enclosing cleanup/status code still runs.
            break
        # Pause for the configured interval; read/compute overhead is additional time.
        time.sleep(min(interval, remaining))
    # Return the documented result to the caller without starting another operation.
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
        # Return the documented result to the caller without starting another operation.
        return ", ".join(f"{name}={value:+.3f}" for name, value in zip("XYZ", values))

    # Return the documented result to the caller without starting another operation.
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
    # Use the stationary baseline estimate as a constant per-axis correction.
    offset = baseline["gyro_mean_dps"]
    # Read the second-window mean so the bias is checked on independent data.
    raw_mean = verification["gyro_mean_dps"]
    # Return the documented result to the caller without starting another operation.
    return {
        "offset_dps": offset,
        "verification_raw_mean_dps": raw_mean,
        "verification_corrected_mean_dps": tuple(
            raw - bias for raw, bias in zip(raw_mean, offset)
        ),
        # Subtracting a constant changes the mean, not the spread.
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
        # Return the documented result to the caller without starting another operation.
        return ", ".join(f"{name}={value:+.3f}" for name, value in zip("XYZ", values))

    # Return the documented result to the caller without starting another operation.
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
    # Define the command-line interface without starting hardware work yet.
    parser = argparse.ArgumentParser(description=__doc__)
    # Declare --seconds with its existing default, validation and help text.
    parser.add_argument("--seconds", type=float, default=10.0)
    # Declare --interval with its existing default, validation and help text.
    parser.add_argument("--interval", type=float, default=0.1)
    # Declare --verify-gyro with its existing default, validation and help text.
    parser.add_argument(
        "--verify-gyro",
        action="store_true",
        help="use a second, separate stationary window to check the gyro offset",
    )
    # Declare --settle-seconds with its existing default, validation and help text.
    parser.add_argument(
        "--settle-seconds",
        type=float,
        default=2.0,
        help="pause between baseline and verification windows (default: 2)",
    )
    # Parse command-line values into the namespace used by this operation.
    args = parser.parse_args(argv)
    # Choose the next branch using args.seconds <= 0 or args.interval <= 0.
    if args.seconds <= 0 or args.interval <= 0:
        # Call parser.error for this step; its contract describes the result or side effect.
        parser.error("--seconds and --interval must be positive")
    # Choose the next branch using args.settle_seconds < 0.
    if args.settle_seconds < 0:
        # Call parser.error for this step; its contract describes the result or side effect.
        parser.error("--settle-seconds cannot be negative")

    # Keep failure handling alongside the operation so cleanup/status remains explicit.
    try:
        # Import the existing Pi driver only when a real sensor path is requested.
        from sunfounder_imu import IMU
    # Handle this failure without losing the error or skipping the enclosing cleanup.
    except ImportError:
        # Explain the current result, progress or failure in the terminal.
        print("The SunFounder IMU library is required on the Pi.", file=sys.stderr)
        # Return the process-style status code to the caller.
        return 2

    # Keep failure handling alongside the operation so cleanup/status remains explicit.
    try:
        # Select the accelerometer/gyroscope driver interface, not the saved calibration output.
        sensor = IMU().accel_gyro
        # Keep both actual observations and measured wall duration for the baseline.
        samples, elapsed = collect(sensor, args.seconds, args.interval)
        # Prepare baseline for the next step using the values calculated so far.
        baseline = summarize(samples, elapsed)
        # Explain the current result, progress or failure in the terminal.
        print(format_report(baseline))
        # Choose the next branch using args.verify_gyro.
        if args.verify_gyro:
            # Explain the current result, progress or failure in the terminal.
            print(
                f"Keep the board still. Waiting {args.settle_seconds:g} s "
                "before a separate verification window.",
                flush=True,
            )
            # Pause for the configured interval; read/compute overhead is additional time.
            time.sleep(args.settle_seconds)
            # Collect new data for verification rather than reusing calibration samples.
            verification_samples, verification_elapsed = collect(
                sensor, args.seconds, args.interval
            )
            # Summarize the independent second window in the same physical units.
            verification = summarize(verification_samples, verification_elapsed)
            # Explain the current result, progress or failure in the terminal.
            print(format_gyro_validation(validate_gyro_offset(baseline, verification)))
    # Handle this failure without losing the error or skipping the enclosing cleanup.
    except (OSError, ValueError, struct.error) as error:
        # Explain the current result, progress or failure in the terminal.
        print(f"IMU baseline failed: {error}", file=sys.stderr)
        # Return the process-style status code to the caller.
        return 1
    # Return the process-style status code to the caller.
    return 0


# Run the command only when executed directly, not when imported by tests or another module.
if __name__ == "__main__":
    # Return the command's status to the shell instead of leaving success ambiguous.
    raise SystemExit(main())
