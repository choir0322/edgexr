# One-shot live quaternion pan/tilt test

This is an attended physical demonstration, not an AP benchmark. The motor
controller is a separate process so the existing preview remains the sole
owner of `/dev/video0`. It does not save a video or motor/IMU log.

On the Pi, first make sure no other motor controller or camera capture is
running. Keep the camera head still during the preview's first second:

```bash
cd ~/projects/edgexr
PYTHONPATH=src python3 -m app.live_preview \
  --device /dev/video0 --imu \
  --camera-axis-basis configs/camera_axes_neutral.json \
  --relative-orientation
```

Open the usual SSH-forwarded browser on the Mac. Check that IMU and relative
orientation both say ready, with a near-zero relative turn before moving.
In a **second Pi terminal**, while physically watching the rig, run:

```bash
cd ~/projects/edgexr
sudo env PYTHONPATH=src python3 -m spatial.servo_orientation_demo \
  --execute --confirm-centered --confirm-clearance
```

The confirmations mean you have checked that 0° is safe, both axes and cables
are free through ±20°, and you can stop power if binding occurs. The command
waits three seconds before importing/initializing the Fusion HAT servo driver,
then centers both axes, waits two seconds, and commands pan
`0 → −20 → +20 → 0`, then tilt `0 → −20 → +20 → 0`. Each 1° command is at least
100 ms after the preceding command; the axes are not moved together. It ends
after this single sweep. `Ctrl+C` stops future commands but may leave a servo
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

The initial demo adds a separate motor-control process and uses a changing
scene. Do not compare its total CPU or temperature directly with a stationary
passive baseline as if only quaternion arithmetic changed. The next AP check
must specify the same movement/scene, duration, polling rate, cooling and
model settings for both configurations, and log live CPU, IMU/analysis rates,
skipped frames, temperature and throttle state separately from this demo.
