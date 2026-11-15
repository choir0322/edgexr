# Screen-based camera calibration

## Purpose / big picture

Use a Mac display instead of a printer to estimate OV9281 intrinsics and
distortion for the planned offline sparse reconstruction. Physical 3D mapping
is not implemented here. The Pi capture and held-out quality check remain needed.

## Context and orientation

Existing `recording.combined_capture` records 1280x720 MJPEG video and IMU on
Pi 4; the gyro does not determine calibration. `camera_calibration` samples
video frames and uses existing FFmpeg, NumPy and OpenCV. Host timestamps are
not exposure synchronization. The screen target is a 10x7 square board with
9x6 internal corners; target unit is one square, not millimeters.

## Progress

- [x] User approved calibration and using Mac screen, 2026-11-15.
- [x] Implement pattern, offline fit, held-out checks and movement guide.
- [x] Review/update PIPELINE and learning guide; mark current vs future.
- [x] Run synthetic and browser checks; document limits.
- [x] Capture varied views on Pi and assess a real fit (provisional only).

## Plan of work

Capture varied poses with constant camera mode, focus and unchanged displayed
grid size; sample video at 0.5Hz. Fit using a temporal subset of successful
boards; hold out every fifth detected board. Compute per-view reprojection RMS
and held-out errors using fixed intrinsics with independently fitted board pose.
Report coverage, pose diversity and warnings; do not promise calibration quality
from fit error alone. Save only a new JSON report, not overwritten artifacts.

## Concrete steps

Follow `docs/SCREEN_CAMERA_CALIBRATION.md`; Pi4 with Linux 6.12, previously
verified `/dev/video0` 1280x720 MJPEG 30 fps. Lighting and screen brightness are
recorded by user; use 120 seconds, no servo automation or hardware rewiring.
Raw video and image-derived output remain under ignored `recordings/`.

## Validation and acceptance

Hardware-independent synthetic camera projection checks, target geometry and
argument/error handling, browser visual inspection. On Pi require ≥12 fit and
≥3 held-out detections, varied positions/tilts and inspect errors/outliers.
No universal quality threshold or actual 3D performance claim. Test that the
frame dimensions stay consistent and no output file is overwritten.

## Surprises and discoveries

Mac display uses square CSS pixels only if aspect ratio is preserved; physical
measurements are unnecessary for intrinsics but unknown for metric scale.
Potential glare, screen flicker and moiré require image review.

## Decision log

2026-11-15: user selected a Pi HDMI monitor. Add an optional loopback UDP
low-rate FFmpeg output and local-user ffplay window, retaining the single V4L2
input and original full-resolution video. Preview is best-effort, not recording
or timing ground truth. Pi graphical session and ffplay availability unverified.

2026-11-15: screen target selected by user, paired with existing recording
infrastructure. Keep patterns fully visible; no use of display dimensions to
claim metric reconstruction scale. Existing Pi preview and recorder cannot own
the camera concurrently.

## Outcomes and retrospective

2026-11-15: [Pi trial review](../../SCREEN_CAMERA_CALIBRATION_RESULTS_01.md)
detected 138/150 boards; separate video-half estimates agree within about 0.6%
on focal lengths. Review found reflection/clipping; candidate is suitable for
the first reconstruction experiment but no independent physical accuracy pass
or metric scale is claimed. Plan remains active for later reconstruction-based
validation. PIPELINE reviewed; unchanged, as this stage only records evidence.

HDMI preview implemented. 227 hardware-free unit tests passed. An actual FFmpeg
run on synthetic camera-like video produced packet-copy video, 60 showinfo
frames and 79 local UDP packets; a separate headless ffplay test recognized the
MPEG-2 stream. This is not a test of the Pi's GUI, camera or physical display.
Preview encoding adds unmeasured AP load. PIPELINE and learning guide updated.

2026-11-15: implemented full-screen fixed-ratio target, existing Pi video
recording workflow, offline OpenCV fitting and review-needed report. Synthetic
projected cameras recovered known intrinsics; an end-to-end synthetic video
passed FFmpeg extraction, detection and fitting (20/20 boards, RMS 0.168px).
The browser displayed the expected 10×7 target and border. These checks do not
establish real camera accuracy. PIPELINE and scene-memory guide updated; the
live pipeline is unchanged. Pi capture, physical image review and AP benchmark
remain pending.
