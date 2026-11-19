# Step 2 trial: does the head remember a bottle it can no longer see?

**Question.** With `--object-memory`, the preview remembers objects by bearing
(class + direction from the starting head pose), predicts which ones should be in
view, and reports events: `new`, `confirmed_return`, `missing`, `seen_again`,
`moved`. Three runs test the three outcomes. **AP question:** how long does one
memory update take on the Pi (reported as `update_ms`), and how does it grow with
the number of remembered objects?

Code: [`spatial/object_map.py`](../src/spatial/object_map.py), wiring in
`app.live_preview` / `vision.live_detector`, judge
[`scripts/analyze_object_trial.py`](../scripts/analyze_object_trial.py).

## Scene (all three runs)

- Head centred (the previous servo run ends at 0°; do not move it).
- One bottle at lens height, 1.2–1.5 m away, placed with the live label reading
  about **−30° / 0°**, fully inside the image (as in bearing trial 02).
- The servo pans 0 → −20 → +20°, **holds 12 s at +20°** (the bottle is then out of
  view), and returns to 0°. No tilt sweep.

## Commands (repeat for each case; replace CASE with stay, removed or moved)

**Pi, terminal 1.** Restart the preview for every case so the memory starts empty.
Keep the head still for the first seconds:

```bash
cd ~/projects/edgexr
git pull --ff-only
PYTHONPATH=src python3 -m app.live_preview --device /dev/video0 \
  --imu --imu-sleep-ms 10 \
  --camera-axis-basis configs/camera_axes_neutral.json --relative-orientation \
  --detect --bearings configs/camera_calibration.json \
  --object-memory --object-evidence recordings/object-evidence-CASE
```

**Mac, terminal 1** (leave running) and **terminal 2**:

```bash
ssh -N -o ExitOnForwardFailure=yes -L 127.0.0.1:8765:127.0.0.1:8765 pi@ai-fusion.local
```

```bash
open http://127.0.0.1:8765
```

Wait until the **Object memory** panel lists `#1 bottle −30… seen`.

**Pi, terminal 2:**

```bash
cd ~/projects/edgexr
sudo env PYTHONPATH=src python3 -m spatial.servo_orientation_demo \
  --execute --confirm-centered --confirm-clearance --pan-only \
  --hold-away-seconds 12 --still-seconds 10 \
  --output recordings/object-trial-CASE
```

When it prints **"Head turned away: holding 12 s"**, do the case's action and step
back out of view before the head returns:

| Case | During the 12 s hold | Expected (fixed 2026-11-20) |
|---|---|---|
| `stay` | nothing | bottle `confirmed_return` after the head returns; never `missing`/`moved` |
| `removed` | take the bottle completely out of the camera's surroundings | bottle `missing` within 5 s of the return; no `confirmed_return` |
| `moved` | move it to about −15° (half-way to straight ahead), same height and distance | `moved` for the same ID, by at least 6°; not left `missing` |

In every case: exactly one bottle learned before the sweep, and no unexplained new
bottle objects. After the run, stop the preview (Ctrl+C in terminal 1) and copy:

```bash
scp -r pi@ai-fusion.local:/home/pi/projects/edgexr/recordings/object-trial-CASE /Users/ryanchoi/Desktop/
scp -r pi@ai-fusion.local:/home/pi/projects/edgexr/recordings/object-evidence-CASE /Users/ryanchoi/Desktop/
```

The evidence folder holds detector frames that contained two boxes of one class
(at most 20); it may be empty. Those frames show what the detector saw when it
reported a second "bottle". If the preview cannot create the evidence folder
(permission denied), run the terminal-1 command with `sudo env PYTHONPATH=src`.
