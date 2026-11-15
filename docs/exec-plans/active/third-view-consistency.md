# Third-view consistency check for the Scene 02 sparse pair

**Status: deferred 2026-11-16, not implemented.** The user's clarified goal is
fixed-base spatial awareness; a pan/tilt head does not translate, so localizing
a moving camera does not serve it. See
[the decision record](../../decisions/2026-11-16-spatial-awareness-integration.md).
The method below remains a valid follow-up if a moving-camera scope returns.

## Purpose / big picture

The Scene 02 pair (5 s / 15 s) produced 323 points with low reprojection error,
but every gate so far was computed from the same two images that built the
cloud. This milestone asks one held-out question: **does a third image, never
used for triangulation, see those 3D points where a single rigid camera pose
says it should?** A pass is a bounded multi-view consistency check, not a 3D
map, metric reconstruction, SLAM or position estimate. The AP question is the
compute cost of registration (ORB on one image, descriptor matching, PnP
RANSAC) versus the original two-view pipeline.

## Context and orientation

- `src/spatial/sparse_reconstruction.py` builds the pair cloud. Its Pi report
  stored points but not which 2D feature produced each point, so the PLY cannot
  be matched to a new image directly.
- Mac OpenCV 4.11.0 equals the Pi's version, and Mac FFmpeg 8.0.1 decodes the
  5 s and 15 s frames byte-identically to the Pi snapshots (checked 2026-11-16).
  Re-running the pair should therefore reproduce the Pi report; the new tool
  verifies this instead of assuming it.
- Terms: **PnP** (Perspective-n-Point) estimates a camera pose from known 3D
  points and their 2D pixels. **RANSAC** fits from random minimal subsets and
  keeps the pose that the most correspondences agree with.
- Private inputs stay on the Desktop: `sparse-scene-02/camera.mkv`,
  `sparse-scene-02-pair-05-15/report.json`, `camera-calibration-screen-01/calibration.json`.

## Progress

- [x] 2026-11-16 Confirm repository state, private inputs and identical Mac frame decoding.
- [ ] Make `reconstruct` also return which input correspondences were kept.
- [ ] Add `spatial.third_view`: re-run pair, keep per-point ORB descriptors, register view 3.
- [ ] Synthetic tests: known pose recovered; shuffled correspondences rejected; too few rejected.
- [ ] Run on Mac for correctness at the preregistered times; record results.
- [ ] Pi run for AP timing (user-run; commands in this plan).
- [ ] Review/update `docs/PIPELINE.md`, `docs/learning/SCENE_MEMORY.md`, `docs/STAGE_RECORDS.md`.

## Plan of work

1. Return kept-correspondence indices from `reconstruct` so each accepted point
   keeps its view-1 and view-2 ORB descriptors (no change to its gates or report).
2. Match view-3 ORB descriptors against both descriptor sets of every point.
   Ratio test compares the best point against the best *different* point; keep
   one view-3 keypoint per point.
3. `cv.solvePnPRansac` with calibrated intrinsics/distortion, fixed seed, then
   compute per-inlier distorted-pixel residual, depth sign in camera 3, image
   coverage, and camera-3 centre/rotation in camera-1 coordinates (baseline units).
4. Save `view-3.png` and `report.json` in a new, never-overwritten folder.

## Concrete steps

Mac correctness run (repeat with `--third-seconds 10` and a new output name):

    cd /Users/ryanchoi/Desktop/edgexr
    PYTHONPATH=src /private/tmp/edgexr-scene-memory-env/bin/python -m spatial.third_view \
      /Users/ryanchoi/Desktop/sparse-scene-02/camera.mkv \
      --calibration /Users/ryanchoi/Desktop/camera-calibration-screen-01/calibration.json \
      --reference-report /Users/ryanchoi/Desktop/sparse-scene-02-pair-05-15/report.json \
      --first-seconds 5 --second-seconds 15 --third-seconds 25 \
      --output /Users/ryanchoi/Desktop/sparse-scene-02-third-25

Pi timing run uses the same module with `recordings/` paths after `git pull`.

## Validation and acceptance

Preregistered before any view-3 result is seen (2026-11-16): primary third time
**25 s** (outside the pair interval: extrapolation), secondary **10 s**
(between the pair: interpolation). No new thresholds; gates reuse the pair's:

- at least 30 PnP inliers;
- RANSAC/inlier residual at most 2.0 px in view 3;
- inlier pixels occupy at least 3 principal-point quadrants, and each vertical
  half holds at least max(10, 20% of inliers);
- every inlier lies in front of camera 3;
- reproduced pair counts equal the Pi reference report (otherwise the run is
  labelled `pair_not_reproduced` and not evaluated).

Reported but not gated: matched candidates, inlier fraction, median/p95 residual,
camera-3 centre and rotation. **Pass means** the held-out view agrees with the
pair's structure and calibration to within 2 px under one rigid pose. **Fail**
means at least one of: insufficient overlap, mismatch-dominated matching,
inconsistent structure, or calibration error; the report states which gate
failed, and failure is a valid result. A pass still does not establish metric
scale, absolute accuracy, or that non-bookshelf regions are well constrained.

## Surprises and discoveries

(none yet)

## Decision log

2026-11-16: Re-run the pair with observation tracking instead of recovering
associations by 2 px proximity to the PLY (as the learning page does): exact
links remove an ambiguity, and reproduction against the Pi report is checkable.
Alternatives: three-view triangulation or bundle adjustment — deferred; they
change the cloud being tested instead of testing it.

## Outcomes and retrospective

(pending)
