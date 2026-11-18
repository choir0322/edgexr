# Calibrate the Pi camera using the MacBook display

**2026-11-16:** calibration 01 did not cover the image corners. Use
[recalibration 03](CAMERA_RECALIBRATION_03.md) for the current procedure (02 also
missed the corners); the
sections below record how calibration 01 was made.

## HDMI preview while recording (current recommended workflow)

The Pi must have an HDMI monitor showing its graphical desktop, with a keyboard
or another way to launch a terminal **in that desktop session**. An ordinary SSH
terminal alone does not open a window on the Pi monitor. The existing `ffplay`
program and an FFmpeg build with MPEG-2 encoding are needed; no package is
installed by these commands. Preview transport is localhost UDP, not Wi-Fi.

On the Mac, open the target and leave its displayed size unchanged:

```bash
open /Users/ryanchoi/Desktop/edgexr/docs/learning/calibration-screen.html
```

On the Pi's HDMI desktop, open a terminal and pull this version:

```bash
cd ~/projects/edgexr
git pull --ff-only
command -v ffplay
```

If `ffplay` prints nothing, stop and report that result. Stop any existing camera
preview or recorder with Ctrl+C. Then, in the same **Pi desktop terminal**, start
the local preview player. It waits for the recording; the window may not appear
until frames arrive:

```bash
ffplay -hide_banner -loglevel warning -fflags nobuffer -flags low_delay \
  -framedrop -window_title "EdgeXR calibration preview" \
  'udp://127.0.0.1:18765?fifo_size=1000000&overrun_nonfatal=1' &
```

In that terminal start the recorder:

```bash
sudo env PYTHONPATH=src python3 -m recording.combined_capture \
  --device /dev/video0 --seconds 120 --hdmi-preview \
  --output recordings/camera-calibration-screen-01 \
  --notes "Mac screen checkerboard; HDMI local preview; fixed focus; varied poses"
```

Use a new output suffix if that directory already exists. FFmpeg reads the camera
once, writes the original 1280x720 MJPEG video and sends a separate 640x360,
target-5fps preview to the player. The preview may lag or drop frames; it is
only for framing. Wait for `RECORDING` and the player window, then follow the
movement sequence under **Record 120 seconds on the Pi** below. Keep the board
and white border visible. This is still a 120-second recording, not 120 seconds
after the preview window opens. If no window appears or preview fails, stop the
recording with Ctrl+C and report both terminal outputs; use a new folder on retry.
The recorder does not monitor whether ffplay is showing frames; if the window
closes or freezes, stop and inspect the recording status instead of assuming the
preview succeeded. `hdmi_preview` in metadata records the extra workload.

When recording stops, close the preview window (or press `q` while it is focused).
Then use the **Analyze on the Pi** and **Transfer results to Mac** sections below.
The prior preflight-only instructions remain below as a fallback; do not start
the old preview and the recorder at the same time.

This is the first step toward offline sparse 3D reconstruction. The Pi records
your screen, then OpenCV fits the camera's lens parameters. This process does not
build a 3D map, operate the servos or change camera controls. Synthetic geometry
was tested on a Mac; camera/screen calibration has not yet been validated on Pi.

## What to prepare

- Raspberry Pi 4, the existing OV9281 USB camera and IMU, MacBook and SSH.
- A stable table with room to gently reposition the whole Pi rig. Keep wires
  loose and away from the moving mount. Do not force a powered servo or lens.
- Place the MacBook screen upright. Reduce glare and reflections. Set screen
  brightness so white squares appear bright but are not blown out in the camera.
- Keep the camera **focus and resolution unchanged** through calibration and
  later reconstruction. Do not rotate the focus ring during this test.

The screen target has **10 columns × 7 rows of squares**: that means **9 × 6
internal corners**. One-square-wide white border surrounds it. It is a pattern
on a screen: no printer or physical square measurement is needed for intrinsics.

## 1. Update Pi and open the pattern on the Mac

On the Pi:

```bash
cd ~/projects/edgexr
git pull --ff-only
```

On the Mac:

```bash
open /Users/ryanchoi/Desktop/edgexr/docs/learning/calibration-screen.html
```

Maximize the browser window so the complete board and white border are visible.
If you enter browser full-screen mode, do so **before** beginning the recording.
Do not resize the window, change zoom or screen resolution during recording:
changing the pattern size changes the target geometry. Remember how to return
to this window after using Terminal.

## 2. Optional camera view check on Mac

Stop any previous Pi preview with Ctrl+C. In the Pi terminal:

```bash
cd ~/projects/edgexr
PYTHONPATH=src python3 -m app.live_preview --device /dev/video0
```

In a separate **Mac** terminal, reuse your existing SSH tunnel or start:

```bash
ssh -N -o ExitOnForwardFailure=yes \
  -L 127.0.0.1:8766:127.0.0.1:8765 pi@ai-fusion.local
```

In another Mac terminal:

```bash
open http://127.0.0.1:8766
```

Arrange windows temporarily to check that the camera sees a sharp pattern
with its border and no glare or moving reflections. This preview is 320x180;
the recording is 1280x720. The target must remain the same displayed size for
the actual recording. Before the recording, stop the Pi preview with Ctrl+C:
the recorder needs exclusive camera access. Restore the target window and its
chosen fixed size. The preview will not update during the recording.

## 3. Record 120 seconds on the Pi

Put the whole rig on a firm surface facing the Mac screen. The approximate
starting distance can be 40–80 cm, **adjusted so the entire checkerboard and
white margin fit clearly in the camera view**. The exact distance is not a
calibration measurement. Turn the screen to the camera; avoid standing in view.

In the Pi SSH terminal:

```bash
cd ~/projects/edgexr
sudo env PYTHONPATH=src python3 -m recording.combined_capture \
  --device /dev/video0 --seconds 120 \
  --output recordings/camera-calibration-screen-01 \
  --notes "Mac screen checkerboard, fixed camera focus; varied board poses"
```

When `RECORDING` appears, switch back to the target window. Begin with the first
position below. Move deliberately between poses and **hold still for about
6–8 seconds** at each. You do not need exact timing; the analyzer samples every
2 seconds and can reject frames without a visible board. If the window was
resized while recording, restart with a new output folder.

All directions below are relative to the camera **looking at the screen**:

1. **Center, straight on:** screen directly ahead; hold.
2. **Left oblique:** move the whole camera/rig toward the screen's left side,
   keeping the camera pointing toward the screen. The screen should be viewed
   from roughly 15–25° to its left; hold.
3. **Right oblique:** move to the screen's right side, roughly 15–25°; hold.
4. **Above:** lift or raise the camera slightly and aim down toward the center,
   roughly 15–25° downward relative to straight-on; hold securely.
5. **Below:** lower the camera and aim upward toward the center, roughly
   15–25° upward; hold. If difficult, gently tilt the Mac screen instead.
6. **Diagonal upper-left:** combine a modest left-side and high position; hold.
7. **Diagonal lower-right:** combine a modest right-side and low position; hold.
8. **Near:** return near center and move closer while retaining all squares and
   the border in view; hold.
9. **Far:** move back until the board is smaller but squares remain sharp; hold.
10. **Board near image left:** shift/aim the rig so the full board appears near
    the left side of the camera image without clipping the border; hold.
11. **Board near image right:** similarly place it near the image right; hold.
12. **Board near image top:** similarly place it near the top; hold.
13. **Board near image bottom:** similarly place it near the bottom; hold.
14. **Final oblique:** use a different moderate diagonal than before; hold until
    recording ends. Avoid extreme edge-on angles, blur and reflections.

These are approximate **viewpoint** angles, not servo commands. Keep the lens
pointed toward the board and the entire grid visible. If you cannot confidently
place the board near an image edge without seeing the live preview, prefer a
safe fully visible pose; we can inspect coverage and add a second recording if
needed. The original video provides the actual evidence.

## 4. Analyze on the Pi

After the recorder stops, run:

```bash
cd ~/projects/edgexr
sudo env PYTHONPATH=src python3 -m spatial.camera_calibration \
  recordings/camera-calibration-screen-01/camera.mkv \
  --output recordings/camera-calibration-screen-01/calibration.json
```

The recorder ran with sudo and creates its output directory as root, so this
analysis command also uses sudo to write the new report there. The program
extracts temporary samples every 2 seconds, finds the 9×6 internal
corners and fits intrinsics on four out of five detected samples. Every fifth
detected sample is held out from fitting; each held-out board pose is then
estimated using the fixed intrinsics. At least 15 detected samples are required.
The holdout frames can be close together in time, so they are not an independent
session. `needs_review` is intentional even when fitting succeeds.

If it reports too few detected samples, keep the video and paste the error;
we'll inspect it before deciding what to repeat. If the JSON already exists,
choose a different new output filename. Analysis needs temporary disk space for
decoded samples and can take several minutes; progress is printed.

## 5. Transfer results to Mac

On the Mac:

```bash
scp -r pi@ai-fusion.local:/home/pi/projects/edgexr/recordings/camera-calibration-screen-01 \
  /Users/ryanchoi/Desktop/
```

Tell me when transfer finishes. The folder contains private video and sensor
logs; do not commit them. We will inspect image sharpness, screen artifacts,
board coverage, fit errors, held-out errors and outlier poses before calling
the calibration useful. Calibration square units do not supply metric scale to
the later 3D scene. Camera exposure times are not synchronized to IMU readings.
