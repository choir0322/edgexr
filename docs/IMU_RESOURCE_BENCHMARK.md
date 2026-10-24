# Fixed IMU sleep: resource and quality comparison

## Question and workload

How much additional CPU work does 10 ms post-read sleep cost versus 50 ms,
and does the orientation-quality improvement survive another same-workload
comparison? This is the fixed-rate baseline for the approved later adaptive
policy. There is no NPU and no detector in this recording experiment.

Use Pi 4, existing aarch64 Bookworm/Linux 6.12.47+rpt-rpi-v8, camera-head-mounted
SH3001, OV9281 USB camera requested 1280x720 MJPEG/30, fixed scene/base and passive
metal heatsink. Each recording lasts 21.5 s after its camera cue, commands
pan channel 2 through 0 → −20 → +20 → 0 at 5 commanded °/s, and initializes
tilt channel 3 to the already-confirmed safe zero. Keep the same power source,
lighting, exposure and mounting; fill known power information into run notes.
Camera negotiation remains a separate V4L2 check; requested mode is not proof.

## What is measured

`--measure-resources` opts into `profiling.capture_resources.CaptureResources`.
At the recording cue, approximately once per second, and immediately before
camera shutdown it reads Linux `/proc` counters for:

- **Recorder CPU seconds**: Python camera/IMU recorder, its camera-log thread,
  IMU reads, CSV writes and observer work.
- **FFmpeg CPU seconds**: camera packet copying, decoding and timestamp logging.
- **Mean CPU percent**: CPU seconds / actual measured wall seconds × 100.
  Here 100% means one logical CPU, not the entire four-core Pi.
- Sampled RSS maxima in MiB, initial/final temperature and adjacent raw firmware
  throttling flags. RSS is neither a continuously measured peak nor unique
  physical memory; shared pages can occur in both processes.

`resources.json` retains raw tick/RSS/temperature observations and the summary.
Kernel clock-tick resolution is saved; short CPU deltas may be quantized. Both
configurations include the same observer, whose overhead is not subtracted.
The measured window excludes camera startup, camera shutdown, and later FFT
analysis. It excludes the separate servo-controller parent process and does
not measure electrical power or energy. Missing observations, changing process
identity or an interrupted window produce an incomplete resource report.

CPU deltas compare the complete instrumented workloads. They do not isolate the
cost of a single I2C transaction. If recorder work increases while FFmpeg stays
similar, that supports attribution to the changed recorder polling/logging load.

## Run the short fixed-rate comparison

After pushing the new commit from the Mac, update the Pi. Close any camera
preview first. Keep the same scene; verify the camera still uses `/dev/video0`.
The ABBA order (50, 10, 10, 50 ms) helps expose order/temperature effects with
two trials per configuration. It provides 86 seconds of capture in total;
offline analysis adds wall time between trials. Check the saved temperatures
and flags before treating results as comparable. This is a short screening
experiment, with no thermal-equilibrium or statistical-significance claim.

```bash
cd ~/projects/edgexr
git pull --ff-only

for trial in 50ms-01 10ms-01 10ms-02 50ms-02; do
  case "$trial" in
    50ms-*) imu_sleep=0.05 ;;
    10ms-*) imu_sleep=0.01 ;;
  esac
  sudo env PYTHONPATH=src python3 -m recording.servo_motion_quality \
    --commission --wide-pan --axes pan --execute \
    --confirm-centered --confirm-cable-slack --confirm-wide-pan-clearance \
    --pan-channel 2 --tilt-channel 3 --device /dev/video0 \
    --imu-interval "$imu_sleep" --measure-resources \
    --output "recordings/imu-resource-$trial" \
    --scene "fixed base; same lit scene; pan and return; fixed-rate resource ABBA" \
    --power "unknown" --cooling "passive metal heatsink" || break
done
```

The loop runs the real, previously tested movement automatically. Observe that
each run returns the head near its starting view. Existing output directories
are refused; choose a new coherent set of suffixes for another ABBA sequence.
An error stops the loop; inspect partial metadata before repeating anything.

## Compare and share

After all four complete, run as the Pi user (reading sudo-created files is
normally allowed; the small comparison output is created by this user):

```bash
PYTHONPATH=src python3 -m profiling.compare_imu_resources \
  recordings/imu-resource-50ms-01 \
  recordings/imu-resource-10ms-01 \
  recordings/imu-resource-10ms-02 \
  recordings/imu-resource-50ms-02 \
  --output benchmarks/results/imu-resource-fixed-01.json
```

The tool checks completed resources and matching software, host, requested
duration/camera mode and planned servo phases. It recomputes each recording's
relative IMU rotation with its own two-second still bias, then reports IMU rate,
read duration, maximum gap, final residual, camera timing and per-run CPU/memory.
Check notes, temperatures and firmware flags manually; these cannot prove that
two scenes or power conditions were identical. Host timestamps do not establish
camera exposure synchronization, and a return residual is not angle calibration.

`medians` retains both configuration summaries. `faster_minus_slower` is
**10 ms minus 50 ms**: positive CPU seconds mean more work; negative residual
degrees mean a smaller apparent return error. CPU-percent differences are
percentage points of one logical CPU. For example, 2% to 3% is +1 percentage
point; it is also 50% more recorder CPU work per wall second. Treat small
differences cautiously and examine both repeats, not just their medians.

Transfer the one small report from the Mac terminal:

```bash
scp pi@ai-fusion.local:/home/pi/projects/edgexr/benchmarks/results/imu-resource-fixed-01.json \
  /Users/ryanchoi/Desktop/imu-resource-fixed-01.json
```

The report is suitable for Git after review. Raw videos and recording CSVs stay
out of Git. Previous uninstrumented recordings cannot be assigned CPU costs
retroactively. Existing live AP baselines used a different workload and are
not direct comparison rows for this experiment.

## Next: adaptive reads

Review the fixed-rate CPU difference, quality and repeatability first. Then
implement a command-driven high-rate window before the sweep through settling,
with lower-rate reads at rest. Run all three policies with the same scene,
servo schedule, recording duration and resource observer. An adaptive policy
must also report its transitions/read counts and discuss unexpected base motion.
This policy is a planned follow-up, not current behavior.
