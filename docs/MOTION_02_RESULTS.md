# Marked return trial: combined-motion-02

Reviewed 2026-10-04 from the Desktop copy. Metadata says complete, with the note
“Marked starting direction; whole-base turn and exact return.” The physical
endpoint has not been independently measured from the video.

Pi 4, Linux 6.12.47+rpt-rpi-v8 aarch64, Python 3.11.2. Negotiated MJPEG
1280x720 at 30 fps; SH3001 raw driver readings. Capture duration 15 seconds
after the cue, with startup recorded separately. Lighting, exposure, warm-up,
temperature and precise physical angle were not measured for this run.

## Checks and comparison

All 454 saved video frames decoded successfully, matching frames.csv.
There are 303 IMU samples. Every camera PTS, receipt time, and IMU midpoint
increases strictly. Camera PTS rate excluding the first 148.017 ms interval
is 30.081 fps; maximum later interval 36.020 ms. Maximum host frame receipt
gap is 42.812 ms. IMU rate is 18.935 Hz, with median/max gaps 53.089/53.610 ms.
Common host coverage is 14.997 seconds; this does not establish exposure
synchronization or a one-to-one camera/IMU sample mapping.

Using the first second after the cue (20 low-variation readings) as the
stationary bias window gives X/Y/Z offsets (-4.89204, +13.04952, -4.13214)
degrees/second. Axis standard deviations are (0.169, 0.172, 0.107) deg/s.
Integrating corrected rates across 14.961 seconds gives:

| Trial | Final X | Final Y | Final Z |
| --- | ---: | ---: | ---: |
| combined-motion-01 | +0.923 degrees | +13.149 degrees | -0.468 degrees |
| combined-motion-02 | +0.435 degrees | -1.476 degrees | -0.467 degrees |

Y reaches -86.291 degrees during the new turn. The major outward movement
falls around 3–7 seconds after the cue, returning around 7–11 seconds and
settling afterward. At 1.561 seconds a brief gyro excursion appears on all
axes; its cause is unknown, so the entire first three seconds should not be
treated as motionless. Two-/three-second baseline choices give final angles
(+0.731, +0.273, -2.406) / (+0.865, -0.399, -1.957) degrees respectively.
The first-second window is used consistently for comparison and has lower
spread; do not choose a baseline just to minimize the final angle.

The last two seconds' corrected mean is (-0.079, -0.013, -0.009) deg/s,
supporting within-run offset consistency. Initial gyro Y offset was about
+14.838 deg/s in trial 01, versus +13.050 deg/s in trial 02. X and Z also
changed. Cause is not determined; warm-up, temperature and sensor initialization
were not controlled. Reusing trial 01's Y offset would introduce approximately
27 degrees of additional error over 15 seconds.

## Interpretation and next step

The new run supports proceeding with exploratory visual-motion analysis.
It does not prove absolute angle accuracy, establish the cause of trial 01's
larger residual, or calibrate camera axes. Estimate gyro bias from a verified
stationary period in every run; do not persist a universal correction.

Next use these existing videos and logs to compare image motion with the
gyro turn/reversal pattern. Keep visual measurements, host receipt times and
camera PTS separate until a timing relationship is actually measured.
No additional identical hand-turn trial is needed at this stage.
