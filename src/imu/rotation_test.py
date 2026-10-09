"""Read-only, timestamped SH3001 gyro rotation experiment.

First estimate gyro offset while still. Then integrate a separate timed
rotation window. Angles are in sensor axes, not yet camera or world axes.
"""

# Postpone type evaluation so optional drivers/libraries stay optional.
from __future__ import annotations

# Describe data contracts without adding third-party runtime dependencies.
from typing import Sequence, TYPE_CHECKING

# Resolve documentation-only types for editors; this block does not run in production.
if TYPE_CHECKING:
    # Reuse the documented frame, sensor and report vocabulary for type checking.
    from _contracts import Axes, Record, Sensor, TimedGyro


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
        # Read the host clock immediately before the sensor call.
        before = time.monotonic()
        # Read converted sensor units; only angular rate is used on this path.
        _accel, gyro, _temperature = sensor.read_raw()
        # Read the host clock immediately after the sensor call.
        after = time.monotonic()
        # Retain this item/chunk for the current calculation or bounded history.
        samples.append(((before + after) / 2, tuple(gyro)))
        # Compute time left using actual elapsed duration rather than sample count.
        remaining = seconds - (after - start)
        # Choose the next branch using remaining <= 0.
        if remaining <= 0:
            # Leave this loop; the enclosing cleanup/status code still runs.
            break
        # Pause for the configured interval; read/compute overhead is additional time.
        time.sleep(min(interval, remaining))
    # Return the documented result to the caller without starting another operation.
    return samples


def check_samples(samples: Sequence[TimedGyro]) -> None:
    """Require finite three-axis samples and strictly increasing observation times.

    Args:
        samples (Sequence[TimedGyro]): Sequence of (host monotonic seconds, XYZ gyro
            degrees/s) pairs.

    Returns:
        None: None if valid; raises ValueError otherwise.
    """
    # Reject this invalid input before it can produce misleading output.
    if len(samples) < 2:
        # Stop this operation with an explicit error rather than publishing invalid data.
        raise ValueError("At least two timed gyro samples are required")
    # Process each (timestamp, gyro) in the selected collection.
    for timestamp, gyro in samples:
        # Reject this invalid input before it can produce misleading output.
        if not math.isfinite(timestamp) or len(gyro) != 3:
            # Stop this operation with an explicit error rather than publishing invalid data.
            raise ValueError("Each sample needs a finite time and three axes")
        # Reject this invalid input before it can produce misleading output.
        if not all(math.isfinite(value) for value in gyro):
            # Stop this operation with an explicit error rather than publishing invalid data.
            raise ValueError("Gyro readings must be finite")
    # Reject this invalid input before it can produce misleading output.
    if any(b[0] <= a[0] for a, b in zip(samples, samples[1:])):
        # Stop this operation with an explicit error rather than publishing invalid data.
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
    # Call check_samples for this step; its contract describes the result or side effect.
    check_samples(samples)
    # Return the documented result to the caller without starting another operation.
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
    # Call check_samples for this step; its contract describes the result or side effect.
    check_samples(samples)
    # Reject this invalid input before it can produce misleading output.
    if len(offset_dps) != 3 or not all(math.isfinite(v) for v in offset_dps):
        # Stop this operation with an explicit error rather than publishing invalid data.
        raise ValueError("Offset must contain three finite values")
    # Start all three sensor-axis integrals at zero degrees.
    angles = [0.0, 0.0, 0.0]
    # Keep real timestamp gaps instead of assuming an exact polling frequency.
    intervals = []
    # Process adjacent observations using their actual time separation.
    for (first_time, first_gyro), (next_time, next_gyro) in zip(samples, samples[1:]):
        # Measure the actual seconds between these adjacent gyro observations.
        delta = next_time - first_time
        # Retain this item/chunk for the current calculation or bounded history.
        intervals.append(delta)
        # Process each axis in the selected collection.
        for axis in range(3):
            # Average endpoint rates for a trapezoidal integration step.
            mean_rate = (first_gyro[axis] + next_gyro[axis]) / 2
            # Accumulate corrected degrees/second times real elapsed seconds into sensor-axis
            # degrees.
            angles[axis] += (mean_rate - offset_dps[axis]) * delta
    # Return the documented result to the caller without starting another operation.
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
        # Return the documented result to the caller without starting another operation.
        return ", ".join(f"{name}={value:+.2f}" for name, value in zip("XYZ", values))

    # Return the documented result to the caller without starting another operation.
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
    # Define the command-line interface without starting hardware work yet.
    parser = argparse.ArgumentParser(description=__doc__)
    # Declare --still-seconds with its existing default, validation and help text.
    parser.add_argument("--still-seconds", type=float, default=10.0)
    # Declare --rotate-seconds with its existing default, validation and help text.
    parser.add_argument("--rotate-seconds", type=float, default=5.0)
    # Declare --interval with its existing default, validation and help text.
    parser.add_argument("--interval", type=float, default=0.05)
    # Parse command-line values into the namespace used by this operation.
    args = parser.parse_args(argv)
    # Choose the next branch using min(args.still_seconds, args.rotate_seconds, args.interval)
    # <= 0.
    if min(args.still_seconds, args.rotate_seconds, args.interval) <= 0:
        # Call parser.error for this step; its contract describes the result or side effect.
        parser.error("Durations and interval must be positive")

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
        # Explain the current result, progress or failure in the terminal.
        print(f"Keep the board still for {args.still_seconds:g} seconds.", flush=True)
        # Collect the physically stationary samples before asking for movement.
        still = collect_timed_gyro(sensor, args.still_seconds, args.interval)
        # Use the stationary baseline estimate as a constant per-axis correction.
        offset = estimate_stationary_offset(still)
        # Explain the current result, progress or failure in the terminal.
        print("Still period complete. Keep wiring slack and avoid pulling the HAT.")
        # Call input for this step; its contract describes the result or side effect.
        input(
            "When safe and ready, press Enter; then rotate the board about "
            "90 degrees while keeping it level, and stop within the timed window. "
        )
        # Explain the current result, progress or failure in the terminal.
        print(f"Recording rotation for {args.rotate_seconds:g} seconds.", flush=True)
        # Collect a separate motion window rather than reusing the baseline samples.
        turning = collect_timed_gyro(sensor, args.rotate_seconds, args.interval)
        # Explain the current result, progress or failure in the terminal.
        print(format_report(offset, integrate_rotation(turning, offset)))
    # Handle this failure without losing the error or skipping the enclosing cleanup.
    except (OSError, ValueError, struct.error, EOFError) as error:
        # Explain the current result, progress or failure in the terminal.
        print(f"Rotation test failed: {error}", file=sys.stderr)
        # Return the process-style status code to the caller.
        return 1
    # Handle this failure without losing the error or skipping the enclosing cleanup.
    except KeyboardInterrupt:
        # Explain the current result, progress or failure in the terminal.
        print("\nStopped; no calibration was changed.", file=sys.stderr)
        # Return the process-style status code to the caller.
        return 130
    # Return the process-style status code to the caller.
    return 0


# Run the command only when executed directly, not when imported by tests or another module.
if __name__ == "__main__":
    # Return the command's status to the shell instead of leaving success ambiguous.
    raise SystemExit(main())
