# Diagnose live scheduling before changing it

Run two stationary 120-second trials with a textured center view. Keep the
camera still throughout, enroll that view once soon after startup, and keep
the Mac preview open. Detector off, 10 ms IMU sleep, identical thresholds.
No motors are operated. Diagnostic overhead is present in both modes.

## Pi: A, JSON only

```bash
cd ~/projects/edgexr
git pull --ff-only
PYTHONPATH=src python3 -m app.live_preview \
  --device /dev/video0 --imu --imu-sleep-ms 10 \
  --camera-axis-basis configs/camera_axes_neutral.json \
  --relative-orientation --scene-memory \
  --scene-output recordings/scheduling-no-images-01 --scene-seconds 120
```

## Mac preview for both trials

Reuse an existing tunnel or run:

```bash
ssh -N -o ExitOnForwardFailure=yes \
  -L 127.0.0.1:8766:127.0.0.1:8765 pi@ai-fusion.local
```

In another Mac terminal: `open http://127.0.0.1:8766`.
Wait for live camera/IMU, click Remember current view once and keep still.
Each trial stops automatically; reload the browser after starting the next.

## Pi: B, JSON plus images

```bash
PYTHONPATH=src python3 -m app.live_preview \
  --device /dev/video0 --imu --imu-sleep-ms 10 \
  --camera-axis-basis configs/camera_axes_neutral.json \
  --relative-orientation --scene-memory \
  --scene-output recordings/scheduling-images-01 --scene-seconds 120 \
  --scene-save-images
```

Transfer on Mac:

```bash
scp -r pi@ai-fusion.local:/home/pi/projects/edgexr/recordings/scheduling-no-images-01 /Users/ryanchoi/Desktop/
scp -r pi@ai-fusion.local:/home/pi/projects/edgexr/recordings/scheduling-images-01 /Users/ryanchoi/Desktop/
```

## What is measured

- IMU `read_ms`: time inside the driver call, including any scheduling delay.
- `publish_ms`: time in validation, locks, bias/conversion/integration and publication.
- `wake_late_ms`: read-start lateness relative to previous wait-start + requested
  sleep; not a direct OS scheduler latency or proof of CPU starvation.
- `midpoint_gap_ms`: elapsed time between read midpoints; >200 ms counted.
- `first_stale_observation`: first snapshot that invalidated orientation,
  retaining observation time and latest sample age.
- Scene `compute_ms` remains wall time. `scene_thread_cpu_ms` counts only the
  calling thread; OpenCV helper threads are excluded. `process_cpu_during_compute_ms`
  includes *all* application threads during the interval; it is not scene-only CPU.
- Image-write start/end timestamps allow correlation with slow IMU events.
  `previous_log_write` records JSON serialization/write/flush in the preceding
  iteration. `timing-final.json` preserves the final such interval and IMU counters.

The IMU performs no diagnostic disk I/O. It retains 64 slow events plus lifetime
maxima/counts. Events may recur in several JSON rows: deduplicate by `poll` within
each run. More than 64 events between snapshots can overwrite detail, while
maxima/counts survive. Current read exceptions still use the existing error path;
an unfinished read cannot supply a completed duration. No fsync/durable-storage
latency, hardware timestamps, per-thread OS scheduling trace or full AP benchmark
is claimed. Keep unknown orientation fail-closed. A/B association is not causal
proof: repeat in reverse order if a difference appears before selecting a fix.
