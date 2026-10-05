# Offline image motion and gyro comparison

## Purpose / big picture

Check whether visible motion in existing video follows the mounted gyro's turn
and reversal. Report pixels/second and degrees/second separately. This step is
exploratory, not camera calibration or a synchronization measurement.

## Context and orientation

Use combined-still-01 and combined-motion-02 from the Pi 4 (Bookworm aarch64,
Python 3.11.2), MJPEG 1280x720 requested at 30 fps and SH3001 polling near 19 Hz.
Recordings include frames.csv, imu.csv, metadata.json and camera.mkv. Scene,
exposure, warm-up and temperature were not precisely recorded. The user
confirmed visible motion and rigid mounting. Mounted pan projects mainly onto
sensor Y; the actual camera-to-IMU transform is unknown.

## Progress

- [x] 2026-10-05: Inspect repo and available packages. FFmpeg, NumPy and
  Matplotlib exist locally; OpenCV is absent. No package installation needed.
- [x] 2026-10-05: Implement patch-shift estimator; all 24 tests pass with NumPy.
- [x] 2026-10-05: Evaluate still and motion recordings; inspect chart and quality
  metrics. Motion correlation -0.936 with 442/451 accepted pairs; stationary
  median absolute horizontal speed 0.033 pixels/s at 320x180.
- [x] 2026-10-05: Document results and package changes for the Desktop repo.

## Plan of work

1. Decode grayscale images at 320x180 using FFmpeg. Compare fixed image patches
   using FFT phase correlation; combine agreeing shifts with a median. This
   measures local image translation rather than tracking object identities.
2. Check video frame count and container timestamps against frame logs before
   associating rows by index; reject unexplained mismatches. Exclude startup.
3. Estimate this run's gyro bias from the first second after its cue. Compare
   visual rates with gyro Y on approximate host receipt times, retaining camera
   PTS for image rate calculation. Do not fit a time shift to improve agreement.
4. Save local CSV/JSON analysis and a chart; commit only a concise results doc.

## Concrete steps

Run tests with PYTHONPATH=src python3 -m unittest discover -s tests/unit -v.
Run python3 -m recording.visual_motion with PYTHONPATH=src, a recording folder
and a new output directory under recordings/. See docs/VISUAL_MOTION.md for
commands. NumPy is an explicit optional dependency of this offline tool; prior
capture tools still need only their existing dependencies. Do not install
packages implicitly. Raw images are decoded locally and not uploaded.

## Validation and acceptance

Synthetic translated textures must recover shift signs/magnitudes; flat and
unrelated patches must be rejected. Periodic textures remain a documented
ambiguity. Timestamp mismatch and out-of-range IMU
times must not be silently accepted. Still footage should have low visual
motion; the motion run should show coherent opposing phases. Check quality
rejections, not only correlation. If frames cannot be matched reliably, stop
and fix timestamp association before presenting a comparison.

## Surprises and discoveries

The initial camera PTS interval is about 148 ms. Camera receipt and exposure
are not the same time. The motion-02 initial gyro window has a disturbance
after its first second, so use only the first second for bias. This is not
an automatic stillness detector or a permanent calibration.

## Decision log

- 2026-10-05: Use existing NumPy and FFmpeg rather than install OpenCV. Phase
  correlation is a small first motion indicator, with limitations for low
  texture, parallax, rotation, moving objects and repeating patterns.
- 2026-10-05: Decode at 320x180; output pixels refer to that analysis resolution.
  Keep rates separate and label host-clock pairing approximate.

## Outcomes and retrospective

Offline acceptance checks passed. Image and gyro show opposing signs and
matching broad motion phases. Eight motion pairs failed visual quality near
the reversal; one final pair per run lacked IMU coverage. They remain visible
as rejected rows, with no extrapolation. The chart and results document retain
these limitations. This milestone is complete; live tracking, camera/IMU
calibration, timing synchronization and object detection remain future work.
