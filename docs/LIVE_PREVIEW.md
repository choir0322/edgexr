# Camera preview through SSH

For optional live IMU readings, see [LIVE_IMU.md](LIVE_IMU.md). Start with the
camera-only procedure here if troubleshooting capture or SSH access.

Run capture and image-motion analysis on the Pi; view the result in your Mac
browser. The server binds only 127.0.0.1 on the Pi. SSH forwards a local Mac
port to it. No router changes, public hosting, camera upload or web framework.

## 1. Check the Pi environment

In your existing Pi SSH terminal, after pulling the change:

```bash
cd ~/projects/edgexr
git pull --ff-only
python3 -c "import numpy; print(numpy.__version__)"
ffmpeg -version
PYTHONPATH=src python3 -m unittest discover -s tests/unit -v
```

NumPy is the existing optional offline-analysis dependency, but it may not yet
be installed on the Pi. If its import fails, stop and report the error so we can
choose an explicit installation step. Do not assume the Mac environment and
Pi environment match. No dependency is installed automatically by this tool.

## 2. Start the Pi program

Close other camera readers; remove lens cap. Verify the device path if it
changed since the earlier capture checks. Run without sudo first:

```bash
PYTHONPATH=src python3 -m app.live_preview --device /dev/video0
```

Leave this terminal running. It requests 1280x720 MJPEG at 30 fps, decodes and
analyzes 320x180 grayscale, and announces port 8765. It does not move servos,
read the IMU, change exposure controls or save footage. Camera mode is the
same request as the combined recording, but this is a different workload.

## 3. Open a second terminal on your Mac

Run this on the Mac, not at the Pi prompt:

```bash
ssh -N -o ExitOnForwardFailure=yes -L 127.0.0.1:8765:127.0.0.1:8765 pi@ai-fusion.local
```

Use the Pi IP address if ai-fusion.local does not resolve. Enter your normal
SSH password if asked. After connecting this command may display nothing:
that is normal. Leave it running and open http://127.0.0.1:8765 in the Mac browser.

If Mac port 8765 is busy, forward 8766 instead:

```bash
ssh -N -o ExitOnForwardFailure=yes -L 127.0.0.1:8766:127.0.0.1:8765 pi@ai-fusion.local
```

Then open http://127.0.0.1:8766. The Pi still uses 8765. To stop, press Ctrl+C
in the Pi preview terminal and in the Mac tunnel terminal.

## What to observe

Keep the setup still in a well-lit textured scene for roughly 10 seconds.
The page should show a current image and usually report little movement.
Then gently turn the whole robot base and stop; do not force the servo shaft.
The green arrow shows scene content displacement, not the camera's angle.
Right/down are positive. Arrow length is exaggerated for visibility. Blank
or repetitive scenes and moving objects can make the estimate unreliable.

The page explicitly marks unreliable, stale or disconnected data. Stale means
the analyzed result's host receipt time is over two seconds old. A ten-second
startup without an analyzed frame displays a diagnostic. Last images may remain
visible during failures; the arrow is hidden. Status is local observation,
not proof of end-to-end camera freshness through upstream buffering.

## Metrics and architecture

- Decoded receipt rate: frames arriving from FFmpeg over a recent window.
- Analyzed rate: completed analysis outputs over a recent window.
- Estimator time: latest image_shift computation, excluding FFmpeg decode,
  base64 conversion, HTTP serialization, network and browser rendering.
- Skipped decoded frames: frames superseded before analysis; cumulative.
- Result age: time on Pi since the displayed frame was received from FFmpeg,
  measured when the HTTP response was built. Excludes SSH and browser delay.

These are not end-to-end camera latency or sensor exposure FPS. Camera PTS is
not collected by this first preview. The capture reader continually replaces
one latest frame. The analysis worker takes the newest available frame, so slow
analysis cannot build an unbounded Python queue. FFmpeg/driver buffering is
still possible. Motion describes displacement between analyzed frames, which
may not be consecutive capture frames. Gaps over 0.5 seconds invalidate the
motion estimate. At rest shifts below 0.15 analysis pixels are displayed without
an arrow; this is a display deadband, not a calibrated motion threshold.

The browser polls sequentially at up to five updates/s; this is independent
of the Pi analysis rate. Raw grayscale pixels use base64, about 0.4 MB/s at
five updates/s. It is a simple inspectable transport, not optimized streaming.

## First Pi acceptance record

Record Git revision, Python/NumPy/FFmpeg versions, camera mode, scene/lighting,
warm-up, power/cooling, and Pi temperature if available. Observe for 30 seconds
still and 30 seconds with slow movement, and note typical displayed rates,
estimator time, skipped count change, arrow behavior and stale/error states.
Do not compare Mac synthetic test rates to Pi performance. No target FPS has
been promised. CPU, percentile cost and true display latency are future measures.

## Development and limits

To test without a camera, use --demo instead of --device:

```bash
PYTHONPATH=src python3 -m app.live_preview --demo
```

Synthetic motion is not a validation of physical camera motion. Tests cover
pipe chunking, bounded state, stale/error reporting and HTTP routes. The actual
socket test skips explicitly when a sandbox forbids localhost binding; this
must be rerun on the Pi. The initial development sandbox blocked binding, so
real browser/SSH acceptance is pending. Frame processing and shutdown were
tested with real FFmpeg synthetic video, without a server socket.

This server is for development over a trusted SSH tunnel. It only serves two
fixed routes, rejects non-loopback Host names and cross-site requests, and has
no camera-control endpoints. Do not expose it to the public network.
