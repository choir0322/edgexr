# Combined recording review — 2026-10-04

Inspected combined-still-01 and combined-motion-01 copied from the Pi.
Both metadata files report complete; FFmpeg exited normally on signal 2.
Full saved videos decoded as MJPEG 1280x720 with 453 and 454 frames respectively,
matching the frame CSVs. The user confirmed visible stationary/motion content.

## Conditions and scope

Pi 4; Linux 6.12.47+rpt-rpi-v8 aarch64, glibc 2.36, Python 3.11.2.
Vendor-described OV9281 USB camera; negotiated MJPEG 1280x720 at 30 fps.
SH3001 raw driver readings, no vendor calibration. IMU firmly mounted beside
camera. Approximately 15 seconds after the RECORDING cue, plus startup.
Motion notes describe whole-base counterclockwise turn and clockwise return.
Precise angle, lighting, exposure, temperature, cooling, warm-up, software commit
and servo state were not recorded; no full performance or accuracy claim follows.
This measures recording/decode/logging plus IMU polling, with no detection.

## Timing results

| Metric | Still | Motion |
| --- | ---: | ---: |
| Decoded frames | 453 | 454 |
| IMU samples | 305 | 304 |
| Camera PTS rate, all intervals | 29.851 fps | 29.854 fps |
| Camera PTS rate, first interval excluded | 30.079 fps | 30.081 fps |
| First PTS interval | 148.022 ms | 148.020 ms |
| Largest later PTS gap | 36.011 ms | 36.040 ms |
| Largest host frame receipt gap | 45.659 ms | 43.838 ms |
| IMU rate over timestamp span | 19.074 Hz | 18.953 Hz |
| IMU median / maximum gap | 52.074 / 53.694 ms | 52.947 / 54.380 ms |
| Common host timestamp coverage | 14.991 s | 15.035 s |

All three timestamp sequences strictly increase in both runs. No large later
gap is apparent at these requested rates. This does not prove that every
sensor sample or exposure was captured. Camera PTS and host times retain
different meanings; common host coverage does not establish synchronization.

## Motion and stationary correction

Use the first 1.0 second after each cue as an assumed stationary window
(20 samples each). These windows have gyro standard deviations below 0.24 deg/s
on every axis. Biases in X/Y/Z deg/s:

- Still: (-4.46479, +14.86534, -2.85344).
- Motion: (-4.33661, +14.83787, -2.79240).
- Independent full stationary recording mean: (-4.44493, +14.94173, -2.81096).

After subtracting each run's initial bias and trapezoidal integration across
its cue-bounded samples, the still run ends at (+0.264, +1.145, +0.685) degrees.
This is an observed stationary residual over 14.950 s, not a general drift spec.

The motion run ends at (+0.923, +13.149, -0.468) degrees over 14.946 s.
Its Y excursion reaches -82.462 degrees before returning. One-second average
rates show motion beginning in the 1–2 s bin, reversing around 5–6 s and
settling around 11 s; the planned 3-second initial hold was not followed.
The first motion is negative Y, unlike the earlier positive-Y turn labeled
counterclockwise. Do not assign a physical direction from the label alone.

Last two seconds' corrected means are (-0.076, +0.065, -0.027) deg/s for motion,
consistent with little final motion at the available sampling rate. Yet Y
has not integrated back to zero. Baselines of 0.5, 0.75 and 1.0 seconds give
Y residuals +14.335, +13.757 and +13.149 degrees. Using the independent full
stationary mean gives +11.597 degrees. Baseline choice alone does not remove
the discrepancy. Possible causes include a different physical endpoint,
unmeasured tilt/mount movement, or dynamic sensor/driver error; these data
do not isolate the cause. Per-axis integration is not a full 3D orientation.

## Next step

The offline analyzer is implemented in src/recording/analyze_capture.py.
All 19 unit tests pass, and it was run against both full recordings.
Keep raw recordings outside Git. Repeat one marked-endpoint motion run:
stay still 3 seconds after cue, turn slowly, pause, return to the exact
reference direction, stay still. Record actual direction viewed from above.
If the approximately 13-degree discrepancy persists with a verified endpoint,
investigate dynamic scale/axis behavior before camera motion compensation.
Precise synchronization and visual motion estimation remain future work.
