# Capture the kernel I/O path during spatial recording

This experiment follows [spatial-stalls-02](SPATIAL_STALL_RESULTS_02.md): the
observer's longest gap was dominated by its own log write, and the scene writer
was sampled waiting in `do_get_write_access` / `__lock_buffer` during long PNG
writes. The question is where journal, block and MMC activity occur relative
to these intervals. Correlation alone does not establish a failing SD card.

## Verified target and collection scope

Pi 4, Linux 6.12.47+rpt-rpi-v8 aarch64; recordings on ext4 `/dev/mmcblk0p2`,
root storage on `mmcblk0`. User inventory reports 86 GB available (24% used),
tracefs/debugfs mounted, root current_tracer `nop`, root tracing_on `1`.
`nop` is a tracer selection; it does not prove all root trace events are off.

`profiling.kernel_io_trace` uses existing Python and ftrace, requiring root only
for a separate trace helper. It creates a unique instance beneath
`/sys/kernel/tracing/instances/edgexr-io-*`. Its controls and ring are private;
the root tracer/event configuration and other instances are never written.
It removes only that newly owned instance on normal exit/error/Ctrl+C/SIGTERM.
SIGKILL or power loss prevents cleanup; if needed, report the printed instance
path rather than deleting other trace instances.

The selected event set contains request insert/issue/complete/requeue; MMC start
and completion; JBD2 buffer stalls and commit stages; ext4 write begin/end and
writepages; dirty-page balancing. Exact event names/layouts are saved in metadata.
The supplied inventory supports all 18 requested events. Missing optional events
are recorded; missing core block issue/complete or journal stall events aborts.

Capture is system-wide for those events: kernel workers and interrupt completions
would be lost by filtering only the Python PID. Device and task fields must be
inspected during analysis; unrelated root-filesystem traffic is also included.
Event presence does not guarantee an event fires during the trial.

## Memory, clocks and loss

The helper requests 2 MiB per exposed CPU buffer (about 8 MiB on the four-core Pi),
checks the total, and refuses this profile above a 32 MiB ring allocation.
The instance uses `mono`, aligned with the host monotonic clock in app logs.
Enable/disable host brackets and a start marker preserve collection boundaries.
Trace timestamps still do not synchronize camera exposures.

No trace log is streamed to storage while tracing runs. After stopping, it saves
the static text trace with a 64 MiB export cap, per-CPU raw statistics and loss
counters, and the root tracer state before/after. The kernel ring can overwrite
or drop events under load; loss accounting and exported coverage must be checked
before matching durations. A clipped export or missing/nonzero loss counters
produces a nonzero exit with evidence retained. `status=complete` describes the
timed collection; inspect loss and export fields as well.

No scheduler statistics/sysctls, mount options or trace_options are changed.
Kernel event collection itself adds CPU/memory overhead even without live disk
logging. Setup and final export also do I/O. This is a diagnostic workload,
not an uninstrumented performance baseline. Timer and cleanup can be delayed by
OS I/O; no hard deadline guarantee. Block requests may merge, split, requeue or
complete partially: do not blindly pair sector numbers as unique request IDs.

## Run: prepare two Pi terminals and the Mac preview

Stop any previous preview. Open both SSH terminals before starting, and remove
the lens cap. No automatic servo commands are issued.

Pi terminal 1: pull, then start the 210-second trace:

```bash
cd ~/projects/edgexr
git pull --ff-only
sudo env PYTHONPATH=src python3 -m profiling.kernel_io_trace \
  --output recordings/kernel-io-01 --seconds 210
```

Once `TRACING` appears, start this in Pi terminal 2 within about 15 seconds:

```bash
cd ~/projects/edgexr
PYTHONPATH=src python3 -m profiling.spatial_stalls \
  --device /dev/video0 \
  --output recordings/spatial-io-01 \
  --seconds 180 --interval 0.25 \
  --scene "three remembered views and revisits; fixed base; kernel I/O tracing" \
  --power "unknown" --cooling "passive metal heatsink; no fan"
```

The app stays under the normal Pi user; the root helper never launches it.
Hold the rig still for the first 10 seconds and check that IMU/orientation is
ready before view changes. Enroll center/left/right; revisit each with 10-second
holds; show an unenrolled direction for 10 seconds; return to center until the
app finishes. Keep people/arms away from remembered views where practical.
If startup calibration fails, retain/report it; raw I/O evidence can still help,
but that run does not represent the full orientation workload. Do not silently
relax calibration. Both commands stop automatically; let trace terminal 1 finish
after app terminal 2. Starting the app late can leave its tail outside the trace;
preserve timestamps and report that rather than assuming complete overlap.

On the Mac, reuse an existing tunnel or run:

```bash
ssh -N -o ExitOnForwardFailure=yes \
  -L 127.0.0.1:8766:127.0.0.1:8765 pi@ai-fusion.local
```

In another Mac terminal:

```bash
open http://127.0.0.1:8766
```

## Finish and transfer

After both commands finish, on the Pi:

```bash
cat recordings/kernel-io-01/summary.json
cat recordings/spatial-io-01/summary.json
```

On the Mac:

```bash
scp -r \
  pi@ai-fusion.local:/home/pi/projects/edgexr/recordings/kernel-io-01 \
  pi@ai-fusion.local:/home/pi/projects/edgexr/recordings/spatial-io-01 \
  /Users/ryanchoi/Desktop/
```

The helper returns ownership of its newly created files to the invoking sudo
user so this SCP needs no broad chown command. Use new `-02` output folders for
any repeat; previous folders are never overwritten. Trace output can contain
process names and filesystem metadata: keep the raw capture outside Git.

## Analysis and acceptance

First verify stop/export/cleanup, per-CPU loss counters, selected event formats,
clock, coverage of the app interval, initial IMU health and final recording
counts. Compare app and observer write windows to journal stall/commit events,
request issue/completion and MMC activity, retaining device/task identity.
Events can narrow the wait to journal/buffer, writeback or device activity;
they do not inherently assign every block request to an individual Python file
write. If no long write occurs, retain that outcome without claiming a fix.

The source is [kernel_io_trace.py](../src/profiling/kernel_io_trace.py);
hardware-free fixtures cover private-instance configuration, failure cleanup,
supported events, export caps and missing/lost-event accounting. Actual tracefs
behavior remains a Pi check. No model, driver or kernel installation is needed.

Primary interface references:
[Linux 6.12 ftrace](https://www.kernel.org/doc/html/v6.12/trace/ftrace.html)
(instances, clocks, buffers and statistics) and
[event tracing](https://www.kernel.org/doc/html/v6.12/trace/events.html)
(event enable controls and field formats).
