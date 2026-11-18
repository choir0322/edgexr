# Camera recalibration 03: on-screen corner tour

**Result (2026-11-19):** best fit error so far (held-out 0.12/0.30 px) but corners
still not reached (centre span 0.66 × 0.38; points 158–232 px from image corners)
and focal length unstable within the session (halves 841 vs 735 px): each round's
views lie on one plane, and the browser toolbar was still visible. Combined with
02 and refitted with k3 fixed at zero, it gives the working calibration for step 1
([joint review](../benchmarks/results/camera-calibration-joint-02-03.json),
[03 summary](../benchmarks/results/camera-calibration-screen-03.json)).

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

Keep the MacBook **close**, so its screen fills the camera view, and let a
self-running page move a **smaller board** through the four corners, four edges and
centre of the screen. Page: [calibration-tour.html](learning/calibration-tour.html).
One click starts it; it shows on screen when to change the laptop's angle. No keys.
Schedule after the click: 30 s line-up (board in the centre), then four rounds of
nine 8-second positions with a 10-second "change angle" pause between rounds
(348 s). The original [calibration-screen.html](learning/calibration-screen.html)
is unchanged.

## Steps

1. **Mac:** open the tour page, then make the browser full screen (⌃⌘F):

   ```bash
   open /Users/ryanchoi/Desktop/edgexr/docs/learning/calibration-tour.html
   ```

2. **Pi desktop terminal** (HDMI monitor): start the preview and the 380 s recording:

   ```bash
   cd ~/projects/edgexr
   git pull --ff-only
   ffplay -hide_banner -loglevel warning -fflags nobuffer -flags low_delay \
     -framedrop -window_title "EdgeXR calibration preview" \
     'udp://127.0.0.1:18765?fifo_size=1000000&overrun_nonfatal=1' &
   sudo env PYTHONPATH=src python3 -m recording.combined_capture \
     --device /dev/video0 --seconds 380 --hdmi-preview \
     --output recordings/camera-calibration-screen-03 \
     --notes "Recalibration 03: close screen fills view, self-running corner tour"
   ```

3. When `RECORDING` appears, **click once anywhere on the Mac page**.
4. **Line-up (30 s, countdown on screen):** looking at the Pi preview, move the
   laptop until the screen fills the preview almost edge to edge (thin strip of
   bezel on every side; roughly 20–35 cm away), the small squares look sharp, and
   there are no reflections. Then leave the laptop still.
5. **Follow the screen text.** Hold still while it says "Hold still". When it says
   "Now turn the laptop…", do that within the 10 seconds, turning the laptop about
   its own centre. Three changes in total: turn ~20°, turn ~20° the other way, face
   the camera and tilt the lid back ~20°.
6. When it says **Finished**, wait for the recording to stop by itself, then close
   the preview (`q`).
7. **Analyze on the Pi, then copy to the Mac:**

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
