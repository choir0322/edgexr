# Live camera and IMU preview

The browser now has an optional `--imu` mode. It reads the SunFounder SH3001
gyroscope while the existing camera preview continues. The IMU uses its own
thread and the vendor library's `read_raw()` conversion; it does not use the
previously invalid saved user calibration or change sensor settings. No sensor
values or video are written to disk.

The browser shows corrected X, Y, Z gyro rates in degrees/second, IMU sample
rate, sample age and an IMU status. These are the IMU board's axes. The mounted
Y axis mostly responds to pan, but a complete camera-axis transform is unknown.
The arrow still shows scene content displacement in 320x180 image pixels. The
two displays are concurrent observations, not exactly synchronized samples.

## Start on the Pi

Stop the old preview with Ctrl+C in its Pi SSH terminal. Leave the Mac SSH
tunnel running. After applying/pushing on Mac, run on the Pi:

```bash
cd ~/projects/edgexr
git pull --ff-only
python3 -c "from sunfounder_imu import IMU; print('IMU library ready')"
PYTHONPATH=src python3 -m unittest discover -s tests/unit -v
PYTHONPATH=src python3 -m app.live_preview --device /dev/video0 --imu
```

Have the camera and IMU still before starting the last command. Keep the whole
rig still for at least two seconds. The first one second of gyro samples
(at least ten readings) supplies this run's stationary offset. The tool rejects
that calibration if any axis varies by more than 0.5 deg/s standard deviation.
If it says to restart, stop with Ctrl+C and retry while still. The offset is
never saved; a new one is estimated each run. The gyro can drift after startup.

Reload the existing Mac browser page (for you, http://127.0.0.1:8766).
Port 8766 is on your Mac; the Pi program stays on 8765. The SSH tunnel can
remain open through the Pi program restart. If the browser disconnects briefly,
wait for the Pi program's Preview line and reload.

Camera-only behavior remains available by omitting `--imu`.

## What to look for

First hold still: IMU status should become **ready**; gyro X/Y/Z should stay
near zero after offset subtraction. The Y value may wander a little because
this is a short stationary estimate, not a permanent calibration. Slowly turn
the whole robot base left, stop, then turn it back without forcing servo gears.
The image arrow and gyro Y should respond in opposite signed directions in
this mounting. On returning to stillness, both should settle. The exact pixels
and degrees/second are different units and should not be equated.

If the IMU reports an error or stale sample (>300 ms), its old corrected rate
is hidden; the camera image continues. A missing first sample after two seconds
also shows as stale. If there is an I2C permission error, share the browser IMU
message and the output of `id -nG` and `ls -l /dev/i2c-1`; do not automatically
run the whole preview with sudo. The Pi's SunFounder library was previously
tested under sudo, so non-root I2C access must be confirmed on this run.

## Initial comparison to the camera-only run

Record approximate values after ten seconds still, and while slowly turning:

```text
Camera-only reference: analyzed ~30.1 fps; latest estimator 27–29 ms;
skipped decoded frames 0 during the earlier short observation.

With IMU, still: analyzed ___ fps; latest estimator ___ ms;
skipped decoded frames ___; IMU ___ samples/s; IMU age ___ ms.
After 10 more seconds still: skipped decoded frames ___.
With IMU, turning: analyzed ___ fps; latest estimator ___ ms;
skipped decoded frames ___; gyro Y sign for each direction ___.
```

The browser shows the *latest* estimator duration, not a maximum or a
percentile; a few readings cannot establish long-run performance. Record the
scene, lighting, Pi temperature, power/cooling and warm-up if you want a
reproducible benchmark. Capture is requested at 1280x720 MJPEG/30 fps and
analysis stays at 320x180. Actual capture/analysis rates remain separate.
The IMU reader sleeps 50 ms after each read, so its sample rate is expected
to be under 20 Hz. This is read scheduling, not the sensor's internal rate.

If analyzed FPS falls or skipped frames accumulate rapidly, stop and share
the observations. The near-30 fps earlier result had little visible headroom;
this new workload needs measurement on the actual Pi before optimization.

## Local verification status

Unit tests cover per-run offset, contaminated startup, stale/error hiding,
poll failure and existing camera logic. A synthetic FFmpeg camera plus fake
IMU ran locally: after the simulated IMU disconnected, the camera analysis
continued. No local direct socket/browser test was possible in the development
sandbox; the Pi browser check is still needed. No exact camera/IMU timing
alignment, sensor fusion, camera angle or compass heading is claimed.
