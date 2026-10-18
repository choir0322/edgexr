# Supervised pan/tilt motion-quality experiment

This optional program commands the Fusion HAT+ pan and tilt servos **one axis
at a time** while the existing recorder saves USB camera video and raw IMU
readings. It then runs the existing visual-motion and per-patch analyses.
Default mode is a dry run: no camera, IMU or servo library is loaded.

SunFounder's [AI Fusion pan/tilt example](https://docs.sunfounder.com/projects/ai-lab-kit/en/latest/python/4.16_pan_tilt_camera.html)
uses `Servo(channel).angle(degrees)` and shows channels 2 and 3. Its
[servo API](https://docs.sunfounder.com/projects/fusion-hat/en/latest/api/fusion_hat.servo.html)
supports angle commands. **Those example channels do not verify your own HAT
wiring.** Inspect the actual plugs/labels before entering channel numbers.
Your EdgeXR camera is the separate USB OV9281, not the CSI camera in that
example. No software limit can detect a wrongly centered horn, snagged cable,
blocked mount or weak power supply.

## 1. Review the schedule without touching hardware

From the repo root, on Mac or Pi:

```bash
PYTHONPATH=src python3 -m recording.servo_motion_quality --commission --axes pan
PYTHONPATH=src python3 -m recording.servo_motion_quality --commission --axes tilt
PYTHONPATH=src python3 -m recording.servo_motion_quality --axes both
```

Commission mode makes a single ±2° sweep at 5 commanded degrees/second.
The full program makes six sweeps, pan and tilt separately, at commanded 5,
10 and 20 degrees/second, using 1° steps. Pan stays within ±8° and tilt
within ±6° around software 0°. The first 2.5 seconds after the recording cue
are still for IMU bias, with a one-second gap between phases. Total full-run
capture is about 30 seconds, within the existing 3000-frame offline limit.
These are **commands**, not measured shaft angles or rates.

## 2. Physical preflight — required before `--execute`

- Confirm the actual pan and tilt HAT channels from the wiring, not the
  SunFounder example numbers. Ensure both are distinct.
- Confirm the head's **physical** neutral orientation corresponds to the
  library's 0° commands. The program commands 0° before recording; if the
  mounting is not centered, even this could move it unexpectedly. Do not
  force an energized servo shaft by hand.
- Confirm cable slack through each proposed tiny movement, clear mechanical
  travel, stable HAT power, rigid camera/IMU attachment, and a fixed base.
- Stay beside the rig with a way to remove servo power. Stop immediately for
  binding, unusual noise, cable tension, brownout or unexpected motion.
  `Ctrl+C` stops future commands and interrupts capture, but may leave the
  servo holding its last position; it does **not** automatically sweep home.
- Close any live preview or other process that uses the USB camera or servos.
  Check that the Pi already has `fusion_hat`, `sunfounder_imu`, NumPy, FFmpeg
  and ffprobe. The program installs nothing.

Do **not** use the full series until both small commissioning runs have been
observed safely. `--execute` also requires explicit `--confirm-centered` and
`--confirm-cable-slack`; the full series additionally requires
`--confirm-commissioned`. Replace `PAN_NUMBER` and `TILT_NUMBER` below with
the verified numeric channel labels. The literal placeholders will fail
safely if not replaced.

```bash
sudo python3 src/recording/servo_motion_quality.py \
  --commission --axes pan --execute \
  --confirm-centered --confirm-cable-slack \
  --pan-channel PAN_NUMBER --tilt-channel TILT_NUMBER \
  --device /dev/video0 --output recordings/servo-commission-pan-01

sudo python3 src/recording/servo_motion_quality.py \
  --commission --axes tilt --execute \
  --confirm-centered --confirm-cable-slack \
  --pan-channel PAN_NUMBER --tilt-channel TILT_NUMBER \
  --device /dev/video0 --output recordings/servo-commission-tilt-01
```

Only after reviewing both complete commissioning recordings and checking
travel, use a **new** output name for the full series:

```bash
sudo python3 src/recording/servo_motion_quality.py \
  --axes both --execute \
  --confirm-centered --confirm-cable-slack --confirm-commissioned \
  --pan-channel PAN_NUMBER --tilt-channel TILT_NUMBER \
  --device /dev/video0 --output recordings/servo-quality-01
```

Check the actual camera device path; `/dev/video0` is not guaranteed. No
remote, unattended run is recommended. Neither the program nor the docs
authorize altering the SunFounder IMU calibration or camera settings.
Optionally add `--scene "..." --power "..." --cooling "..."` to each armed
command so those conditions are retained in capture notes; omitted values
are explicitly `unknown`. Confirm the actual negotiated video mode afterward
from the capture's `ffmpeg.log`.

## 3. What to read afterward

The capture folder contains `camera.mkv`, `frames.csv`, `imu.csv`,
`metadata.json`, `servo_commands.json` and `servo_quality_summary.json`.
Sibling `-analysis/` and `-patch/` folders contain the existing visual and
per-patch outputs. All are under Git-ignored `recordings/`.

In `servo_quality_summary.json`, `visual_rejection_fraction` is the share of
analyzed adjacent frame pairs without a trustworthy image-shift estimate
**during a commanded phase**. This is the main quality measure. Separately,
`pts_gap_fraction` counts video presentation-time intervals longer than 1.5
times the requested 30-fps interval. That is a **timing-gap indicator**, not
proof of camera sensor frame loss. Neither metric is display-frame loss in the
browser. The report also lists per-phase patch-failure checks and approximate
IMU Y rate. Servo command times, camera host receipts and IMU read midpoints
use host monotonic time; none is an exposure timestamp or physical shaft
feedback. Compare only like-for-like scene, light, camera mode and power.

Code tour: `build_schedule()` defines bounds/rates; `validate_arming()` gates
real runs; `execute_commands()` uses monotonic deadlines and never bursts late
commands; `run_capture()` wraps the existing recorder; `analyze_run()` reuses
the saved-video tools; `phase_report()` keeps visual rejection and PTS gaps
separate. Unit tests use fake servos and clocks, not hardware.
