# Step 1 trial: does a bottle keep its bearing while the head turns?

**Question.** The live preview now gives each detection a *bearing*: its yaw/pitch
from the head's starting direction (camera geometry + gyro orientation). If that
works, a bottle that stays put should report about the same bearing while the head
pans and tilts, even though its position in the image moves by ~30°. **AP question:**
how late is a camera frame compared with the gyro reading paired with it? Turning
in opposite directions shifts the bearing in opposite directions; half the
difference divided by the turn rate estimates that delay.

Code: [`spatial/bearing.py`](../src/spatial/bearing.py),
[pipeline](PIPELINE.md), calibration [`configs/camera_calibration.json`](../configs/camera_calibration.json)
(working joint 02+03 fit, `needs_review`), analysis
[`scripts/analyze_bearing_trial.py`](../scripts/analyze_bearing_trial.py).

## Scene

- Base on a table, head at neutral (it is centred by the servo script).
- **One bottle**, upright, 1.0–1.5 m from the lens, **30° left** of straight ahead,
  roughly at lens height: measure F forward, then 0.58 × F to the left
  (1.0 m → 0.58 m, 1.5 m → 0.87 m). A larger bottle (1–1.5 L) is detected more reliably.
- Plain background, steady light, no other bottles or people in view. Tape the spot.

The existing sweep pans 0 → −20 → +20 → 0°, then tilts 0 → −20 → +20 → 0°. The bottle
is visible for pan below about +13° and leaves the view beyond that.

## Commands

**Pi, terminal 1** (live preview with detector, gyro orientation and bearings). Keep
the head still for the first seconds while the gyro bias is measured:

```bash
cd ~/projects/edgexr
git pull --ff-only
PYTHONPATH=src python3 -m app.live_preview --device /dev/video0 \
  --imu --imu-sleep-ms 10 \
  --camera-axis-basis configs/camera_axes_neutral.json --relative-orientation \
  --detect --bearings configs/camera_calibration.json
```

**Mac, terminal 1** (SSH tunnel; leave it running):

```bash
ssh -N -o ExitOnForwardFailure=yes \
  -L 127.0.0.1:8765:127.0.0.1:8765 pi@ai-fusion.local
```

**Mac, terminal 2:**

```bash
open http://127.0.0.1:8765
```

Check in the browser before moving anything: IMU and relative orientation say
ready, and the bottle's box label ends with a bearing like `bottle 0.81 @ −30.2°/+0.4°`
(`~` before the number = outside the calibrated area; `@ ?` = no orientation yet).
If the bottle is not detected, move it a little closer or use a larger bottle.

**Pi, terminal 2** (watch the rig while it runs; Ctrl+C stops further commands):

```bash
cd ~/projects/edgexr
sudo env PYTHONPATH=src python3 -m spatial.servo_orientation_demo \
  --execute --confirm-centered --confirm-clearance --still-seconds 10 \
  --output recordings/bearing-trial-01
```

When it finishes, stop the preview (Ctrl+C in Pi terminal 1) and copy the run:

```bash
scp -r pi@ai-fusion.local:/home/pi/projects/edgexr/recordings/bearing-trial-01 \
  /Users/ryanchoi/Desktop/
```

Tell me the measured forward/left distances you used.

## Pass criteria (fixed 2026-11-20, before the trial)

Using bottle bearings that are ready and not extrapolated:

1. At least 20 bearings, collected while the head yaw spans at least 15°.
2. Bearing yaw spread (5th–95th percentile) at most 4°; pitch spread at most 4°.
3. Yaw spread while the head is still at most 3°.
4. Average yaw of the first and last still periods within 2° (returns after the sweep).

Reported but not gated: how much the image position moved without gyro correction,
the turn-direction delay estimate, orientation pairing lag, unknown/extrapolated
counts, and the bearing compared with your tape measurement (±1–2° expected from
placement alone). Not claimed: distance, object identity or a world compass heading.
