# Bounded RAM observer control

## Purpose / big picture

Test whether moving only the profiler's sample output off the live microSD write
path changes observer gaps. Keep scene images/JSON on microSD. This is an AP
latency/memory tradeoff experiment, not a card-health test. User authorized it
2026-11-07. No new dependency, mount, swap setting or hardware change.

## Context and orientation

Pi 4; Linux 6.12.47+rpt-rpi-v8; Python 3.11.2; 720p MJPEG/30 requested;
scene memory, detector off, 10 ms IMU pause; passive heatsink/no fan; power unknown.
Same 180 s scene and 0.25 s observer profile as run 03, 210 s mmc0 trace. The
previous samples.jsonl is about 42 MiB. A new 64 MiB sample-payload cap allows
headroom but does not cap total process RSS or guarantee memory availability.

## Progress

- [x] Agree controlled variable and no implicit kernel changes.
- [x] Implement file/RAM sample sink, explicit overflow and post-run export.
- [x] Record observer RSS/swap and add comparison tooling for timing/resources.
- [x] Test bounds, exact export, write failure and schema compatibility.
- [x] Update PIPELINE, configuration register, learning modes and instructions.
- [x] Run fresh file A and RAM B on Pi, inspect trace coverage and swap evidence.
- [x] Review single pair with limits; reverse-order replication deferred unless stronger claims are needed.

## Plan of work

Use ordinary process-memory byte chunks, not tmpfs. Only samples.jsonl changes
destination. Defaults remain buffered file writes. RAM payload limit is 64 MiB
(CLI 4–128 MiB); reject the entire next row on overflow, stop the owned child,
export accepted rows as incomplete evidence, never spill silently to storage.
Keep JSON serialization, sampling, app parameters, and preview.log route equal.
Both modes gain identical sampled observer RSS/swap instrumentation.

Record collection end before exporting. RAM export waits 45 s after collection
to normally fall after the 210 s trace; actual boundaries must be checked.
No loss-free/power-loss guarantee: RAM disappears on crash/reboot; a failed
export retains its partial disk file and reports failure. Linux may swap this
memory. Record /proc/self/status, /proc/swaps and vmstat; swap activity makes
strict storage-isolation conclusions inconclusive. Do not change swap settings.

## Concrete steps

See [OBSERVER_RAM_CONTROL.md](../../OBSERVER_RAM_CONTROL.md) for the paired run,
SSH preview, SCP and comparison commands. Run normal-user profiler and separate
root trace helper. No automatic servo motion. New output directories only.

## Validation and acceptance

Hardware-free tests: payload bound before admission, UTF-8 accounting, no disk
file during RAM collection, exact ordered export, no overwrite, overflow/error
status, previous-cycle deduplication, missing counters remain unavailable.
Pi acceptance: child exits cleanly, sample sink/export complete within cap,
app recording drains, trace covers collection without loss, orientation/IMU
health retained; inspect memory and swap. Compare gaps/write tails, observer
CPU/RSS, preview CPU/RSS, queue high-water/drops, image writes and IMU gaps.

## Surprises and discoveries

Ordinary in-memory buffering can still be swapped; RAM routing alone does not
prove zero storage traffic. Preview stdout remains a separate small disk log.

## Decision log

2026-11-07: bounded process-memory chunks avoid mounts/root privileges and keep
the control small. No ByteIO growth or full-buffer copy during export; stream
chunks in order. Export delay is separate from collection CPU/elapsed time.

## Outcomes and retrospective

2026-11-08: bounded diagnostic milestone closed. See
[measured results](../../OBSERVER_RAM_RESULTS.md). Observer maximum gap fell
2017→254 ms and app image-write maximum 2110→39 ms. Both recorders drained with
zero drops; no IMU gap over 200 ms. RAM cost increased; CPU essentially unchanged.
No trace buffer loss or swap activity reported. Manual scene/order/temperature
confounds remain; no sole-cause or card-health conclusion. Strong causal claims
would require replication. Earlier implementation tests reproduced run-03's
4.604 s observer gap and 4.630 s image-write maximum.
Full hardware-independent suite: 211 tests passed, including local HTTP tests.
Changed Python documentation/type contracts and JavaScript syntax checks pass.
