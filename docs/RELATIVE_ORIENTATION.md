# First offline relative-orientation estimate

## Purpose and AP question

This small experiment turns timestamped raw SH3001 gyro reads into a relative
rotation estimate. The AP question is: what data quality and compute work does
even a minimal orientation estimate require? It reuses the existing recorder
and runs after capture, without opening the camera, moving the servos or adding
a model. CPU cost in a live application remains unmeasured.

Run from the repository root on a completed combined recording:

```bash
PYTHONPATH=src python3 -m spatial.relative_orientation \
  recordings/combined-motion-02 --bias-seconds 2
```

If the data live on the Mac, replace the folder argument with their Desktop
path. For the recent 60-second stationary Pi recording, use `--bias-seconds 10`.
The first window **must physically be still**. The default allowed IMU interval
is 0.2 seconds; the command returns an error rather than bridge a longer gap.
It reads only `metadata.json` and `imu.csv` and writes only JSON to stdout.
`camera.mkv` and `frames.csv` are not used to correct rotation in this step.
The original bias window starts at the recording cue. An optional
`--bias-start-seconds` moves its start without changing the stillness or gap
limits; the output records both window endpoints. This is a protocol change
for any saved run that uses it, so report the selected window and why it was
chosen rather than silently replacing the default result. The separate
[camera-axis validation](IMU_CAMERA_AXES.md#independent-tilt-only-check-and-bias-window-reanalysis)
also requires its selected bias window to end before the first motor command.

## What the code does

1. `analyze()` checks completed metadata, numeric IMU samples, timestamp order,
   and whether any gap exceeds the configured limit. It estimates each gyro
   axis's offset from the selected physically still window. Large variation in
   that window is rejected, but low variation is not proof of stillness.
2. `integrate_gyro()` starts at identity orientation after the bias window. For
   each adjacent pair of read-midpoint timestamps, it averages the two XYZ
   rates, subtracts that recording's estimated offset, multiplies by the
   **measured elapsed time**, and composes the resulting 3D body-axis rotation.
   A normalized quaternion holds the sequence of rotations; independent XYZ
   angle sums would be wrong when rotations about different axes are combined.
3. `rotation_vector_degrees()` reports the shortest rotation from the start in
   IMU axes. Its direction and length are easier to inspect than four quaternion
   coefficients, but its 0–180° representation cannot count a full revolution.

This estimate is relative to the IMU at the first post-bias sample. It is not
camera yaw/pitch, compass heading or world pose. There is no camera–IMU axis
calibration, exposure synchronization, gravity correction or visual drift
correction. The offset may vary between runs; never apply the October 4 offset
to the October 24 recording. The `integration_compute_ms` field times one local
Python integration after CSV parsing; it excludes disk I/O and does not measure
Pi CPU use or sustained latency. Repeat on the Pi under a fixed workload before
using it in an AP comparison.

## Initial offline checks (2026-10-24)

The previously saved `combined-motion-02` recording requested 1280×720 MJPEG
at 30 fps, ran for 15 seconds on a Raspberry Pi 4 with Linux
`6.12.47+rpt-rpi-v8`, and was annotated as a whole-base turn and return. Its
first two seconds after the cue supplied 39 bias samples. Offline processing
on the Mac found a peak 86.10° shortest rotation, chiefly along negative IMU
Y, and a final rotation vector of approximately (+0.94°, +0.29°, −1.65°).
The final shortest-rotation magnitude is about 1.92°. This is consistent with
the annotated return, but the physical angle was not independently measured,
so it is not an 86° accuracy result. The maximum IMU interval was 53.61 ms;
none exceeded the 200 ms rejection limit.

On the older 15-second `combined-still-01` recording, the same two-second-bias
procedure reported a final apparent rotation of 0.62° over 12.92 post-bias
seconds. The small nonzero result illustrates integration drift/noise even when
the rig is believed stationary. These two recordings are historical input checks
from the Mac, not new Pi performance benchmarks. No energy, CPU, temperature,
memory or end-to-end latency comparison follows from them.

## Current Pi results and polling experiment (2026-10-24)

`orientation-still-01` used its own ten-second still bias window and showed
2.72° apparent rotation over 49.96 subsequent seconds. The one-run integration
time was 22.45 ms on the Pi, excluding parsing and recording.

`orientation-pan-01` commanded 0° → −20° → +20° → 0° at 5 commanded °/s,
with the camera-head-mounted IMU, fixed base, 1280x720 MJPEG/30 and passive
metal heatsink. It recorded 649 decoded frames and 427 IMU samples. With a
two-second bias window, the integration used 369 samples over 19.46 s; the
largest IMU gap was 53.88 ms. Peak relative rotation was 20.30°, but final
rotation magnitude was about 11.44°. The user observed the physical return.

Offline video inspection supports that return: direct start/end comparison
estimated (−1.615, −0.039) pixels at 320x180, with all nine patches agreeing.
Cumulative horizontal image motion traversed roughly 79, 161 and 83 pixels
across the three legs, whereas the gyro's Y rotation-vector component changed
approximately +19°, −29° and +21°. Pixel translations are scene-dependent,
and commanded servo angles are not calibrated ground truth.

Most visible movement above one pixel per pair occurred in bursts of one or two
video intervals, comparable to the approximately 53 ms IMU polling period.
Missing parts of these bursts is a leading hypothesis for the gyro discrepancy.
Sensor filtering and transient bias remain possible contributors. No precise
exposure/gyro alignment has been established.

### Repeat the same movement with 10 ms post-read sleep

The AP question is whether spending more work on IMU reads improves the
orientation estimate. Change only polling sleep, from 0.05 s to 0.01 s. Keep
the scene, mounting, camera mode, power, cooling, servo path and commanded
speed the same. `servo_motion_quality --imu-interval` forwards the value to
`combined_capture --interval`; `metadata.json` records `imu_sleep_seconds`
and the full capture command. The servo-quality summary also includes sleep.
The existing default is 0.05 s. This experiment does not change the live IMU
worker's polling cadence or the sensor's internal output rate.

After updating the Pi checkout, close any live preview using the camera and run:

```bash
cd ~/projects/edgexr
git pull --ff-only
sudo env PYTHONPATH=src python3 -m recording.servo_motion_quality \
  --commission --wide-pan --axes pan --execute \
  --confirm-centered --confirm-cable-slack --confirm-wide-pan-clearance \
  --pan-channel 2 --tilt-channel 3 --device /dev/video0 \
  --imu-interval 0.01 \
  --output recordings/orientation-pan-10ms-01 \
  --scene "fixed base; camera-head pan and return; same scene as orientation-pan-01" \
  --cooling "passive metal heatsink"

PYTHONPATH=src python3 -m spatial.relative_orientation \
  recordings/orientation-pan-10ms-01 --bias-seconds 2
PYTHONPATH=src python3 -m recording.analyze_capture \
  recordings/orientation-pan-10ms-01 --baseline-seconds 2
```

The command uses previously confirmed pan channel 2, tilt channel 3, safe zero
and ±20° travel; verify the camera still uses `/dev/video0`. It commands the
same 21.5-second recording, followed by offline visual diagnostics. Use a new
output directory for each repeat; existing recordings are preserved.

Compare the measured IMU rate/gaps/read durations, final rotation vector and
magnitude, peak angle, initial/final raw rates, and camera timing. Confirm
`imu_sleep_seconds` is 0.01 in the new metadata. A 10 ms sleep does not promise
100 Hz: reading, CSV writing and scheduling also take time. A lower residual
on one run is preliminary evidence; repeat both configurations before choosing
a default. Report integration time alongside sample count; more samples mean
more integration work. CPU, memory and sustained energy cost remain to be
measured under a fixed protocol, so this run alone cannot establish efficiency.

The [fixed/adaptive resource cycle is complete](IMU_POLLING_FINDINGS.md).
The approved next step is [camera-axis mapping](exec-plans/active/imu-camera-axis-mapping.md),
using explicit fixed 10 ms polling as the reference configuration.

After polling is understood, calibrate the IMU-to-camera axes and obtain an
independent rotation reference before reporting viewing direction.
