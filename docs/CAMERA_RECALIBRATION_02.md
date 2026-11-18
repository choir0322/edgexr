# Camera recalibration 02: cover the image corners

**Result (2026-11-19):** better centre fit, but corner coverage and whole-image
invertibility failed; see [recalibration 03](CAMERA_RECALIBRATION_03.md) and the
[summary](../benchmarks/results/camera-calibration-screen-02.json).

## Why repeat calibration

Calibration 01 (`camera-calibration-screen-01`) fitted well where the board was
seen, but the board never reached the image corners: its median width was 680 px
(over half the image) and its detected corners stayed 90–160 px from every image
corner. The fitted lens polynomial (negative k3) therefore extrapolates there and
folds at normalized distorted radius 0.973, so three corners and a left-edge strip
have no valid inverse (see
[spatial-awareness plan](exec-plans/active/spatial-awareness-integration.md)).
Step 1 converts detections to directions everywhere in the image, so the lens
model must hold out to the corners.

The fix is a **smaller board in the image** (so it fits into a corner), placed
deliberately in all four corners and along every edge, plus tilted views. Same
tool, same 1280×720 mode, same fixed focus; no code change.

## Preparation

- Pi HDMI monitor + keyboard showing the Pi desktop (for the live framing preview).
- Same camera and lens; **do not touch the focus ring**. Rig at rest; no servo
  commands are sent by this procedure. Do not push the powered pan/tilt head by hand.
- Dim or switch off lamps that reflect in the MacBook screen. Set the MacBook to
  roughly 60–70% brightness: white squares bright but not glowing in the preview.
- Put the Pi rig on a stable surface, e.g. on a book stack so the lens is about
  level with the middle of the MacBook screen. Keep cables slack.
- You will move **the MacBook**, not the camera, to place the board around the image.

## 1. Board and framing (Mac + Pi desktop)

On the Mac, open the target, then enter browser full-screen **before** recording
and do not change zoom or window size afterwards:

```bash
open /Users/ryanchoi/Desktop/edgexr/docs/learning/calibration-screen.html
```

On the Pi desktop terminal, update and confirm the camera device and preview player:

```bash
cd ~/projects/edgexr
git pull --ff-only
v4l2-ctl --list-devices
command -v ffplay
```

Use the video device listed for the USB camera (it has been `/dev/video0`; change
the commands below if it is not). If `ffplay` prints nothing, stop and report.

## 2. Record 360 seconds with the HDMI preview

In the Pi desktop terminal start the preview player, then the recorder:

```bash
ffplay -hide_banner -loglevel warning -fflags nobuffer -flags low_delay \
  -framedrop -window_title "EdgeXR calibration preview" \
  'udp://127.0.0.1:18765?fifo_size=1000000&overrun_nonfatal=1' &

sudo env PYTHONPATH=src python3 -m recording.combined_capture \
  --device /dev/video0 --seconds 360 --hdmi-preview \
  --output recordings/camera-calibration-screen-02 \
  --notes "Recalibration 02: small board, all corners and edges, tilts; fixed focus"
```

**Board size rule:** before the corner poses, move the MacBook back until the whole
board **including its white border is about one quarter of the preview width**
(roughly 1.5–2× the distance used in calibration 01). Squares must still look
crisp, not blurred or moiré-patterned. Keep that distance for poses 1–13.

**Every pose:** all 70 black-and-white squares and a thin white margin visible;
hold still **8 seconds**; then move. The analyzer samples every 2 s and drops
blurred or incomplete frames, so smooth movement between holds is fine.

Directions are as seen **in the preview image**:

| # | Where the board sits in the image | Screen orientation |
|---|---|---|
| 1 | top-left corner: white border almost touching both edges | facing camera |
| 2 | top edge, centred | facing camera |
| 3 | top-right corner | facing camera |
| 4 | right edge, middle | facing camera |
| 5 | bottom-right corner | facing camera |
| 6 | bottom edge, centred | facing camera |
| 7 | bottom-left corner | facing camera |
| 8 | left edge, middle | facing camera |
| 9 | centre | facing camera |
| 10 | top-left corner again | MacBook turned ~30° on the table |
| 11 | top-right corner | turned ~30° the other way |
| 12 | bottom-right corner | lid tilted back ~30° |
| 13 | bottom-left corner | lid tilted forward (more upright) ~20° |
| 14 | centre | turned ~35° left |
| 15 | centre | turned ~35° right |
| 16 | centre | lid tilted back ~35° |
| 17 | centre | lid more upright ~25° |
| 18 | centre, **near**: board ~2/3 of the preview width | facing camera |
| 19 | centre, **far**: board ~1/6 of the preview width, squares still sharp | facing camera |

To reach the top or bottom of the image, raise the MacBook on a book or lower it
to the table (or tilt the lid); to reach the sides, slide it left or right. If time
remains after pose 19, repeat corners 1, 3, 5, 7 with different tilts until the
recording stops. The corners matter most: pushing the board as far into each corner
as possible while keeping its margin visible is the point of this recording.

When the recorder stops, close the preview window (`q`).

## 3. Analyze on the Pi

```bash
cd ~/projects/edgexr
sudo env PYTHONPATH=src python3 -m spatial.camera_calibration \
  recordings/camera-calibration-screen-02/camera.mkv \
  --output recordings/camera-calibration-screen-02/calibration.json
```

Takes several minutes (≈180 samples). Paste the printed summary if it errors.

## 4. Transfer to the Mac

```bash
scp -r pi@ai-fusion.local:/home/pi/projects/edgexr/recordings/camera-calibration-screen-02 \
  /Users/ryanchoi/Desktop/
```

The folder contains private video; it is never committed.

## Optional: framing check from the Mac before recording

If the HDMI preview is unavailable, check the board size from the Mac first, then
stop the preview (the recorder needs the camera) and record without
`--hdmi-preview`. On the Pi (SSH terminal):

```bash
cd ~/projects/edgexr
PYTHONPATH=src python3 -m app.live_preview --device /dev/video0
```

On the Mac, in one terminal (leave running):

```bash
ssh -N -o ExitOnForwardFailure=yes \
  -L 127.0.0.1:8766:127.0.0.1:8765 pi@ai-fusion.local
```

and in another:

```bash
open http://127.0.0.1:8766
```

Stop the Pi preview with Ctrl+C before starting the recorder.

## Acceptance checks (decided before seeing the result)

Checked on the Mac after transfer; the result stays `needs_review` until all pass:

1. At least 100 detected board samples.
2. Board-centre span at least 0.6 of the image width and of the height (01: 0.37).
3. Detected board corners within 80 px of each of the four image corners (01: 90–160 px).
4. Held-out median per-view error ≤ 0.3 px and 95th percentile ≤ 1.2 px.
5. **Lens model invertible over the whole image:** the fold radius lies beyond the
   image-corner radius, and every image corner round-trips through
   undistort → project within 0.5 px.
6. Split-half focal lengths (first versus second half of the samples) agree within 1%.
7. Visual inspection of sampled frames: no glare, clipping or blur on accepted views.

If 1–4 pass but 5 fails, the coverage was adequate and the 5-coefficient model
itself is unsuitable; the next step is a constrained refit (for example k3 fixed
at zero), which needs a small, explained code option. Calibration 01 stays as the
historical record either way.
