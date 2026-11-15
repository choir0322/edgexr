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
- [x] Capture translated static scene on Pi, inspect candidate and record quality/runtime.
- [x] Capture first Pi scene and inspect 5/15-second pair; reject for concentrated upper-bookcase points.
- [x] Add and test vertical-half point-coverage gate after identifying first-scene failure.
- [ ] Repeat with textured foreground supplying points in both image halves.
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
First Pi pair had 309 numerically accepted points, but 307 projected onto the
upper 240 rows of the first image and none onto the desk. The first candidate
was insufficient as a spatial scene map despite low reprojection residuals.
See [first-scene review](../../SPARSE_SCENE_01_RESULTS.md).

## Decision log

2026-11-15: Build a two-view inspectable starting step using existing OpenCV;
avoid introducing a large reconstruction package before seeing the first scene.
Use fixed 30-point, 1-degree parallax and 2-pixel reprojection gates, plus spatial
distribution. They are provisional diagnostic settings, not accuracy guarantees.

2026-11-15: Add a vertical-half support gate after the first real scene exposed
the weakness of three occupied quadrants: only one or two exceptional points
could satisfy it. Require at least 20% and 10 points in each vertical half of
both views. Keep this revision distinguished from the original Pi report.

## Outcomes and retrospective

Implementation and synthetic checks complete; Pi capture and real geometry
review of the **first scene complete**; that scene is diagnostic, not accepted.
Repeat with textured foreground. Full multi-view reconstruction/refinement
remains future work.
Five focused unit tests pass, including report/image preservation on rejection
and refusal to overwrite output. FFmpeg extraction was checked on the existing
calibration video (720x1280 uint8), and CLI help/diff whitespace checks pass.
The repository-wide learning-contract audit still reports existing docstring
and anonymous-callback issues in other files; none were reported for this
new source/test pair. No unrelated code was changed to resolve that audit.
