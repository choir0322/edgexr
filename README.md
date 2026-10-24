# EdgeXR

## Current priority

As clarified on 2026-10-24, the primary goal is **AP workload and systems
engineering**, without an NPU. The
[AP handoff](docs/exec-plans/active/EdgeXR_AP_Workload_Benchmark_Handoff.md)
is a flexible anchor, not a mandate to replace working code or follow its
proposed model/runtime sequence. The current application milestone remains
**orientation-aware surroundings**: where the camera looks and what it has
observed, with measured timing and resource costs. Re-identification improvements and
learning-site expansion are paused, not removed. Start with the
[orientation and directional-memory plan](docs/exec-plans/active/orientation-aware-surroundings.md).
This is planned work, not an existing 3D pose or mapping capability.
See the [research review](docs/SPATIAL_AWARENESS_RESEARCH.md) for the papers,
alternative approaches and why a relative visual compass comes before full SLAM.
Next runnable step: [stationary orientation-input baseline](docs/ORIENTATION_BASELINE.md).
An [offline IMU-relative orientation estimator](docs/RELATIVE_ORIENTATION.md)
now reads combined-capture logs; camera-axis calibration and Pi performance
measurement are still upcoming.

Next AP experiment: [fixed IMU polling resource comparison](docs/IMU_RESOURCE_BENCHMARK.md)
measures the CPU cost of 50 ms versus 10 ms sleep on the same servo/camera workload.

## Learn the implementation

Start with the [current pipeline diagram](docs/PIPELINE.md) and the
[source-reading guide](docs/learning/README.md). Study
[image motion](docs/learning/IMAGE_MOTION.md), then
[object detection](docs/learning/OBJECT_DETECTION.md), then
[IMU readings](docs/learning/IMU.md). These describe the current code, including
its timing and limitations. Basic session-local tracking and optional
[motion-aware ID matching](docs/learning/MOTION_AWARE_TRACKING.md) exist;
an [experimental, opt-in appearance memory](docs/LIVE_DETECTION.md#quick-experimental-re-entry-check)
can now attempt to restore a recently retired ID. Its thresholds are not
calibrated. Optional provisional retries and image-motion spatial support are
documented in the [next re-identification trial](docs/REIDENTIFICATION_NEXT_TRIAL.md).
IMU fusion, verified identity and long-term memory do not exist.
For a repeatable Pi comparison of basic and motion-aware tracking, follow the
[metrics-only tracking trial](docs/TRACKING_TRIAL.md).

New: [optional live detection](docs/LIVE_DETECTION.md) adds boxes with source
age and a target 2 Hz update rate. The [saved-frame Pi baseline](docs/DETECTION_RESULTS.md)
took about 196 ms per detection. The first
[Pi tracking comparison](benchmarks/results/tracking-comparison-2026-10-18.md)
found no necessary motion-assisted ID hold in two exploratory 60-second runs;
the turns were not speed-matched, so this is not an accuracy ranking.

The [first five-minute AP result](benchmarks/results/ap-baseline-basic-2026-10-18.md)
is recorded using the [sustained AP procedure](docs/AP_BASELINE.md) and its
[active plan](docs/exec-plans/active/ap-baseline.md). The read-only collector
requires the basic `--detect --imu` preview, not the motion-aware trial.
Temperature was still rising across the measured window with a passive metal
heatsink and no fan, so power-supply details and thermal stabilization remain
open before tuning. The earlier
[saved-frame detector baseline](docs/DETECTION_BASELINE.md) remains available
for studying model output and single-image timing.

The SSH browser preview can now show [live IMU readings](docs/LIVE_IMU.md)
with `--imu`. The gyro gets a fresh stationary offset each run; image and IMU
readings are displayed together without claiming exact synchronization.

For SSH-only operation, start the [live browser camera preview](docs/LIVE_PREVIEW.md).
It reuses image-motion analysis and reports processing rates. The Pi binds only
to loopback; your Mac connects through an SSH tunnel. Initial Pi/browser checks
passed with near-30 fps analysis and zero reported skips. Optional IMU readings
are available; no footage is saved and there is no servo control.

Offline [visual motion versus gyro analysis](docs/VISUAL_MOTION.md) is now
available for saved recordings. It uses optional NumPy plus FFmpeg, with an
optional Matplotlib chart; nothing is installed automatically. Read
[the first results](docs/VISUAL_MOTION_RESULTS.md) before interpreting correlation
as calibration or synchronization.

An optional [servo-driven motion-quality experiment](docs/SERVO_MOTION_QUALITY.md)
now has a dry-run preview and a supervised, explicitly armed Pi workflow. It
uses small, sequential pan/tilt sweeps and the existing saved-video analyses;
the live browser preview still does not control servos. Verify the actual HAT
channels and physical center before any real movement.

The [camera and IMU recorder](docs/COMBINED_CAPTURE.md)
saves local video and timestamp logs at 720p/30 fps using existing dependencies.
Mounted IMU turn/return results are recorded in the active IMU plan; camera/IMU
synchronization and camera-axis calibration remain unverified.

EdgeXR is a learning-first spatial-perception and performance project for a
Raspberry Pi 4. The intended system will use a USB global-shutter OV9281 camera,
an IMU from the SunFounder AI Fusion Lab Kit, object detection/tracking, and
careful measurement of latency, CPU use, memory use, and temperature.

This repository is deliberately starting with documentation and verification
tools rather than a large codebase. Each addition should answer a question,
explain its tradeoffs, and be tested or observed.

## What EdgeXR will demonstrate

Move the camera around a small scene. The system should detect and track visible
objects, use IMU information to distinguish camera motion from scene motion,
and report how its workload performs on the Raspberry Pi.

Read [the project brief](docs/PROJECT.md), [architecture](docs/ARCHITECTURE.md),
[hardware guide](docs/HARDWARE.md), and [benchmark protocol](docs/BENCHMARKING.md)
before adding a feature.

## Start in VS Code

1. Open this root folder in VS Code: `code .`
2. Read `AGENTS.md` and `docs/ROADMAP.md`.
3. Run `bash scripts/check_project.sh` to confirm the starter layout is intact.
4. Work through Roadmap Phase 0: verify the Pi, USB camera, and IMU separately
   before integrating them.

The included VS Code recommendation only suggests the Python extension; it does
not install anything or choose a Python environment for you.

## GitHub workflow

This folder is initialized locally on the `main` branch. Create an empty GitHub
repository named `edgexr` (do not add a README or `.gitignore` there), then add
it as this repository's `origin`:

```bash
git remote add origin https://github.com/YOUR-ACCOUNT/edgexr.git
git push -u origin main
```

For each small, working unit of progress:

```bash
git status
git diff
bash scripts/check_project.sh
git add <specific files>
git commit -m "docs: describe the first camera check"
git push
```

Use a short branch for experiments or a feature, and merge it only after its
documentation and checks are current. Push at the end of a meaningful session;
do not treat an unpushed local commit as a backup. Never add passwords, tokens,
raw video, or large model files to commits.

## Current status

The first Pi check identified a 1280x720 MJPEG mode near 119 decoded frames per
second. The observation and remaining unknowns are in `docs/HARDWARE.md`.
To repeat a timestamped capture/decode baseline on the Pi:

```bash
python3 src/camera/capture_baseline.py --device /dev/video0 --seconds 10
```

Choose the device reported by `scripts/hardware_inventory.sh`; `/dev/video0`
was correct for the first check but is not guaranteed. The tool requires FFmpeg,
which was already available on the tested Pi. It requests 1280x720 MJPEG at
120 fps by default and does not save footage. Use `--help` to see mode options.
Run hardware-independent checks with:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests/unit -v
```

Camera capture, the sample image, and initial IMU checks have been reviewed.
See the linked results for what is measured and what remains unverified.

## IMU raw baseline

The SunFounder 10-axis IMU is connected and responds to motion, but its vendor
calibration produced invalid stationary values. Do not use that calibration
for camera-motion estimates. The first EdgeXR IMU tool only reads SH3001
acceleration and gyro data; it does not change the vendor configuration.

After reviewing and pushing this change, pull it on the Pi. Place the IMU
motionless on a stable, nonmetallic surface, and run:

```bash
cd ~/projects/edgexr
git pull --ff-only
sudo python3 src/imu/raw_baseline.py --seconds 10
```

The tool reports axis means and variation, acceleration magnitude in g, and
the stationary gyro mean as an **offset estimate**. It does not apply that
offset yet. SunFounder's read_raw() skips its saved user calibration but still
converts sensor registers, so this is a driver-level baseline rather than a
direct register dump. Record the exact board orientation and keep the board
still throughout the run. See docs/exec-plans/active/imu-baseline.md.

To test whether the offset holds beyond the samples used to estimate it, run
two separate stationary windows with a pause between them:

```bash
sudo python3 src/imu/raw_baseline.py --seconds 10 --verify-gyro
```

The second window reports raw and offset-corrected gyro means. Keep the board
still through both windows and the pause. The correction is only shown in the
report; it is not saved, applied to the accelerometer, or used by tracking.

## Timestamped IMU rotation check

After the stationary gyro offset has been checked, use a separate, read-only
test to see how the sensor responds to an approximate 90-degree turn:

```bash
sudo python3 src/imu/rotation_test.py --still-seconds 10 --rotate-seconds 5
```

Keep the IMU still during the first 10 seconds. The program then waits for
Enter. If the wires and mounting allow safe motion, press Enter, turn the board
approximately 90 degrees around the vertical direction while keeping it level,
and stop within five seconds. Do not disconnect the board or strain the HAT
while powered; if safe movement is not possible, skip the rotation phase.

The tool subtracts that run's stationary gyro offset and integrates using
actual monotonic timestamps. It reports relative angles around the IMU's X,
Y, and Z axes, plus sample timing. These are not yet camera coordinates or an
absolute compass heading. It does not change hardware settings, save data, or
modify the SunFounder calibration file.
