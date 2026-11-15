# Screen camera calibration trial 01

Reviewed 2026-11-15. The user reports a 300s session, deliberately using varied
center, left, right, above, below, diagonal, near and far camera viewpoints rather
than following a strict scripted pose order. Original video and logs remain
private in the Mac's transferred recording folder; no images are committed.

## Capture and calibration

- Pi metadata: complete, requested 300s, HDMI preview enabled; 9028 decoded
  frame records, 5694 IMU samples, no nonincreasing camera PTS, 301.09s elapsed.
- The copied video reports MJPEG, 1280×720, 30/1 nominal fps and 300.22s duration.
  Source video is about 577 MiB. `ffmpeg_returncode` 255 corresponds to the
  recorder's deliberate interrupt at the end; metadata reports no error.
- OpenCV 4.11.0 sampled 150 frames at a nominal two-second interval and detected
  the 9×6 inner corners in 138. Training has 111 detections; holdout has 27.
  Reported full analysis wall time was 129.45s; CPU utilization, RAM, temperature
  and energy were not recorded. HDMI preview was enabled and adds unmeasured work.
- Estimated intrinsics at 1280×720: fx 733.56px, fy 733.16px, principal point
  (670.33px, 330.78px). Distortion coefficients k1, k2, p1, p2, k3:
  0.08618, -0.06567, 0.000538, -0.000259, -0.06962. The camera model is OpenCV's
  pinhole model with distortion, not a physical distance estimate.
- Training global reprojection RMS 0.569px. Per-view training median 0.237px,
  empirical p95 1.336px, max 2.060px. Held-out per-view median 0.188px,
  empirical p95 1.107px, max 1.238px. Per-view RMS is the root mean squared 2D
  pixel distance between detected and reprojected board corners. Each holdout
  pose is fitted to its own image; near-neighbor video frames are correlated.

## Coverage, visual review and stability check

Detected board-center ranges were 34.0–70.5% of image width and 26.4–64.0% of
height. The recorded inner-corner bounds reached about 7.3% from the left,
3.1% from the right, 6.1% from the top and 5.7% from the bottom. These are
separate extremal observations, not proof every corner of the image was covered.
There were no automated warnings; the checks do not assess all failure modes.

Review of sampled images shows varied scale and oblique views. Some images
clip the outer board or contain visible screen reflections; detection failed in
12 sampled images. A frame around 181s shows a reflection near the board. Its
reported training sample near that time has the largest error (2.060px), but
the time alignment is approximate and the reflection is not established as its
cause. Other high-error views should be inspected before selective exclusion.

As an additional diagnostic on the Mac, a separate extraction sampled every
6s (approximately 3, 9, ..., 297s). 45 of 50 frames detected the board. Fit
the first and second 150s independently (24 and 21 views respectively):

| Independent subset | fx (px) | fy (px) | Training RMS (px) |
|---|---:|---:|---:|
| First half | 726.96 | 726.44 | 0.548 |
| Second half | 730.78 | 730.48 | 0.387 |

The focal estimates differ by about 0.53% and 0.56%. Fitting board poses from
the opposite half with each fixed model yielded median cross-half reprojection
errors 0.188px (first → second) and 0.252px (second → first), with maxima
1.254px and 1.447px. This is more temporally separated than the original split,
but still uses the same video/screen; it does not independently validate camera
accuracy. Distortion coefficients vary more than focal lengths, especially the
higher-order radial term; compare resulting geometry, not coefficients alone.

## Decision and limitations

The fit is a **reasonable provisional candidate for the first offline sparse
reconstruction experiment**, not an independently verified metric calibration.
Keep the same camera, focus and 1280×720 image mode; if they change, reassess
intrinsics. Preserve the original `calibration.json` and source video outside
Git. Do not silently replace the original result or call `needs_review` a pass.

No new calibration trial is required before beginning a small reconstruction
experiment. During reconstruction, verify parallax, matched features, positive
depth and reprojection error; a held-out pose or known-size reference can reveal
problems the same-screen test misses. Monocular reconstruction remains up to
scale until an independent known scene measurement is applied. Hardware
measurements and full reconstruction success remain unproven.

[Machine-readable summary](../benchmarks/results/camera-calibration-screen-01.json).
