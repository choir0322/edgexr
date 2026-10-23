# Orientation input baseline — first runnable step

## Why this matters for AP engineering

Before adding computation, establish the timing of its inputs. A requested
polling pause is not a delivered sample period: driver work, file writes and
OS scheduling also take time. This affects both orientation accuracy and the
latency budget of the application. This is a data-validity baseline, not a
full CPU/thermal benchmark or camera–IMU calibration.

The AP handoff is a flexible anchor. Existing working pieces include camera
mode verification, Caffe/OpenCV MobileNet-SSD, tracking and experimental memory,
timestamped camera/IMU capture, and a sustained AP collector. Missing pieces
include calibrated orientation, verified directional memory, a common-dataset
multi-model benchmark and controlled backend/thread comparisons. No NPU exists.
We are not replacing the detector or adding a website in this milestone.

## Procedure on the Pi

Stop any existing live preview or camera recording with Ctrl+C in its terminal.
Leave the base and camera head stationary; keep the current rigid IMU mounting.
No servo command, manual servo movement or sensor-setting change is needed.
Use a stable, well-lit scene without people moving through it. Footage is private
and remains outside Git. Check free space because this records MJPEG video.

From `~/projects/edgexr`, collect the following read-only context and retain the
terminal output with the run. `/dev/video0` is the previously verified camera;
if enumeration changes, substitute the correct capture node.

```bash
cd ~/projects/edgexr
git rev-parse --short HEAD
uname -a
free -h
df -h recordings
v4l2-ctl --list-devices
vcgencmd measure_temp
vcgencmd get_throttled
```

Record ambient/power details if known; otherwise explicitly say unknown. Current
cooling is a passive metal heatsink, no fan. No stabilization/warm-up claim is
made for this input-validity run; note whether the Pi was already warm/busy.

Run the existing recorder; no new code or dependency is required:

```bash
sudo python3 src/recording/combined_capture.py \
  --device /dev/video0 \
  --seconds 60 \
  --interval 0.05 \
  --output recordings/orientation-still-01 \
  --notes "Orientation input baseline; base/head still; fixed lighting; passive heatsink/no fan; detector off; power unknown"
```

It requests 1280x720 MJPEG at 30 fps, and stops about 60 seconds after the first
decoded-frame startup cue, followed by shutdown/finalization. It does not run
detection, motion estimation, a browser or motor control. Do not start another
camera program simultaneously. If the directory exists, choose a new numbered
run; never overwrite the old one. Use sudo only as required by the established
Pi setup; resulting files may be root-owned, so analyze by reading them and
write later analysis into a separately user-writable directory.

After completion:

```bash
cat recordings/orientation-still-01/metadata.json
v4l2-ctl -d /dev/video0 --get-fmt-video --get-parm
vcgencmd measure_temp
vcgencmd get_throttled
```

Copy only the small logs to the Mac initially (run this on the Mac):

```bash
mkdir -p /Users/ryanchoi/Desktop/edgexr-orientation-still-01
scp pi@ai-fusion.local:/home/pi/projects/edgexr/recordings/orientation-still-01/metadata.json \
  pi@ai-fusion.local:/home/pi/projects/edgexr/recordings/orientation-still-01/frames.csv \
  pi@ai-fusion.local:/home/pi/projects/edgexr/recordings/orientation-still-01/imu.csv \
  /Users/ryanchoi/Desktop/edgexr-orientation-still-01/
```

The command may prompt for the Pi password separately for each file.

Analyze the copied logs on the Mac from the repository root (or on the Pi using
the Pi recording path). The tool reads only the three small files and prints JSON:

```bash
cd /Users/ryanchoi/Desktop/edgexr
PYTHONPATH=src python3 -m recording.analyze_capture \
  /Users/ryanchoi/Desktop/edgexr-orientation-still-01 \
  --stationary --window-seconds 10
```

The first and last ten-second windows must both have remained physically still.
Paste that JSON and the Pi's negotiated camera-mode output for interpretation.
On the older 15-second `combined-still-01` capture, a five-second smoke check
of this analyzer found 19.06 observed IMU reads/s, a 52.08 ms median interval,
and no intervals above three times that median. Its raw Y gyro mean changed
by about -0.035 degrees/s between windows. This confirms the analyzer runs on
real EdgeXR files; it does not replace the new 60-second check, establish a
camera-to-IMU transform, or measure AP CPU use.

## What we will inspect before proceeding

1. Completion status, actual negotiated mode, input counts and timestamp order.
2. IMU midpoint interval median/p95/max, read durations and long gaps. The
   `0.05` setting is a sleep AFTER work, not an exact 20 Hz sample-rate guarantee.
3. Camera PTS spacing versus host receipt spacing. Neither host receipt nor
   read midpoint is a verified physical exposure/sampling timestamp.
4. Gyro mean/variation in the first and last ten seconds of the recording window;
   use the first window's bias on the later window to assess short-term stability.
   Stillness is supplied by the procedure; low variation alone does not prove it.
5. Flag gaps larger than three times the median interval as diagnostic outliers,
   not a universal pass/fail cutoff. Do not integrate across them uncritically.

Success for this step means an inspectable, complete input record and an honest
account of timing/stability limitations, not a predetermined orientation accuracy.
No physical sample-loss count can be inferred from host intervals alone. These
logs also cannot prove CPU saturation, full end-to-end latency or synchronization.

## Next decision and source-reading checkpoint

Read `combined_capture.read_row`, `record` and `camera_command`, then
`imu.rotation_test.integrate_rotation`. Explain why measured delta-time matters
more than the requested sleep when integrating angular velocity. The existing
integrator sums sensor-axis rates; it is not general 3D orientation.

Review the resulting logs before axis tests, intrinsics calibration and the
bounded visual-compass prototype. Any polling-rate experiment will be a separate
controlled change with a new run name. Full spatial mapping is not required
before returning to AP model/runtime or concurrency comparisons.
