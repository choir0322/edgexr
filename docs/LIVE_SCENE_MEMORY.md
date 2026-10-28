# Live scene memory with relative-orientation context

This opt-in stage recognizes explicitly remembered views, not object identities
or a 3D position. Recognition thresholds are unchanged. A separate recording
(`combined-motion-01`, reference 2 s, queries 7/13 s) returned enrolled A →
unknown → known A with 33/45 geometric inliers on return. See the
[result record](../benchmarks/results/scene-revisit-heldout-2026-10-29.json).
This is limited same-room evidence, not a general accuracy estimate.

## Run on Pi

Stop the previous preview with Ctrl+C first. Keep the head still during startup.
The following does **not** operate the servos or change the existing 50 ms default;
it explicitly selects the previously tested 10 ms option for this run.

```bash
cd ~/projects/edgexr
git pull --ff-only
PYTHONPATH=src python3 -m app.live_preview \
  --device /dev/video0 --imu --imu-sleep-ms 10 \
  --camera-axis-basis configs/camera_axes_neutral.json \
  --relative-orientation --scene-memory \
  --scene-output recordings/live-scene-01
```

Use your verified camera path. The output directory must be new; choose
`live-scene-02` on repeat runs. Detection is intentionally off for the first
functional check; `--detect` remains compatible but adds compute contention.

On a **Mac terminal**, leave this tunnel running:

```bash
ssh -N -o ExitOnForwardFailure=yes \
  -L 127.0.0.1:8766:127.0.0.1:8765 pi@ai-fusion.local
```

In another Mac terminal:

```bash
open http://127.0.0.1:8766
```

If the local port is already occupied by your existing correct tunnel, reuse
that tunnel; otherwise choose an unused Mac port and open the same port.

## Observe and retain evidence

1. Wait for the camera and relative orientation to become ready. Aim at a
   textured room view, not a blank wall or a person filling the image.
2. Click **Remember current view** once and hold still until enrolled View-1.
   This stores the next fresh frame, not the older browser image. Weak-image
   rejection consumes the request; improve the view and click again if needed.
3. Change the view safely, without forcing a powered servo. Use already-approved
   controls or turn the whole fixed-head rig; this page does not command motors.
   When overlap is lost, expect unknown. Hold each view a few seconds.
4. Return to the original view. Expect known View-1. A different visible region
   can be explicitly remembered too, but do not enroll duplicate views: near-equal
   candidate matches deliberately become unknown/ambiguous_views.
5. Stop with Ctrl+C. Transfer the non-image evidence from a Mac terminal:

```bash
scp -r pi@ai-fusion.local:/home/pi/projects/edgexr/recordings/live-scene-01 \
  /Users/ryanchoi/Desktop/
```

`metadata.json` retains settings/provenance; `updates.jsonl` retains every
processed decision, frame sequence/time, compute time, current orientation
context and the matched reference's enrollment orientation. No images, raw
descriptors or video are saved. The files remain outside Git. The log is flushed
per update but is not a transactional recorder; an abrupt power loss may leave
an incomplete final line. Memory itself resets on application restart.

## Scheduling and timing limits

### Image-backed diagnostic run (opt-in)

The earlier telemetry cannot reconstruct camera images. For the next trial use
the same launch command above, replace the output with
`recordings/live-scene-images-01`, and append:

```bash
--scene-save-images --scene-seconds 180
```

The preview stops automatically after approximately 180 seconds of serving
time (plus startup/shutdown). Save one textured reference, turn away and return
several times, holding each view for about five seconds. Finish at the reference
direction and hold for ten seconds before Ctrl+C if finishing before the timer.
Do not force a powered servo. This program does not command motors.

Every processed scene frame, including unknown results and enrollment, gets a
640×360 grayscale PNG. JSONL `image` identifies that frame; `reference_images`
maps stored scene IDs to enrollment PNGs, so rejected candidates can be inspected
against their actual references. Images are the canonical input to feature
extraction. `image_write_ms` separately records resize/PNG write wall time;
`compute_ms` still excludes file I/O. Added disk work can affect scheduling,
so do not compare this recording's timing directly to non-image runs.
Image diagnostics require a new output directory and a 10–600 s timer. Default
logging remains image-free. Files show your surroundings: keep them in ignored
recordings/ and transfer only to your own Mac, not Git. Transfer with:

```bash
scp -r pi@ai-fusion.local:/home/pi/projects/edgexr/recordings/live-scene-images-01 \
  /Users/ryanchoi/Desktop/
```

### Ordinary live scheduling

With scene memory or detection enabled, FFmpeg sends 1280×720 gray to Python.
Capture makes 320×180 motion pixels and retains one latest full frame. The
scene worker resizes its selected full frame to 640×360 and targets **1 Hz**;
it never queues intermediate frames. A frame older than 0.5 s is not processed.
The browser marks scene results stale after 2 s or if camera analysis is not live.
The last decision remains available as diagnostic data, not a fresh claim.

The IMU retains at most 256 orientation snapshots. At frame receipt, capture
selects the latest preceding snapshot no more than 200 ms old; future samples
are never used. Each context retains the IMU sample time, frame lag, quaternion
and startup reference time. Unavailable/failed IMU context remains unknown:
visual recognition still runs. This is **host observation association**, not
camera exposure synchronization, interpolation, gyro correction or fusion.
Orientation does not determine whether a scene matches. Bounds and unknown
behavior of the original relative-orientation estimator are unchanged.

Capacity is 12 views, LRU eviction; corresponding orientation contexts are
evicted together. The dedicated worker owns all feature memory; locks protect
only shared slots/status. Explicit same-origin POST requests enroll views;
GET requests never mutate memory. Source age and compute time are visible.
Pi live CPU, memory, thermals, sustained query rate and contention remain
unmeasured and belong to the later AP phase. One-Hz target is not guaranteed.
