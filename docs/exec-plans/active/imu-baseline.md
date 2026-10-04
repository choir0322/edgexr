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
- [ ] Run the tool on the Pi and record conditions and results.

## Plan of work

1. Add pure summary functions for acceleration norm, axis means, and spread.
2. Add a Pi-only reader that collects timed SH3001 raw samples without writing
   calibration or requiring other installed packages.
3. Test the math without hardware, then run the reader on the Pi while still.

## Concrete steps

From the repository root, run unit tests on a development computer. On the Pi,
place the IMU still on a nonmetallic surface, then run:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests/unit -v
python3 src/imu/raw_baseline.py --help
sudo python3 src/imu/raw_baseline.py --seconds 10
```

Stop with Ctrl+C if a sensor read fails; no cleanup is needed. Do not move
wiring while the Pi is powered.

## Validation and acceptance

Unit tests pass. The Pi report states sample count, duration, per-axis means
and standard deviations, acceleration magnitude, and stationary gyro offset.
It must not alter /root/.config/sunfounder-imu-config.json. The user reviews
the Pi result before any correction is applied to live motion data.

## Surprises and discoveries

The vendor calibration saved identical bias/scale arrays for acceleration,
gyroscope, and magnetometer. Its LinearCalibrator mutates shared default
lists; its six-face scale calculation is unsuitable for stationary gyroscope
data. Before and after a Z flip, raw Z acceleration was +1.269 and -0.726 g,
while the gyroscope remained near (-4.3, +15, -2.7) degrees/second. The
driver's SH3001 temperature byte order also appears inconsistent with its
datasheet. None of these observations alone proves sensor damage.

## Decision log

- 2026-10-04: Start with a read-only raw baseline and stationary gyro offset.
  Defer accelerometer six-face and magnetometer calibration until axis
  orientation and driver behavior are verified.

## Outcomes and retrospective

The baseline tool and unit tests are ready; the Pi run is pending.
