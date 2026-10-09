# Study 3: IMU reading, timestamp and gyro display

Read [the live diagram](../PIPELINE.md) and [image-motion guide](IMAGE_MOTION.md).
The gyroscope measures angular rate around the board's axes. The live path
shows bias-corrected rates; it does not yet calculate camera orientation or
feed a motion-compensation algorithm. Rigid attachment means camera and IMU
move together, not that their coordinate axes are automatically identical.

## Source reading route

| Order | File | Symbols to read |
|---|---|---|
| 1 | [live_preview.py](../../src/app/live_preview.py) | `main`'s `--imu` setup and worker creation |
| 2 | [live_reader.py](../../src/imu/live_reader.py) | `poll_imu`, `validate_gyro` |
| 3 | [live_reader.py](../../src/imu/live_reader.py) | `LiveImu.__init__`, `publish`, `stationary_offset` |
| 4 | [live_reader.py](../../src/imu/live_reader.py) | `snapshot`, `fail` |
| 5 | [live_preview.py](../../src/app/live_preview.py) | `State.snapshot`, `make_handler`, `stop_workers` |
| 6 | [preview.html](../../src/app/preview.html) | `render`'s `imu` section, `poll` |

Each named function now declares its inputs and return type. `Axes`, `TimedGyro`
and `SensorSample` are short aliases in [the shared contracts](../../src/_contracts.py),
not new conversion/calibration algorithms. The `Sensor` Protocol documents
`read_raw()` without importing or changing the vendor driver. See
[code conventions](CODE_CONVENTIONS.md) for `TYPE_CHECKING` and callback notation.

## 1. Hardware and vendor boundary

`main()` imports `sunfounder_imu.IMU` only if `--imu` was requested. It selects
`IMU().accel_gyro` and starts a thread calling `poll_imu`. Missing sensor/setup
errors are stored in `state.imu` so camera preview can still operate. No servo
channel is needed for this read-only path, because it does not command motion.

The vendor driver lives outside this repository. On the tested Pi its files
were in `/usr/local/lib/python3.11/dist-packages/sunfounder_imu/`, including
`sensors/sh3001.py`. Our call boundary is `sensor.read_raw()`, which returns
`(acceleration_xyz_g, gyro_xyz_dps, temperature_c)`. The name raw does not mean
uninterpreted register bytes: the driver still reads I2C and converts units,
while bypassing its saved user calibration on this read path. Do not silently
edit that installed package when refactoring the EdgeXR wrapper.

The HAT provides the physical connection; the board is attached rigidly beside
the camera. For the present mounting, Y has been observed to dominate pan-like
turns. That observation is not a complete camera-to-IMU rotation calibration.

## 2. Poll and timestamp the reading

`poll_imu(imu, sensor, stop, interval=.05, clock=time.monotonic)` receives a
`LiveImu` state object, a sensor exposing `read_raw()`, a stop event, a positive
finite wait duration in seconds and a callable returning monotonic seconds.
Clock and sensor can be faked in unit tests without I2C hardware.

```python
before = clock()
_accel, gyro, _temperature = sensor.read_raw()
after = clock()
imu.publish((before + after) / 2, gyro)
stop.wait(interval)
```

Read each statement: note host time before I2C; request a reading; note time
afterwards; use the read interval midpoint as approximate host observation
time; wait 50 ms unless shutdown interrupts that wait. Acceleration and
temperature are intentionally unused in the live preview.

This is not a hardware sample timestamp or exactly 20 Hz. A 2 ms read plus
50 ms wait would produce about 19.2 polls/s before scheduling overhead. The
sensor's internal sample rate is independent. This worker does not wait for a
camera frame or run once per browser request.

## 3. Validate and estimate the initial gyro offset

`validate_gyro(gyro)` converts an iterable into a tuple of three finite numeric
values. `LiveImu.publish(timestamp, gyro)` also rejects nonfinite or
non-increasing timestamps. Inside its lock it updates the latest sample,
counts samples and stores a bounded recent-timestamp history.

Before an offset exists, readings are accumulated until at least one second
has elapsed since the first sample. `stationary_offset(samples)` requires at
least ten samples and calculates each axis's mean and population standard
deviation. Any axis with standard deviation above 0.5 degrees/s rejects this
initial window and asks the user to restart with the rig still.

Important limitation: low variation does not prove physical stillness. A
steady turn can have nearly constant gyro rate and could be mistaken for bias.
The user must actually keep the assembly stationary. The check only catches
some kinds of movement/noise. It does not independently observe the board.

Offset estimation is per run and in memory only. The code does not repair or
overwrite the vendor calibration JSON, calibrate the accelerometer, or perform
a magnetometer calibration. After a failed initial window it does not silently
retry while the rig might be moving; the stored error remains visible.

## 4. Correct and report the latest reading

`LiveImu.snapshot(now)` accepts a host monotonic timestamp in seconds and returns
a dictionary for display. For ready data it subtracts the estimated constant
bias separately from each latest raw axis:

```text
raw Y = +25 degrees/s
estimated stationary Y offset = +15 degrees/s
displayed Y = +10 degrees/s
```

This is angular speed. It is not a ten-degree angle and not metres/second.
Snapshot fields include `status`, `gyro_dps`, `offset_dps`,
`stationary_std_dps`, `samples`, `rate_hz`, `age_ms` and `error`.

Recent poll frequency is `(n-1)/(last-first)` using recent timestamps, while
age is `1000*(now-latest_timestamp)`. Thus a displayed `19 Hz` and `6.8 ms`
can coexist: the first is frequency, the second the age of the newest sample.

After more than 300 ms without a fresh reading, ready values become stale and
the corrected gyro field is hidden. Startup without samples has a two-second
timeout; explicit errors have their own status. Failed/stale IMU state does
not get converted into a false zero angular rate. The camera worker need not fail.

## 5. Browser and shutdown

`State.snapshot()` calls the IMU snapshot when responding to the browser, along
with independent image/detector data. In `preview.html`, `render()` shows
`imu.rate_hz`, `imu.age_ms` and `imu.gyro_dps[1]` (Y) in cards, and all three
axes in explanatory text. It displays calibrating, stale or error messages
instead of a misleading valid-looking number. Network errors clear the fields.

The browser polls after a 200 ms delay following each response, so it shows
only some of the IMU readings. Displaying the newest image and newest gyro in
one response does not align sensor exposure with gyro sampling. Neither this
snapshot nor the live reader integrates rate to angle.

The shared stop event interrupts the reader's wait on shutdown. Exceptions
from sensor reads are captured as IMU errors. Slow/blocking vendor calls are
not made magically nonblocking by the separate thread; isolation keeps them
out of the camera-analysis worker but is not hard real-time scheduling.

## Earlier IMU programs: what each established

### Stationary baseline and second-window verification

[raw_baseline.py](../../src/imu/raw_baseline.py)'s `main` calls `collect`,
`summarize` and `format_report`. `collect` returns acceleration/gyro sample
pairs plus elapsed seconds. `summarize` validates finite three-axis readings,
calculates means/stddevs and acceleration magnitudes, and reports gyro mean as
an offset estimate. Its default wait is 0.1 s, unlike the live reader's 0.05 s.

With `--verify-gyro`, it waits separately, gathers new samples and calls
`validate_gyro_offset(baseline, verification)`. It subtracts the first window's
mean from the second window's mean. This tests short-term consistency without
trivially subtracting a window's own mean from itself. Constant subtraction
changes the mean, not its spread. No correction file is written.

### Controlled rotation

[rotation_test.py](../../src/imu/rotation_test.py)'s `main` gathers a still
window using `collect_timed_gyro`, estimates its offset, waits for the user's
Enter cue and gathers a separate rotation window. `check_samples` validates
timestamps/axes. `integrate_rotation(samples, offset_dps)` uses each actual time
gap, not an assumed exact sample period:

```text
angle increment = ((first_rate + next_rate) / 2 - offset) * elapsed_seconds
```

That is trapezoidal integration: degrees/second times seconds gives degrees.
It reports each sensor-axis integral plus timing intervals. It is useful for
simple controlled-axis turn checks, but independently integrating three body-axis
rates is not a full 3D orientation algorithm. Bias drift accumulates with time.
The still-window mean in this older tool assumes stillness; unlike the live
reader it does not apply the same standard-deviation gate.

### Combined camera/IMU recording and analysis

[combined_capture.py](../../src/recording/combined_capture.py)'s `read_row`
records read midpoint, read duration, acceleration and gyro relative to a
shared monotonic origin. `record` writes video, CSV logs and metadata while a
separate thread drains camera timestamp messages. Unlike the live preview,
this command explicitly saves files. It preserves an incomplete/failed record
if something goes wrong and refuses to overwrite an existing run directory.

[analyze_capture.py](../../src/recording/analyze_capture.py)'s `analyze` validates
metadata/counts, chooses the assumed stationary window after the recording cue,
computes bias with `mean_axes`, and integrates with `integrate`. `timing` checks
strict timestamp ordering; `numeric_csv` reads finite numeric fields. The
analysis assumes the chosen baseline was really still and does not prove that.

[visual_motion.py](../../src/recording/visual_motion.py)'s `gyro_at` interpolates
only between sufficiently close bracketing host timestamps (gap at most 0.15 s).
It does not extrapolate beyond the data. The offline visual/gyro comparison is
evidence about association, not exposure synchronization, camera calibration
or a ready-to-use fusion algorithm.

## Tests and study exercises

Read [test_live_imu.py](../../tests/unit/test_live_imu.py) for fake sensor polling,
initial offset, motion rejection, bad timestamps, stale state and isolated
read failures. Read [test_imu_baseline.py](../../tests/unit/test_imu_baseline.py)
for separate-window correction and [test_imu_rotation.py](../../tests/unit/test_imu_rotation.py)
for irregular-time integration. Recording and analysis checks live in
[test_combined_capture.py](../../tests/unit/test_combined_capture.py) and
[test_capture_analysis.py](../../tests/unit/test_capture_analysis.py).

Explain why a constant +15 degrees/s can be bias only when the board is known
to be still; why subtracting that bias doesn't calibrate acceleration; why
the read midpoint is approximate; and what additional mapping/timing work is
needed before using gyro readings to compensate image motion. Trace the fake
sensor test before attempting any new physical motion.
