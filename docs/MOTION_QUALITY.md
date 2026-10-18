# Run the four motion-quality trials

This tests the existing image-motion estimate, not object tracking or inference
speed. Run one trial at a time on the Pi; do not change camera/model settings.
Keep the Pi base secure, avoid forcing the pan servo, and leave cable slack.
The IMU must stay fixed to the camera head throughout.

## Before recording

From `~/projects/edgexr`, pull the reviewed commit and check that no live
preview is using the camera. Confirm the camera still negotiates 1280×720
MJPEG/30 fps with `v4l2-ctl -d /dev/video0 --get-fmt-video --get-parm`. Replace
`/dev/video0` if the actual capture device has changed. Note Pi OS/commit,
lighting, scene texture, cooling and mounting in a notebook. Use the same
scene, light and 15-second duration for all four trials. Record the approximate
second when each action starts and stops; imperfect timing is okay when noted.

Every clip needs the first 1–2 seconds genuinely still after `RECORDING` so
the offline tool can estimate a per-run gyro offset. Capture each separately:

```bash
sudo python3 src/recording/combined_capture.py --device /dev/video0 --seconds 15 --output recordings/quality-still-01 --notes "Still camera and scene throughout"
sudo python3 src/recording/combined_capture.py --device /dev/video0 --seconds 15 --output recordings/quality-slow-01 --notes "Still first 2 s; smooth camera turn; then hold"
sudo python3 src/recording/combined_capture.py --device /dev/video0 --seconds 15 --output recordings/quality-fast-01 --notes "Still first 2 s; one controlled quick turn; then hold"
sudo python3 src/recording/combined_capture.py --device /dev/video0 --seconds 15 --output recordings/quality-person-01 --notes "Camera fixed; person crosses view after 2 s"
```

For the slow and fast trials, turn the entire camera/IMU assembly together,
preferably once in the same direction. A quick turn need not be a spin. For
the person trial, keep both the camera head and Pi base fixed; include a
textured, stationary background. Do not try to hit exact timing by rushing.
If a clip has motion during the initial still window, give the retry a **new**
name and exclude the bad clip from comparison.

## Analyze and compare

Run after recording, from the repo root. The capture directories may be
root-owned because recording used sudo; read access is enough for analysis.
If access is denied, inspect ownership/permissions and fix only the specific
trial directory. No `sudo` is needed for analysis when files are readable.

```bash
PYTHONPATH=src python3 -m recording.visual_motion recordings/quality-still-01 --output recordings/quality-analysis-still-01
PYTHONPATH=src python3 -m recording.visual_motion recordings/quality-slow-01 --output recordings/quality-analysis-slow-01
PYTHONPATH=src python3 -m recording.visual_motion recordings/quality-fast-01 --output recordings/quality-analysis-fast-01
PYTHONPATH=src python3 -m recording.visual_motion recordings/quality-person-01 --output recordings/quality-analysis-person-01
PYTHONPATH=src python3 -m recording.motion_quality --still recordings/quality-analysis-still-01 --slow-turn recordings/quality-analysis-slow-01 --fast-turn recordings/quality-analysis-fast-01 --moving-person recordings/quality-analysis-person-01 --output recordings/quality-comparison-01
```

Share `recordings/quality-comparison-01/comparison.json` and each visual
analysis `summary.json`, plus your approximate action start/stop times and
observations. Keep `camera.mkv` and raw logs out of Git. New output names are
required for retries. These tools require NumPy, FFmpeg and ffprobe already in
the selected environment; stop if one is missing rather than installing it
silently. Analysis is limited to 3000 frames per clip.

## Reading the report

`visual_coverage` is the fraction of inspected adjacent frame pairs with an
image shift. Low coverage on a fast turn may mean the shift exceeded a patch's
search limit or the scene was hard to match; it is a result, not missing data.
`gyro_covered_pairs` separately counts usable approximate IMU interpolation.
`paired_pairs` requires both. `median_shift_pixels` and `p95_shift_pixels`
include **only** visual estimates, in 320×180 pixels per pair, not degrees or
pixels/second. A rejected pair is never inserted as a zero.

`noticeable_shift_pairs` counts accepted estimates above 1 pixel per pair;
this is only a diagnostic aid, especially for the still/person trials. A
person crossing may obscure most patches or cause false consensus. The
per-second signs of dx/dy and gyro Y can help locate an action, but their
alignment and scaling are not calibrated. Without ground-truth rotation and
known action windows, do not call any number an accuracy percentage. Review
the clip and per-pair CSV before deciding whether the estimator failed.
