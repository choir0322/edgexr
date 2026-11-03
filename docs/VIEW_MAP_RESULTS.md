# View-map evidence and visibility review — 2026-11-04

## Status

**Live map bookkeeping verified; angular accuracy not validated.**
Source: local `live-view-map-01`, Pi commit
`4c01f7fdd1dc4133cc54c623c6386866b05126f1` with dirty worktree reported.
Raspberry Pi 4, Linux 6.12.47+rpt-rpi-v8 aarch64, Python 3.11.2,
OpenCV 4.11.0, two internal threads; 1280×720 grayscale source, ORB 640×360,
1 Hz scene target, 10 ms IMU sleep, detector off. Three textured indoor views.
180 observations spanning 179.109 s. Power/cooling were not recorded in this
trial; no dedicated warm-up or total CPU, memory, temperature or energy benchmark.
Raw private images and logs remain outside Git.

All 180 rows contain map snapshots. Final map: three nodes, five directed links,
11 observed label changes. Decisions: 95 known, 65 unknown no-match, 17 empty
memory, three enrollments. Orientation ready on 179 rows, unknown at startup on
one. Recording accepted/wrote all 180 with zero drops, queue high-water one.
Map-update wall time median 0.4733 ms, maximum 1.7075 ms; not total CPU cost.
Maximum IMU midpoint gap 33.64 ms, zero gaps over 200 ms and no stale observation.

## Images versus orientation

Viewed each enrollment PNG and the last recognized query for that view. Then
re-extracted ORB features from the saved 640×360 PNGs on the Mac (OpenCV 4.11.0):
600 features, mutual Hamming matches, ratio <0.75, distance ≤64, homography
RANSAC 3 px, 2000 iterations, confidence .995, RNG seed 0 per pair. Values below
are medians over geometric inliers of query minus reference feature positions.
This offline PNG diagnostic is not the original live candidate count, a pose
solver, or a calibrated angular measurement.

| View | Reference → last query frame | Inliers | Median dx, dy (pixels) | Median displacement length | Logged pointing separation |
|---|---|---:|---:|---:|---:|
| 1 center | 515 → 5391 | 329 | −12.44, +2.07 | 13.00 px | 16.53° |
| 2 left | 1027 → 3645 | 61 | +200.40, +3.80 | 201.49 px | 21.07° |
| 3 right | 1508 → 3224 | 132 | +84.60, +6.80 | 84.75 px | 7.70° |

Center: same cabinet/books/bottles, small visible displacement, not pixel-identical.
After 162.09 seconds the logged full orientation difference is 23.68°, including
roll; pointing separation is 16.53°. This discrepancy is a reason to investigate
gyro drift/calibration, not proof of its exact cause. No camera intrinsics or
ground-truth angles exist here to convert 13 pixels into degrees or quantify error.

Left: the last recognized image shows much more doorway and the coat displaced
across the image. Right: the same shelf and tissue box overlap but are clearly
shifted. These are legitimate overlapping-view candidates, not exact returns.
It would be wrong to force their gyro differences to zero just because the label
matches. No thresholds, poses or saved orientations were modified.

## Browser visibility

Previously the map followed the image, fourteen metric cards and several status
paragraphs. Now a non-collapsible **Session View Map** panel precedes the camera,
with top navigation and marker **Preview UI: view-map-2**. Scene enrollment and
recording status are grouped with it. Angular estimates explicitly warn of drift.

Real in-app browser check against a localhost fixture of the actual final row:
three nodes/five links rendered, map visible at page top, camera/map links worked;
switching fixture to stale removed bearings and disabled enrollment. This was a
Mac browser check, not remote verification of the user's Pi browser session.
The server already sends `Cache-Control: no-store`; no cache workaround was added.
`make_handler` loads HTML once at server startup: after pulling, stop/restart the
Pi preview, then reload the Mac page. Pulling while it runs does not update HTML.

Checks: 188 hardware-independent tests passed, including a new layout regression
for unique IDs and map placement. Browser JavaScript syntax and diff whitespace
checks passed. The repository-wide learning-contract checker still reports
pre-existing docstring/style issues outside this change; no broad refactor was made.

## Next bounded check

Keep the map experimental. Compare repeated, image-confirmed same-direction
returns over time and stationary intervals to distinguish accumulating gyro
error from genuine viewpoint differences. Use recorded image geometry as evidence,
not as an automatic zero-angle correction. Do not claim room position or depth.
