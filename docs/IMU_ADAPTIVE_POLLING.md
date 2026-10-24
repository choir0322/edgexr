# Command-driven IMU polling experiment

The six-run experiment is now complete. See [all polling findings](IMU_POLLING_FINDINGS.md)
and the [full small report](../benchmarks/results/imu-resource-three-policy-2026-10-24.json).
Adaptive reduced reads by 15.97%, with no demonstrated recorder CPU saving in
this workload. The procedure below remains the reproducible experiment record.

The [fixed-rate benchmark](../benchmarks/results/imu-resource-fixed-2026-10-24.md)
found that 10 ms sleep used an extra 0.47 recorder CPU seconds per roughly
21.4-second measured trial. Median apparent return residual fell from 10.77°
to 0.79°. Camera rate stayed near 30.08 fps; flags were 0x0. Recorder mean
CPU utilization increased 2.19 percentage points of one logical CPU.
The application benefit is clear in these traces; the extra cost is modest.

## Current policy and code path

`--imu-policy command-driven --imu-interval 0.05 --imu-active-interval 0.01`
selects the following explicit policy for the existing servo recording tool:

1. At rest and during startup/bias acquisition, use 50 ms post-read sleep.
2. `servo_motion_quality.execute_commands` invokes `prepare_motion` 300 ms
   before the first planned servo command. `request_fast_reads` writes `fast`
   to the child recorder's stdin pipe. Motor command deadlines are preserved.
3. `combined_capture.record` checks the pipe before each read using
   `imu.command_polling.CommandPolling.poll`. It switches to 10 ms sleep and
   records the observed host time. A pending slow sleep can delay receipt by
   about 50 ms plus scheduling; the 300 ms lead allows room for this delay.
4. Keep fast reads across the entire sequence, including its small pauses.
   After the last actual servo call finishes, wait one second for settling,
   then send `idle`. This timing follows actual command completion; delayed
   commands do not prematurely leave a precomputed high-rate window.
5. The recorder returns to 50 ms sleep. Fixed-duration capture ends normally.

This controls software polling pauses, not the sensor's internal sample rate
or filtering. It adds no worker thread. `select` and bounded pipe reads avoid
blocking on a fragmented message. Broken or malformed controls fail the capture
with preserved partial logs. The separate servo controller issues no more angles
if the recorder fails. Fixed mode retains its explicit selected interval.

`metadata.json` stores `imu_policy`, idle/active sleeps, observed
`imu_policy_transitions`, and `imu_policy_sample_counts_all` (including startup).
`servo_commands.json` stores requested policy changes and absolute host send
times, plus configured lead/settling durations. The existing `imu.csv` schema
is unchanged. The comparison additionally reports reads within the requested
recording window. It rejects adaptive traces lacking idle→fast→idle transitions,
fast receipt before the first command, or fast coverage through one-second
settling after the last command.

## Scope and expected benefit

This first policy assumes a fixed base and known commanded head movement. It
cannot anticipate an unexpected shove/whole-base turn during idle. A quiet
latest gyro reading does not solve that problem, because a burst may occur
between sparse reads. Future experiments may evaluate a faster idle rate,
sensor FIFO or activity-triggered control, with explicit hardware verification.

Only about four seconds of this 21.5-second workload use idle polling. Savings
may be small, and pipe coordination adds some CPU work to the recorder.
Measure the net effect; failure to save meaningful work is a valid AP result.
A workload with longer natural idle periods would be a separate labelled test.
CPU time remains distinct from energy, and return residual from angle accuracy.

## Same-revision three-policy comparison

After pushing this implementation from the Mac, run the following on the Pi
with the same fixed scene/base, camera-head mount, power and passive heatsink.
The previously confirmed safe movement remains 0 → −20 → +20 → 0 on pan channel
2, tilt channel 3 at zero, with requested 1280x720 MJPEG/30. Verify `/dev/video0`
still identifies the camera. All trials use the same resource observer.

The order 50, 10, adaptive, adaptive, 10, 50 gives two trials per policy. Capture
totals 129 seconds; offline FFT diagnostics add time. A new matched set ensures
the comparator can enforce identical software revisions. The prior fixed-rate
results remain a separate recorded benchmark.

```bash
cd ~/projects/edgexr
git pull --ff-only

for trial in 50ms-01 10ms-01 adaptive-01 adaptive-02 10ms-02 50ms-02; do
  case "$trial" in
    50ms-*) imu_sleep=0.05; imu_policy=fixed ;;
    10ms-*) imu_sleep=0.01; imu_policy=fixed ;;
    adaptive-*) imu_sleep=0.05; imu_policy=command-driven ;;
  esac
  sudo env PYTHONPATH=src python3 -m recording.servo_motion_quality \
    --commission --wide-pan --axes pan --execute \
    --confirm-centered --confirm-cable-slack --confirm-wide-pan-clearance \
    --pan-channel 2 --tilt-channel 3 --device /dev/video0 \
    --imu-policy "$imu_policy" --imu-interval "$imu_sleep" \
    --imu-active-interval 0.01 --measure-resources \
    --output "recordings/imu-policy-$trial" \
    --scene "fixed base; same lit scene; pan and return; three-policy comparison" \
    --power "unknown" --cooling "passive metal heatsink" || break
done

PYTHONPATH=src python3 -m profiling.compare_imu_resources \
  recordings/imu-policy-50ms-01 recordings/imu-policy-10ms-01 \
  recordings/imu-policy-adaptive-01 recordings/imu-policy-adaptive-02 \
  recordings/imu-policy-10ms-02 recordings/imu-policy-50ms-02 \
  --output benchmarks/results/imu-resource-three-policy-01.json
```

Outputs refuse existing paths. If a run fails, inspect its logs before retrying
with a new suffix. Observe whether the head physically returns after each run.
`adaptive_minus_fixed_10ms` reports signed changes: negative CPU seconds/read
counts indicate savings; positive residual degrees indicate a worse return
estimate. Inspect each repeat, temperatures and flags as well as medians.
No statistical confidence or electrical-energy saving is inferred from these
short runs. Transfer the small report for review from the Mac terminal:

```bash
scp pi@ai-fusion.local:/home/pi/projects/edgexr/benchmarks/results/imu-resource-three-policy-01.json \
  /Users/ryanchoi/Desktop/imu-resource-three-policy-01.json
```
