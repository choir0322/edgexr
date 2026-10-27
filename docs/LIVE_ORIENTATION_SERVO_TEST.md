# One-shot live quaternion pan/tilt test

This is an attended physical demonstration, not an AP benchmark. The motor
controller is a separate process so the existing preview remains the sole
owner of `/dev/video0`. It does not save video. It now saves sampled preview
telemetry and each issued motor command in an ignored `recordings/` folder.

On the Pi, first make sure no other motor controller or camera capture is
running. Keep the camera head still during the preview's first second:

```bash
cd ~/projects/edgexr
PYTHONPATH=src python3 -m app.live_preview \
  --device /dev/video0 --imu \
  --camera-axis-basis configs/camera_axes_neutral.json \
  --relative-orientation
```

On the Mac, use a terminal for the SSH tunnel (leave it open):

```bash
ssh -N -o ExitOnForwardFailure=yes \
  -L 127.0.0.1:8765:127.0.0.1:8765 pi@ai-fusion.local
```

Then open `http://127.0.0.1:8765` on the Mac. If local port 8765 is already
in use, first check whether an existing tunnel/browser tab already works.
Check that IMU and relative orientation both say ready, with a near-zero
relative turn before moving.
In a **second Pi terminal**, while physically watching the rig, run:

```bash
cd ~/projects/edgexr
sudo env PYTHONPATH=src python3 -m spatial.servo_orientation_demo \
  --execute --confirm-centered --confirm-clearance \
  --output recordings/servo-orientation-01
```

The confirmations mean you have checked that 0° is safe, both axes and cables
are free through ±20°, and you can stop power if binding occurs. The command
waits three seconds before importing/initializing the Fusion HAT servo driver,
then centers both axes, waits two seconds, and commands pan
`0 → −20 → +20 → 0`, then tilt `0 → −20 → +20 → 0`. Each 1° command is at least
100 ms after the preceding command; the axes are not moved together. It ends
after this single sweep and two seconds of final orientation logging. `Ctrl+C`
stops future commands but may leave a servo
holding its last angle; inspect the rig before intervening. Do not manually
force a powered servo.

Watch three different quantities in the browser: (1) corrected gyro rate
should change during each leg, (2) the relative rotation angle should depart
from zero and return toward it, and (3) quaternion `(w,x,y,z)` should vary as
the head changes orientation. The image-motion arrow may also move, but it is
an independent pixel-shift estimate, not an input to the quaternion. Record
the peak and final relative-turn angles for pan and tilt, whether the lens
visibly returned, any `unknown`/stale status, and any unexpected cable or
servo behavior. A nonzero final angle can arise from gyro bias/drift and
sparse sampling; commanded servo degrees are not measured shaft angle.

The command requires the live quaternion preview to be ready before any motor
command. It writes `servo_commands.jsonl` (including initial 0° commands),
`telemetry.jsonl` (one full image-free preview snapshot about every 50 ms),
and `metadata.json` (sample count, sampled peak angle, last ready orientation,
and errors). The files retain Pi host-monotonic times, so command and telemetry
can be compared approximately. The snapshots are **not every underlying IMU
read** and are not exposure-synchronized. An interrupted run keeps its partial
logs. A telemetry failure or absence of a ready sample at least one second
after final tilt 0° makes the run status `telemetry_incomplete` rather than
silently claiming a complete recorded trial. The [first logged trial](LIVE_ORIENTATION_SERVO_RESULTS.md)
showed why this final settle period matters.

The newer logger also saves 320×180 grayscale view checkpoints before pan,
after the settled pan return, and after the settled tilt return, with source
times in `checkpoints.jsonl`. Use the separate
[50 ms versus 10 ms comparison guide](LIVE_IMU_POLLING_AB.md) for fresh-reference
repeated trials and unique output names. These `.pgm` images are private raw
captures under ignored `recordings/`; do not commit them.

After the run, inspect the summary on the Pi:

```bash
cat recordings/servo-orientation-01/metadata.json
head -n 2 recordings/servo-orientation-01/telemetry.jsonl
tail -n 2 recordings/servo-orientation-01/telemetry.jsonl
```

To transfer the small logs to the Mac (run on the Mac):

```bash
scp -r pi@ai-fusion.local:/home/pi/projects/edgexr/recordings/servo-orientation-01 \
  /Users/ryanchoi/Desktop/
```

The initial demo adds a separate motor-control process and uses a changing
scene. Do not compare its total CPU or temperature directly with a stationary
passive baseline as if only quaternion arithmetic changed. The next AP check
must specify the same movement/scene, duration, polling rate, cooling and
model settings for both configurations, and log live CPU, IMU/analysis rates,
skipped frames, temperature and throttle state separately from this demo.
