# Guarded servo-driven motion-quality experiment

## Purpose / big picture

Repeat camera motion at known **commanded** speeds while measuring how often
the image-motion estimator rejects adjacent frame pairs. Use the existing
USB camera, camera-mounted IMU and offline patch diagnostics. Never call a
camera PTS gap a proven sensor frame loss, or a servo command an actual measured
joint angle. Keep physical movement optional and explicitly armed.

## Context and orientation

The Pi 4's Fusion HAT+ can drive pan/tilt servos using SunFounder's
`fusion_hat.servo.Servo(channel).angle(degrees)` API. The official example
uses channels 2 and 3. The user confirms this build uses HAT PWM channels
2 (pan) and 3 (tilt) and that a 0° command is mechanically safe. The small
commissioning sweep has not been observed. These are HAT channel labels, not
BCM GPIO pin numbers. The USB OV9281 camera is **not** SunFounder's CSI camera.
`combined_capture.py` already records MJPEG plus IMU; `visual_motion.py` and
`patch_diagnostics.py` analyze saved frames. Use those components rather than
another camera/FFT implementation.

## Progress

- [x] 2026-10-19: Inspect local capture/analysis code and official SunFounder
  servo documentation; no hardware was commanded.
- [x] 2026-10-19: Build dry-run schedule, armed adapter, bounded movement and
  automatic read-only analysis with fake-servo tests. Add a smaller ±2°
  commissioning mode before the full speed series.
- [x] 2026-10-19: Review/update `docs/PIPELINE.md` and
  `docs/learning/IMAGE_MOTION.md` for the optional servo path, shapes, units,
  clocks, rates and failure behavior. The live diagram itself remains unchanged
  because no new live-preview worker was added.
- [x] 2026-10-19: User reports pan/tilt HAT PWM channel labels 2/3, in that
  order; no real servo movement has occurred in this work session.
- [x] 2026-10-20: User confirms pan = 2, tilt = 3, and safe mechanical 0°.
- [x] 2026-10-20: Add an explicit pan-only ±20° commissioning option after
  the user found the ±2° pan movement too small. Keep a separate wider-range
  clearance acknowledgement; no hardware was commanded by Codex.
- [ ] Confirm cable slack, power and clear travel; run a supervised short Pi
  commissioning trial before the full speed series.
- [ ] Review camera/IMU/video results and select one justified estimator change
  or retain the current rejection behavior.

## Plan of work

1. Generate a deterministic pan/tilt schedule about a software 0° center,
   with hard caps of ±8° pan and ±6° tilt, no more than 20 commanded degrees/s
   and 1° command steps. Run axes sequentially; no diagonal or edge sweep.
   Before that, a one-axis commissioning schedule uses only ±2° at 5°/s.
2. Make dry-run the default. Real execution requires explicit channel mapping,
   camera device, output, `--execute`, and two physical-confirmation flags.
   The full series also requires acknowledgement that both commissioning runs
   were safely observed.
   Do not import Fusion HAT or touch the camera in dry-run.
3. After arming, command 0° while the user watches, start the existing camera
   recorder, wait for its `RECORDING` cue, then keep the first 2.5 s still for
   IMU bias. Issue scheduled servo commands with a monotonic clock and log
   their host times. On Ctrl+C or fault, stop issuing commands and interrupt
   recording; do **not** automatically sweep back through an obstruction.
4. Run existing visual and patch analyses. By commanded phase, report visual
   rejection fraction and patch-failure reasons, plus a separately labeled
   camera-PTS gap fraction as a capture-timing indicator, not ground-truth
   lost frames. Preserve raw video/CSV under ignored `recordings/`.

## Concrete steps

Run the dry-run and hardware-free tests on Mac. Review the exact printed
schedule. Push/pull only after user review. On the Pi, first verify the
`fusion_hat` import, actual servo channels, correct 0° center and cable slack
by inspection and a supervised tiny commissioning movement. Follow
`docs/SERVO_MOTION_QUALITY.md`; stop at any binding, unusual noise, power dip
or unexpected motion. Never run two camera readers or servo controllers.

## Validation and acceptance

- Schedule tests prove every command stays within hard caps and step/rate
  limits; dry-run never imports or calls hardware.
- Fake-servo/recorder tests cover the arming gate, planned order, and stopping
  further commands on interruption/fault.
- The Pi result separates rejected **motion estimates** from camera PTS gaps,
  logs commanded vs observed time and notes IMU/camera non-synchronization.
- `docs/PIPELINE.md` and the image-motion guide accurately show that this is
  an optional offline experiment, not a live-preview servo worker.
- No real movement occurs until the user confirms channels and physical setup.

## Surprises and discoveries

No physical servo trial has occurred in this work session. The earlier
hand-driven stress clip showed
219 weak-peak flags across 252 rejected-pair patch checks, but those sweeps
reached hundreds of IMU degrees/s and are not a safe target for the servo test.
The nominal full dry-run schedule is 30.1 s, with 168 one-degree commands
across six sequential phases. A delayed servo API call must not trigger a
burst of later commands; the tested scheduler now preserves the minimum step
interval after each completed call.

## Decision log

- 2026-10-19: User reports channels 2/3 for pan/tilt. Keep explicit mapping
  and physical confirmation for an armed run.
- 2026-10-20: User confirms pan = 2, tilt = 3 and safe 0°. Still require
  cable/travel/power preflight and supervised commissioning.
- 2026-10-20: Preserve the original small-sweep default. The requested
  0° → −20° → +20° → 0° path is opt-in for pan only, at 5 commanded °/s;
  the wider physical path needs its own clearance check.
- 2026-10-19: Keep speeds conservative; a software angle bound cannot detect a
  misassembled linkage, a blocked shaft or cable tension.

## Outcomes and retrospective

The dry run and hardware-independent tests are complete; the physical gate
remains open. No servo was commanded by Codex. The user confirmed the Pi
channel assignment and safe 0° command; cable clearance, power and camera
mode still need supervised verification before the first commissioning run.
