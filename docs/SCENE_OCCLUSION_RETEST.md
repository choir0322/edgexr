# Paired-source partial-background trial

Implemented 2026-11-10; Pi acceptance and incremental AP cost are pending.
This supersedes the earlier enrollment-only retest. No motors, dependencies or
models are changed. Use the existing verified camera and safe manual view changes.

## What changed

- The detector publishes one latest completed image/boxes/orientation package.
  Scene recognition uses the exact source image, never newer pixels with old
  boxes. Target rates stay detector 2 Hz / scene 1 Hz. Source age at selection
  must be ≤1.5s; the browser hides scene evidence once its source is >2s old.
- Remember accepts only post-click sources and waits at most 8s for eligible
  input/recording capacity. Timeout is NOT STORED and requires another click.
  This bounds waiting, not a hard real-time guarantee on native computation.
- Enrollment requires a clear detector mask: any excluded person area rejects
  the attempt with `clear_background_required`. An empty detection result does
  not prove that no person is present. Check the image yourself before clicking.
- Recognition preserves the full reference and compares visible background.
  Existing minimum 60 features, 24 matches, 20 inliers, 55% inlier fraction,
  homography/footprint and ambiguity checks remain. Partial support must cover
  at least 25% visible frame, 4% absolute supported frame area, 12% of visible
  area and three grid cells, in both query and warped reference coordinates.
  Masked holes do not contribute hull area. These are experimental safeguards,
  not calibrated success probabilities. Unmasked full-frame checks stay unchanged.
- At the end of Session View Map, left = stored reference, right = exact query.
  Amber = excluded rectangles; green dots = geometrically verified matches
  (up to 128 shown). Unknown has no accepted reference/green matches. It is not
  painted over the newest live preview. Age excludes network/browser delay.

## Pi launch

Stop the old preview using Ctrl+C in its terminal. If port 8765 is occupied,
identify the existing preview rather than running another camera reader.
Keep the head still during initial IMU bias estimation. `/dev/video0` is the
previously verified device; adjust only if your device enumeration changed.

```bash
cd ~/projects/edgexr
git pull --ff-only
PYTHONPATH=src python3 -m app.live_preview \
  --device /dev/video0 --port 8765 \
  --imu --imu-sleep-ms 10 \
  --camera-axis-basis configs/camera_axes_neutral.json \
  --relative-orientation --scene-memory --detect --scene-exclude-people \
  --scene-output recordings/spatial-occlusion-01 \
  --scene-save-images --scene-seconds 180
```

The timer starts after application startup, not enrollment. Use a new output
suffix for each retry; never delete/overwrite a previous trial just to rerun.

## Mac preview

Reuse a running tunnel, or in a separate Mac terminal:

```bash
ssh -N -o ExitOnForwardFailure=yes \
  -L 127.0.0.1:8766:127.0.0.1:8765 pi@ai-fusion.local
```

In another Mac terminal:

```bash
open http://127.0.0.1:8766
```

Reload after restarting the Pi. The new evidence panel is below Remember/history
inside Session View Map. The usual camera preview remains independent below it.

## Short trial

1. Clear center background, click Remember and wait for STORED. Repeat left
   and right. Record actual stored labels; rejected attempts can skip numbers.
2. Return left. Keep the camera fixed and confirm the stored left label with
   nobody blocking it. Green dots should agree between reference/query panels.
3. Cross the view and leave, twice, without clicking Remember. Allow about
   five seconds of clear background after each crossing. Partial known is useful;
   unknown during heavy occlusion is legitimate. Check recovery afterward.
4. Show a substantially different, unenrolled direction for about ten seconds,
   then return left. Overlapping adjacent views can legitimately match.
5. Let the timer stop the preview. Note any wrong recognized label or persistent
   failure on the clear view. Do not redo the whole trial for imperfect timing.

If Remember says `clear_background_required`, clear the visible person/arm and
click again. If it reports timeout, preserve the trial; the logs distinguish
missing paired evidence from a recording backlog. Do not keep clicking blindly.

## Check and transfer

On Pi after auto-stop:

```bash
cat recordings/spatial-occlusion-01/timing-final.json
```

On Mac (use the same folder suffix if you changed it):

```bash
scp -r pi@ai-fusion.local:/home/pi/projects/edgexr/recordings/spatial-occlusion-01 \
  /Users/ryanchoi/Desktop/
```

Raw images stay outside Git. JSONL includes source sequence/time, exact-pair
mask metadata, geometry/support reasons and point coordinates, encode timing,
orientation context and recording acceptance. Final timing retains enrollment
receipts even if a timeout happened without any further scene image.

## Resource scope and acceptance

Default reference capacity stays 12, now retaining canonical gray images:
2.64 MiB raw pixel payload plus descriptors/object overhead. One latest completed
1280x720 detector source is retained, not a growing frame queue. One composite
JPEG is replaced per scene update; browser requests transfer it, but telemetry
and ordinary JSONL never include image bytes. Encoding occurs in the scene worker
and is included in `compute_ms`, separately exposed as `evidence_encode_ms`.
Pi CPU, RSS, achieved rates and added transport/encoding cost are **not measured**.
Do not compare this changed workload directly to detector-off storage baselines.

Accept only after reviewing clear references, crossing/recovery, unknown control,
timeout/error outcomes and complete recording. The first trial establishes
functionality, not general occlusion accuracy or a performance improvement.
