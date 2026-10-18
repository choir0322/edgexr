# Run the first sustained AP baseline on the Pi

This measures the existing application, not a new model or faster camera mode.
Use a stable, well-lit scene and keep the Pi still throughout the warm-up and
measurement. Record the actual power supply and cooling arrangement; `unknown`
is allowed but weakens later comparisons. Do not leave the Pi unattended for a
first sustained run. The collector reads metrics and never opens the camera,
moves the servo, or applies calibration.

## Before the run

Review the diff/tests on the Mac, commit and push the collector, then pull on
the Pi. Stop the currently running **motion-aware** preview with Ctrl+C in its
SSH terminal. It has been running 10–15 minutes, which is useful informal
stability evidence, but this benchmark fixes **basic** tracking. The collector
will reject a motion-aware preview instead of silently mixing modes.

Check that the camera, IMU, Pi power and cooling are secure. If you see a
low-voltage warning, unexpected temperature rise, or instability, stop the
run and report it. Note ambient temperature if known. Do not change cooling,
power, camera settings, or the scene midway through a run.

In Pi SSH terminal 1:

```bash
cd ~/projects/edgexr
git pull --ff-only
PYTHONPATH=src python3 -m app.live_preview --device /dev/video0 --detect --imu
```

Keep the camera head still for the IMU's first-second offset estimate. The
command assumes `/dev/video0` is still the correct path; verify it if USB
enumeration changed. Do **not** add `--motion-aware-tracking`. Wait until the
preview reports it is running. The browser need not be open during this
headless baseline; if it is open, note that as a workload difference.

In Pi SSH terminal 2, after reviewing the planned 2-minute warm-up and 5-minute
measurement duration:

```bash
cd ~/projects/edgexr
PYTHONPATH=src python3 -m profiling.ap_baseline \
  --output recordings/ap-baseline-basic-01 \
  --scene "stationary, well-lit desk; camera head still" \
  --power "describe supply, or unknown" \
  --cooling "describe fan/heatsink, or unknown"
```

The output directory must not already exist; choose `-02` for a repeat. The
collector waits 120 seconds, then polls once per second for 300 seconds. It
checks live camera, ready detector/IMU, basic tracking, and the exact Python
preview/FFmpeg child process. A failed preflight creates no output. An
interruption after preflight leaves metadata with `warming_up` or `recording`
status, not a false `complete` summary. You can stop safely with Ctrl+C.

To verify the result on the Pi:

```bash
cat recordings/ap-baseline-basic-01/metadata.json
cat recordings/ap-baseline-basic-01/summary.json
```

Send both JSON texts for analysis. Keep `samples.jsonl` on the Pi unless a
specific anomaly needs inspection; all files are under ignored `recordings/`.
Before committing a concise Markdown result to `benchmarks/results/`, record
OS/Pi RAM, camera device and negotiated mode (e.g. `v4l2-ctl -d /dev/video0
--get-fmt-video --get-parm`), scene, power, cooling, duration and Git commit.
Do not publish the raw trace by default.

## What the numbers mean

`/api/telemetry` supplies recent capture/motion rates, last motion estimator
time, cumulative motion-skipped decoded frames, latest detector rate/compute
and box source age, and IMU rate. It also supplies the preview and FFmpeg PIDs
so `/proc` can sample **those** processes. Python/FFmpeg CPU percentages use
100% for one fully occupied logical core and can exceed 100%; system CPU busy
uses 100% for all-core capacity. RSS is resident memory for each process,
not total Pi RAM or peak allocation. Temperature is Linux thermal zone 0 in
°C; firmware throttle flags are saved as raw hex rather than interpreted.

The collector's one-second polls are sequential observations from HTTP,
`/proc`, thermal sysfs and `vcgencmd`; they are not synchronized with camera
exposure or IMU chip samples. Detector compute and box age summaries count
each distinct detector sequence once so repeated HTTP polls do not duplicate
a result. Box source age begins at **host receipt** of its camera frame, not
at exposure. It is neither sensor-to-screen latency nor browser-network
latency. Current camera mode and model file hashes are recorded where
available; the metadata's camera string is a **request**, not negotiation
proof. Missing thermal/throttle/model information stays null, not zero.

The first run is a measurement, not a performance verdict. Review time trends
and skipped-frame growth along with medians/p95s before selecting one
optimization variable. See [the plan](exec-plans/active/ap-baseline.md) and
[the code walk-through](learning/AP_BASELINE.md).
