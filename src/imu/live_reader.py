"""Read-only, per-run gyro offset and current SH3001 rates for live display."""

# Postpone type evaluation so optional drivers/libraries stay optional.
from __future__ import annotations

# Describe data contracts without adding third-party runtime dependencies.
from typing import Callable, Iterable, Sequence, TYPE_CHECKING

# Resolve documentation-only types for editors; this block does not run in production.
if TYPE_CHECKING:
    # Reuse the documented frame, sensor and report vocabulary for type checking.
    from _contracts import Axes, Record, Sensor, TimedGyro


# Keep bounded timestamp/diagnostic histories with deque.
from collections import deque

# Validate finite numbers and perform scalar numerical calculations.
import math

# Compute means, spreads and medians from collected measurements.
import statistics

# Coordinate independent workers using threads, locks, conditions and events.
import threading

# Measure host intervals and provide bounded polling pauses.
import time


def validate_gyro(gyro: Iterable[float]) -> Axes:
    """Validate a driver angular-rate reading before publishing it.

    Args:
        gyro (Iterable[float]): XYZ angular rates in degrees/second from the driver.

    Returns:
        Axes: Three finite XYZ rates; raises ValueError for invalid length or values.
    """
    # Materialize exactly three finite sensor-axis rates before storing the observation.
    values = tuple(gyro)
    # Reject this invalid input before it can produce misleading output.
    if len(values) != 3 or not all(math.isfinite(v) for v in values):
        # Stop this operation with an explicit error rather than publishing invalid data.
        raise ValueError("IMU gyro needs three finite axes")
    # Return the documented result to the caller without starting another operation.
    return values


def stationary_offset(
    samples: Sequence[TimedGyro], min_samples: int = 10, max_std_dps: float = 0.5
) -> tuple[Axes, Axes]:
    """Estimate per-axis gyro means after checking sample count and variation.

    Args:
        samples (Sequence[TimedGyro]): Sequence of (monotonic seconds, XYZ degrees/s)
            from a physically still window.
        min_samples (int): Minimum number of initial still-window observations.
        max_std_dps (float): Largest allowed population standard deviation per gyro
            axis, degrees/s.

    Returns:
        tuple[Axes, Axes]: Offset and population standard deviation, both XYZ degrees/s.
            Stillness must be assured physically.
    """
    # Reject this invalid input before it can produce misleading output.
    if len(samples) < min_samples:
        # Stop this operation with an explicit error rather than publishing invalid data.
        raise ValueError(f"Need at least {min_samples} still samples")
    # Transpose readings so each sequence contains observations of one physical axis.
    axes = list(zip(*(gyro for _, gyro in samples)))
    # Estimate each gyro axis variation in degrees/second.
    spread = tuple(statistics.pstdev(axis) for axis in axes)
    # Reject this invalid input before it can produce misleading output.
    if any(std > max_std_dps for std in spread):
        # Stop this operation with an explicit error rather than publishing invalid data.
        raise ValueError(
            "Initial gyro varied too much; keep rig still and restart preview"
        )
    # Return the documented result to the caller without starting another operation.
    return tuple(statistics.mean(axis) for axis in axes), spread


class LiveImu:
    def __init__(self, enabled: bool = False) -> None:
        """Initialize a per-run gyro baseline and bounded live reading history.

        Args:
            enabled (bool): Whether this optional live subsystem is requested.

        Returns:
            None: no I2C read or saved-calibration write occurs here.
        """
        # Remember whether the user requested this optional subsystem.
        self.enabled = enabled
        # Protect this subsystem while capture, workers and HTTP requests run concurrently.
        self.lock = threading.Lock()
        # Collect the initial still-window readings until an offset can be estimated.
        self.baseline = []
        # Use no correction until a valid per-run offset has been estimated.
        self.offset = None
        # Keep the initial per-axis noise estimate alongside the bias.
        self.spread = None
        # Retain only the newest observation; readers may still hold an earlier local reference.
        self.latest = None
        # Retain the failure message for subsequent status snapshots.
        self.error = None
        # Bound the sample-time history used by the live rate estimate.
        self.sample_times = deque(maxlen=40)
        # Count validated IMU observations during this run.
        self.samples = 0
        # Remember monotonic startup time for no-data timeout checks.
        self.started = time.monotonic()

    def publish(self, timestamp: float, gyro: Iterable[float]) -> None:
        """Validate and publish a gyro sample, estimating the first-second offset once.

        Args:
            timestamp (float): Host monotonic observation time in seconds, not sensor
                exposure time.
            gyro (Iterable[float]): XYZ angular rates in degrees/second from the driver.

        Returns:
            None: a rejected initial baseline remains an error until a new run.
        """
        # Validate the driver vector before modifying the latest sample or baseline.
        gyro = validate_gyro(gyro)
        # Reject this invalid input before it can produce misleading output.
        if not math.isfinite(timestamp):
            # Stop this operation with an explicit error rather than publishing invalid data.
            raise ValueError("IMU timestamp must be finite")
        # Hold the shared-state lock only while reading or replacing shared values.
        with self.lock:
            # Reject this invalid input before it can produce misleading output.
            if self.latest and timestamp <= self.latest[0]:
                # Stop this operation with an explicit error rather than publishing invalid
                # data.
                raise ValueError("IMU timestamps must increase")
            # Retain only the newest observation; readers may still hold an earlier local
            # reference.
            self.latest = (timestamp, gyro)
            # Count validated IMU observations during this run.
            self.samples += 1
            # Retain this item/chunk for the current calculation or bounded history.
            self.sample_times.append(timestamp)
            # Estimate bias once per run; never silently recalibrate during later movement.
            if self.offset is None and not self.error:
                # Retain this item/chunk for the current calculation or bounded history.
                self.baseline.append((timestamp, gyro))
                # Wait for a full second of observed baseline time before estimating the offset.
                if timestamp - self.baseline[0][0] >= 1:
                    # Keep failure handling alongside the operation so cleanup/status remains
                    # explicit.
                    try:
                        # Prepare self.offset, self.spread for the next step using the values
                        # calculated so far.
                        self.offset, self.spread = stationary_offset(self.baseline)
                    # Handle this failure without losing the error or skipping the enclosing
                    # cleanup.
                    except ValueError as error:
                        # Retain the failure message for subsequent status snapshots.
                        self.error = str(error)
                    finally:
                        # Clear temporary baseline samples after the one-time estimate attempt.
                        self.baseline = []

    def fail(self, message: str) -> None:
        """Retain an IMU-specific failure without stopping the camera pipeline.

        Args:
            message (str): Human-readable error retained for the terminal or browser.

        Returns:
            None: future snapshots expose the error instead of corrected rates.
        """
        # Hold the shared-state lock only while reading or replacing shared values.
        with self.lock:
            # Retain the failure message for subsequent status snapshots.
            self.error = str(message)

    def snapshot(self, now: float) -> Record:
        """Report freshness, frequency and bias-corrected angular rate when ready.

        Args:
            now (float): Host monotonic seconds used to calculate age; None selects the
                clock now.

        Returns:
            Record: JSON-ready IMU fields; gyro_dps is None when unavailable, stale or
                failed.
        """
        # Hold the shared-state lock only while reading or replacing shared values.
        with self.lock:
            # Choose the next branch using not self.enabled.
            if not self.enabled:
                # Return the documented result to the caller without starting another operation.
                return dict(status="off")
            # Measure age from the observation/source time, not from when its result was
            # published.
            age = (now - self.latest[0]) * 1000 if self.latest else None
            # Estimate recent observed sample frequency only when a usable time span exists.
            rate = None
            # Select recent observations for a local rate estimate instead of a lifetime
            # average.
            recent = [t for t in self.sample_times if now - t < 2]
            # Choose the next branch using len(recent) >= 2 and recent[-1] > recent[0].
            if len(recent) >= 2 and recent[-1] > recent[0]:
                # Estimate recent observed sample frequency only when a usable time span exists.
                rate = (len(recent) - 1) / (recent[-1] - recent[0])
            # Detect startup without any IMU reading independently of stale-data handling.
            no_start = self.latest is None and now - self.started > 2
            # Choose the visible state from enablement, errors, startup and freshness.
            status = (
                "error"
                if self.error
                else "stale"
                if no_start or (age is not None and age > 300)
                else "calibrating"
                if self.offset is None
                else "ready"
            )
            # Subtract each axis bias only when the latest reading is fresh and ready.
            corrected = (
                [raw - bias for raw, bias in zip(self.latest[1], self.offset)]
                if status == "ready"
                else None
            )
            # Return the documented result to the caller without starting another operation.
            return dict(
                status=status,
                gyro_dps=corrected,
                offset_dps=self.offset,
                stationary_std_dps=self.spread,
                samples=self.samples,
                rate_hz=rate,
                age_ms=age,
                error="No IMU samples within two seconds"
                if no_start and not self.error
                else self.error,
            )


def poll_imu(
    imu: LiveImu,
    sensor: Sensor,
    stop: threading.Event,
    interval: float = 0.05,
    clock: Callable[[], float] = time.monotonic,
) -> None:
    """Poll a sensor on a dedicated thread and timestamp each read midpoint.

    Args:
        imu (LiveImu): LiveImu state receiving samples and isolated read errors.
        sensor (Sensor): Read-only object implementing read_raw: acceleration g, gyro
            degrees/s, temperature C.
        stop (threading.Event): Threading event signalling shutdown; wait can finish
            early when it is set.
        interval (float): Positive pause after each read, in seconds; not the complete
            sample period.
        clock (Callable[[], float]): Zero-argument host clock; units are seconds except
            explicitly named nanosecond stages.

    Returns:
        None: stores readings/errors in imu and never writes sensor calibration.
    """
    # Reject this invalid input before it can produce misleading output.
    if interval <= 0 or not math.isfinite(interval):
        # Stop this operation with an explicit error rather than publishing invalid data.
        raise ValueError("Polling interval must be positive and finite")
    # Keep failure handling alongside the operation so cleanup/status remains explicit.
    try:
        # Repeat until the stop signal, deadline or explicit exit condition is reached.
        while not stop.is_set():
            # Read the host clock immediately before the sensor call.
            before = clock()
            # Read converted sensor units; only angular rate is used on this path.
            _accel, gyro, _temperature = sensor.read_raw()
            # Read the host clock immediately after the sensor call.
            after = clock()
            # Publish completed work through the state object's synchronization boundary.
            imu.publish((before + after) / 2, gyro)
            # Pause for the configured interval; read/compute overhead is additional time.
            stop.wait(interval)
    # Handle this failure without losing the error or skipping the enclosing cleanup.
    except Exception as error:
        # Choose the next branch using not stop.is_set().
        if not stop.is_set():
            # Call imu.fail for this step; its contract describes the result or side effect.
            imu.fail(f"IMU read failed: {error}")
