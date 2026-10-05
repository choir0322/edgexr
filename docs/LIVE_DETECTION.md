# Live boxes with camera motion and IMU

Add --detect to the SSH preview to run the already-downloaded MobileNet-SSD
model on the CPU, with two OpenCV threads and a target of two updates/second.
No new dependency, model download, saved footage or servo control is involved.

The detector processes the newest available 1280x720 grayscale frame, using
the saved-frame tool's 300x300 normalization and threshold 0.5. Intermediate
frames are intentionally skipped for detection. The existing Skipped decoded
frames counter still refers to the motion-analysis worker, not this deliberate
detector sampling. Only one latest frame and one detector result are retained.

With detection enabled, FFmpeg sends 720p gray to Python and OpenCV reduces it
to 320x180 for motion/display. Disabled mode retains FFmpeg's existing small
frame output. The extra pipe traffic and resizing change the workload, so even
the motion-only portion needs remeasurement. No promise of 30 fps under load.

## Run on Pi

Stop the previous preview with Ctrl+C. After reviewing/pushing on Mac:

```bash
cd ~/projects/edgexr
git pull --ff-only
PYTHONPATH=src python3 -m unittest discover -s tests/unit -v
PYTHONPATH=src python3 -m app.live_preview --device /dev/video0 --imu --detect
```

Use normal pi permissions and keep the rig still for at least the first two
seconds for gyro offset estimation. The first inference may be slower while
the model initializes. Existing model paths are defaults; --prototxt and
--weights accept alternate local paths. No files are fetched automatically.
Missing or invalid model files show a detector error while the camera continues.
OpenCV itself is required at startup for this mode; your Pi has 4.11.0.

Leave the Mac SSH tunnel running and reload http://127.0.0.1:8766. If needed,
start the tunnel in a separate Mac terminal:

```bash
ssh -N -o ExitOnForwardFailure=yes \
  -L 127.0.0.1:8766:127.0.0.1:8765 pi@ai-fusion.local
```

If this local port is already occupied by your working tunnel, reuse it rather
than starting a second copy.

## What the display means

Amber dashed boxes are the latest completed detections; green arrow is image
movement. Boxes describe an older frame and can lag during motion. They are
not tracked, warped or fused with IMU. Stationary subjects should be easier to
inspect. The model may miss the right chair, as it did in the saved image.

- Detection updates: completed detections per second over a recent five-second
  window. Two is a target/upper scheduling rate, not guaranteed throughput.
- Latest detection compute: model preprocessing, inference and box parsing for
  the most recent run. It excludes waiting for the next scheduled run.
- Box source age on Pi: time since that input frame arrived from FFmpeg,
  including compute and time waiting on screen for a replacement. It excludes
  exposure-to-pipe and SSH/browser delay, so is not end-to-end latency.

No backlog or catch-up bursts: if inference takes longer than 0.5 seconds,
the next run uses whatever frame is newest when it becomes available. Boxes
are hidden when their source is older than 1.5 seconds, on detector error,
or when the camera snapshot is not live. A browser disconnect also clears them.
An empty detection is valid and replaces old boxes immediately. Model failures
require a restart after fixing the cause; camera/IMU can continue meanwhile.

## Initial one-minute check

This is a new combined-workload observation. Record Pi power/cooling, lighting,
scene and temperature if available. Hold still for about ten seconds, turn
the whole base slowly and return, then observe until about one minute. Exact
turn timing is unimportant. Do not force servo gears or pull cables.

Report a typical range rather than one refresh:

```text
Still / slow turn / back still:
Analyzed frame rate:
Latest estimator time:
Skipped decoded frames at 10 seconds and at 60 seconds:
Detection updates:
Latest detection compute:
Box source age:
IMU sample rate:
Do boxes line up while still? Which labels/misses?
Any detector error or stale message?
```

Some motion-analysis skips under load are information, not automatically a
failure. Report the increase and whether the view remains responsive. Latest
times are not medians/p95s; no formal sustained benchmark is claimed here.
To compare, restart without --detect using the same scene and IMU setting.
Do not run two camera readers at once. No repeated model download is needed.

## Local verification

48 tests: 46 passed, two skipped due local OpenCV absence and loopback socket
restrictions. A synthetic FFmpeg 720p stream plus fake resize/detection checked
framing, 2 Hz scheduling and camera survival after a detector failure. Browser
JavaScript logic checked ready/empty/stale/disconnected boxes. These checks do
not validate real OpenCV live throughput; that awaits this Pi run.
