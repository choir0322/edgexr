# Live camera-axis conversion A/B measurement

## Question and scope

The isolated Pi measurement found about 28 microseconds of process CPU per
`camera_components` call across three 5-second runs (27.73–28.63 microseconds).
At 100 calls/s this projected less than 0.3% of one core, but the live workload
has camera decode, motion analysis, MobileNet-SSD and I2C reads contending for
resources. Does adding one camera-axis projection per valid IMU sample change
measured live CPU, IMU/camera/motion rates, skipped motion frames or temperature?

This is AP workload work directly tied to the bounded orientation application.
It does **not** integrate camera orientation, estimate position/depth, or feed
the tracker. The neutral-head basis is mounting-specific and must be
revalidated after the IMU or camera moves relative to the head.

## What differs between runs

- **A/control:** `--detect --imu` only. The sensor-axis gyro output stays as before.
- **B/conversion:** the same command plus
  `--camera-axis-basis configs/camera_axes_neutral.json`. `LiveImu.publish` subtracts the same
  first-second stationary offset, then calls `camera_components` once for each
  valid later IMU sample. It retains the original sensor-axis display and adds
  separate camera-axis *rates* to telemetry. The conversion count verifies
  actual work. The added mode also computes corrected rates at sample time,
  rather than only when a snapshot is requested; the measured A/B difference
  is therefore the cost of this whole opt-in path, not perfectly isolated
  matrix multiplication.

`profiling.ap_baseline` requires the declared `--camera-axis-mode` to match
live telemetry at preflight, after warm-up and each sample. Both modes use
the same 1280x720 MJPEG/30 camera request, 320x180 motion analysis, 2 Hz CPU
MobileNet-SSD detector, basic tracking, 50 ms post-read IMU sleep, collector,
model, code commit and `--interval 1`. The browser should stay closed during
both measurements to hold workload constant. The collector stores no footage.

## Pi procedure

Hardware: Raspberry Pi 4, Bookworm aarch64/Linux 6.12.47+rpt-rpi-v8,
Python 3.11.2, OV9281 USB camera and camera-head SH3001; passive metal
heatsink without fan. Confirm the actual device path; `/dev/video0` below is
the previously verified path, not a promise after USB re-enumeration. Leave
the base/head still, use the same well-lit scene, power supply and cooling.
Keep the head still for the preview's first-second bias estimate. Do not run
another preview, video recorder or browser during either measurement. Stop if
the Pi reports low voltage, throttling, overheating or IMU error. Do not
change hardware or camera controls to make a result look better.

In Pi terminal 1, start **A** and leave it running:

```bash
cd ~/projects/edgexr
git pull --ff-only
PYTHONPATH=src python3 -m app.live_preview --device /dev/video0 --detect --imu
```

In Pi terminal 2, run its bounded collector (2-minute warm-up + 5-minute
measurement, about 7 minutes total):

```bash
cd ~/projects/edgexr
PYTHONPATH=src python3 -m profiling.ap_baseline \
  --output recordings/camera-axis-ab-off-01 \
  --camera-axis-mode off --warmup-seconds 120 --seconds 300 \
  --scene "stationary well-lit desk; fixed base and camera head" \
  --power "unknown" --cooling "passive metal heatsink; no fan"
```

When the collector reports completion, stop the A preview with Ctrl+C in
terminal 1. Start **B** there; the only preview option added is the basis:

```bash
PYTHONPATH=src python3 -m app.live_preview --device /dev/video0 \
  --detect --imu --camera-axis-basis configs/camera_axes_neutral.json
```

Keep the head still for startup. In terminal 2, run:

```bash
PYTHONPATH=src python3 -m profiling.ap_baseline \
  --output recordings/camera-axis-ab-on-01 \
  --camera-axis-mode on --warmup-seconds 120 --seconds 300 \
  --scene "stationary well-lit desk; fixed base and camera head" \
  --power "unknown" --cooling "passive metal heatsink; no fan"
```

Stop the B preview after the collector finishes. Do not reuse output folders;
choose `-02` for a repeat. If A and B start at meaningfully different
temperatures, throttle, or show scene changes, record that and consider a
third A run after cooldown instead of attributing differences to conversion.
The collector itself does not stop the preview, but it **does** stop its own
measurement after 300 seconds.

Share `metadata.json` and `summary.json` from both ignored output folders,
plus any anomaly in `samples.jsonl`. The metadata records commit, mode,
actual fitted basis, model hashes, scene, durations and Pi conditions. Check
that both say `status: complete` and the two `camera_axis_mode` values differ.
Use `v4l2-ctl -d /dev/video0 --get-fmt-video --get-parm` to confirm negotiated
camera mode separately; the metadata records only the request.

## Interpretation and acceptance

Compare median and p95 preview/FFmpeg/system CPU, IMU and capture/analysis
rates, detector rate, analysis time, skipped decoded-frame growth and first/
last-minute temperatures. `camera_axis_conversions_increase` should be zero
for A and roughly the number of accepted IMU samples during B; a nonzero
count proves the feature was exercised. Both runs should remain `live`/
`ready`, with no new throttle flag. A/B time-series differences, especially
temperature drift, matter more than a tiny difference in one rounded median.

Two sequential live trials are not an isolated causal estimate: thermal
history, background OS work, camera exposure changes and scene variation can
affect them. CPU readings are host observations at about 1 Hz, not
exposure-synchronized latencies. Linux process CPU counters have finite tick
resolution and the projected sub-0.3%-of-one-core change may be smaller than
run-to-run variation; a statistically indistinguishable A/B result is **not**
proof of zero conversion cost. If the opt-in conversion appears cheap and
keeps IMU/camera quality stable, retain per-sample conversion for a later
bounded relative-orientation stage. If results are noisy, repeat with reversed
order or a matched A/B/A design before tuning cadence.
