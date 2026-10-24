# Initial IMU-to-camera axis mapping

## Purpose / big picture

Translate the current IMU-relative rotation into directions meaningful for the
camera. First identify the pan and tilt rotation axes in sensor coordinates,
then propose a mapping at the neutral head pose and validate it on separate
motions. The AP question is what small coordinate-transform workload and data
quality checks are needed before reporting camera viewing direction.

This is the next bounded application step after the completed
[polling quality/resource cycle](../../IMU_POLLING_FINDINGS.md). Explicit fixed
10 ms post-read sleep is the reference; the optional adaptive mode is retained.

## Context and orientation

Pi 4, aarch64 Bookworm/Linux 6.12.47+rpt-rpi-v8, Python 3.11.2, OV9281 USB camera
requested 1280x720 MJPEG/30, camera-head-mounted SH3001, passive metal heatsink.
Pan channel 2, tilt channel 3, commanded zero previously confirmed safe.
Keep the IMU rigid relative to the camera and base fixed. The existing fast
pan recording is `/Users/ryanchoi/Desktop/orientation-pan-10ms-01-data` on the
Mac, with raw IMU/servo timing/metadata available. Reuse it only if mounting is
unchanged. Each recording needs its own still gyro offset.

Relevant source: `recording.servo_motion_quality.build_schedule`,
`run_capture`, `combined_capture.read_row`, and
`spatial.relative_orientation.analyze`/`integrate_gyro`. Gyro units are deg/s;
orientation output is a rotation vector in initial sensor axes, not Euler XYZ.

## Progress

- [x] 2026-10-24: User approved proceeding after recording polling findings.
- [x] Existing fast pan data available; pan mainly excites IMU Y with some X.
- [x] Verify existing tilt commissioning schedule: 0 → −2 → +2 → 0 degrees,
  eight one-degree commands at 5 commanded °/s, 7.1 s capture.
- [x] Review docs/PIPELINE.md and docs/learning/IMU.md: diagram reviewed;
  unchanged, because this step reuses the existing offline recorder and adds
  no coordinate transform or fusion to the implemented live flow.
- [ ] Record tilt-only motion at fixed 10 ms sleep; inspect signs and signal.
- [ ] Fit provisional pan/tilt axes from bias-corrected data; report consistency.
- [ ] Define camera-axis/sign conventions and implement/test a candidate mapping.
- [ ] Validate independent motions; review pipeline and IMU guide at implementation.
- [ ] Measure transform cost on Pi before a live integration/default change.

## Plan of work

1. Reuse the recorded pan sweep and acquire a separate small tilt sweep. Observe
   whether the first (negative-command) tilt movement points the lens up or down.
   The direction of image-content movement is opposite to camera movement.
2. Inspect timestamps and actual rate, estimate a per-run still bias, and use
   movement samples to fit the dominant rotation direction in IMU XYZ for each
   axis. A principal-axis fit is a possible method, not yet implemented. Compare
   both movement directions and the angle between fitted axes; reject weak or
   inconsistent evidence rather than force a mapping. Small tilt amplitude may
   be insufficient; evaluate the data before proposing another movement.
3. Establish physical signs from observation, distinguish camera coordinates
   from servo-positive coordinates, and specify a right-handed convention.
   Report an initial neutral-pose mapping, not a full high-precision extrinsic
   calibration. Pan-axis direction in head coordinates changes with tilt;
   handle reference poses explicitly rather than assuming every mount is aligned.
4. Test the proposed rotation transform on synthetic vectors and separate real
   pan/tilt traces. Then measure its processing cost at the achieved read rate.

## Concrete steps

On the Pi, after saving/pushing the documentation checkpoint from the Mac:

```bash
cd ~/projects/edgexr
git pull --ff-only
sudo env PYTHONPATH=src python3 -m recording.servo_motion_quality \
  --commission --axes tilt --execute \
  --confirm-centered --confirm-cable-slack \
  --pan-channel 2 --tilt-channel 3 --device /dev/video0 \
  --imu-policy fixed --imu-interval 0.01 --measure-resources \
  --output recordings/orientation-tilt-10ms-01 \
  --scene "fixed base; neutral pan; tilt-only camera-axis mapping" \
  --power "unknown" --cooling "passive metal heatsink"

PYTHONPATH=src python3 -m spatial.relative_orientation \
  recordings/orientation-tilt-10ms-01 --bias-seconds 2
```

Close any preview using the camera. Verify its existing device path before
using `/dev/video0`. This is the existing small real-movement commissioning
mode, not a dry run. Observe the first negative tilt leg and the physical return.
If direction is hard to judge, report it as unknown rather than guessing.
The automatic horizontal-motion/gyro-Y correlation is a pan diagnostic; it is
not the acceptance criterion for this tilt experiment. Raw XYZ data is decisive.

Transfer the compact logs from the Mac terminal:

```bash
mkdir -p /Users/ryanchoi/Desktop/orientation-tilt-10ms-01-data
scp pi@ai-fusion.local:/home/pi/projects/edgexr/recordings/orientation-tilt-10ms-01/{metadata.json,imu.csv,servo_commands.json,resources.json} \
  /Users/ryanchoi/Desktop/orientation-tilt-10ms-01-data/
```

## Validation and acceptance

Require complete capture/resources, increasing finite timestamps and no interval
above the existing 0.2 s gap limit. Inspect observed rate and motion signal against
still noise. Keep mount/base fixed and identify what zero/positive commands mean
physically. A dominant axis alone supplies an unsigned direction; one motion
axis cannot determine a full camera-frame rotation. Validate a fitted mapping on
independent data, document residual/cross-axis errors and preserve unknown states.
Do not use the currently untrusted accelerometer as calibrated gravity or infer
position/depth. Camera intrinsic/extrinsic precision and exposure synchronization
remain separate tasks. Servo commands do not establish true angular magnitude.

## Surprises and discoveries

The side-mounted IMU has a mixed response: pan mainly appears on Y but also X.
This is why simply renaming gyro Y as camera yaw is insufficient. Full-rate
sampling improved return consistency, but it did not establish camera axes.

## Decision log

- 2026-10-24: Start with the existing ±2-degree tilt schedule and saved pan data.
  Do not add a new motor controller, change speed/range or build a visualization.
  Fit axes only after checking signal and physical signs. Fixed 10 ms sampling
  keeps this workload comparable with the established quality reference.

## Outcomes and retrospective

Protocol prepared and existing schedule checked locally. Tilt data, fitted
mapping and Pi transform-cost measurements are pending; no camera-frame pose
or mapping code is claimed as implemented.
