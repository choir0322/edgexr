# Systems architecture and AP experiment register

Updated 2026-11-07. The [interactive worker page](learning/edgexr-worker-rates.html#storage-learning)
shows these configurations. Keep future changes here with status, routing,
controlled variables, provenance, evidence and limits. A proposed diagram is
not a claim that the corresponding code or experiment exists.

| Configuration | Status | Application recording | Profiler output | Trace | Evidence / purpose |
|---|---|---|---|---|---|
| Inline scene recording | Historical | Scene worker saves image/JSON before its next query | Not part of this architecture comparison | None required | Storage can delay next scene query; see stage history |
| Bounded writer | Implemented and Pi-observed | Four waiting records in RAM plus one active write; separate writer to microSD | Separate concern | Separate concern | [Implementation and evidence](BOUNDED_SCENE_RECORDING.md); prevents disk wait from directly holding scene worker |
| kernel-io-02 / spatial-io-02 | Measured, partial trace | Bounded writer to microSD | Buffered JSONL to same microSD | All selected MMC hosts, 2 MiB/CPU RAM, export after stop | [Run 02](KERNEL_IO_RESULTS_02.md); CPU 0 overwrote 88,730 trace entries |
| kernel-io-03 / spatial-io-03 | Measured, no reported loss | Same bounded writer | Same microSD destination | Only MMC name == mmc0; other groups unfiltered | [Run 03](KERNEL_IO_RESULTS_03.md); improved evidence retention, not a latency fix |
| RAM-staged observer | Implemented; Pi comparison pending | Keep images/scene JSON on microSD | samples.jsonl in process memory, 64 MiB payload cap; export after collection + 45 s | Keep mmc0 profile | [Paired protocol](OBSERVER_RAM_CONTROL.md); no spill on overflow, sampled RSS/swap plus system swap deltas |

## What changes and what does not

The queue preserves ordered records through temporary delays. It cannot absorb
unlimited work: full-queue submissions are counted as recording drops, and
explicit enrollments check admission. Recognition can continue. These are
software records, not network packets. Run 03 reached 4/4 but dropped none.

The MMC filter applies to diagnostic entries in the private trace instance.
It does not filter sensor data, disable mmc1, or change device commands.
mmc0 identifies a host interface in this Pi's trace, not CPU core zero.

The implemented RAM area is distinct from the scene queue, Linux file cache and
kernel trace rings. It uses ordinary pageable process-memory byte chunks, not
tmpfs. Payload exhaustion stops collection with an explicit error; no disk
fallback. RAM is volatile and swap remains possible. No mount or kernel policy
change has been made. Preview stdout remains on microSD in both modes.
Schema 3 records observer RSS/swap and export timing; use fresh file/RAM runs
at the same revision to compare the new instrumentation fairly.

## Repeatable workload record

Runs 02/03 use Pi 4, Linux 6.12.47+rpt-rpi-v8, Python 3.11.2; camera requests
1280x720 MJPEG 30 fps (negotiation unmeasured); detector off; scene memory on;
10 ms IMU sleep; 180-second scene capture; observer sampling requested every
0.25 s and HTTP telemetry every 1 s; 210-second trace. Passive metal heatsink,
no fan, power/ambient unknown; no explicit warm-up. Enroll center/left/right,
revisit, show an unenrolled direction, return to center. Manual timing varies.
Run 02 commit d72e335; run 03 commit 8296b53. Root storage ext4/mmcblk0p2.

## Measurement rules for the next control

Compare writer tails, observer gaps, queue occupancy/drops, raw IMU continuity,
orientation readiness, observer CPU, memory use and trace loss. Keep application
output on microSD and change only the observer destination policy. Copy RAM
output after the measured interval and label that work separately. Repeat order
as needed before making a causal or performance claim; the card state and scene
can vary. Do not equate wall-minus-CPU time with measured I/O wait.

Source map: [scene_recorder.py](../src/spatial/scene_recorder.py),
[spatial_stalls.py](../src/profiling/spatial_stalls.py),
[kernel_io_trace.py](../src/profiling/kernel_io_trace.py).
