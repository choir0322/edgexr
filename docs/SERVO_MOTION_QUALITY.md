# Supervised pan/tilt motion-quality experiment

This optional program commands the Fusion HAT+ pan and tilt servos **one axis
at a time** while the existing recorder saves USB camera video and raw IMU
readings. It then runs the existing visual-motion and per-patch analyses.
Default mode is a dry run: no camera, IMU or servo library is loaded.

`--imu-interval SECONDS` selects the sleep **after** each IMU read (default
0.05). Use `--imu-interval 0.01` for the approved orientation polling experiment
in [RELATIVE_ORIENTATION.md](RELATIVE_ORIENTATION.md). Actual sample spacing
also includes read, logging and scheduling time. This option changes no servo
positions or speeds. The recorder metadata and final servo-quality summary
store the selected sleep as `imu_sleep_seconds`.

Add `--measure-resources` to save recorder/FFmpeg CPU, sampled RSS and temperature
observations during capture to `resources.json`. Startup, shutdown and offline
diagnostics are excluded from that measurement. The final servo summary includes
the compact resource result. See [the fixed-rate protocol](IMU_RESOURCE_BENCHMARK.md).

SunFounder's [AI Fusion pan/tilt example](https://docs.sunfounder.com/projects/ai-lab-kit/en/latest/python/4.16_pan_tilt_camera.html)
uses `Servo(channel).angle(degrees)` and shows channels 2 and 3. Its
[servo API](https://docs.sunfounder.com/projects/fusion-hat/en/latest/api/fusion_hat.servo.html)
supports angle commands. For this build, the user confirms pan on HAT PWM
channel 2, tilt on channel 3, and a mechanically safe 0° command. These are
HAT servo-channel labels, **not** BCM GPIO pin numbers. The small-angle test
and pan-only ±20° test have now been run; inspect the plugs and travel before
any wider movement.
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
For a larger **pan-only** test after the small pan run, `--commission
--axes pan --wide-pan` commands 0° → −20° → +20° → 0°, in 1° steps at
5 commanded degrees/second. It is a separate opt-in run; it does not change
the small tilt trial or the full series. Its capture lasts about 21.5 seconds.
The optional `--quick-pan --axes pan` test commands **0° → −40° → +40°**
at 20 commanded degrees/second, in 1° steps every 50 ms. It ends at **+40°**;
it does not return to 0°. Its capture lasts about 11.5 seconds. This is a
faster stress test, not a smooth continuous-speed servo command.
The full program makes six sweeps, pan and tilt separately, at commanded 5,
10 and 20 degrees/second, using 1° steps. Pan stays within ±8° and tilt
within ±6° around software 0°. The first 2.5 seconds after the recording cue
are still for IMU bias, with a one-second gap between phases. Total full-run
capture is about 30 seconds, within the existing 3000-frame offline limit.
These are **commands**, not measured shaft angles or rates.

## 2. Physical preflight — required before `--execute`

- Recheck the confirmed HAT mapping (**pan = 2, tilt = 3**) against the
  actual plugs. Do not interpret these as BCM pins.
- The user confirms that the library's 0° command is mechanically safe.
  Recheck the head's physical orientation before each run; the program
  commands 0° before recording. Do not force an energized servo shaft by hand.
- Confirm cable slack through each proposed tiny movement, clear mechanical
  travel, stable HAT power, rigid camera/IMU attachment, and a fixed base.
- The ±20° pan option requires a **new** clearance and cable-slack check over
  that wider range. The previous ±2° check does not establish it. Only pass
  `--confirm-wide-pan-clearance` after checking the wider path.
- The quick ±40° pan option requires a separate **±40°** clearance and
  cable-slack check. The completed ±20° run does not establish safe travel
  through ±40°. Only pass `--confirm-quick-pan-clearance` after that check.
  This test deliberately ends at +40°; leave room for the head to remain there.
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
`--confirm-commissioned`. The channel numbers below reflect the user's
confirmation; do not run until the remaining physical preflight is complete.

```bash
sudo python3 src/recording/servo_motion_quality.py \
  --commission --axes pan --execute \
  --confirm-centered --confirm-cable-slack \
  --pan-channel 2 --tilt-channel 3 \
  --device /dev/video0 --output recordings/servo-commission-pan-01

sudo python3 src/recording/servo_motion_quality.py \
  --commission --axes tilt --execute \
  --confirm-centered --confirm-cable-slack \
  --pan-channel 2 --tilt-channel 3 \
  --device /dev/video0 --output recordings/servo-commission-tilt-01
```

For the requested wider pan sweep, after checking the ±20° path, run this
**instead of** repeating the small pan command. Stay beside the rig:

```bash
sudo python3 src/recording/servo_motion_quality.py \
  --commission --axes pan --wide-pan --execute \
  --confirm-centered --confirm-cable-slack --confirm-wide-pan-clearance \
  --pan-channel 2 --tilt-channel 3 \
  --device /dev/video0 --output recordings/servo-commission-pan-wide-01
```

For the requested quick pan test, after checking the **entire ±40° path**,
run this pan-only command while beside the rig. It begins with the usual 0°
initialization and leaves pan at +40° when complete:

```bash
sudo python3 src/recording/servo_motion_quality.py \
  --axes pan --quick-pan --execute \
  --confirm-centered --confirm-cable-slack --confirm-quick-pan-clearance \
  --pan-channel 2 --tilt-channel 3 \
  --device /dev/video0 --output recordings/servo-quick-pan-01
```

Only after reviewing both complete commissioning recordings and checking
travel, use a **new** output name for the full series:

```bash
sudo python3 src/recording/servo_motion_quality.py \
  --axes both --execute \
  --confirm-centered --confirm-cable-slack --confirm-commissioned \
  --pan-channel 2 --tilt-channel 3 \
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
