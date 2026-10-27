# Bounded live relative camera orientation

## Purpose / big picture

Given a fixed Pi base and an IMU rigidly mounted beside the lens, estimate how
the camera has **rotated relative to its direction at the end of this run's
startup still window**. This supplies a short-term viewing-direction signal
for a later directional scene-memory experiment. It does not locate the Pi in
the room, measure distance, or construct a 3D map.

The AP question is whether timestamped quaternion integration at each IMU
read is affordable under the existing camera/motion/detector workload, and
whether gaps/drift make the result useful over a bounded interval. The
[completed live conversion comparison](../../../benchmarks/results/camera-axis-live-ab-2026-10-25.md)
found no obvious throughput regression from approximately 18.8 camera-axis
conversions/s; its hotter second run limits precise CPU attribution. This is
the next bounded application cycle, not a detour into full SLAM.

## Context and orientation

Raspberry Pi 4, Bookworm aarch64/Linux 6.12.47+rpt-rpi-v8, Python 3.11.2,
OV9281 USB camera requested 1280x720 MJPEG/30, camera-head SH3001, passive
heatsink without fan, no NPU. The neutral-head camera basis in
`configs/camera_axes_neutral.json` was fitted from pan/tilt recordings and
checked on independent pan and uncovered-lens tilt motion. Remounting either
board invalidates that basis. The live `LiveImu.publish` path already subtracts
its first-second still offset and optionally produces camera-axis angular
**rates** in degrees/second, host-read-midpoint timed. The existing
`spatial.relative_orientation.integrate_gyro` composes gyro increments into
a quaternion offline in IMU axes. It is a mathematical reference, not a live
camera estimate or synchronized video pose.

## Progress

- [x] 2026-10-25: User requested the bounded relative camera-orientation step
  after the live conversion A/B run.
- [x] 2026-10-25: Inspect the existing offline quaternion integrator, live IMU
  state, optional camera-axis rate path, AP collector and spatial roadmap.
- [x] 2026-10-25: Draft this learning-first plan before changing the live
  orientation estimator; user review is pending.
- [x] 2026-10-25: Add the standing
  [technique/AP evidence register](../../STAGE_RECORDS.md); future estimator
  and Pi results must update it for the planned website as well as this plan.
- [x] Implement a small incremental orientation state with independent unit
  tests and explicit invalid/gap behavior; reuse the existing quaternion math.
- [x] Replay known synthetic and saved gyro sequences through the incremental
  path and compare with the offline result on the same samples.
- [x] Add opt-in live telemetry/minimal display after synthetic checks;
  preserve raw and camera-axis rates and avoid linking pose into tracking.
- [x] Review/update `docs/PIPELINE.md` and `docs/learning/IMU.md` for the new
  live branch, including axes, units, timing, freshness, unknown/reset rules.
- [x] 2026-10-27: First attended Pi pan/tilt trial completed 160 bounded
  commands and the user saw the browser quaternion change. Exact peak/return
  values were not recorded, so no quantitative orientation claim follows.
- [x] Add image-free timestamped preview telemetry and actual-command logging
  to future one-shot servo runs; hardware-free logger and schedule tests pass.
- [ ] Repeat once on the Pi using the new recording path; inspect `metadata.json`
  and the telemetry around pan/tilt peaks and final commanded center. Do not
  equate a sampled peak with every underlying IMU read.
- [x] 2026-10-28: [First logged trial](../../LIVE_ORIENTATION_SERVO_RESULTS.md)
  showed 428 ready snapshots and a persistent pan-axis return difference;
  telemetry ended just before the final tilt 0° command. Extend logger two
  seconds after the last command and require a post-command ready sample.
- [x] 2026-10-28: User confirmed the lens and browser image visibly returned
  after pan. Treat the ≈12° estimated pan-axis residual as disagreement with
  qualitative visual return, not as evidence of servo non-return. Repeat with
  settled final logging before diagnosing the cause.
- [ ] Run a fixed-base Pi still and supervised return trial; record drift,
  gaps, residual, CPU, IMU rate, motion rate, skips and temperature.

## Plan of work

1. **Define the state precisely.** Start the relative camera quaternion at
   identity after the physically still startup offset is accepted. Convert
   each fresh bias-corrected gyro rate to the fitted camera XYZ axes. Use the
   actual host read-midpoint interval and the average of adjacent rates for
   each small body-frame increment. Normalize the composed quaternion. Report
   its shortest rotation vector in degrees for inspection; do not call its
   XYZ components Euler yaw/pitch/roll or a world heading.
2. **Reject unsupported continuity.** A non-increasing time, non-finite
   reading, or gap over the existing 0.2 s offline limit must make orientation
   `unknown` rather than silently bridge it. Stale or failed IMU status must
   hide the current orientation. Only a deliberate new session/reset, with a
   new still offset, re-establishes identity; no old orientation is presented
   as if tracking continued through a dropout. Bound state to the last sample,
   quaternion, counters and status—no unbounded gyro history.
3. **Check mathematics before hardware.** Unit-test constant single-axis
   rates, alternating axes, irregular intervals, quaternion normalization,
   sign conventions, still bias, reset, gaps and stale/error states. Replay a
   saved capture using the same timestamps and fixed basis and compare an
   incremental result with an offline integration of those *same* converted
   rates. Disagreements must be understood rather than tuned away.
4. **Add an opt-in live view and measure it.** Expose relative camera rotation,
   reference-start time, age, sample count and validity through the existing
   telemetry, with a minimal UI label only if useful. Avoid a new video/IMU
   join or claim of exposure synchronization. On the Pi, compare the live
   workload with/without integration under a matched scene and duration,
   using `profiling.ap_baseline` or a small explicit extension for orientation
   status. Preserve the model, camera mode, polling interval and browser state.
5. **Validate bounded behavior.** First record a 60-second still period to
   quantify drift. Then use a separately approved, supervised fixed-base
   pan/tilt turn-and-return within already confirmed safe mechanical limits;
   do not move a powered servo by hand. Report final residual and peak
   relative rotation, but do not treat commanded servo degrees as measured
   shaft angle or precise ground truth. A repeat at 10 ms IMU post-read sleep
   is a separate variable if the default 50 ms polling misses quick motion.

## Concrete steps

The next implementation action, after plan review, is a hardware-free module
and tests. No model download, hardware setting change, camera opening or motor
command is part of that action. Later Pi commands will be written here only
after the implementation and safety checks exist. Retain distinct ignored
`recordings/` names and commit only small summaries. If the IMU mount changes,
stop and repeat camera-axis validation before using the stored basis.

## Validation and acceptance

Accept the first estimator as **gyro-only, short-term, relative camera-frame
orientation** only if synthetic and saved-sequence replay checks pass, gaps
produce explicit unknown, live samples remain finite/fresh, and Pi still/
return measurements are reported with conditions. The saved-data replay must
specify whether integration begins immediately after the still window, since
changing that start changes the reference identity. Report numerical drift
and return residual without inventing angular accuracy: current servo commands
and camera images are not an independently calibrated angle reference.

Document device, commit, negotiated or merely requested camera mode, scene,
power, cooling, warm-up/duration, read rate and CPU/temp metrics. A stable
quaternion alone is not evidence of physical orientation accuracy. The result
must remain visibly distinct from compass heading, room position and 3D map.

## Surprises and discoveries

The prior 60-second stationary offline run accumulated 2.72° apparent
rotation after its ten-second bias window. A commanded pan/return gave an
11.44° residual at roughly 19 Hz reads; a later fixed 10 ms polling trial
reduced the reported residual to about 1.77° on one run. These data motivate
bounded duration, gap checks and measured read cadence rather than a promise
that live gyro integration will remain accurate indefinitely.

## Decision log

- 2026-10-25: Build gyro-only *relative camera rotation* before a visual
  correction or directional scene memory. Do not use the still-untrusted
  accelerometer for gravity/position or the magnetometer for world heading.
- 2026-10-25: Preserve the existing live `--imu` and `--camera-axis-basis`
  modes; orientation will be an additional opt-in behavior until Pi validation.
  Reuse quaternion composition instead of summing XYZ angles independently.
- 2026-10-25: Keep the 50 ms live polling default for the first controlled
  measurement. Evaluate a 10 ms variant separately if quality, not the cheap
  integration arithmetic, is limited by sparse fast-motion samples.

## Outcomes and retrospective

Hardware-free incremental integration, opt-in telemetry and a minimal browser
readout are implemented. Synthetic ordered-rotation replay matches the offline
integrator. A read-only replay of `orientation-pan-10ms-01-data/imu.csv` used
168 physically-still-window samples in the first two seconds after the cue,
then 1,552 converted camera-axis samples. Incremental and offline quaternions
matched exactly in that Python run; both ended at a 1.769° shortest angle.
That is an algorithm-equivalence check on historical data, **not** measured
camera-angle accuracy or live AP cost. Pi still/return observation and controlled
AP cost comparison remain open. The diagram now includes the opt-in branch.
No physical orientation accuracy or live performance claim follows yet.
