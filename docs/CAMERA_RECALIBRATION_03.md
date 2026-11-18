# Camera recalibration 03: on-screen corner tour

## What 02 showed

[Calibration 02](../benchmarks/results/camera-calibration-screen-02.json)
(2026-11-19) fitted the centre better than 01 (held-out median/p95 0.17/0.42 px
versus 0.19/1.11 px) but failed the corner checks set in
[recalibration 02](CAMERA_RECALIBRATION_02.md): board centres spanned 0.40 of the
image (target 0.6), only the bottom-left corner was reached (36 px; others
139–161 px), and the lens polynomial still folds (distorted radius 0.956), so three
image corners do not invert. Frames show why: the board was drawn nearly
full-screen and the MacBook stayed close, so the board was 370–820 px wide in the
image and could not fit into a corner. A 2–3 s moment showing a work window
(≈177–179 s) contained no board and was excluded automatically.

## The change

Keep the MacBook **close**, so its screen fills the camera view, and let the
calibration page **move a smaller board** through the four corners, four edges and
centre. The camera and laptop stay still within each round; only the laptop's
tilt changes between rounds. Press **T** on the page to start or stop the tour
(9 positions × 8 s = 72 s per round, starting at the top-left). Keys 1–9 jump to a
position (keypad layout: 7 top-left … 3 bottom-right); `+`/`-` resize the board.
Without pressing T the page is unchanged from calibrations 01–02.

## Steps

**Mac:** open the page and enter full screen (View → Enter Full Screen, or ⌃⌘F):

```bash
open /Users/ryanchoi/Desktop/edgexr/docs/learning/calibration-screen.html
```

**Pi desktop terminal** (HDMI monitor), same as 02:

```bash
cd ~/projects/edgexr
git pull --ff-only
v4l2-ctl --list-devices
command -v ffplay
ffplay -hide_banner -loglevel warning -fflags nobuffer -flags low_delay \
  -framedrop -window_title "EdgeXR calibration preview" \
  'udp://127.0.0.1:18765?fifo_size=1000000&overrun_nonfatal=1' &
```

**Record 320 s** (new folder):

```bash
sudo env PYTHONPATH=src python3 -m recording.combined_capture \
  --device /dev/video0 --seconds 320 --hdmi-preview \
  --output recordings/camera-calibration-screen-03 \
  --notes "Recalibration 03: close screen fills view, on-screen corner tour, 4 tilt rounds"
```

**Framing (first ~30 s of the recording).** When `RECORDING` appears the preview
shows the camera view. On the Mac press **T**, then **5**: the small board pauses
at the screen centre. Rig still on its book stack, lens level with the middle of
the screen. Move the laptop until:

- the screen's display area fills the preview **almost edge to edge**, with a thin
  strip of bezel visible on all four sides (expect roughly 20–35 cm away);
- the small board's squares look crisp (if they blur, move back until sharp; a
  slightly larger gap at the edges is acceptable);
- there are no lamp reflections on the screen.

Then press **T** once: the tour restarts at the top-left and runs by itself. Do not
touch the keyboard again. Rounds:

| Round | During it | Change while the board sits in the **centre** (end of the round) |
|---|---|---|
| 1 | screen facing the camera squarely | turn the laptop ~20° on the table (right side farther) |
| 2 | turned ~20° | turn it ~20° the other way |
| 3 | turned ~20° the other way | face the camera again and tilt the lid back ~20° |
| 4 | lid tilted back | — (recording ends) |

Turn the laptop about its own centre so the screen keeps filling the view; some
corner positions may leave the view in turned rounds, which is fine. Close the
preview (`q`) after the recorder stops.

**Analyze on the Pi and copy to the Mac:**

```bash
sudo env PYTHONPATH=src python3 -m spatial.camera_calibration \
  recordings/camera-calibration-screen-03/camera.mkv \
  --output recordings/camera-calibration-screen-03/calibration.json
```

```bash
scp -r pi@ai-fusion.local:/home/pi/projects/edgexr/recordings/camera-calibration-screen-03 \
  /Users/ryanchoi/Desktop/
```

## Acceptance

Unchanged from [recalibration 02](CAMERA_RECALIBRATION_02.md#acceptance-checks-decided-before-seeing-the-result):
≥100 detections; centre span ≥0.6 of width and height; detected board within
80 px of every image corner; held-out median ≤0.3 px and p95 ≤1.2 px; lens model
invertible over the whole image; split-half focal lengths within 1%; visual review.
If coverage passes but the model still folds, the next step is a constrained refit.
