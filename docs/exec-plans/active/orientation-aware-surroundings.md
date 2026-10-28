# Orientation-aware surroundings

## Purpose / big picture

2026-10-26 direction supersedes the earlier alternating feature/AP/lesson cycle:
complete this bounded vision/spatial-memory application, then perform systematic
AP optimization, then detailed teaching/visualizations. Keep correctness tests
and concise records throughout. The AP handoff remains a flexible anchor for
the later phase. See [the accepted decision](../../decisions/2026-10-26-development-order.md).

Help the Pi understand where its camera is looking and remember the scene in
those directions. Start with a fixed base and relative orientation. A successful
demo turns away and back, reports the viewing direction and uncertainty, and
recognizes previously observed regions. Object IDs are optional annotations.
This does not yet estimate world position, metric depth or a full 3D map.

## Context and orientation

Use the Raspberry Pi 4, vendor-described OV9281 monochrome USB camera and
camera-head-mounted IMU. Existing hardware uses pan channel 2 and tilt channel 3;
the user confirmed commanded zero safe previously. This plan does not authorize
new motor movement or assume commanded angles equal measured angles.

Inspect `src/imu/live_reader.py`, `raw_baseline.py`, `rotation_test.py`,
`src/recording/combined_capture.py`, `visual_motion.py`, and
`src/app/live_preview.py` before implementation. Image shifts are pixels between
processed pairs, gyro readings are degrees/second, and host timestamps are not
camera exposure synchronization. Existing raw accelerometer calibration issues
remain unresolved; do not silently use acceleration as trusted tilt or position.

## Progress

- [x] 2026-10-28: Four live polling trials and user confirmation of visible
  pan/tilt returns recorded in [the comparison](../../LIVE_IMU_POLLING_AB_RESULTS.md).
  Explicit 10 ms polling is the proposed reference for scene-memory development;
  systematic AP work remains deferred under the accepted development order.
- [x] 2026-10-26: Record functionality → AP → learning order in AGENTS,
  roadmap, project brief and the decision record. No runtime change in this update.
- [x] 2026-10-26: User reports launching the implemented live quaternion
  preview; quantitative live quality and AP results remain unreported.
- [x] 2026-10-29: Implement [offline scene memory](../../SCENE_MEMORY.md), with
  real OpenCV tests and an inspected return in existing Pi footage.
- [ ] Next: verify on Pi and held-out scenes, then integrate bounded scene
  memory with live telemetry and valid relative direction context.

- [x] 2026-10-24: Review AP handoff against existing capture, IMU, tracker,
  detector and profiler; preserve it as an anchor rather than a replacement plan.
- [x] 2026-10-24: Inspect existing timestamp/polling paths; prepare the
  [stationary input baseline](../../ORIENTATION_BASELINE.md) using existing code.
- [x] 2026-10-24: User ran the 60-second stationary Pi input baseline; 1804
  in-window camera frames at 30.08 Hz and 1126 IMU reads at 18.75 Hz, with no
  observed IMU interval over the diagnostic 160 ms threshold. First-to-last
  ten-second raw gyro means changed by (+0.034, +0.085, −0.033) deg/s. The
  run does not validate camera-axis alignment or AP compute cost.
- [x] 2026-10-24: Build and test the first **offline, gyro-only, IMU-frame**
  relative orientation estimate on prior still and turn-return recordings.
- [x] 2026-10-24: Pi stationary estimate: 2.72° apparent rotation over 49.96 s
  after a ten-second bias window; one integration took 22.45 ms. Sustained
  resource cost and repeatability remain unmeasured.
- [x] 2026-10-24: Controlled ±20° pan/return produced an 11.44° final gyro
  residual despite a close visual return. Video shows brief movement bursts;
  insufficient polling is a hypothesis, not a confirmed sensor failure.
- [x] 2026-10-24: Add explicit `--imu-interval` forwarding to the servo recorder,
  preserving its 0.05 s default, and document the approved 0.01 s repeat.
- [x] 2026-10-24: Review/update docs/PIPELINE.md and docs/learning/IMU.md for
  offline interval forwarding. Live topology and live polling are unchanged.
- [x] 2026-10-24: 10 ms sleep reached about 80 reads/s with 1.77° residual.
  Replay decimation to roughly 20 Hz yielded 3.24–13.10° across four offsets.
- [x] 2026-10-24: Measure short paired fixed-rate Pi resource cost: median
  recorder work 0.415/0.885 CPU s, residual 10.77/0.79° for 50/10 ms sleeps.
  Follow the recorded results in
  [the completed fixed-rate/adaptive plan](../completed/imu-resource-scheduling.md) and
  [resource protocol](../../IMU_RESOURCE_BENCHMARK.md).
- [x] 2026-10-24: Validate command-driven polling: 15.97% fewer reads than fixed
  10 ms, similar small residuals, no demonstrated recorder CPU saving. Record
  all findings and terminology in [IMU_POLLING_FINDINGS.md](../../IMU_POLLING_FINDINGS.md).
  Keep explicit fixed 10 ms as the reference for the next offline step.
- [x] 2026-10-24: User approved the next
  [camera-axis mapping protocol](imu-camera-axis-mapping.md); tilt data pending.
- [x] 2026-10-25: Validate neutral-head camera-axis directions and measure
  isolated/live projection cost; record the controlled
  [AP result](../../../benchmarks/results/camera-axis-live-ab-2026-10-25.md).
- [x] 2026-10-25: Draft the bounded
  [live relative camera-orientation plan](live-relative-camera-orientation.md)
  before integrating camera-axis rates into a quaternion state.
- [x] 2026-10-24: Extend the existing offline capture analyzer with a
  stationary timing/bias report; review docs/PIPELINE.md and docs/learning/IMU.md
  during this implementation. Existing live flow is unchanged.

- [x] 2026-10-23: Complete a focused online primary-source review; document
  evidence, alternatives and Pi-specific limits in
  [SPATIAL_AWARENESS_RESEARCH.md](../../SPATIAL_AWARENESS_RESEARCH.md).

- [x] 2026-10-23: User redirected priority; preserve re-ID checkpoint and pause tuning.
- [x] 2026-10-23: Record standing goal-relevance reminders in AGENTS.md.
- [ ] Audit current sensor units, axis mapping, clocks, gaps and calibration.
- [ ] Agree on a small orientation measurement protocol before hardware work.
- [ ] Calibrate IMU-to-camera axes and validate relative camera orientation
  with an independent reference; current gyro-only IMU rotation is preliminary.
- [ ] Build bounded directional scene memory and a revisit check.
- [ ] Review/update docs/PIPELINE.md and docs/learning/IMU.md at implementation.

## Plan of work

1. Orientation foundation: explain the current inputs and coordinate conventions.
   Measure axis/sign, bias stability and timing before introducing fusion. Check
   camera intrinsics/distortion requirements before converting pixels to angles.
2. Relative orientation: integrate timestamped gyro readings over short windows,
   reject gaps and label drift. Design visual correction only after validating
   its assumptions; nine-patch translation is not full rotational pose.
3. Directional memory: associate bounded scene observations with relative viewing
   directions and uncertainty. Revisit evidence must include scene agreement,
   not merely similar commanded servo angles or a matching person ID.
4. Validate repeat turns and different scene regions, recording errors, false
   revisits and unknown outcomes. Keep detection optional; use only a minimal
   diagnostic display. Propose translation/3D mapping separately afterward.

## Concrete steps

### Research-backed technical sequence (historical outline, reordered 2026-10-26)

The orientation foundation below is partly implemented. The next useful
application increment is bounded visual scene memory and verified revisits.
Build visual recognition on saved frames first, then attach valid orientation
context and integrate the complete live path. Camera intrinsics and reliable
timing remain prerequisites for calibrated visual angle/drift correction, not
for a conservative image-region revisit detector. No new educational site or
dedicated AP experiment gates this implementation. The accepted decision above
defines current scope and completion behavior.

**Step 1 — Calibration and data-validity checkpoint (immediate next work).**
Audit capture timestamps, gyro sample intervals and camera calibration files.
Retain requested 1280x720 MJPEG/30 initially; verify actual negotiation. Record
current Pi OS/RAM, exposure/focus, power, passive cooling and software versions.
The observed approximately 19 Hz IMU rate is an application observation, not a
hardware limit; inspect the polling sleep and driver before proposing changes.
Keep detection/re-ID disabled for this new orientation baseline and label it as
a different workload from the old AP benchmark.

2026-10-24 refinement: first reuse `src/recording/combined_capture.py` under
`docs/ORIENTATION_BASELINE.md`. It already saves read durations and timestamps;
do not create another recorder until analysis demonstrates missing information.
The separate orientation-baseline module is deferred, not implemented.
Proposed `docs/ORIENTATION_BASELINE.md` will give a finite-duration procedure:
60 s still, then separately labelled pan and tilt movements with pauses, then
five turn-away/return cycles. Confirm safe movement method and range with the
user before running; no forced manual back-driving of powered servos. Keep the
base fixed and camera/IMU rigid. Use independent reference marks or, if approved,
a calibrated printed target; servo command zero is not ground truth.

Calibrate camera intrinsics/distortion with multiple target views before
claiming angular accuracy. Store calibration resolution and focus state; scale
intrinsics correctly for analysis images. First establish axis/sign mapping;
a rigorous camera-to-IMU rotation requires more than identifying one dominant
axis. Estimate/check timestamp lag across repeated nonconstant motions and
report jitter; do not call uncertain host alignment synchronized exposure.

**Step 2 — Offline visual compass, without an IMU fusion dependency.**
Prototype `src/spatial/visual_rotation.py` on saved grayscale frames: extract
bounded ORB features using installed OpenCV, match them, reject outliers, and
fit a calibrated rotation to bearing rays. Start at 640x360 as a proposed
experiment, not an established best size; retain source calibration transform.
Compare the rotation fit with a general homography and inspect spatially spread
residuals. Reject translation/parallax/weak evidence rather than converting every
homography to an angle. Use synthetic known-rotation tests and held-out scene
pairs. Retain FFT as a comparison diagnostic, not the angle estimator.

**Step 3 — Short-term gyro propagation and visual correction.**
Proposed `src/spatial/orientation.py` holds a quaternion/rotation matrix relative
to session start, bias, timestamps and validity. Integrate mapped angular rate
in radians with actual sample intervals; never bridge a gap silently. Compare
gyro-only, vision-only and combined outputs on the SAME saved input. Calibrate
the sensor-to-camera rotation and time alignment before fusion. Visual matches
to old keyframes can correct drift; uncertain vision must not overwrite a good
estimate. Do not integrate accelerometer into position or use its current raw
values as trusted gravity. No magnetometer heading claim near the servos.

**Step 4 — Directional scene memory.**
Proposed `src/spatial/scene_memory.py` stores at most 30 keyframes initially:
session orientation, angular coverage, timestamp, bounded descriptors/features,
private thumbnail and validity evidence. Compare to a small candidate set and
verify scene geometry; gyro direction narrows search but does not prove a revisit.
On loss of tracking, mark orientation unknown and attempt visual relocalization
against the bounded memory. Do not overwrite a known region on a weak match.
Use fixed-capacity eviction, explicit reset and stale-region labels; moving
objects must not become permanent spatial landmarks. No 360-degree sweep is
required: observe only the safe reachable sector and mark the rest unobserved.

**Step 5 — Pi integration and honest demonstration.**
Add one optional orientation worker and a minimal status snapshot only after
offline gates pass. Show relative yaw/pitch, validity, last visual correction,
known/unknown region and reference keyframe ID. Preserve latest-frame scheduling,
bounded memory and independent timestamps. Update docs/PIPELINE.md and the IMU
learning guide; do not build another learning website. Measure estimator latency,
CPU, RSS, temperature, sample gaps and revisit latency on Pi before re-enabling
optional detection. Later decide whether base translation warrants a measured
ORB-SLAM3/OpenVINS/VINS/SVO evaluation rather than a home-built full SLAM system.

### Proposed acceptance gates (not measured results)

- Calibration: report reprojection residuals on held-out target images, not just
  the fitting set. Agree on reference precision before claiming degrees accuracy.
- Orientation: initial engineering target is median <=3 degrees and p95 <=5
  degrees reference error on at least 10 held-out, slow fixed-base turns. Also
  report 60-second stationary drift and return error; reject this target if the
  reference measurement cannot resolve it. Limits are project proposals, not
  promises derived from research papers.
- Revisit: test at least 20 labelled old/new scene queries including repeated
  patterns and moving foregrounds. Aim for >=90% correct known-region retrieval
  and no false revisits in that small set; report unknowns separately and never
  interpret zero observed errors as a population guarantee. Keep tuning and
  evaluation clips separate.
- Integrity: every injected missing/invalid timestamp interval must produce an
  explicit gap/unknown state; no unexplained continuous pose through a dropout.
- Pi feasibility: tentative >=5 visual orientation updates/s with p95 compute
  <=200 ms on the orientation-only workload. Measure, then revisit scope if
  unmet; do not silently lower thresholds or hide dropped frames.
- Failure tests: blank wall, fast turn, near/far parallax, obscured camera and
  base translation. Require conservative rejection when evidence is insufficient.

Proceed through authorized implementation and correctness validation without a
separate lesson or AP comparison after each substep. Reuse existing dependencies
and recordings. The visual-rotation and scene-memory module names above remain
proposed; the existing live gyro estimator is `spatial.live_orientation`.

## Validation and acceptance

Hardware-independent tests must cover known constant angular rates, timestamps,
axis/sign transforms, missing samples, resets and directional-memory boundaries.
Hardware trials must record Pi OS/software commit, camera mode, scene, duration,
mounting and timing limits under docs/BENCHMARKING.md. Set numeric acceptance
targets before collecting the orientation trial, not after observing its results.
Report return-to-start error, drift, revisit correctness and uncertainty; do not
substitute successful object-ID recovery for spatial success. Verify learning
guide and pipeline match actual implementation before claiming completion.

## Surprises and discoveries

Prior work focused on identity continuity, although the user's main objective
is spatial awareness. Those components remain useful but are not prerequisites
for the next orientation milestone.

## Decision log

- 2026-10-26: Complete functional spatial scene memory first, then AP work,
  then detailed learning material. Keep records and tests throughout; next
  implementation is geometry-verified scene revisits supported by valid gyro
  context. Do not claim metric pose from uncalibrated image matches.

- 2026-10-24: AP learning is primary; spatial awareness is its current bounded
  workload. Handoff model/runtime suggestions are not verified selections.
- 2026-10-24: Start with one stationary 60-second recording and inspect saved
  timing rather than changing hardware settings or duplicating recorder code.
- 2026-10-24: Reuse `recording.analyze_capture` for first/last still windows,
  measured intervals and read duration. No new camera/IMU worker was needed;
  live pipeline diagram reviewed and unchanged. The IMU guide remains accurate
  about raw gyro units and lack of camera pose.
- 2026-10-24: Add an offline quaternion composition of bias-corrected gyro
  samples. Reject timing gaps over 0.2 s rather than produce a continuous pose.
  `docs/PIPELINE.md` and `docs/learning/IMU.md` now describe the offline branch;
  their live-worker descriptions remain unchanged. Existing Oct 4 recordings
  are useful sanity checks, not calibrated accuracy or Pi AP benchmarks.
- 2026-10-24: Pipeline and IMU learning guide reviewed; unchanged because this
  step reuses the existing raw recorder, without fusion or live topology changes.

- 2026-10-23: Fixed-base relative orientation first; full position/depth deferred.
- 2026-10-23: Pause re-ID tuning and learning-site expansion; keep AP optimization
  later, while retaining profiling when needed for measurement validity.
- 2026-10-23: Explicitly flag less-relevant detours before expanding scope.

## Outcomes and retrospective

Gyro-only live relative camera orientation is implemented and the user reports
running it on the Pi, with four logged polling trials and qualitative visual
return confirmation. Offline visual scene memory was implemented on 2026-10-29;
live scene memory, calibrated visual correction and mapping remain pending.
The pipeline and concise source guide now describe the offline branch while
preserving the current live data flow.
