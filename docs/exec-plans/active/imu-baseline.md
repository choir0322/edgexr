# Raw IMU baseline

## Purpose / big picture

Measure the SunFounder IMU while motionless before using it to infer camera
motion. Success is a repeatable report of raw acceleration and gyroscope
readings, their variability, and a stationary gyro offset. No calibration is
written to the vendor configuration.

## Context and orientation

The Pi 4 uses the SunFounder 10-axis board's SH3001 through the installed
sunfounder_imu library. Its read_raw() values are in g and degrees/second,
but still pass through driver conversion. The vendor calibration file under
/root/.config/ produced invalid stationary readings and must not be used.

## Progress

- [x] 2026-10-04: Compare stationary readings with Z facing up and down.
- [x] 2026-10-04: Add a read-only raw sampling tool and unit tests.
- [x] 2026-10-04: Run a 10-second raw baseline on the Pi and record the report.
- [x] 2026-10-04: Add an independent gyro-offset verification mode and test.
- [x] 2026-10-04: Run the two-window verification on the Pi and review the residual.
- [x] 2026-10-04: Add a read-only timestamped rotation test and unit tests.
- [ ] Run a controlled rotation on the Pi and compare the reported angle with
  the approximate physical turn.

## Plan of work

1. Add pure summary functions for acceleration norm, axis means, and spread.
2. Add a Pi-only reader that collects timed SH3001 raw samples without writing
   calibration or requiring other installed packages.
3. Test the math without hardware, then run the reader on the Pi while still.
4. Estimate gyro offset in one stationary window and test it against a
   separate window; do not save or apply it to live motion yet.
5. Integrate offset-corrected gyro rates over measured monotonic time intervals
   during one approximate 90-degree turn; report all three IMU axes.

## Concrete steps

From the repository root, run unit tests on a development computer. On the Pi,
place the IMU still on a nonmetallic surface, then run:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests/unit -v
python3 src/imu/raw_baseline.py --help
sudo python3 src/imu/raw_baseline.py --seconds 10
sudo python3 src/imu/raw_baseline.py --seconds 10 --verify-gyro
sudo python3 src/imu/rotation_test.py --still-seconds 10 --rotate-seconds 5
```

Stop with Ctrl+C if a sensor read fails; no cleanup is needed. Do not move
wiring while the Pi is powered. The verification command takes two 10-second
windows separated by a two-second pause. Keep the board still throughout.
For the rotation command, first keep the IMU still for its offset window. It
then waits for Enter. Only if wiring and mounting allow safe movement, press
Enter and turn the IMU approximately 90 degrees around the vertical direction
while keeping the board level; finish within the five-second window. Do not
disconnect the IMU or pull on the HAT while powered. If the assembly cannot
move safely, do not run the rotation phase; revisit mounting first.

## Validation and acceptance

Unit tests pass. The Pi report states sample count, duration, per-axis means
and standard deviations, acceleration magnitude, and stationary gyro offset.
It must not alter /root/.config/sunfounder-imu-config.json. The user reviews
the Pi result before any correction is applied to live motion data. The
verification reports the corrected gyro mean from the *second* window, which
was not used to estimate the offset.
The rotation test reports sensor-axis angles, sample count, actual timestamp
span, and median/maximum sample gap. Its result is not yet a camera pose,
absolute heading, or proof of sensor scale accuracy. Compare the dominant
axis with the approximate physical turn; repeatability matters more than one
single match.

## Surprises and discoveries

The vendor calibration saved identical bias/scale arrays for acceleration,
gyroscope, and magnetometer. Its LinearCalibrator mutates shared default
lists; its six-face scale calculation is unsuitable for stationary gyroscope
data. Before and after a Z flip, raw Z acceleration was +1.269 and -0.726 g,
while the gyroscope remained near (-4.3, +15, -2.7) degrees/second. The
driver's SH3001 temperature byte order also appears inconsistent with its
datasheet. None of these observations alone proves sensor damage.

The first 10-second Pi baseline returned 98 samples. Acceleration averaged
(-0.519, -0.010, +1.273) g, with 1.375 g mean magnitude and 0.003 g magnitude
standard deviation. Gyro averaged (-4.186, +15.156, -2.736) degrees/second,
with axis standard deviations (0.184, 0.195, 0.111) degrees/second. The board
was reported still and flat. Exact face, surface, servo state, and warm-up time
were not recorded, so no absolute-accuracy claim is made.

In the later two-window Pi run, the first stationary gyro mean was
(-4.177, +15.133, -2.747) degrees/second. The separate second-window raw mean
was (-4.176, +15.069, -2.717) degrees/second; subtracting the first-window
offset gave (+0.001, -0.064, +0.030) degrees/second. Second-window standard
deviations were (0.178, 0.220, 0.114) degrees/second. This supports short-term
stationary consistency over roughly 22 seconds, not dynamic angle accuracy or
long-term drift stability. The same run showed 1.373 g acceleration magnitude,
still uncalibrated.

## Decision log

- 2026-10-04: Start with a read-only raw baseline and stationary gyro offset.
  Defer accelerometer six-face and magnetometer calibration until axis
  orientation and driver behavior are verified.
- 2026-10-04: Check gyro offset on a separate stationary window. Subtracting
  the offset from the same samples used to estimate it would trivially give
  zero and would not test whether the estimate remains useful.
- 2026-10-04: Use monotonic timestamps and trapezoidal integration for the
  next rotation check. A fixed assumed sample period could hide delayed reads.
  Report sensor axes rather than guessing their alignment with the camera.

## Outcomes and retrospective

The baseline and independent stationary verification ran on the Pi. The
short-term gyro offset was stable, but acceleration remains uncalibrated and
the dynamic response is unknown. The timestamped rotation test and local
tests are ready; the Pi rotation run and review remain pending.
