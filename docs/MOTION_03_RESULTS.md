# Repeated camera and IMU motion — user-reported Pi results

Reviewed 2026-10-05 from pasted terminal output; the raw files and video for
this run were not inspected locally. Rig: Pi 4, USB OV9281-described monochrome
camera, SH3001 rigidly attached beside it. Combined recorder requests 1280x720
MJPEG at 30 fps. Analysis: 320x180 grayscale, NumPy 1.26.4. Current OS/library
versions, lighting, power, temperature and precise turn angle were not supplied.
Git revision for this capture was not supplied.

30 seconds after cue; 904 decoded-frame records and 588 IMU samples. Camera PTS
rate excluding the initial 148.019 ms interval: 30.0828 fps, maximum subsequent
gap 36.100 ms. IMU midpoint rate: 18.9708 Hz, maximum gap 54.986 ms. Common host
coverage: 29.9845 seconds. Receipt times remain distinct from exposure times.

First-second stationary estimate: 20 samples; gyro bias X/Y/Z
(-15.28954, +13.02510, -5.37728) deg/s and standard deviations
(0.28563, 0.27561, 0.39291) deg/s. This is a per-run estimate, not a persistent
calibration. Sensor X offset differs from earlier runs; cause is unverified.

Visual comparison accepted 901/902 pairs, rejecting one; the summary does not
identify its reason. Maximum relative video/log PTS difference: 0.500 ms.
Image-X speed versus corrected gyro-Y correlation: -0.96523, no fitted delay.
Median absolute image speed: 42.19375 px/s; p95: 151.10724 px/s. Acceptance is
algorithm quality filtering, not a ground-truth accuracy percentage.

One-second medians show image-right/gyro-negative during approximately 4–8 and
19–21 seconds, image-left/gyro-positive during 11–15 and 25–28 seconds, and
near-zero pauses. The user could not follow the suggested timing exactly;
actual measurements define these phases. Second 22 includes a transition
(its mean and median differ), and second 29 is nearly still by median.

Last-two-second corrected gyro Y mean +11.75555 deg/s includes return movement
and cannot estimate stationary drift. Final integrated sensor angles
(+4.13522, -4.94237, +8.78843) degrees are not measured endpoint errors; physical
return angle and camera-axis alignment remain unverified. This result supports
repeatable broad visual/gyro motion agreement, not exact synchronization or
camera pose. No repeat is required solely to follow the suggested schedule.

## Earlier live preview acceptance reported in the same session

With IMU enabled: still analyzed 30.0 fps, latest estimator 27.4 ms, zero skips
after ten seconds and ten more seconds. IMU 19.1 Hz, one observed sample age
6.8 ms, corrected gyro Y approximately -0.3 to +0.3 deg/s. Turning: 30.0–30.4 fps,
latest estimator 25–29 ms, zero skips; gyro sign changed negative to positive
on return and the arrow reversed. These are brief UI observations, not timing
percentiles or a sustained benchmark. No real sensor-disconnection test reported.

Next: saved-frame detector baseline in DETECTION_BASELINE.md.
