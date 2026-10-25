# Study 3: IMU reading, timestamp and gyro display

For the measured polling tradeoff and definitions of CPU seconds/return
residual, read [IMU_POLLING_FINDINGS.md](../IMU_POLLING_FINDINGS.md). The
[offline camera-axis fit](../IMU_CAMERA_AXES.md) reuses saved pan/tilt recordings;
it is provisional and not part of the live pipeline.

Read `spatial.camera_axes.movement_legs` after the relative-orientation code:
it checks the saved command order, aligns command and IMU **host** times, and
integrates bias-corrected XYZ rates within three movement legs. Read
`fitted_direction` next: two opposing legs fit an axis and the third checks
its sign. `fit_camera_axes` uses the user's observed lens directions to set
camera-X and camera-Y signs, makes the axes perpendicular, then uses their
cross product for camera-Z. `camera_components` projects an IMU angular vector
onto those camera axes. Neither servo sign nor raw IMU board labels alone tell
us which way the lens points.

For the independent direction check, `servo_motion_quality.build_schedule`
has a dedicated `--axis-validate-tilt` path: one 0° → −6° → +6° → 0° tilt
sweep at 5 commanded degrees/s, not the usual multi-phase series.
`camera_axes.validate_recording` maps each new tilt-leg integral into the
original fitted camera frame. With `--validate-tilt-folder`, only tilt is
checked and `axes_checked` says so; pan is not silently retested. A weak leg
stays inconclusive. The [run and retrospective bias-window procedure](../IMU_CAMERA_AXES.md#independent-tilt-only-check-and-bias-window-reanalysis)
keeps this offline until measured evidence supports live use. The original
first-two-seconds bias protocol remains the default; the new window is
explicitly selected only for the validation recording and is reported.
The uncovered-lens `-03` repeat passed all three tilt legs and physically
confirmed the first tilt sign; the earlier independent pan legs had passed.
Next, `profiling.camera_axis_cost.measure` repeatedly calls the real
`camera_components` conversion using the fitted basis to estimate its isolated
Pi CPU cost. It excludes camera, IMU reads and the live worker. See the
[AP cost procedure](../IMU_CAMERA_AXES.md#uncovered-lens-repeat-and-ap-cost-check).
The subsequent [controlled live A/B test](../IMU_CAMERA_AXIS_AB.md) adds a
**separate opt-in branch**: `live_preview.main` loads the validated neutral
basis only with `--camera-axis-basis`, passes it through `State.__init__` to
`LiveImu`, and `LiveImu.publish` converts each valid new gyro sample after its
first-second offset exists. `LiveImu.snapshot` exposes both the original
sensor-axis `gyro_dps` and optional `camera_gyro_dps`, each in degrees/second,
plus a conversion count. A stale/error sample exposes neither rate as current.
The browser still displays the sensor-axis rate; this A/B conversion mode does
not by itself integrate orientation or feed tracking. `profiling.ap_baseline.validate_preview`
requires the declared A/B mode, and the collector records CPU, rates, skipped
frames and temperature without opening a second camera. The fit is only for
the unchanged neutral-head mounting.

The additional opt-in `--relative-orientation` path integrates those camera-
axis rates. `spatial.live_orientation.RelativeCameraOrientation.add` uses actual
host read-midpoint intervals. A quaternion `(w,x,y,z)` begins at `(1,0,0,0)`
at the accepted still reference. Its four numbers jointly encode rotation:
`w` is not time/speed, and `x,y,z` are not image pixels or position. A turn θ
around unit axis `(ax,ay,az)` gives an increment `(cos(θ/2), ax sin(θ/2),
ay sin(θ/2), az sin(θ/2))`. The program composes each increment instead of
adding Euler angles. The displayed shortest rotation vector is not
yaw/pitch/roll. `preview.html` shows its angle/vector/quaternion separately
from the image-motion arrow. There is no visual correction or frame pairing.
A gap over 200 ms, stale reading or error makes it unknown until a new run.
This is implemented but not yet measured on the Pi; see the
[active plan](../exec-plans/active/live-relative-camera-orientation.md).

The new [offline relative-orientation experiment](../RELATIVE_ORIENTATION.md)
reads saved IMU samples after a run. `spatial.relative_orientation.analyze`
estimates a per-run gyro offset from an assumed-still window;
`integrate_gyro` composes angular changes with actual host time intervals into
a quaternion. Its output stays in the IMU's initial frame and cannot yet tell
which direction the camera is looking. It does not change the live `--imu` path
described below.

For the offline servo experiment, `servo_motion_quality.capture_command`
passes `--imu-interval` into `combined_capture --interval`. That recorder sleeps
after each read and logs the requested pause in `metadata.json`. The 10 ms
experiment changes this software pause; the sensor's internal sampling and
filtering are separate. See [the comparison procedure](../RELATIVE_ORIENTATION.md).

The [resource experiment](../IMU_RESOURCE_BENCHMARK.md) adds `--measure-resources`
to that recorder. `CaptureResources` samples cumulative Linux CPU counters,
not wall-clock duration of an IMU read. A blocked I2C read can take wall time
without using a CPU throughout. CPU seconds divided by observed wall seconds
give one-core utilization: 0.5 CPU seconds over 20 wall seconds is 2.5%.
`compare_imu_resources` compares these costs alongside the orientation residual.
It does not change the live worker's polling.

The [offline command-driven policy](../IMU_ADAPTIVE_POLLING.md) now switches
the recorder's sleep through a stdin pipe. Read `execute_commands`'s
`prepare_motion` callback, `run_capture.request_fast_reads`, then
`CommandPolling.poll` and the recorder's `time.sleep` selection. Servo-control
requests and recorder receipt are separate events with separate host timestamps.
The comparison verifies that observed fast polling covered motion and settling.

Read [the live diagram](../PIPELINE.md) and [image-motion guide](IMAGE_MOTION.md).
The gyroscope measures angular rate around the board's axes. The default live
path shows bias-corrected rates; only the new opt-in path estimates relative
camera rotation, and neither feeds a motion-compensation algorithm. Rigid attachment means camera and IMU
move together, not that their coordinate axes are automatically identical.
The optional [motion-aware tracker](MOTION_AWARE_TRACKING.md) uses image shifts,
not gyro values; the IMU remains a separate readout in that mode.

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
