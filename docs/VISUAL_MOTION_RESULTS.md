# Visual movement versus gyro — 2026-10-05

## Scope and reproducibility

Analyzed existing combined-still-01 and combined-motion-02 locally on Mac.
Original capture: Pi 4, kernel 6.12.47+rpt-rpi-v8, Python 3.11.2, SH3001,
USB MJPEG 1280x720 requested/negotiated at 30 fps, approximately 15 seconds
after cue. Scene lighting, exposure, temperature, warm-up and precise physical
turn angle were not recorded. Camera is vendor-described OV9281; IMU taped
firmly beside camera. No saved vendor calibration or permanent gyro correction.
Source repository base: 8958aef795d238eb2eb9417e7cbc6f94c05ae023 plus this patch.

Analysis uses NumPy 1.26.4, local FFmpeg grayscale decode at 320x180 and nine
phase-correlation patches. Parameter definitions and repeat commands are in
VISUAL_MOTION.md. No network, package installation or hardware operation was
used. The recording files were not modified.

## Results

| Metric | Stationary control | Motion trial 02 |
| --- | ---: | ---: |
| Compared adjacent-frame pairs | 451 | 451 |
| Accepted visual/gyro pairs | 450 | 442 |
| Rejected pairs | 1 | 9 |
| Median absolute horizontal speed | 0.033 pixels/s | 29.161 pixels/s |
| 95th percentile absolute horizontal speed | 0.106 pixels/s | 145.338 pixels/s |
| Maximum video/log relative PTS difference | 0.500 ms | 0.500 ms |
| Image horizontal speed versus gyro Y correlation | Omitted: little motion | -0.936 |

All decoded frames match frame-log count and relative timestamps. The first
startup interval and pre-cue pairs are excluded. In each run, the final pair
lies outside IMU interpolation coverage and is rejected rather than extrapolated.
Motion has eight additional patch-quality/consensus rejections, around
7.229–7.328 and 7.763–7.862 seconds after cue, near the reversal region. Their
specific visual cause is not established. These rows remain in motion.csv.

The first second of each run supplies its own stationary gyro bias, as in the
previous analysis. This avoids reusing trial 01's different offset.

Motion trial 02, one-second medians:

| Seconds after cue | Image X (pixels/s) | Corrected gyro Y (degrees/s) |
| --- | ---: | ---: |
| 2–3 | -0.027 | -0.028 |
| 4–5 | +98.975 | -23.537 |
| 5–6 | +95.399 | -24.587 |
| 6–7 | +115.613 | -25.896 |
| 7–8 | -0.111 | -0.322 |
| 8–9 | -118.259 | +25.696 |
| 9–10 | -111.882 | +24.483 |
| 10–11 | -106.977 | +23.448 |
| 12–13 | -0.031 | -0.032 |

The signals show the same broad outward-turn, reversal, return and stationary
phases. Opposite signs reflect image-content direction relative to this sensor
axis. No lag was fitted and no angular scale was inferred. Raw estimates have
spikes and rejected intervals, so the one-second medians must not be mistaken
for uniformly accurate tracking.

## Verification and interpretation

All 24 unit tests passed with NumPy available, including five visual-analysis
tests: known signed shifts, flat/unrelated patch rejection, patch outlier,
frame association checks and interpolation bounds. Both complete real recordings
were analyzed and the generated comparison chart was visually inspected.

This establishes a useful preliminary visual motion signal consistent with
the IMU in this scene. It is not a camera pose estimator, object tracker, proof
of exact synchronization, or absolute angle calibration. Sensor read and
frame receipt times include different delays. Stationary control gives an
empirical low-motion reference for this recording, not a universal threshold.

Next: a small live preview with feature/image-motion display and measured
processing cost can build on this foundation. Camera intrinsics, camera/IMU
alignment and timestamp offset are still needed before accurate compensation.
No further identical hand-turn capture is required for this offline milestone.
