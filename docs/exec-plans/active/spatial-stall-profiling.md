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

- [x] 2026-11-07: Review run 02: storage requests overlap writer tails; CPU 0
  trace overwritten. Preserve limitations in KERNEL_IO_RESULTS_02.md.
- [x] 2026-11-07: Add opt-in exact MMC-host filtering and beginner worker-page
  diagrams separating AP wall/CPU cost from Linux storage mechanisms.
- [x] 2026-11-07: Update pipeline and learning page for the filtered observer path.
- [ ] Run filtered kernel-io-03 / spatial-io-03 on Pi; confirm filter readback,
  no unexpected MMC hosts, complete trace coverage and zero loss before analysis.

- [x] 2026-11-05: Scope and read-only collection design recorded.
- [x] 2026-11-05: Add named worker/native-ID telemetry and bounded Linux observer.
- [x] 2026-11-05: Test parsing, identity, unavailable counters and timing calculations.
- [x] 2026-11-05: Update pipeline and learning source guide, with units/limits.
- [x] 2026-11-05: Analyze spatial-stalls-01: no IMU continuity failure, but writer
  tails and observer gaps persist. See ../../SPATIAL_STALL_RESULTS.md.
- [x] 2026-11-06: Separate observer serialization/write/wake timing, with fake-clock
  tests and final-cycle retention; pipeline/source guide reviewed and updated.
- [x] 2026-11-06: Analyze spatial-stalls-02: largest observer gap is dominated by
  buffered write; app recorder sampled in D/__lock_buffer during longest PNG.
  Initial gyro stability rejected, so orientation remains unknown. See
  ../../SPATIAL_STALL_RESULTS_02.md. Pipeline/source guide reviewed; unchanged.
- [x] 2026-11-06: Confirm recording storage: ext4 root /dev/mmcblk0p2 on
  mmcblk0; tracefs/debugfs already mounted. No settings changed.
- [x] 2026-11-06: Available events include JBD2 buffer stalls/commit, ext4,
  block request and MMC start/done; root tracer nop/tracing_on=1, 86 GB free.
- [x] 2026-11-06: Implement private-instance bounded I/O trace helper and protocol;
  retain calibration failure as a limitation for full-workload CPU comparison.
- [ ] Validate kernel trace helper on Pi, check loss/coverage, and correlate I/O waits.
- [x] 2026-11-06: Review/update pipeline and relevant learning source map for trace helper.

## Plan of work

Current focused step: [KERNEL_IO_TRACE.md](../../KERNEL_IO_TRACE.md). A separate
root helper enables 18 selected events in a unique trace instance for 210 seconds,
while the existing normal-user spatial observer runs for 180 seconds. Allocate
2 MiB per CPU with total cap 32 MiB; export stopped trace only, cap 64 MiB, retain
event formats, per-CPU loss statistics, monotonic timing and cleanup failures.
Do not write global trace controls or run the camera app as root. The user has
seen the trace design and provided target event inventory; no further discovery
run is required before preparing this concrete helper.

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

Run 02 completes raw polling and recording while corrected orientation is absent:
startup gyro stability rejected. Timing counters alone are not orientation health.
The largest observer write uses 0.435 ms CPU across 714.929 ms wall time; the app
writer separately appears in kernel D/__lock_buffer waits for 15 samples during
its longest PNG call. Kernel waiting is observed; ultimate device cause unresolved.

The old AP profiler requires a ready detector and cannot collect this workload
unchanged. Existing logs locate the pause but lack task scheduler evidence.

## Decision log

- 2026-11-06: Use a private ftrace instance with selected I/O events and delayed
  export to avoid live trace logging to the same recording storage. Existing
  root tracing_on=1 and nop selection are preserved. Save event layouts rather
  than assuming fixed request identities or MMC formatting. Default capture
  covers unrelated I/O too, with task/device attribution deferred to analysis.

- 2026-11-06: Conclude phase-localization repeat; move to mount/backing-device
  inspection and bounded I/O tracing. Exclude arm-related right-view recognition
  changes from diagnosis. Do not attribute run-to-run CPU differences to phase
  instrumentation when startup failure disables orientation processing.

- 2026-11-06: Keep buffered I/O and workload unchanged; carry previous-cycle
  timings in the next sample and retain the last in summary. No fsync or kernel
  setting changes. Schema 2 distinguishes this repeat from the initial capture.

- 2026-11-05: Begin with existing readable procfs counters; record schedstats
  availability instead of silently enabling it. Deeper tracing follows evidence.
- 2026-11-05: Launch observer and app together so startup failures and early
  gaps are retained, with bounded timer and no unowned process termination.

## Outcomes and retrospective

2026-11-07: six focused trace tests pass, including exact host filters, missing
events/field rejection and failed readback. Existing stop/export/cleanup checks
remain green. Browser verified the rendered timeline and expanding explanation;
existing worker graph still renders. Diff whitespace check passed. These tests
do not emulate kernel filter evaluation: actual Pi filter acceptance and trace
retention remain pending in the documented run-03 protocol.

2026-11-06 kernel helper validation: all 203 hardware-independent tests passed;
new source/test contract checks passed. Fixtures verify core event requirements,
private controls and host clock, memory bound, missing/lost accounting, exact
export cap, stop-before-export, preserved global state, existing-output rejection
and setup-failure cleanup. These do not exercise the real Pi tracefs; target
execution and subsequent loss/coverage analysis remain pending.

2026-11-06 instrumentation validation: all 198 hardware-independent unit tests
passed, including fake-clock phase timing and existing HTTP behavior. Pi repeat
reviewed: 741 unique cycle indices, 180 matching image files, zero recording
drops. Observer write phase explains its largest gap; kernel write waits narrow
the next investigation. Full-workload CPU/orientation comparison is limited by
the rejected startup baseline. Ultimate stall cause remains open.

Implementation and first Pi capture analysis complete; causal diagnosis pending.
The first capture did not reproduce the IMU failure. It did retain long writer
intervals and observer gaps; unavailable kernel accounting limits attribution.
Final implementation full suite passed 196 tests
after allowing the existing localhost HTTP test to bind its temporary server.
Changed-source learning-contract checks passed; the global
audit still reports unrelated pre-existing documentation issues. Linux task and
observer timings are now measured; original IMU failure cause remains unresolved.
Low-level kernel/BSP/driver exercises
are now explicit roadmap outcomes, not claimed experience already completed.
