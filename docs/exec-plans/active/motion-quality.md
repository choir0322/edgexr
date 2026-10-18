# Motion-estimator quality: four controlled recordings

## Purpose / big picture

Find when the existing 320×180 image-shift estimator reports a useful global
camera-view displacement, rejects an ambiguous pair, or mistakes local object
motion for camera motion. Keep this separate from the AP speed/thermal baseline.

## Context and orientation

The Pi 4 records OV9281 USB camera MJPEG at requested 1280×720/30 fps plus raw
camera-mounted IMU readings in `combined_capture.py`. `visual_motion.py`
decodes to 320×180, compares nine patches per adjacent frame pair, and pairs
its estimate with host-observed IMU readings. Pairing is approximate, not
exposure synchronization. `motion_quality.py` aggregates those CSV rows. No
tracking/detector changes, servo commands, model downloads or new dependencies.

## Progress

- [x] 2026-10-19: User asked to move on to this test; define four controlled
  conditions and implement an offline comparison without changing the live path.
- [x] 2026-10-19: Review `docs/PIPELINE.md` and `docs/learning/IMAGE_MOTION.md`;
  add offline-test links/limits if they need clarification.
- [ ] Run four Pi recordings and analyze them; record conditions and outcomes.
- [ ] Identify one evidenced failure mode and decide whether to change the
  estimator, scene protocol, or neither. Do not tune thresholds beforehand.

## Plan of work

1. Preserve the current camera mode and estimator thresholds. Capture still,
   slow turn, fast but controlled turn, and a moving person with the rig still,
   one recording each. Begin every clip with at least one full second still.
2. Analyze all four with `visual_motion.py`. Rejected pairs must remain in the
   CSV, including a run with no accepted pair.
3. Compare visual coverage, displacement per pair and gyro coverage with
   `motion_quality.py`. Inspect per-second direction and the video before
   judging any mismatch. Movement timing is manually noted, not ground truth.
4. After reviewing the data with the user, pick exactly one improvement if
   the evidence justifies it, then repeat the relevant trial unchanged.

## Concrete steps

Follow `docs/MOTION_QUALITY.md`. Use new names for each retry, never overwrite
recordings. Confirm the camera head/IMU are rigid together and cables have
slack. No camera preview should have the device open during recording. Capture
files remain ignored by Git; share summaries and notes, not raw video by default.

## Validation and acceptance

- Hardware-free tests cover an all-rejected clip, missing gyro observations,
  and rejected pairs excluded from displacement statistics.
- Each Pi run records commit, camera mode, scene/light, approximate movement
  timing, duration and whether the mount moved relative to the camera.
- Still and person-motion trials are assessed for false global shift; turn
  trials for direction, coverage and rejection, not absolute angle accuracy.
- `docs/PIPELINE.md` and `docs/learning/IMAGE_MOTION.md` have been checked for
  accurate input shape, units, scheduling, freshness and links.

## Surprises and discoveries

None from the new Pi trials yet. Earlier AP measurements showed a sustained
~26 fps live motion-analysis rate, but this offline video analysis is a
different workload and must not be compared as a speed benchmark.

## Decision log

- 2026-10-19: Use existing saved-video and IMU tools before touching live
  motion logic. Report failures explicitly rather than filtering them away.
- 2026-10-19: A >1-pixel per-pair magnitude is a reporting aid for fixed-camera
  trials, not a correctness threshold or an algorithm setting.

## Outcomes and retrospective

Awaiting the four Pi recordings. The test can describe consistency and failure
modes, but no ground-truth camera pose or synchronized sensor latency.
