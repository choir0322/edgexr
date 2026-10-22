# Orientation-aware surroundings

## Purpose / big picture

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

- [x] 2026-10-23: User redirected priority; preserve re-ID checkpoint and pause tuning.
- [x] 2026-10-23: Record standing goal-relevance reminders in AGENTS.md.
- [ ] Audit current sensor units, axis mapping, clocks, gaps and calibration.
- [ ] Agree on a small orientation measurement protocol before hardware work.
- [ ] Implement/test relative orientation with explicit reset and uncertainty.
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

Next session: read the modules above and the IMU hardware notes; explain which
measurements already exist and which need confirmation. Present the axis/timing
protocol for review, including safe range, duration, units and result files.
Do not download models, add dependencies, alter sensor settings or move motors
as part of this documentation checkpoint.

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

- 2026-10-23: Fixed-base relative orientation first; full position/depth deferred.
- 2026-10-23: Pause re-ID tuning and learning-site expansion; keep AP optimization
  later, while retaining profiling when needed for measurement validity.
- 2026-10-23: Explicitly flag less-relevant detours before expanding scope.

## Outcomes and retrospective

Planning checkpoint only. No new orientation estimator or spatial map exists
yet. Runtime pipeline diagram reviewed; unchanged because this commit changes
priority and documentation, not data flow. Implementation must revisit the
diagram and IMU learning guide rather than depicting planned fusion as existing.
