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
  All 130 unit tests passed (two skipped); Pi observations remain pending.
- [x] 2026-10-24: Update docs/PIPELINE.md and docs/learning/IMU.md with the
  offline observer, timing scope and source route. Live topology is unchanged.
- [ ] Run fixed-rate ABBA sequence on Pi; inspect CPU work and orientation quality.
- [ ] Implement the command-driven policy after inspecting those measurements.
- [ ] Compare fixed 50 ms, fixed 10 ms and adaptive on the same workload.

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

Follow [IMU_RESOURCE_BENCHMARK.md](../../IMU_RESOURCE_BENCHMARK.md). The same
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

## Outcomes and retrospective

Fixed-rate instrumentation and comparison implementation are checked locally;
Pi measurements remain pending. Adaptive policy is an approved
follow-up, dependent on the fixed-rate resource results rather than implemented
speculatively in the baseline phase.
