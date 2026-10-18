# Record a two-mode tracking comparison on the Pi

The recorder measures whether motion-aware matching had usable shift history,
whether it chose predicted overlap, and whether that prediction was necessary
to retain an ID. Your current observation—coverage for identified objects but
zero **ID matches needing motion**—means raw box overlap has sufficed in the
turns tried so far. This is a valid outcome, not a broken IMU or detector.

The recorder reads the preview's metrics-only `/api/telemetry` endpoint. It does
**not** access the camera, save images/video, change model settings, or command
the servo. Keep the browser open if useful, but note that both browser and
recorder add some HTTP work. The endpoint omits Base64 image bytes to limit
that extra load. Trial files live under ignored `recordings/` and should not be
committed without review.

## Before the trial

On your Mac, review/commit/push this change; on the Pi, `git pull --ff-only`.
Use the same Pi 4, OS, camera mode (live preview requests 1280×720 MJPEG at
30 fps), model, lighting, distance, target and movement route for both runs.
Choose **one** visible person or chair and pass its MobileNet-SSD class as
`--target-label person` or `--target-label chair`. If there are two people,
the recorder marks that update ambiguous rather than pretending it knows
which person is which. Record cooling, power, lighting and unusual events in
`--notes`. A physical course need only be approximately repeatable; it cannot
give exactly paired frames across the two runs.

Use two SSH terminals on the Pi. In terminal 1, run the basic preview:

```bash
cd ~/projects/edgexr
PYTHONPATH=src python3 -m app.live_preview --device /dev/video0 --imu --detect
```

Wait until boxes appear. In terminal 2, run the basic trial:

```bash
cd ~/projects/edgexr
PYTHONPATH=src python3 -m vision.tracking_trial \
  --mode basic --target-label person --seconds 60 \
  --output recordings/tracking-trials/basic-01 \
  --notes "Pi 4; same lit room; one person; whole-base turns; note cooling/power"
```

The recorder prints three cues: remain still for the first 10 seconds, gently
turn and return while keeping the target visible for the next 40, then remain
still for the final 10. The turns need not line up perfectly between trials.
Do not spin abruptly or pull the camera/IMU wiring. You can use a chair if that
is more reproducible. The program stores every successful poll and marks
distinct detector source sequences; default polling is 0.1 seconds, while
the detector targets a new result about every 0.5 seconds.

Stop terminal 1 with Ctrl+C. Restart it in motion-aware mode:

```bash
PYTHONPATH=src python3 -m app.live_preview \
  --device /dev/video0 --imu --detect --motion-aware-tracking
```

Wait for boxes again, then in terminal 2 run:

```bash
PYTHONPATH=src python3 -m vision.tracking_trial \
  --mode motion-aware --target-label person --seconds 60 \
  --output recordings/tracking-trials/aware-01 \
  --notes "Pi 4; same lit room; one person; repeated whole-base turns"
```

Do not reuse an output directory: the recorder refuses to overwrite it.
The `--mode` flag is checked against the running preview, so an accidental
baseline/aware mix-up fails before creating trial files. The default endpoint
is the Pi's local `127.0.0.1:8765`; use `--url` only if you changed the preview
port. No Mac SSH tunnel is needed for the recorder itself.

## Compare and share

On the Pi, print a side-by-side comparison:

```bash
PYTHONPATH=src python3 -m vision.compare_tracking_trials \
  recordings/tracking-trials/basic-01 recordings/tracking-trials/aware-01
```

Each trial directory contains `metadata.json`, `samples.jsonl`, and
`summary.json`. The logs include source sequence, IDs, labels, box coordinates,
capture/analysis rate, detector cost/age, skipped frames, IMU status, and the
latest matching counts. They also record gyro Y turn rate so the two courses
can be compared approximately; gyro is **not** an input to ID matching. They
contain no image pixels. To share them with me,
copy the two small folders to your Mac from a **Mac** terminal:

```bash
scp -r pi@ai-fusion.local:/home/pi/projects/edgexr/recordings/tracking-trials/basic-01 \
  /Users/ryanchoi/Desktop/edgexr-basic-01
scp -r pi@ai-fusion.local:/home/pi/projects/edgexr/recordings/tracking-trials/aware-01 \
  /Users/ryanchoi/Desktop/edgexr-aware-01
```

If you prefer, share `summary.json` first; the JSONL is helpful for inspecting
specific ID transitions. The logs may reveal what objects were in your room
through labels and box locations, so review them before sharing.

## Read the measurements carefully

- `covered_tracks` counts old tracks whose detector-to-detector interval had
  reliable image-shift coverage. `fallback_tracks` counts old tracks that
  lacked a usable prediction. The coverage fraction is covered divided by
  covered plus fallback, across **observed detector updates**.
- `motion_matches` counts assignments for which predicted IoU was larger than
  raw IoU. They might also have matched without prediction.
- `motion_only_matches` counts assignments where predicted IoU crossed the
  0.3 threshold and raw IoU did not. This is the strongest evidence that the
  new algorithm changed an ID decision, but it does not prove the ID is right.
  These tracker counts include **all detected classes**, not just your chosen
  `--target-label`; inspect `samples.jsonl` before attributing a change to
  the person or chair you followed.
- `continuous_target_id_changes` counts ID changes only across observed,
  adjacent detector updates with exactly one box of your target class. A
  missing/multiple-target update breaks the chain. Polling can still miss an
  update, so this is an observational proxy, not labelled ground truth.
- `target_missing_updates` and `target_ambiguous_updates` are as important as
  ID changes: a detector miss or second same-class object makes comparison
  less conclusive. Box age and compute time are Pi-side host measurements,
  not camera-exposure-to-display latency.
- Absolute gyro Y rate by phase is a rough check that the two runs had similar
  turn intensity. It is not camera-angle ground truth, and manual movement
  cannot produce identical timing or viewpoint across trials.

For a fair conclusion, inspect the visible #ID behavior too and tell me if it
ever incorrectly *held* one ID across two different people/chairs. The logger
cannot infer that physical truth from model boxes alone. If both runs have
zero apparent errors and zero motion-only matches, the current scene has not
shown an advantage for motion-aware matching; we should record that honestly
before changing thresholds or making sharper turns.
