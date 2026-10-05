"""Read-only, per-run gyro offset and current SH3001 rates for live display."""

from collections import deque
import math
import statistics
import threading
import time


def validate_gyro(gyro):
    values = tuple(gyro)
    if len(values) != 3 or not all(math.isfinite(v) for v in values):
        raise ValueError('IMU gyro needs three finite axes')
    return values


def stationary_offset(samples, min_samples=10, max_std_dps=.5):
    """Estimate only after an independently checked stationary window."""
    if len(samples) < min_samples:
        raise ValueError(f'Need at least {min_samples} still samples')
    axes = list(zip(*(gyro for _, gyro in samples)))
    spread = tuple(statistics.pstdev(axis) for axis in axes)
    if any(std > max_std_dps for std in spread):
        raise ValueError('Initial gyro varied too much; keep rig still and restart preview')
    return tuple(statistics.mean(axis) for axis in axes), spread


class LiveImu:
    def __init__(self, enabled=False):
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

    def publish(self, timestamp, gyro):
        gyro = validate_gyro(gyro)
        if not math.isfinite(timestamp):
            raise ValueError('IMU timestamp must be finite')
        with self.lock:
            if self.latest and timestamp <= self.latest[0]:
                raise ValueError('IMU timestamps must increase')
            self.latest = (timestamp, gyro)
            self.samples += 1
            self.sample_times.append(timestamp)
            if self.offset is None and not self.error:
                self.baseline.append((timestamp, gyro))
                if timestamp - self.baseline[0][0] >= 1:
                    try:
                        self.offset, self.spread = stationary_offset(self.baseline)
                    except ValueError as error:
                        self.error = str(error)
                    finally:
                        self.baseline = []

    def fail(self, message):
        with self.lock:
            self.error = str(message)

    def snapshot(self, now):
        with self.lock:
            if not self.enabled:
                return dict(status='off')
            age = (now - self.latest[0]) * 1000 if self.latest else None
            rate = None
            recent = [t for t in self.sample_times if now-t < 2]
            if len(recent) >= 2 and recent[-1] > recent[0]:
                rate = (len(recent)-1)/(recent[-1]-recent[0])
            no_start = self.latest is None and now-self.started > 2
            status = ('error' if self.error else
                      'stale' if no_start or (age is not None and age > 300) else
                      'calibrating' if self.offset is None else 'ready')
            corrected = [raw-bias for raw,bias in zip(self.latest[1],self.offset)] if status == 'ready' else None
            return dict(status=status,gyro_dps=corrected,offset_dps=self.offset,
                        stationary_std_dps=self.spread,samples=self.samples,
                        rate_hz=rate,age_ms=age,
                        error='No IMU samples within two seconds' if no_start and not self.error else self.error)


def poll_imu(imu, sensor, stop, interval=.05, clock=time.monotonic):
    """Keep I2C reads out of the camera-analysis thread."""
    if interval <= 0 or not math.isfinite(interval):
        raise ValueError('Polling interval must be positive and finite')
    try:
        while not stop.is_set():
            before = clock()
            _accel, gyro, _temperature = sensor.read_raw()
            after = clock()
            imu.publish((before+after)/2, gyro)
            stop.wait(interval)
    except Exception as error:
        if not stop.is_set():
            imu.fail(f'IMU read failed: {error}')
