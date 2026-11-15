# First offline sparse 3D reconstruction

This implements the **two-view starting step** of the approved offline sparse
reconstruction milestone. It exports points and two camera poses, in arbitrary
scale. Multi-view registration, refinement and independent validation remain
pending. No new package or model is required: use the existing OpenCV/NumPy and
FFmpeg. Calibration-screen-01 is a provisional candidate, not ground truth.

## Prepare a scene

Choose a well-lit static desk or room corner, with textured books/boxes at
different depths and a textured background. Avoid a single flat wall, repeated
checkerboard, screens, mirrors, shiny surfaces and moving people. Switch off the
checkerboard display. Keep focus, lens and 1280x720 mode unchanged. Aim initially
from roughly 0.7–1.2 m away, adjusted for sharpness and a broad view.

Leave the pan/tilt head fixed. Move the **whole rig sideways** to move the camera
center; a servo sweep alone cannot supply the required translation. Support the
rig securely with slack cables. Most of the same scene should remain visible
from every position, ideally at least 70% overlap. The distances below are setup
guidance, not a measured scale supplied to reconstruction.

## Record on the Pi, with HDMI preview

Stop any live application or recorder with Ctrl+C to release the camera. On the
Pi HDMI desktop terminal (not solely an SSH terminal):

```bash
cd ~/projects/edgexr
git pull --ff-only
ffplay -hide_banner -loglevel warning -fflags nobuffer -flags low_delay \
  -framedrop -window_title "EdgeXR sparse reconstruction capture" \
  'udp://127.0.0.1:18765?fifo_size=1000000&overrun_nonfatal=1' &
sudo env PYTHONPATH=src python3 -m recording.combined_capture \
  --device /dev/video0 --seconds 60 --hdmi-preview \
  --output recordings/sparse-scene-01 \
  --notes "Static textured desk; fixed head and focus; whole-rig sideways translation; candidate screen calibration"
```

Use the same verified camera device as calibration, and a new output suffix if
the folder exists. The preview may appear only after recording starts. Close any
previous ffplay listener on this port first. It is a framing aid at 5 fps, not
the full-resolution recording used for geometry.

Approximate schedule, starting at the `RECORDING` cue:

| Time | Action |
|---|---|
| 0–10 s | Hold the starting viewpoint still. |
| 10–12 s | Shift the whole rig about 5–8 cm to the right, maintaining its direction. |
| 12–22 s | Hold the second viewpoint still. |
| 22–24 s | Move another 5–8 cm to the right. |
| 24–34 s | Hold the third viewpoint still. |
| 34–40 s | Move back toward the starting position. |
| 40–60 s | Hold the starting view; recorder stops automatically. |

Exact timing is unnecessary. Keep notes if a hold starts later; analysis accepts
explicit frame times. We initially use 5 s and 15 s on the **video timeline**,
which is only approximately aligned with the recording cue. Saved selected
images let us check whether these times actually captured the intended holds.
If the HDMI framing shows too little overlap, reduce sideways distance. Do not
rotate the camera just to chase individual objects. No servo commands are sent.

## Analyze the first two views on Pi

```bash
cd ~/projects/edgexr
sudo env PYTHONPATH=src python3 -m spatial.sparse_reconstruction \
  recordings/sparse-scene-01/camera.mkv \
  --calibration recordings/camera-calibration-screen-01/calibration.json \
  --first-seconds 5 --second-seconds 15 \
  --output recordings/sparse-scene-01-pair-05-15
```

Sudo permits writing beneath the root-owned recordings directory. This reads the
existing calibration and video without altering them. Each retry needs a new
output directory. A rejected pair is useful diagnostic evidence; preserve its
report and images before capturing again. We can select another pair from the
same recording. Keep both selected viewpoints within the same static scene.

## Transfer on Mac

```bash
scp -r pi@ai-fusion.local:/home/pi/projects/edgexr/recordings/sparse-scene-01 \
  /Users/ryanchoi/Desktop/
scp -r pi@ai-fusion.local:/home/pi/projects/edgexr/recordings/sparse-scene-01-pair-05-15 \
  /Users/ryanchoi/Desktop/
```

Send the printed report and confirm the transfers. Review `view-1.png` and
`view-2.png` for sharpness, overlap and actual viewpoint translation. We will
inspect `points.ply` and the poses against those images. No Mac browser preview
or SSH tunnel is required for the HDMI workflow. A reconstruction viewer is not
installed by this command. Private video, point clouds and images stay out of Git.

## What the program does and records

`src/spatial/sparse_reconstruction.py` extracts two full-size frames with FFmpeg.
ORB finds up to 3,000 keypoints per frame; Hamming descriptor matching applies
a 0.75 ratio test and mutual nearest-neighbor check. `reconstruct()` removes lens
distortion, uses RANSAC to fit an essential matrix at a nominal 1.5-pixel
threshold, and recovers relative camera rotation and translation. Triangulation
intersects corresponding viewing rays to estimate point coordinates.

The output gates require at least 30 positive-depth pose matches and 30 final
points with at least 1 degree of parallax and at most 2 pixels reprojection error
in each image. Accepted points must occupy at least three quadrants relative to
the calibrated principal point in each image. These are initial fixed diagnostic
thresholds, not experimentally established accuracy limits. Do not lower them
to force success. Planar scenes, repetitive texture, blur and calibration error
can still fool two-view estimation; `candidate_needs_review` requires inspection.

`report.json` records thresholds, matches, pose inliers, accepted point count,
parallax, reprojection errors, two world-to-camera matrices, calibration hash,
host/OpenCV version, and elapsed wall/Python process CPU time. Coordinates use
camera one as reference: X right, Y down, Z forward. The second camera baseline
has unit length, so points are not in meters. `points.ply` is only created for
a candidate passing the gates. Rejected estimates retain a reason when possible.
I/O/subprocess failures print an error and can leave partial output; a folder's
existence alone is not successful reconstruction.

IMU logs are retained by the recorder but are not used to estimate translation
or fuse pose in this step. This is not a dense mesh, room-scale position or live
SLAM. Future work: third-view pose registration, refinement, independent
reprojection checks and geometry review before calling the milestone validated.

## Correctness and AP record

Synthetic nonplanar points test recovered shape and translation up to scale;
stationary and pure-rotation inputs test rejection. Real-scene validation is
pending this capture. The tool uses two OpenCV threads and records one-run wall
and Python CPU time (including I/O but excluding FFmpeg child CPU). Peak memory,
temperature, power and full-workload CPU are **not measured**. Mac test timings
are not Pi benchmarks. The bounded workload exposes feature matching and
numerical geometry for later AP profiling.
