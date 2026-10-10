"""Read-only, per-run gyro offset and current SH3001 rates for live display."""

from __future__ import annotations
from typing import Callable, Iterable, Sequence, TYPE_CHECKING

if TYPE_CHECKING:
    from _contracts import Axes, Record, Sensor, TimedGyro


from collections import deque
import math
import statistics
import threading
import time


def validate_gyro(gyro: Iterable[float]) -> Axes:
    """Validate a driver angular-rate reading before publishing it.

    Args:
        gyro (Iterable[float]): XYZ angular rates in degrees/second from the driver.

    Returns:
        Axes: Three finite XYZ rates; raises ValueError for invalid length or values.
    """
    values = tuple(gyro)
    if len(values) != 3 or not all(math.isfinite(v) for v in values):
        raise ValueError("IMU gyro needs three finite axes")
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
    # Require enough still samples and reject excessive variation before estimating
    # a per-axis mean offset. This assumes stillness; it cannot prove it.
    if len(samples) < min_samples:
        raise ValueError(f"Need at least {min_samples} still samples")
    axes = list(zip(*(gyro for _, gyro in samples)))
    spread = tuple(statistics.pstdev(axis) for axis in axes)
    if any(std > max_std_dps for std in spread):
        raise ValueError(
            "Initial gyro varied too much; keep rig still and restart preview"
        )
    return tuple(statistics.mean(axis) for axis in axes), spread


class LiveImu:
    def __init__(self, enabled: bool = False) -> None:
        """Initialize a per-run gyro baseline and bounded live reading history.

        Args:
            enabled (bool): Whether this optional live subsystem is requested.

        Returns:
            None: no I2C read or saved-calibration write occurs here.
        """
        # Keep per-run calibration, latest raw data and bounded rate history together
        # behind a lock; these values are not saved as permanent calibration.
        self.enabled = enabled
        self.lock = threading.Lock()
        self.baseline = []
        self.offset = None
        self.spread = None
        self.latest = None
        self.error = None
        self.sample_times = deque(maxlen=40)
        self.samples = 0
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
        # Validate all three axes and a strictly increasing timestamp before updating
        # the latest reading and sample history under the lock.
        gyro = validate_gyro(gyro)
        if not math.isfinite(timestamp):
            raise ValueError("IMU timestamp must be finite")
        with self.lock:
            if self.latest and timestamp <= self.latest[0]:
                raise ValueError("IMU timestamps must increase")
            self.latest = (timestamp, gyro)
            self.samples += 1
            self.sample_times.append(timestamp)

            # Collect the initial one-second window, estimate stationary bias once,
            # and discard its samples whether calibration succeeds or fails.
            if self.offset is None and not self.error:
                self.baseline.append((timestamp, gyro))
                if timestamp - self.baseline[0][0] >= 1:
                    try:
                        self.offset, self.spread = stationary_offset(self.baseline)
                    except ValueError as error:
                        self.error = str(error)
                    finally:
                        self.baseline = []

    def fail(self, message: str) -> None:
        """Retain an IMU-specific failure without stopping the camera pipeline.

        Args:
            message (str): Human-readable error retained for the terminal or browser.

        Returns:
            None: future snapshots expose the error instead of corrected rates.
        """
        with self.lock:
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
        # Build a coherent status snapshot with measured rate and sample age.
        # Disabled, calibrating, stale and failed readings must not look like zero motion.
        with self.lock:
            if not self.enabled:
                return dict(status="off")
            age = (now - self.latest[0]) * 1000 if self.latest else None
            rate = None
            recent = [t for t in self.sample_times if now - t < 2]
            if len(recent) >= 2 and recent[-1] > recent[0]:
                rate = (len(recent) - 1) / (recent[-1] - recent[0])
            no_start = self.latest is None and now - self.started > 2
            status = (
                "error"
                if self.error
                else "stale"
                if no_start or (age is not None and age > 300)
                else "calibrating"
                if self.offset is None
                else "ready"
            )

            # Subtract the per-run bias only for ready readings. Return sensor-axis rates
            # in degrees/second, not integrated angle, compass heading or camera pose.
            corrected = (
                [raw - bias for raw, bias in zip(self.latest[1], self.offset)]
                if status == "ready"
                else None
            )
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
    # Reject an invalid polling pause before entering the sensor loop.
    if interval <= 0 or not math.isfinite(interval):
        raise ValueError("Polling interval must be positive and finite")
    try:
        while not stop.is_set():
            # Bracket the raw read and timestamp its host midpoint, then pause after
            # reading. Read time plus this pause makes the achieved rate lower than 20 Hz.
            before = clock()
            _accel, gyro, _temperature = sensor.read_raw()
            after = clock()
            imu.publish((before + after) / 2, gyro)
            stop.wait(interval)

    # Expose a sensor failure independently unless shutdown was already requested.
    except Exception as error:
        if not stop.is_set():
            imu.fail(f"IMU read failed: {error}")
