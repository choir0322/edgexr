# Verify background scene recording on the Pi

The scene worker now submits evidence to a bounded recorder instead of waiting
for PNG/JSON writes. Recognition, camera settings and IMU sleep are unchanged.
Pi validation now demonstrates recognition continuing during a 1.335-second
image write, with all 120 records/images saved and no IMU continuity failure.
See [results and limits](LIVE_SCHEDULING_RESULTS.md). This is not a total CPU,
power or universal latency improvement claim. The protocol below is retained
for reproduction; another stationary repeat is not currently required.
Local validation: 183 unit tests passed, including real ORB progress during a
blocked image write and full-queue enrollment deferral. A ten-second synthetic
CLI run saved ten rows/PNGs and shut down with zero drops or pending records.
Source contracts, JavaScript syntax and diff checks passed. These checks are
correctness evidence on the Mac, not resource measurements on the Pi.
Timing schema 2 differs from the earlier synchronous trials. Keep the same scene,
lighting, browser polling and power/cooling setup; record any deviations.

## Run one image-enabled trial

On the Pi, stop the previous preview first:

```bash
cd ~/projects/edgexr
git pull --ff-only
PYTHONPATH=src python3 -m app.live_preview \
  --device /dev/video0 --imu --imu-sleep-ms 10 \
  --camera-axis-basis configs/camera_axes_neutral.json \
  --relative-orientation --scene-memory \
  --scene-output recordings/scheduling-background-01 \
  --scene-seconds 120 --scene-save-images
```

On the Mac, reuse a working tunnel or start one (do not duplicate it):

```bash
ssh -N -o ExitOnForwardFailure=yes \
  -L 127.0.0.1:8766:127.0.0.1:8765 pi@ai-fusion.local
```

In another Mac terminal:

```bash
open http://127.0.0.1:8766
```

Reload after Pi startup. Keep base/head still, enroll once around four seconds
after startup once camera/IMU are ready, then leave untouched. No servo commands.
The page shows recording status, queue depth, saved count and recording drops.
Timer stops acquisition at about 120 seconds; allow up to five extra seconds
for recording to drain. Check the final console recording status. Enrollment
can remain pending while the recording queue is full; do not repeatedly click.

After shutdown, on the Pi:

```bash
cat recordings/scheduling-background-01/timing-final.json
```

On the Mac:

```bash
scp -r pi@ai-fusion.local:/home/pi/projects/edgexr/recordings/scheduling-background-01 \
  /Users/ryanchoi/Desktop/
```

## Acceptance and interpretation

- Final recording status `complete`, or explicitly `partial` with counted query
  drops; no unexplained missing evidence. Enrollment evidence precedes linked
  query rows. A writer error or missing final file is incomplete evidence.
- Compare source-frame gaps, compute times and recording queue waits with both
  prior trial orders. If no slow write occurs, this is a smoke test, not proof
  that buffering solved the observed Pi stall.
- Inspect final accepted/written/dropped counts. Saved-row cadence alone can
  understate recognition cadence when query evidence drops. Browser/telemetry
  scene results continue independently; recording drop is not camera frame loss.
- Keep IMU gap/stale counters. A recurrence must still fail orientation closed.
- No full CPU, memory, power or thermal benchmark is added in this step. Thread
  scheduling/encoding can still contend with other work despite separate I/O.
- Final counters are authoritative after draining. Per-row IMU counters were
  sampled before enqueue; PNG and JSON timings now belong to the writer thread.
