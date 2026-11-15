# First sparse scene: geometry works, scene coverage does not

The Pi completed a 60-second 1280×720 MJPEG recording with HDMI preview: 1,807
decoded frame records, 1,168 IMU samples, no recorded timestamp reversals. The
user moved the whole rig to the right twice and back toward the initial area.
Exact movement timings need not match the suggested schedule. At 5, 15, 27 and
45 seconds the saved images show overlapping but different viewpoints. The
bookcase, smooth tissue box and largely plain tabletop stayed in view.

The Pi's original 5/15-second analysis reported **375 descriptor matches, 309
essential-matrix inliers, 309 accepted triangulated points**, 14.35° median
parallax and 0.40-pixel median per-point worst-view reprojection error (p95
0.94 pixels). The relative second camera center moved in positive X, consistent
with the lens shifting right. These numbers show a plausible two-view estimate,
not a measured 3D room shape or metric distance.

Inspection of the exported 309-point PLY reveals the limitation: when projected
onto the first image, **307 points fall in the upper 240 image rows, 2 in rows
240–479, and 0 on the lower desk**. The points cluster on the textured
bookcase. Smooth foreground boxes and tabletop supplied almost no accepted
features. The 5/15 pair is therefore useful algorithm evidence, but is **not
accepted as a representative multi-depth scene reconstruction**. This is a
scene-support failure, not a failure to follow the original timing instructions.

A diagnostic Mac rerun of the same frames produced 299 accepted geometry points
before coverage gating: 298 above and 1 below the calibrated principal-point
horizontal line in each view. The exact RANSAC inlier count differed from the
Pi, but the upper-image concentration did not. The new coverage rule requires
at least 20% of the points and at least 10 points in **each** vertical half of
both images. This first pair now reports `rejected` with a reason instead of
creating a misleading candidate cloud. A synthetic background-only scene test
checks this rule. It is a provisional diagnostic gate added after observing
this limitation, not proof that a passing cloud has accurate depths.

Another pair, 15/27 seconds, yielded geometry points but failed the original
quadrant-coverage gate. The 27/45-second pair had broad enough coverage to pass
the revised gate, but it is a separate two-view cloud; it does not independently
validate the first pair or create a shared multi-view map. The 45/55-second
images remain shifted from the 5-second image, so the video does not demonstrate
an exact return to the initial lens viewpoint. A precise return is not needed
for initial triangulation.

**Next capture:** keep the static bookcase background, and add strongly textured
foreground objects at a visibly different depth in the *lower half* of the image.
For example, place a book with large print/illustration or a patterned keyboard
on the nearer desk, while preserving the bookshelf behind it. The same 60-second
sideways-translation procedure can be used. Check `view-1.png` and `view-2.png`
before interpreting a report. After a well-supported two-view result, register
a third view against the shared points and inspect held-out reprojection error.

## AP and systems evidence

One Pi analysis reported 2.96 seconds wall and 1.16 seconds Python process CPU,
excluding the FFmpeg subprocess CPU. There was no warmup or repeated run. Peak
memory, whole-device CPU, temperature, electrical energy and live latency were
not measured. The private video/images/cloud are on the user's Desktop, outside
Git; a small [structured result](../benchmarks/results/sparse-scene-01-analysis.json)
records provenance, configuration, quality and limits.
