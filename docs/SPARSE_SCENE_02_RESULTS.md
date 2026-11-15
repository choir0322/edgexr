# Sparse Scene 02: broader coverage, still a candidate

Reviewed 2026-11-15 from transferred `sparse-scene-02` and
`sparse-scene-02-pair-05-15`. The user reframed toward the textured bookshelf.
This review covers the exported 5s/15s pair, its original point cloud and
capture metadata; it is not a full-video or third-view reconstruction validation.

## What the evidence shows

| Measure | Scene 01 | Scene 02 |
|---|---:|---:|
| Descriptor matches | 375 | 421 |
| Accepted original Pi points | 309 | 323 |
| Median worst-view reprojection error | 0.402 px | 0.349 px |
| Median parallax | 14.35° | 11.20° |
| Points projected in first-image top/middle/bottom thirds | 307 / 2 / 0 | 51 / 260 / 12 |
| Estimated relative camera rotation | 4.14° | 8.05° |

Scene 02 has support in all four principal-point quadrants in both images.
Above/below-principal-point counts are 225/98 and 195/128, exceeding the
65-per-half requirement. It therefore passes the implemented coverage gates.
The photographs still show that much of the support is on the bookshelf.
Reframing moved that textured surface toward the image middle: broader image
coverage does **not** establish foreground/background depth accuracy.

The original camera-two center is `(0.99034, 0.09910, 0.09695)` in a coordinate
system where camera one is the origin, X right, Y down and Z forward, and the
camera baseline is one arbitrary unit. This is consistent with a largely
rightward viewpoint change. It is not a measured centimeter displacement.
Rotation is estimated from the recovered rotation matrix, not the IMU or
servo commands. Different trials have independent scales and coordinate frames.

## Measured computation and limits

Original Pi run: OpenCV 4.11.0, two OpenCV threads, 3,000 ORB features per image,
0.75 descriptor ratio, minimum 1° parallax and maximum 2px error in each view.
Elapsed time was 3.06195s; Python process CPU was 1.20007s, excluding FFmpeg.
These are single offline observations, not a speedup benchmark. Peak memory,
energy, temperature and full-pipeline CPU were not measured. Power, cooling and
warm-up were not recorded for this reconstruction invocation.

The 60s capture requested 1280×720 MJPEG at 30fps, recorded 1,807 frame records
and 1,169 IMU samples, reported complete with no error and no nonincreasing
camera PTS. The calibration remains `needs_review`, SHA-256
`b891cbb59a3c6d02ce4f136afdc911ef18fe0412fbd0d3c2db9bdc233f8a38a2`.
Low reprojection errors are internal fit checks, not independent depth truth.

## Interactive explanation and provenance

[The walkthrough](learning/sparse-scene-01.html) now switches between both trials
and displays actual keypoints, candidate correspondence traces, original cloud
projections, camera rays and magnified reprojection residuals. It loads private
PNGs locally, with file-picker fallback; no snapshots or video are committed.

The original Pi exports did not include observed feature IDs. The
[evidence generator](../scripts/build_sparse_learning_data.py) regenerates ORB
matches on the exact images and associates only an unambiguous paired match
within 2px of both original cloud projections. There were 190 such associations
for Scene 01 and 219 for Scene 02; 48 examples per trial are displayed. These
are recovered teaching associations, not original saved IDs. Full projected
point coverage uses the original clouds. Candidate matching lines are not
presented as geometrically accepted matches.

Reproduce with an environment already containing OpenCV and NumPy:

```sh
python3 scripts/build_sparse_learning_data.py /Users/ryanchoi/Desktop \
  --output docs/learning/images/sparse-scene-evidence.js
node scripts/check_sparse_learning.js
```

Checks: JS syntax and mocked DOM/canvas interaction checks across both trials,
all six stages, point selection and overlay toggle; numerical reprojection
checks on displayed associations. Browser visual inspection remains pending:
the browser rejected local-file access, and no alternate access workaround was
attempted. The live pipeline diagram was reviewed; unchanged because this
revision only replays offline evidence.

## Next bounded step

Check a third viewpoint from the existing recording against the same 3D points:
match observations, estimate its pose, and examine support and reprojection
error. Do not tune thresholds to force a pass. This would test consistency
beyond the two images used to construct the points, without yet claiming metric
distance, dense reconstruction or a room map.
