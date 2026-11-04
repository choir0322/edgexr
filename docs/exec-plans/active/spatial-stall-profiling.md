# Profile spatial workload stalls on Linux

## Purpose / big picture

Explain IMU lateness and image-recording backlog using processor and Linux
accounting evidence. The user authorized this stage after the 879 ms IMU gap
and 9.24 s PNG write in v1. This directly advances AP learning and introduces
kernel scheduler/procfs interfaces before later kernel/BSP/driver exercises.

## Context and orientation

Pi 4, current 6.12-based OS, USB 720p MJPEG/30 camera, 10 ms IMU pause, scene
target 1 Hz, detector off. Keep the existing recognition and 200 ms continuity
rules. `profiling.spatial_stalls` will launch the existing app and sample Linux
task CPU/fault/context-switch/schedstat/I/O counters. Native TIDs in telemetry
map Python workers to Linux tasks. No scheduler/driver settings are changed.

## Progress

- [x] 2026-11-05: Scope and read-only collection design recorded.
- [x] 2026-11-05: Add named worker/native-ID telemetry and bounded Linux observer.
- [x] 2026-11-05: Test parsing, identity, unavailable counters and timing calculations.
- [x] 2026-11-05: Update pipeline and learning source guide, with units/limits.
- [x] 2026-11-05: Analyze spatial-stalls-01: no IMU continuity failure, but writer
  tails and observer gaps persist. See ../../SPATIAL_STALL_RESULTS.md.
- [ ] Separate observer serialization/write/wake timing; repeat before causal attribution.

## Plan of work

Implement a separate standard-library observer with a fixed duration, new
output directory, exact launched-child identity and graceful stop. Keep raw
counter samples on the Pi monotonic clock and record observer cost. Query app
telemetry periodically with a short timeout; collect procfs independently of
whether HTTP is responsive. Missing accounting remains explicit. Provide all
Pi, Mac browser/tunnel and SCP commands. Then analyze the captured evidence.

## Concrete steps

Follow `docs/SPATIAL_STALL_PROFILING.md` after implementation. Use new output
paths; the helper launches one profile and never attaches to an unrelated app.
Use the same three views/holds as v1. No motor commands, installs, sysctls or
kernel changes. Stop prior preview first. Duration and maximum shutdown wait
are bounded. Private source images remain outside Git.

## Validation and acceptance

Hardware-free tests cover Linux stat names containing parentheses, task identity
reuse, counter deltas, unsupported/denied files and wrong telemetry PID. Check
full existing tests after telemetry changes. A successful collector is not an
application pass; retain partial recording and unknown orientation explicitly.
Kernel runqueue time is runnable waiting, not GIL/lock wait. A state/wchan
snapshot does not reconstruct every scheduling event. Observer I/O and polling
can perturb the workload; report overhead and sample gaps. No hard real-time,
energy or root-cause claim from wall time alone.

## Surprises and discoveries

The old AP profiler requires a ready detector and cannot collect this workload
unchanged. Existing logs locate the pause but lack task scheduler evidence.

## Decision log

- 2026-11-05: Begin with existing readable procfs counters; record schedstats
  availability instead of silently enabling it. Deeper tracing follows evidence.
- 2026-11-05: Launch observer and app together so startup failures and early
  gaps are retained, with bounded timer and no unowned process termination.

## Outcomes and retrospective

Implementation and first Pi capture analysis complete; causal diagnosis pending.
The first capture did not reproduce the IMU failure. It did retain long writer
intervals and observer gaps; unavailable kernel accounting limits attribution.
Final implementation full suite passed 196 tests
after allowing the existing localhost HTTP test to bind its temporary server.
Changed-source learning-contract checks passed; the global
audit still reports unrelated pre-existing documentation issues. No Linux target
performance or root cause has yet been measured with this observer.
Low-level kernel/BSP/driver exercises
are now explicit roadmap outcomes, not claimed experience already completed.
