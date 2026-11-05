# Separated observer timing: spatial-stalls-02

2026-11-06 review of the transferred metadata, 741 observer samples/cycles,
180 scene records/images, final timing counters and preview output.
[Structured evidence](../benchmarks/results/spatial-stalls-02.json).
Raw logs and private images remain outside Git. The user reports an arm entering
the rightmost remembered view; associated recognition changes are excluded from
this timing investigation. Recognition accuracy was not scored.

## Result and comparison

The largest observer gap is explained at the operation level: a buffered log
write took 714.929 ms within a 740.461 ms sample interval. That cycle's
serialization took 2.601 ms, observer write CPU took 0.435 ms, and sleep/wake
lateness was 0.101 ms. The observer spent little CPU in the long write call.
This localizes the interval to the write phase; it does not identify every
kernel or device event occurring inside that interval.

| Metric | Run 01 | Run 02 |
| --- | ---: | ---: |
| Largest observer sample gap | 1,977.109 ms | 740.461 ms |
| Largest app image write | 1,858.333 ms | 3,611.540 ms |
| Largest app JSON write | 1,962.492 ms | 6.341 ms |
| Largest app recording queue wait | 979.431 ms | 2,621.396 ms |
| Waiting-queue high-water / capacity | 1 / 4 | 3 / 4 |
| Saved / dropped records | 180 / 0 | 180 / 0 |
| Largest raw IMU midpoint gap | 32.484 ms | 31.038 ms |
| Scene rows with ready orientation | 179 / 180 | 0 / 180 |
| Observer CPU / elapsed seconds | 18.002 / 184.362 | 18.929 / 186.095 |

These are two observations, not an improvement claim. Run 02's startup gyro
stability check failed, so camera-axis conversion and orientation integration
were unavailable. CPU/temperature changes cannot be attributed to instrumentation
alone. Scene enrollment, views and CPU work also vary across these human-run trials.

## AP measurements

Pi 4, Linux 6.12.47+rpt-rpi-v8 aarch64, Python 3.11.2, OpenCV 4.11.0,
revision 21cdff5. Requested 720p MJPEG30, scene 1 Hz/640x360 PNG, detector off,
10 ms IMU pause, two OpenCV threads, passive heatsink/no fan, power unknown.
No separate warmup; negotiated camera mode not measured. Git status contains
the same two untracked benchmark summaries; tracked changes are absent.

All 741 cycle indices (0–740) are present exactly once, including the final
cycle from summary. Serialize wall median/p95/max: 2.101/5.034/8.049 ms.
Buffered-write wall median/p95/max: 0.271/0.562/714.929 ms. Only two writes
exceed 100 ms (308.553 and 714.929 ms). Maximum wake lateness across all cycles
is 4.690 ms. Percentiles use nearest rank, ceil(0.95*n).

Observer CPU is 18.929 s over 186.095 s, averaging 10.172% of one core.
The diagnostic samples file is 50,147,252 bytes. This overhead and extra writes
remain part of the experiment. Preview sampled CPU median is 107.917% of one
core; temperature median/max is 51.121/53.556 C. These do not measure total
pipeline CPU or electrical energy, and startup failure changes the workload.

## Kernel and application evidence

The two long observer writes overlap application image writes:

- Observer host 409.903753–410.212307, app image 409.787938–410.230954.
- Observer host 476.841665–477.556594, app image 476.815909–477.574448.

At sampled instants during both app writes, the named `scene-recorder` thread
(native TID 1893) reports state `D` and wait channel `do_get_write_access`.
During the longest app image write, host 548.846677–552.458217, 15 successive
samples report `D` / `__lock_buffer`. This is direct sampled evidence of kernel
waiting in the recording path, beyond merely observing a long image function.
It does not prove the exact backing device fault, mount type, continuous wait
between samples, or why a particular buffer was unavailable.

The observer continues sampling at roughly 250 ms through the 3.61-second app
write. Application stalls can therefore exceed observer stalls. The bounded
writer queue absorbed this interval: high-water 3 waiting, zero drops, all 180
records and corresponding images present at completion.

Scheduler/delay accounting remains disabled, pressure interfaces absent, and
perf/trace-cmd/pidstat unavailable. The four HTTP errors occur at startup and
shutdown. No mid-run HTTP failure was recorded.

## Separate startup orientation failure

The first error telemetry reports `Initial gyro varied too much; keep rig still
and restart preview`, with null offset, zero camera-axis conversions and zero
integrated intervals. `LiveImu.publish` retains a rejected initial baseline;
it continues storing raw samples but does not start corrected-rate integration.
All 179 post-startup scene records consequently report unknown / IMU error.
14,063 raw polls still completed, with zero gaps above 200 ms.

The `first_stale_observation` field records status `error`, with sample age
6.252 ms. Despite the field name, this is not evidence of an old IMU sample.
The logs do not preserve the rejected baseline spread, so motion, vibration and
sensor variation cannot be distinguished here. The user's arm note concerns
the later right-view recognition; it does not establish this startup cause.

## Decision and next step

The requested observer-phase question is answered: this run's largest sampling
gap is dominated by the observer's write call, not serialization or oversleep.
The earlier 879 ms raw IMU failure still has no demonstrated cause or fix.

Next inspect the mount and backing device for `recordings/`, then select a
bounded filesystem/block-I/O trace using the Pi's available kernel interfaces.
This directly advances low-level AP/systems learning and can identify the waits
behind these buffer/write-access samples. Do not repeat the same broad capture
merely to collect another maximum, or infer that more CPU threads fix this wait.
Any tracing configuration changes need a documented procedure and overhead scope.
Check that initial IMU status is ready before a later full-workload comparison.

Read-only inventory on the Pi (no preview required):

```bash
cd ~/projects/edgexr
findmnt -T recordings -o TARGET,SOURCE,FSTYPE,OPTIONS
lsblk -o NAME,TYPE,FSTYPE,SIZE,MOUNTPOINTS
findmnt -t tracefs,debugfs
```

An empty last command only means those tracing filesystems are not currently
listed as mounts. Keep device and filesystem identities with the next trace;
this inventory installs nothing and changes no mount or kernel setting.

### Confirmed target inventory — 2026-11-06

User-provided Pi output resolves `recordings/` to `/`, source `/dev/mmcblk0p2`,
ext4 with `rw,noatime`. Its parent is `mmcblk0` (119.3 GiB as displayed by lsblk),
with a 512 MiB vfat firmware partition and 118.7 GiB ext4 root partition.
Both `/sys/kernel/tracing` (tracefs) and `/sys/kernel/debug` (debugfs) are mounted.
Application and observer evidence share the root storage device. This does not
identify media make, health, service latency or the cause of buffer waiting.

Next read available event names and current tracer state before choosing a
small event set. This does not start tracing:

```bash
sudo grep -E '^(block|ext4|jbd2|writeback|mmc):' \
  /sys/kernel/tracing/available_events
sudo cat /sys/kernel/tracing/current_tracer \
  /sys/kernel/tracing/tracing_on
df -h recordings
```

Current tracer state records existing tracing activity; later collection should
use its own trace instance and retain buffer-loss statistics. The planned trace
will distinguish filesystem/journal waiting from block-request delays where
supported, use bounded kernel memory buffers and avoid streaming trace output
to the recording device during measurement. Event availability and tracing
overhead must be checked on this kernel before claiming that distinction.

Pipeline and learning source map reviewed; unchanged because this is analysis
of existing paths, with no runtime modification or new inference connection.
