# IMU resource cost and command-driven scheduling

## Purpose / big picture

Measure the CPU work needed for fixed 50 ms and 10 ms post-read sleeps on the
Pi 4, then test whether a servo-command-driven policy can retain the faster
configuration's orientation quality while doing fewer reads during rest.
This directly exercises the project's AP quality/resource tradeoff goal.

## Context and orientation

Use the existing `servo_motion_quality` 21.5 s pan workload: channel 2,
0 → -20 → +20 → 0 degrees at 5 commanded degrees/s; tilt channel 3 initialized
to the previously confirmed safe zero. Camera/IMU remain rigidly mounted on
the head, base fixed, OV9281 requested 1280x720 MJPEG/30, passive heatsink.
Measured Pi platform: aarch64 Linux 6.12.47+rpt-rpi-v8, Python 3.11.2.
Capture and FFmpeg run as separate processes. Offline diagnostics happen after
capture and must be excluded from capture CPU measurements.

## Progress

- [x] 2026-10-24: User approved fixed-rate resource measurement before adaptive work.
- [x] 2026-10-24: Add opt-in one-second process observations inside the recording
  window and a fixed-rate quality/resource comparison command.
- [x] 2026-10-24: Test CPU accounting, identity/counter/missing-data failures,
  recorder lifecycle, complete-file reading and workload-mismatch rejection.
  At this stage the suite ran 130 tests (two skipped); Pi observations followed.
- [x] 2026-10-24: Update docs/PIPELINE.md and docs/learning/IMU.md with the
  offline observer, timing scope and source route. Live topology is unchanged.
- [x] 2026-10-24: Fixed-rate ABBA complete. Median recorder CPU work 0.415 versus
  0.885 s; apparent return residual 10.77 versus 0.79 degrees. Camera near
  30.08 fps, flags 0x0, temperatures 46.25–52.10 C. Store the reviewed
  [small results record](../../../benchmarks/results/imu-resource-fixed-2026-10-24.md).
- [x] 2026-10-24: Implement command-driven pipe control with 0.3 s pre-command
  lead and 1 s settling after actual command completion; log receipt times and
  sample counts. Add pipe, lifecycle, scheduling and comparison-coverage tests.
  At this stage the suite ran 135 tests (two skipped); Pi validation followed.
- [x] 2026-10-24: Update pipeline and IMU guide for the optional offline control
  pipe. Live workers retain their existing behavior.
- [x] 2026-10-24: Six-run matched comparison complete. Adaptive reduced reads
  15.97% versus fixed 10 ms; both recorder CPU medians were 0.865 s. All modes
  retained about 30.08 camera fps, flags 0x0. Record the complete metrics/chart
  and explanations in [IMU_POLLING_FINDINGS.md](../../IMU_POLLING_FINDINGS.md).
- [x] 2026-10-24: User approved proceeding to camera-axis mapping. Preserve
  fixed 10 ms as explicit experimental reference and adaptive as optional.

## Plan of work

1. Reuse tested `/proc` parsing from `profiling.ap_baseline`. Add a small
   optional collector to `combined_capture`, driven by its existing loop.
   Measure recorder and FFmpeg CPU seconds/mean percent separately, sampled
   RSS, temperature and adjacent firmware flags. Start at the recording cue;
   finish before camera shutdown and offline analysis. Preserve defaults.
2. Repeat the unchanged motor/camera workload in order 50, 10, 10, 50 ms.
   Record exact durations, actual IMU rate/read timing, camera timing, residual,
   CPU seconds and temperature. CPU percent uses one logical CPU as 100%.
3. Based on cost and quality, add a policy which requests fast reads before
   the scheduled motion, throughout the sweep and settling, then slower reads
   at rest. Keep proposed timing explicit and test it against fixed-rate modes.
   Unexpected whole-base motion remains a separate limitation to evaluate.

## Concrete steps

Follow [IMU_RESOURCE_BENCHMARK.md](../../IMU_RESOURCE_BENCHMARK.md) for the completed
fixed-rate stage and [IMU_ADAPTIVE_POLLING.md](../../IMU_ADAPTIVE_POLLING.md) for
the completed six-run three-policy comparison. The same
resource observer must be enabled in every compared trial. Existing recordings
without resource logs cannot supply historical CPU measurements.

## Validation and acceptance

Synthetic counters must yield known CPU seconds and one-core utilization;
PID reuse, counter reset and missing `/proc` data must prevent valid CPU claims.
Recorder tests must show final observation before FFmpeg shutdown, capture
cleanup on failure, and default-off behavior. Verify flag forwarding without
hardware. The live diagram/guide must identify this as an offline experiment.
On Pi, require complete metadata/resources and consistent workload before
comparing configurations; record observer overhead and unmeasured power.

## Surprises and discoveries

The earlier 50 ms trial ended with an 11.44 degree gyro residual despite a close
visual return. The 10 ms trial ended at 1.77 degrees. Decimating the same fast
trace to about 20 Hz gave 3.24–13.10 degree residuals across four offsets,
supporting sparse-sampling sensitivity. Those trials did not measure CPU work.

## Decision log

- 2026-10-24: Keep this first step opt-in and fixed-rate. Observe cumulative
  process counters at 1 Hz rather than time the entire servo tool, whose runtime
  includes startup and substantial offline FFT diagnostics. Observe the parent
  servo process only in a future whole-system measurement if needed; this first
  report scopes recorder plus FFmpeg explicitly. Do not infer electrical energy.
- 2026-10-24: Fixed-rate resource results justify the approved adaptive experiment,
  though absolute potential savings are small on this mostly-moving workload.
  Use a bounded nonblocking stdin pipe, preserving CSV schema and command
  deadlines. Log sent and observed requests separately; broken control fails
  capture rather than silently claiming correct active coverage.
- 2026-10-24: No demonstrated adaptive recorder CPU saving in this mostly-moving
  workload. Added control work is a possible contributor, not a separately
  measured cause. The policy follows servo commands and does not estimate
  physical motor speed. Finish this bounded cycle and proceed to axis mapping.

## Outcomes and retrospective

The bounded quality/resource cycle is complete. Short fixed-rate and matched
adaptive results are reviewed and saved; two trials per policy establish
screening evidence, not statistical significance or calibrated angle accuracy.
Adaptive worked and reduced reads but did not demonstrate lower recorder CPU
work. This is a valid AP result. Live defaults and unexpected-base-motion
handling remain unchanged; those are explicit limits rather than claimed work.
The next capability is the separate camera-axis mapping plan.
