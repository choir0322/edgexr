# Re-identification: gallery, retry and spatial trials

This is a supervised Raspberry Pi 4 test using the existing OV9281-described
USB camera at requested 1280×720 MJPEG/30 and MobileNet-SSD at target 2 Hz.
Use steady lighting. Keep all footage under ignored `recordings/`; share it
deliberately and do not commit it. The Pi run needs the current code pushed from
Mac and pulled onto the Pi. Stop any earlier camera preview before each run.

## A. Validate the current gallery with two people

Run gallery-only first, with no retry or spatial option:

```bash
cd ~/projects/edgexr
git pull --ff-only
PYTHONPATH=src python3 -m app.live_preview \
  --device /dev/video0 --detect --reidentify \
  --trial-output recordings/reid-crowd-gallery-01 --trial-seconds 90 \
  --trial-notes "two people; fixed camera; steady light; gallery only"
```

Use the browser through the existing SSH tunnel. The trial stops itself after
90 seconds. Record approximate host-clock times and the physical person (A/B)
for these events: both visible; A leaves for 3–5 seconds while B stays; A
returns; B leaves and returns; both cross positions; one person leaves and a
different person takes roughly the same position. Do not treat equal numbers
as success unless the video confirms physical continuity. Record correct
restores, missed restores, false old-ID claims, and ambiguous abstentions.
Check `metadata.json` for `"status": "complete"` and the selected mode fields.

Copy the private directory to the Mac for review:

```bash
scp -r pi@ai-fusion.local:/home/pi/projects/edgexr/recordings/reid-crowd-gallery-01 \
  /Users/ryanchoi/Desktop/
```

## B. Evaluate a two-second retry on the same recorded inputs

Replay the exact detector boxes, source images and times without moving the
robot or changing the detector. This isolates the ID matching change:

```bash
cd /Users/ryanchoi/Desktop/edgexr
PYTHONPATH=src python3 scripts/replay_reidentification.py \
  /Users/ryanchoi/Desktop/reid-crowd-gallery-01
PYTHONPATH=src python3 scripts/replay_reidentification.py \
  /Users/ryanchoi/Desktop/reid-crowd-gallery-01 --retry-seconds 2
```

`retry_restores` lists provisional IDs revised on a later detector update.
Compare those rows with the footage and your A/B notes; the script does not
know the true identity. It does not measure live Pi speed. If the offline
comparison looks safe, run a separate live trial with
`--reid-retry-seconds 2` and a new output directory. `?` means a provisional
new ID; `↺` means an appearance restore. A provisional number can change.

## C. Test spatial support separately

For a new, clearly labelled camera-pan trial, first run the same scene with
`--motion-aware-tracking` but without `--reid-spatial`, using a fresh output
directory such as `recordings/reid-spatial-control-01`. Then run:

```bash
cd ~/projects/edgexr
PYTHONPATH=src python3 -m app.live_preview \
  --device /dev/video0 --detect --reidentify \
  --motion-aware-tracking --reid-spatial \
  --trial-output recordings/reid-spatial-pan-01 --trial-seconds 60 \
  --trial-notes "two people; slow camera pan and return; no retry"
```

Use a slow manual pan within safe cable travel, then return. No servo command
is issued. The image-motion path must cover the *entire* interval from the old
box to the new detector frame. Check `spatial_covered_candidates` and
`spatial_supported_candidates` in `updates.jsonl`; zero coverage means spatial
evidence could not participate. The spatial clue is a small ranking tie-break
between already strong appearances. It neither restores weak appearances nor
uses IMU readings. Compare correct/false claims with the motion-aware control
run and record when coverage was unavailable. Repeating a manual movement is
not identical input, so treat this as an exploratory live comparison.

`--device /dev/video0` is the previously observed device path; check with
`v4l2-ctl --list-devices` if it has changed. For a retry use a fresh output
name because the recorder refuses to overwrite an existing trial.
