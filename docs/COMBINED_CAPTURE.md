# First camera and IMU recording

## Offline analysis

After copying or recording a run, use the standard-library analyzer:

```bash
python3 src/recording/analyze_capture.py recordings/combined-motion-01 --baseline-seconds 1
```

It prints JSON and does not change the recording. The baseline is the specified
number of seconds after the RECORDING cue: the board must actually be still.
Review per-second rates and baseline spread before interpreting integrated
angles. A three-second baseline was unsuitable for the first motion run because
the movement started early. The first-second mean is compared with the last
two seconds, not assumed to remain correct indefinitely. Axis integrals are
appropriate for this approximate single-axis experiment, not general 3D pose.

Initial results are in COMBINED_RESULTS.md. Next repeat with a marked base edge
and exact return direction. Keep still for 3 seconds after the cue; turn over
3 seconds, hold 2 seconds, return over 3 seconds, then remain still. Use output
recordings/combined-motion-02 and record the actual physical direction, because
the first motion's gyro sign is opposite the earlier assumed direction label.
Check the lens cap is off and the mount remains fixed. Do not force servo gears.

This is a new workload: 1280x720 MJPEG at a requested 30 fps, video packet
copy, frame decode/logging, and concurrent raw IMU reads. Do not compare its
throughput directly to the earlier 120 fps camera-only decode benchmark.
No detector, RGB conversion, display, servo control, or fusion runs here.

## Run on the Pi

From the repository root, close other camera readers and remove the lens cap.
Use a well-lit scene with visible edges. Keep the first run entirely still.

```bash
sudo python3 src/recording/combined_capture.py --device /dev/video0 --seconds 15 --output recordings/combined-still-01 --notes "Still; add scene, lighting, warm-up, power, cooling and servo state"
```

Device paths can change; verify yours using scripts/hardware_inventory.sh.
The tool uses existing FFmpeg and sunfounder_imu installations. It requests
the documented 30 fps camera mode without changing exposure/gain or saved
IMU calibration. Capture starts before the RECORDING cue; that cue begins
the 15-second experiment window. Give each retry a new output directory.

Once the still recording works, use another directory for a motion run.
After RECORDING: stay still 3 seconds, slowly turn the whole base left over
3 seconds, pause 2 seconds, return over 3 seconds, then remain still. Keep the
base level, cables slack, and camera fixed relative to the base. Do not force
servo gears by hand. Note approximate turn angle; precision is not required.

## What is saved

- camera.mkv: original compressed MJPEG packets in a playable container.
- frames.csv: decoded frame number, camera presentation timestamp (PTS), and
  host receipt time of that frame's FFmpeg diagnostic line.
- imu.csv: read midpoint and duration, acceleration in g, gyro in degrees/s.
  Raw means vendor driver conversion only; no user calibration or gyro offset.
- ffmpeg.log: negotiated mode, FFmpeg/library versions and diagnostics.
- metadata.json: requested mode, clock origin, conditions, counts and status.

All host times are seconds relative to one Python monotonic clock origin.
The IMU midpoint approximates when a read happened, not the sensor's sampling
instant. Camera receipt time includes decode and logging delays. Camera PTS
has a separate origin; never directly subtract it from IMU host timestamps.
Stream-copy video packets can outnumber decoded log entries at shutdown.
These files support inspection and future timing analysis, not synchronized
camera pose. The tool does not automatically pair frames and IMU readings.

## Review and share

Check metadata status is complete, then open camera.mkv and confirm the image
and motion. Inspect CSV timing gaps and ffmpeg.log for the negotiated mode.
The first hardware run may expose a device-specific FFmpeg or I2C issue; share
terminal output and metadata.json first, plus the end of ffmpeg.log on failure.
Retain the Git revision (`git rev-parse HEAD`) with your experiment notes.

recordings/ is already ignored by Git. Keep video and raw logs local; commit
only a concise reviewed result summary. Ctrl+C preserves a failed partial run.
The tool refuses to reuse existing output directories and stops FFmpeg on
sensor errors. A kernel-level blocked sensor read may still require manual
interruption; no real-time scheduling or hardware timeout guarantee is made.
