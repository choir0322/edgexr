# Image-backed live scene diagnosis — 2026-10-29

Trial `live-scene-images-01` contains 180 readable JSONL observations and all
180 linked PNGs. Pi commit `03528eb`, dirty working tree reported, OpenCV 4.11.0,
Python 3.11.2, two OpenCV threads, detector off, 10 ms IMU sleep. Thresholds
unchanged. Private images remain on the user's Desktop, not in Git.

## What the camera saw and why it rejected views

Reference enrollment occurred at approximately 46 seconds, using
`frame-00001386.png`: a room view with a large nearby bottle on the right,
hanging clothes in the middle and doorway on the left. Reviewed a contact sheet
of every post-enrollment unknown frame plus reference, transition and return
frames. Times below are rounded seconds from the first logged observation.

There were 46 startup empty-memory results, one enrollment, 77 known results,
and **56 post-enrollment unknown results**:

| Logged rejection | Count | Image-backed interpretation |
|---|---:|---|
| few_matches | 31 | Larger turns reveal shelves/tissue box to the right or bed/doorway to the left; part of a person also occludes the left side in some frames. Too little distinctive overlap with the sole reference. |
| concentrated_support | 24 | Recognizable room content remains, but verified correspondences span too little area in one or both frames. These are genuine limits of single-view coverage, not proof that the room is different. |
| few_geometric_inliers | 1 | At approximately 71 s, correspondences did not satisfy the geometric inlier requirements. Cannot uniquely attribute this to blur, parallax or mismatches from this one frame. |

At 55 s, 67 of 101 descriptor matches were geometric inliers, yet their convex
hull covered only **8.36% of the reference and 8.97% of the query**, below the
12% requirement. At 124 s, 128 inliers still covered only 11.03%/11.00%.
Many matches concentrated in a narrow region are intentionally insufficient
for declaring a whole-view revisit. Do not remove this guard merely because
we recognize the room ourselves.

Recognized intervals begin near 47, 60, 81, 99, 119, 127 and 167 s. The last
13 observations, approximately 167–179 s, are all known View-1. The final
image is `frame-00005388.png`, as identified by the final JSONL row.
The final image visually resembles the reference, with 366/397 inliers,
30.84%/30.68% coverage across all nine cells and footprint area ratio 0.99981.
This trial therefore **does not reproduce the previous trial's final unknown**.
It cannot retroactively explain that previous failure because its images were
not saved. Strong visual overlap still is not measured exact same pose.

## Orientation remains a separate unresolved issue

The final quaternion is approximately **9.63° from the enrollment quaternion**,
despite similar endpoint images. This is a relative quaternion difference,
not the scalar rotation from application startup. It is evidence that orientation
accuracy remains unvalidated, not a calibrated 9.63° error measurement.
The nearby bottle and distant room features have differing depth; translation,
parallax and exact physical direction are not measured. No claim is made that
gyro bias, sampling, or mounting alone caused the discrepancy.
The IMU is not used to accept/reject scene matches, so it did not trigger any
of these unknown decisions.

## Runtime observations, not an AP comparison

180 updates span 179.077 s (approximately 1 Hz). Median/p95 scene compute was
78.39/111.49 ms, with maximum 131.75 ms. PNG preparation/write median/p95 was
14.49/21.79 ms, with one maximum of 904.50 ms. Timing is wall time, not CPU;
PNG work is additional workload. No CPU, RSS, temperature, power or sustained
full-pipeline performance claim follows. Power/cooling and negotiated camera
mode were not recorded. Orientation status was ready for 179 rows after one
startup unknown; ready denotes numerical continuity, not truth.

## Decision and next bounded step

Keep thresholds unchanged. The current memory has been taught **one view**, not
the entire room. Use the already-supported explicit enrollment to teach distinct
left, center and right views, then test repeated revisits and an untaught view.
Avoid nearly duplicate references, which can correctly trigger ambiguity.
This directly expands spatial coverage without weakening geometric safeguards.
Continue logging image-backed evidence. Investigate orientation consistency
separately before using it as a hard scene gate or claiming spatial pose.
No code/threshold changes were made from this diagnosis. Raw images are not
committed; this record retains derived evidence only.
