# Offline sparse reconstruction: first calibrated pair

## Purpose / big picture

Produce a reviewable sparse point cloud and camera poses from a translated pair
in one static scene. This is the first bounded implementation of the user's
approved 3D milestone, a numerical workload for later AP study.

## Context and orientation

Pi 4 with existing OV9281 camera at fixed-focus 1280x720 MJPEG; existing OpenCV,
NumPy and FFmpeg. Candidate calibration from camera-calibration-screen-01.
`spatial.sparse_reconstruction` does offline two-view geometry; existing
`recording.combined_capture` records the 60-second scene and HDMI preview.
See [capture/analysis instructions](../../OFFLINE_SPARSE_RECONSTRUCTION.md).

## Progress

- [x] 2026-11-15 User authorized candidate calibration and offline sparse reconstruction.
- [x] Implement two-view matching, pose, triangulation, gates and export.
- [x] Test known synthetic geometry, insufficient data and stationary/pure rotation rejection.
- [x] Review/update PIPELINE.md and learning/SCENE_MEMORY.md.
- [ ] Capture translated static scene on Pi, inspect candidate and record quality/runtime.
- [ ] Add third-view registration/refinement and independent geometry checks.

## Plan of work

Start with explicit pair selection so failures can be traced to the actual
images. Export both images, geometry statistics and arbitrary-scale PLY points.
Use fixed gates before inspecting this trial; don't tune on the result to
declare success. Expand to multi-view only after the first pair is reviewable.

## Concrete steps

Follow OFFLINE_SPARSE_RECONSTRUCTION.md: 60-second translated static scene,
first pair at 5/15 seconds, transfer capture and result. Use a new output folder
on retry. Keep calibration resolution/focus. Existing software sends no motor
commands and changes no camera controls.

## Validation and acceptance

Synthetic known 3D points must recover shape up to unit baseline; identical
views and pure rotation must not produce an accepted cloud. Check malformed
input rejection. Real acceptance needs actual translation, broad matches,
positive-depth points, adequate parallax and low residuals, plus visual review.
Two-view gates alone are not proof of metric accuracy. Camera poses/points have
arbitrary scale. Final multi-view milestone and held-out validation remain open.

## Surprises and discoveries

The calibration already exists; no new dependencies or calibration session are
needed. The detector/IMU/scene-label map do not supply camera translation.

## Decision log

2026-11-15: Build a two-view inspectable starting step using existing OpenCV;
avoid introducing a large reconstruction package before seeing the first scene.
Use fixed 30-point, 1-degree parallax and 2-pixel reprojection gates, plus spatial
distribution. They are provisional diagnostic settings, not accuracy guarantees.

## Outcomes and retrospective

Implementation and synthetic checks complete; Pi capture and real geometry
review pending. Full multi-view reconstruction/refinement remains future work.
Five focused unit tests pass, including report/image preservation on rejection
and refusal to overwrite output. FFmpeg extraction was checked on the existing
calibration video (720x1280 uint8), and CLI help/diff whitespace checks pass.
The repository-wide learning-contract audit still reports existing docstring
and anonymous-callback issues in other files; none were reported for this
new source/test pair. No unrelated code was changed to resolve that audit.
