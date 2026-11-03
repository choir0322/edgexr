# One-run direction-consistency check

Completed once on 2026-11-04: [result and limitations](DIRECTION_CONSISTENCY_RESULTS.md).
No repeat requested. Short-run consistency is supported; exact tilt return and
angular accuracy remain unvalidated.

One 30-second stationary interval, one existing pan sweep and one existing tilt
sweep: about 55–60 seconds, plus startup. No repeated trial series unless evidence
is missing or the hardware did not execute the intended motion.

## Evidence and purpose

The existing demo commands pan channel 2 and tilt channel 3 through
0 → −20 → +20 → 0 sequentially, at ≤10 commanded degrees/second. Remain present,
check cable clearance and never force powered gears. No new motor range or speed.

`--still-seconds 30` adds a stationary interval after centering and two seconds
settling. Four private 320×180 PGM images and full independently sampled gyro
orientations are saved in `checkpoints.jsonl`: `before_still`, `before_pan`,
`after_pan`, `after_tilt`. `direction_summary.json` compares still start→end,
before→after pan, after pan→after tilt, and before pan→after tilt. These are local
quaternion differences, not the browser's accumulated angle from startup.
Missing/stale/invalid orientation or a changed reference yields unknown, not zero.
The summary always requires image review; run completion is not an accuracy pass.
Existing telemetry and command logs are retained. No manual enrollment is needed:
the saved center checkpoint is the reference for this diagnostic, not a scene label.

## Run once

Pi terminal 1: stop the old preview with Ctrl+C. Keep the head/base still during
startup bias collection. Use a textured, well-lit scene, lens cap removed, without
a moving person blocking the reference.

```bash
cd ~/projects/edgexr
git pull --ff-only
PYTHONPATH=src python3 -m app.live_preview \
  --device /dev/video0 --imu --imu-sleep-ms 10 \
  --camera-axis-basis configs/camera_axes_neutral.json \
  --relative-orientation --scene-memory
```

Mac terminal: reuse the existing tunnel, or start one if none is running:

```bash
ssh -N -o ExitOnForwardFailure=yes \
  -L 127.0.0.1:8766:127.0.0.1:8765 pi@ai-fusion.local
```

Another Mac terminal:

```bash
open http://127.0.0.1:8766
```

Wait for camera/orientation ready. In a second Pi SSH terminal:

```bash
cd ~/projects/edgexr
sudo env PYTHONPATH=src python3 -m spatial.servo_orientation_demo \
  --execute --confirm-centered --confirm-clearance \
  --still-seconds 30 --output recordings/direction-consistency-01
cat recordings/direction-consistency-01/direction_summary.json
```

Do not touch the rig. Motion starts automatically after the still period. Observe
whether both sweeps return visibly, plus any slip/unexpected movement. Ctrl+C
stops future commands but can leave the servo holding its last angle. Output must
be a new directory. The demo stops itself; the separate preview stays running.

Transfer on the Mac:

```bash
scp -r pi@ai-fusion.local:/home/pi/projects/edgexr/recordings/direction-consistency-01 \
  /Users/ryanchoi/Desktop/
```

## One decision, then move forward

Inspect all four images first. For this coarse application use **5° pointing
separation** as a provisional engineering tolerance during stillness and at
image-confirmed returns, not a measured accuracy specification. Inspect full
rotation difference too for roll. If close image returns remain within tolerance,
proceed with the bounded application, recording the limited single-run evidence.
If not, identify whether stillness or motion introduces the discrepancy and pick
one focused correction next. Do not repeatedly collect identical runs or force
recognized views to zero angle. Clearly different images cannot establish return
error; record the physical/viewpoint mismatch instead.

## Limits and AP record

Pi 4; requested 1280×720 MJPEG 30 fps, scene memory on, detector off, 10 ms IMU
post-read sleep. HTTP telemetry polls about every 50 ms, not every IMU sample.
Images and orientations share a response but are not exposure-synchronized.
Checkpoint sample time is approximated from HTTP midpoint and reported sample age
only for freshness validation; handler/transfer delay remains. Servo commands
are not measured shaft angles. No absolute heading/position/depth claim, live
correction, new dependency or recognition threshold change. CPU/memory/energy/
temperature are not measured; rates/counters remain in telemetry. Systematic AP
comparison is deferred. `still_then_returns_v1` distinguishes this protocol from
the old sweep; omitted --still-seconds retains the three-checkpoint default.
