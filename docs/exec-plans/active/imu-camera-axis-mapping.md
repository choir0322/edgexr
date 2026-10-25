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
The user now confirms clearance for commanded pan within ±40° and tilt within
±25° on this assembly. These are safety bounds, not a chosen test amplitude;
the current recorder still enforces a ±6° tilt software limit.
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
- [x] Record tilt-only motion at fixed 10 ms sleep; first negative tilt points
  lens up. Analyze the transferred 653-sample run separately from an earlier
  pasted 666-sample run.
- [x] Fit provisional pan/tilt axes from bias-corrected data; report consistency
  in [the axis record](../../IMU_CAMERA_AXES.md).
- [x] Define camera-axis/sign conventions and implement/test an offline
  candidate mapping in `spatial.camera_axes`; keep it out of the live worker.
- [x] Review `docs/PIPELINE.md` and `docs/learning/IMU.md` for the offline fit;
  no live diagram edge was added.
- [x] Inspect independent combined run: pan and first two tilt legs pass the
  fixed basis; final tilt return is 0.255° and inconclusive under the 0.4° gate.
- [x] Make independent validation report all leg measurements and status
  instead of discarding useful evidence behind the first weak-leg exception.
- [x] User reviewed the independent video: lens turned right, then left,
  followed by up, then down; first-leg physical signs match the fit inputs.
- [x] Record user-confirmed safe command bounds: pan ±40°, tilt ±25°; keep
  current smaller test schedule and software limit unchanged for now.
- [x] Implement a single-phase ±6° tilt-only validation schedule and offline
  tilt-only check against the unchanged pan/tilt fit; test without hardware.
- [x] Review `docs/PIPELINE.md` and `docs/learning/IMU.md`: the live diagram
  remains unchanged because this is a separate offline recording path; the
  IMU learning guide points to the dedicated validation procedure.
- [ ] Validate on independent pan/tilt motions before using the mapping live.
- [ ] Measure transform cost on Pi before a live integration/default change.

## Plan of work

1. Reuse the recorded pan sweep and acquire a separate small tilt sweep. Observe
   whether the first (negative-command) tilt movement points the lens up or down.
   The direction of image-content movement is opposite to camera movement.
2. Inspect timestamps and actual rate, estimate a per-run still bias, and use
   movement samples to fit the dominant rotation direction in IMU XYZ for each
   axis. The implemented fit averages normalized, sign-aligned first and second
   leg integrals; it does not perform a principal-axis fit. Compare
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

The independent check uses the existing bounded commissioning mode for both
axes in one run: pan 0 → −2 → +2 → 0, then tilt through the same path. Keep
the base fixed. On the Pi, after this code is available there:

```bash
cd ~/projects/edgexr
git pull --ff-only
sudo env PYTHONPATH=src python3 -m recording.servo_motion_quality \
  --commission --axes both --execute \
  --confirm-centered --confirm-cable-slack \
  --pan-channel 2 --tilt-channel 3 --device /dev/video0 \
  --imu-policy fixed --imu-interval 0.01 --measure-resources \
  --output recordings/orientation-axis-validation-01 \
  --scene "fixed base; sequential small pan and tilt; axis validation" \
  --power "unknown" --cooling "passive metal heatsink"
```

Observe whether the first pan leg still points right and the first tilt leg
still points up. If either physical direction differs, do not label the fit
validated. Transfer only compact logs to the Mac:

```bash
mkdir -p /Users/ryanchoi/Desktop/orientation-axis-validation-01-data
scp pi@ai-fusion.local:/home/pi/projects/edgexr/recordings/orientation-axis-validation-01/{metadata.json,imu.csv,servo_commands.json} \
  /Users/ryanchoi/Desktop/orientation-axis-validation-01-data/
```

On the Mac, check the original transferred fit runs against the new run:

```bash
cd /Users/ryanchoi/Desktop/edgexr
PYTHONPATH=src python3 -m spatial.camera_axes \
  /Users/ryanchoi/Desktop/orientation-pan-10ms-01-data \
  /Users/ryanchoi/Desktop/orientation-tilt-10ms-01-data \
  --pan-first right --tilt-first up \
  --validate-folder /Users/ryanchoi/Desktop/orientation-axis-validation-01-data
```

The new capture is not included in the fitted directions. Its
`independent_validation` field reports the three pan and three tilt magnitudes,
directions and statuses relative to the fixed camera axes. Overall `pass` is
required before live use. `inconclusive_weak` does not pass, even if the weak
vector points roughly along the expected axis. Inspect motion and mounting
before changing thresholds.

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
The newly transferred tilt run has 653 IMU samples and 215 frames, differing
from an earlier pasted 666/217 output. Its own matched command and IMU logs
show +Z, −Z, +Z across the three tilt legs. The fitted pan and tilt directions
are 87.37 degrees apart. Their third-leg direction errors are 1.02 and 8.79
degrees, respectively. Tilt amplitude is small, so independent validation
remains required. Raw still gyro offsets differ substantially between runs;
each fit uses its own two-second offset.

The independent combined capture has 845 IMU samples and 293 frames. Three
pan legs were 1.82–3.27° with 2.18–2.76° error from the fixed basis. The first
two tilt legs were 0.95°/5.00° and 2.11°/1.20°. The last tilt leg was only
0.255°; its computed 20.08° error is noise-sensitive and does not turn the
weak leg into a direction failure or a pass. After the final command around
7.75 s, the IMU was nearly still by roughly 7.9 s, so a longer integration
window is not a justified fix. The user confirmed from the saved video that
the first pan leg turned the lens right and the first tilt leg pointed it up.
Keep the basis offline and the validation checkbox open. The new dedicated
`--axis-validate-tilt` schedule commands ±6° at 5 commanded degrees/s in one
phase. `--validate-tilt-folder` checks just those three legs against the
unchanged fit, leaving the earlier independent pan evidence separate. See
[the camera-axis procedure](../../IMU_CAMERA_AXES.md#next-independent-tilt-check)
for the exact Pi command and acceptance criteria. The physical run is pending;
do not weaken the gate to make the earlier weak leg pass.

## Decision log

- 2026-10-24: Start with the existing ±2-degree tilt schedule and saved pan data.
  Do not add a new motor controller, change speed/range or build a visualization.
  Fit axes only after checking signal and physical signs. Fixed 10 ms sampling
  keeps this workload comparable with the established quality reference.
- 2026-10-24: Fit only the first two command legs; hold out each final return
  leg for a direction check. Supply observed lens directions explicitly. Use
  camera +X right, +Y down, +Z forward and a right-handed orthonormal basis.
  Reject weak/inconsistent axes rather than using an unverified fit live.
- 2026-10-24: Review `docs/PIPELINE.md` and `docs/learning/IMU.md` with the new
  offline code. Add a text note and source route; the live Mermaid diagram
  remains unchanged because no live data-flow edge was added.
- 2026-10-25: Preserve the 0.4°/20° independent leg criteria. Report weak
  motion as inconclusive with per-leg evidence, not as a successful mapping.
- 2026-10-25: User confirmed this assembly can safely command pan through
  ±40° and tilt through ±25°. Choose the smallest useful bounded follow-up
  tilt sweep; do not equate a safe endpoint with a required test amplitude or
  silently change the recorder's present ±6° tilt limit.
- 2026-10-25: Use one ±6° tilt phase with existing 5°/s step spacing and fixed
  10 ms post-read sleep. Do not rerun pan merely to satisfy the former combined
  validator; retain the already-measured independent pan legs and label the
  new result tilt-only. This changes the test protocol and requires separate
  recording names and evidence, not a direct numerical comparison of tilt
  magnitude against the old ±2° command trial.

## Outcomes and retrospective

The tilt transfer and provisional offline fit are complete. Synthetic unit
tests and the two-run local CLI check pass. The first independent recording
is partially supportive but inconclusive because its last tilt leg is weak.
A strong independent check and Pi transform-cost measurement remain. No live
camera-frame pose or spatial-memory feature is claimed as implemented.
