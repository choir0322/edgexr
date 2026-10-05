# Add live gyro to the SSH preview

## Purpose / big picture

Show live SH3001 gyro readings next to image motion in the existing Pi browser
preview. Test whether the extra sensor polling affects the previously observed
~30 fps camera analysis. This is exploratory comparison, not camera pose.

## Context and orientation

Existing preview decodes requested 1280x720 MJPEG/30 to 320x180 grayscale and
analyzes on a separate thread. The Pi 4 has SunFounder's SH3001, read via
sunfounder_imu. Earlier combined recordings showed gyro offset changed across
runs; a new stillness estimate is needed for each preview start. Mounted pan
projects mainly onto sensor Y, with an X component. Exact camera/IMU alignment
and sensor-exposure timing are unknown.

## Progress

- [x] 2026-10-05: Inspect preview code, tests, and prior gyro methods.
- [x] 2026-10-05: Add opt-in IMU worker and clearly labeled browser readings.
- [x] 2026-10-05: Test startup stillness, failed reads, stale samples, shutdown
  and concurrent camera throughput with synthetic FFmpeg/fake IMU. 36 unit
  tests run: 35 pass, one local socket test skips because sandbox bind is
  forbidden. UI rendering logic smoke test passes. Pi rates remain unmeasured.
- [x] 2026-10-05: User reported initial Pi/browser check: 30.0–30.4 fps,
  latest estimator 25–29 ms, zero skipped frames, IMU 19.1 Hz; gyro and arrow
  reverse on return. See docs/MOTION_03_RESULTS.md. Conditions are incomplete.
- [ ] Real Pi stale/error behavior and reproducible sustained benchmark.

## Plan of work

1. Keep existing camera worker unchanged. Add independent IMU poller using
   SH3001 read_raw(), with monotonic midpoint timestamps and ~50 ms interval.
2. Estimate gyro offset from the first one second of stationary samples.
   Require sufficient samples and low spread; if movement contaminates the
   window, report invalid calibration and restart while still. Never write
   SunFounder calibration or silently reuse a previous offset.
3. Publish only the latest gyro reading and recent sample rate. Display X/Y/Z
   corrected rates, IMU state/age and a broad Y sign indicator. Show raw sensor
   motion even when camera estimates are unreliable, without inventing a fused
   pose. Sensor error leaves camera preview running.
4. Measure camera analysis FPS, estimator cost and skipped frames with IMU on,
   comparing to the user's 30.1 fps / 27-29 ms / zero skips initial observation.

## Concrete steps

Mac: apply patch, run `PYTHONPATH=src python3 -m unittest discover -s tests/unit -v`,
review diff and push. Pi: pull, ensure sunfounder_imu import and I2C access,
then stop old preview and restart with `--imu`. Keep the whole assembly still
for the first two seconds after the preview starts. Existing SSH tunnel to
127.0.0.1:8765 may stay connected; reload Mac browser page. See docs/LIVE_IMU.md.

## Validation and acceptance

Camera-only mode remains available. With IMU enabled, calibrated rates should
be near zero while still, change sign between opposite turns, and become stale
or error visibly on failure without hiding the camera image. No permanent
calibration change, footage saving or servo operation. Capture/analyze rates
and skipped count must be reported; no promise they remain unchanged.

## Surprises and discoveries

The SunFounder saved user calibration was previously invalid. read_raw() avoids
that user calibration but still converts driver data to g and degrees/second.
Only gyro rates are used here. The earlier one-second stationary window was
cleaner than a three-second window in motion-02 due to an early disturbance.

## Decision log

- 2026-10-05: Opt-in `--imu` so existing camera-only experiments are directly
  comparable. Sensor polling must not run in the frame-analysis thread.
- 2026-10-05: Display sensor-axis rates, not camera yaw or absolute heading.
  Do not infer exact synchronization from HTTP snapshots.

## Outcomes and retrospective

Local checks passed, including a fake IMU disconnect while the synthetic camera
continued near 30 analyzed frames/s. That is not a Pi performance result. Pi
browser check and brief throughput comparison now pass by user observation;
real fault handling and sustained performance remain untested. Record scene, lighting, warm-up,
camera mode, OS, NumPy/SunFounder versions, power/cooling and run duration for
any performance comparison; the earlier preview observation lacked some of
these conditions.
