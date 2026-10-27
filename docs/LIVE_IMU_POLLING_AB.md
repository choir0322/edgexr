# Live IMU polling return comparison

This is an attended **orientation-quality** experiment, not an AP benchmark.
The preview's `--imu-sleep-ms` selects the pause **after** each SH3001 read;
actual IMU rate also includes read time. Keep the base fixed, camera/IMU mount
unchanged, lighting and scene steady, and the same confirmed safe ±20° head
clearance for every run. Do not run another camera owner. The 320×180 grayscale
checkpoint images and telemetry are saved under ignored `recordings/`, not Git.

Use four new output names in the order `50a`, `10a`, `10b`, `50b`. This repeats
each setting and balances run-order effects. Restart the preview **before each
run** so its first-second still bias and relative-orientation reference are
fresh. Do not touch the head during that still second. The live preview must
use its default Pi port 8765 because the attended servo logger queries its
local HTTP routes there.

In Pi terminal 1, pull once, then start the first (50 ms) preview:

```bash
cd ~/projects/edgexr
git pull --ff-only
PYTHONPATH=src python3 -m app.live_preview \
  --device /dev/video0 --imu --imu-sleep-ms 50 \
  --camera-axis-basis configs/camera_axes_neutral.json \
  --relative-orientation
```

On the Mac, leave the SSH tunnel running, then open the browser in another
Mac terminal. If port 8765 is already occupied, first check whether the
existing tunnel and page already work.

```bash
ssh -N -o ExitOnForwardFailure=yes \
  -L 127.0.0.1:8765:127.0.0.1:8765 pi@ai-fusion.local
```

```bash
open http://127.0.0.1:8765
```

When camera, IMU and relative orientation are ready, check the head and cable
clearance. In Pi terminal 2, physically watch the rig and run:

```bash
cd ~/projects/edgexr
sudo env PYTHONPATH=src python3 -m spatial.servo_orientation_demo \
  --execute --confirm-centered --confirm-clearance \
  --output recordings/servo-orientation-ab-50a
cat recordings/servo-orientation-ab-50a/metadata.json
```

After a complete run, stop preview with `Ctrl+C` in Pi terminal 1. Restart it
with `--imu-sleep-ms 10` and run the same servo command in terminal 2 using
`recordings/servo-orientation-ab-10a`. Repeat once more with 10 ms and a fresh
preview using `recordings/servo-orientation-ab-10b`; finish with 50 ms and
`recordings/servo-orientation-ab-50b`. **Every output name must be new**;
the script deliberately refuses to overwrite a prior recording. Never
delete an earlier trial merely to reuse its name. Press `Ctrl+C` if the head
binds; inspect the rig before further movement.

Each output contains `servo_commands.jsonl`, `telemetry.jsonl`, `metadata.json`,
`checkpoints.jsonl`, and `before_pan.pgm`, `after_pan.pgm`, `after_tilt.pgm`.
The portable-graymap images are the preview's 320×180 display pixels, **not**
720p sensor frames or exposure-synchronized IMU samples. The checkpoint row
records its host poll time, source sequence and age. A stale/missing image or
unready final orientation marks the run partial/incomplete. Verify the
metadata's `status`, `imu_poll_sleep_ms`, `image_checkpoints`, and
`settled_final_sample` before comparing runs.

To copy a run to the Mac, replace `50a` with each finished name:

```bash
scp -r pi@ai-fusion.local:/home/pi/projects/edgexr/recordings/servo-orientation-ab-50a \
  /Users/ryanchoi/Desktop/
```

Report whether the lens/browser view visibly returned after **each** axis,
any servo/cable issue, and any change to scene or lighting. The later analysis
must compare quaternion `inverse(start) × end` around settled pan and tilt
windows, the saved images, actual reported IMU rate and error/skip counters.
The metadata's final scalar angle uses the preview-start reference and is
not by itself a start-to-return error. A 10 ms improvement would implicate
sampling, not prove it is the only cause; no improvement directs us to bias,
mechanics, calibration or integration checks. CPU/temperature tradeoffs belong
to a subsequent matched AP experiment.
