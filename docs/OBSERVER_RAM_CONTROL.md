# Profiler-only RAM staging: controlled file / RAM repeat

Status: implemented, **Pi results pending**. This advances AP learning by testing
observer responsiveness versus RAM consumption. No card-defect diagnosis.

## What changes

| Setting | A: file | B: RAM |
|---|---|---|
| Observer samples.jsonl during collection | Buffered microSD file | Process-memory byte chunks |
| Sample payload bound | Existing time-bounded collection | 64 MiB; stop on overflow, no spill |
| App images + scene JSON | Existing microSD writer | **Unchanged** |
| preview.log | microSD | microSD (not part of staged sample stream) |
| Final sample export | Already written | Wait 45 s after collection, then stream to microSD |
| Scene/IMU/trace settings | 180 s / 10 ms / mmc0 | Identical |

Both modes now sample observer RSS (resident memory) and VmSwap around once a
second and save system swap counters before/after collection. Use a fresh A,
not just old run 03: both sides should use this same code/instrumentation.
The 64 MiB limit is accepted UTF-8 payload, not all process memory. Run 03's
sample log was about 42 MiB. Objects/current-row serialization add overhead.
On overflow, accepted rows are exported but the run exits incomplete/nonzero.

RAM is **ordinary pageable memory**, not locked memory, tmpfs or a mount change.
It is lost on crash/reboot. Check VmSwap and system pswpin/pswpout deltas before
claiming storage isolation. Nonzero swap is a confound; zero sampled counters
are not a proof of zero page faults/waits. No swap, scheduler or kernel setting
is changed. Export failure leaves a `.partial` file, reports failure and cannot
preserve unsaved RAM across process exit. Export is buffered, without fsync.

The export delay normally puts copying after the 210 s trace. Verify actual
trace stop against `sample_export.started_host_s`; never assume alignment.
`elapsed_s` and `observer_cpu_s` stop before export/delay. A completed RAM run
takes about 3 minutes of app activity **plus 45 seconds and export time**.

## Prepare the Mac and Pi

Stop the previous preview with Ctrl+C. Keep the lens uncovered and the base
fixed. Open two SSH terminals to the Pi. On the Pi:

```bash
cd ~/projects/edgexr
git pull --ff-only
```

On the Mac, reuse an existing tunnel, or run this in its own terminal and leave
it running (a silent terminal after authentication is normal):

```bash
ssh -N -o ExitOnForwardFailure=yes \
  -L 127.0.0.1:8766:127.0.0.1:8765 pi@ai-fusion.local
```

In another Mac terminal:

```bash
open http://127.0.0.1:8766
```

If port 8766 is occupied, reuse the working tunnel or use local 8767 in both
commands. The Pi destination stays 8765. The page works once the profiler
launches the preview, not before. Device `/dev/video0` is the previously used
camera; change it if the camera's device assignment has changed.

## A: buffered-file control

Pi terminal 1:

```bash
cd ~/projects/edgexr
sudo env PYTHONPATH=src python3 -m profiling.kernel_io_trace \
  --output recordings/kernel-observer-file-01 --seconds 210 --mmc-host mmc0
```

Within about 15 s of `TRACING`, Pi terminal 2:

```bash
cd ~/projects/edgexr
PYTHONPATH=src python3 -m profiling.spatial_stalls \
  --device /dev/video0 --output recordings/spatial-observer-file-01 \
  --observer-output file --seconds 180 --interval 0.25 \
  --scene "three remembered views and revisits; fixed base; kernel I/O tracing" \
  --power "unknown" --cooling "passive metal heatsink; no fan"
```

Workload, same for both runs: hold still for the first 10 s and confirm ready
orientation; remember center, left, right; revisit center/left/right holding
each about 10 s; show an unenrolled direction for 10 s; return to center and
hold until the app stops. Keep people/arms out of remembered views. Record any
mistakes, rejected calibration, or differences; do not reinterpret them as a
storage effect. No automatic motor commands. Let both terminals finish.

## B: RAM samples, application files still on microSD

Same scene/lighting, no other new work. Refresh Mac preview for the new session.
Pi terminal 1:

```bash
cd ~/projects/edgexr
sudo env PYTHONPATH=src python3 -m profiling.kernel_io_trace \
  --output recordings/kernel-observer-ram-01 --seconds 210 --mmc-host mmc0
```

Within about 15 s of `TRACING`, Pi terminal 2:

```bash
cd ~/projects/edgexr
PYTHONPATH=src python3 -m profiling.spatial_stalls \
  --device /dev/video0 --output recordings/spatial-observer-ram-01 \
  --observer-output ram --ram-limit-mib 64 --ram-export-delay 45 \
  --seconds 180 --interval 0.25 \
  --scene "three remembered views and revisits; fixed base; kernel I/O tracing" \
  --power "unknown" --cooling "passive metal heatsink; no fan"
```

Repeat the same viewing sequence. **Do not stop the profiler at `COLLECTION
ENDED`: it still needs to export the RAM data.** No samples.jsonl on disk during
RAM collection is expected. Both programs stop by themselves. A rerun needs new
folder suffixes; previous evidence is never overwritten.

## Compare and transfer

On Pi (read-only comparison; nearest-rank p95, missing counters stay null):

```bash
cd ~/projects/edgexr
PYTHONPATH=src python3 -m profiling.compare_observer_storage \
  recordings/spatial-observer-file-01 recordings/spatial-observer-ram-01
cat recordings/kernel-observer-file-01/summary.json
cat recordings/kernel-observer-ram-01/summary.json
```

Mac:

```bash
mkdir -p /Users/ryanchoi/Desktop/edgexr-observer-ram
scp -r \
  pi@ai-fusion.local:/home/pi/projects/edgexr/recordings/spatial-observer-file-01 \
  pi@ai-fusion.local:/home/pi/projects/edgexr/recordings/spatial-observer-ram-01 \
  pi@ai-fusion.local:/home/pi/projects/edgexr/recordings/kernel-observer-file-01 \
  pi@ai-fusion.local:/home/pi/projects/edgexr/recordings/kernel-observer-ram-01 \
  /Users/ryanchoi/Desktop/edgexr-observer-ram/
```

## What makes this useful evidence?

Check collector/child/export status; no RAM overflow; queue accepted/written,
drops/high-water; IMU gaps and orientation readiness; trace loss/coverage and
post-trace export timing. Compare observer gaps, serialization/admission/write
tails, image writes, queue waits, observer CPU, preview CPU/RSS, observer RSS,
MemAvailable, temperature and swap. CPU uses one core = 100%; no electrical
energy measurement. Raw samples retain FFmpeg, system CPU and task accounting
for deeper analysis. The summary tool does not independently validate trace
events or image recognition. Memory counters are sampled, not true peak RSS.

If observer gaps shrink but app writes still stall, that supports separating
observer disturbance from app stalls. If both improve, shared-path interference
is plausible, not proven by one pair. If neither changes, do not call RAM a fix.
Thermal history, background I/O, manual views and storage state vary: repeat
B then A if needed before a causal claim. No new spatial feature is required.

Sources: [sample_sink.py](../src/profiling/sample_sink.py),
[collector](../src/profiling/spatial_stalls.py),
[comparison](../src/profiling/compare_observer_storage.py),
[configuration history](SYSTEMS_EXPERIMENTS.md).
