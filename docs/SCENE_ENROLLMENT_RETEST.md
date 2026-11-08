# Confirmed enrollment and short left-view crossing retest

2026-11-09. This closes the evidence gap in
[the first trial](SPATIAL_FOREGROUND_RESULTS_01.md): the previous click reached
the worker, but View-2 was rejected as weak_image. This is not evidence of a
missed click. Thresholds and source-age policy are unchanged.

## What is new

The Session View Map panel retains the last 12 Remember requests:

- PENDING: waiting for a fresh frame, usable detector evidence or recording
  capacity, or currently checking the selected image. Keep that direction.
- STORED: label, assigned scene ID and stored-view count at completion.
- NOT STORED: requested label and rejection reason; no reference was created.
  Clear the background, hold still and click again. The retry gets a new label.

Normal recognition updates do not erase these receipts. They describe past
requests, not proof that recognition is currently live. Current status/age still
controls the live map. Each selected scene record includes `enrollment_status`;
`enrollment_requested` identifies the exact attempt frame. No silent retry of a
rejected image occurs. Fresh-detector/recording deferrals remain pending.

## Launch on Pi

Stop the prior preview with Ctrl+C in its own terminal. Keep the rig still
during IMU initialization. Use the same verified camera, model, lighting, fixed
base, focus and safe head movement method as before; this command sends no
servo commands. The 120-second timer starts after app startup, not enrollment.

```bash
cd ~/projects/edgexr
git pull --ff-only
PYTHONPATH=src python3 -m app.live_preview \
  --device /dev/video0 --port 8765 \
  --imu --imu-sleep-ms 10 \
  --camera-axis-basis configs/camera_axes_neutral.json \
  --relative-orientation --scene-memory --detect --scene-exclude-people \
  --scene-output recordings/spatial-foreground-02 \
  --scene-save-images --scene-seconds 120
```

Output must be a new folder. If already used, choose `spatial-foreground-02-r1`
and use that exact suffix in the check and transfer commands below.

## Watch from Mac

Reuse the tunnel if it is already running. Otherwise, in a Mac terminal:

```bash
ssh -N -o ExitOnForwardFailure=yes \
  -L 127.0.0.1:8766:127.0.0.1:8765 pi@ai-fusion.local
```

In another Mac terminal:

```bash
open http://127.0.0.1:8766
```

Reload after the Pi restart. The request-history area is directly below
Remember current view. A displayed PENDING acknowledgment is not success.

## Short sequence

1. Clear background at center. Click Remember once, hold still until **STORED**.
   Note its actual label and scene ID.
2. Point left, remove your arm/person from the image and hold still. Click once
   and wait for **STORED**. If NOT STORED, clear the view and explicitly retry.
   Do not start crossings until the left view appears as a stored map node.
3. Repeat at right. Confirm three successfully stored references. Labels may
   skip numbers after rejected attempts; a requested label is not a view count.
4. Return left and keep the camera fixed. With nobody crossing, hold about
   5–10 seconds and check that it recognizes the actual saved left label.
5. Have the person cross and leave, then hold a clear background for about
   5 seconds. Repeat once. Do not click Remember during crossings. Note rough
   times; exact timing is not necessary. Unknown under occlusion is allowed;
   after the person leaves, check whether left recognition returns.
6. Show an unenrolled direction for about 10 seconds, then return left for the
   remaining time. Choose a direction with substantially different content:
   an adjacent overlapping view can legitimately match an enrolled view.

If enrollment is still incomplete when the timer ends, keep the result as an
incomplete trial; do not interpret its crossings as a confirmed-reference test.
The preview stops automatically. No need for a separate recording program.

## Check and transfer

After the Pi stops:

```bash
cat recordings/spatial-foreground-02/timing-final.json
```

From Mac:

```bash
scp -r pi@ai-fusion.local:/home/pi/projects/edgexr/recordings/spatial-foreground-02 \
  /Users/ryanchoi/Desktop/
```

Send the actual left label, whether recognition returned after each crossing,
and any visibly wrong label. Files provide the exact enrollment/decision times.
Raw PNGs/logs stay local; only a small reviewed result belongs in Git.

## Acceptance and limits

First verify all three stored outcomes and the exact left reference PNG. Review
clear-left, crossing, recovery and unenrolled PNG/decision pairs together. Check
detector lag/mask, weak-image reasons, recording completion/drops and IMU gaps.
An unknown result alone is not a false match. This single masked run checks
functionality; a quality benefit requires a matched unmasked comparison.
No CPU savings, general occlusion accuracy, 3D capability or metric position is
established by this retest. Preserve these boundaries in the stage record.
