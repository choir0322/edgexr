# Profile the IMU pause and recording backlog

This is the first AP-led Linux investigation of v1's 879 ms IMU gap and 9.24 s
PNG write. `profiling.spatial_stalls` launches the detector-off spatial profile
and samples Linux procfs from a separate process. It changes no kernel, driver,
frequency or scheduling setting and issues no motor commands. The sensor gap
limit and recording queue remain unchanged so we can observe the same failure.

## What is measured

- Every 250 ms by default: preview and direct-child process/task `stat`,
  `status`, `schedstat`, `wchan` and `io`. CPU ticks, faults, context switches,
  sampled state and task IDs can be correlated with the application's workers.
- Approximately once a second: local telemetry with a 150 ms timeout, host CPU,
  memory/VM/disk counters, CPU/I/O/memory pressure, CPU0 frequency and temperature.
- Native thread IDs in `/api/telemetry` map `imu-poll`, `scene-worker`,
  `scene-recorder`, `camera-capture`, `motion-worker` and `ffmpeg-log` to Linux
  tasks. Native library threads may have no Python role name.
- Exact preview command, revision and Git status; readable kernel accounting
  settings and tool availability. Observer process CPU seconds, sample gaps and
  collection durations are recorded. Raw task counters are cumulative.

`schedstat` is runtime ns, runnable-wait ns and timeslices. A runnable-wait delta
suggests scheduling competition; it does not measure time asleep on a lock or
the GIL. Disabled/unsupported counters can be zero; read errors stay explicit.
`wchan` and state are instant samples. They cannot reconstruct a complete
schedule or prove why a thread stopped progressing. Process I/O counters and
host disk activity are not proof of a particular disk fault. The profiler's
own polling and JSON writes add CPU/I/O and may change the workload.

References: [Linux 6.12 scheduler statistics](https://www.kernel.org/doc/html/v6.12/scheduler/sched-stats.html),
[procfs interfaces](https://www.kernel.org/doc/html/latest/filesystems/proc.html).
We inspect these interfaces before deciding whether detailed scheduler tracing
or a driver/kernel change is warranted. No hard real-time or energy claim.

## Run on Pi

Stop the old preview with Ctrl+C first. Remove the lens cap; use the verified
camera device and existing IMU mount. This command launches the preview too;
do not start a second preview. Keep the head still through startup calibration.

```bash
cd ~/projects/edgexr
git pull --ff-only
PYTHONPATH=src python3 -m profiling.spatial_stalls \
  --device /dev/video0 \
  --output recordings/spatial-stalls-01 \
  --seconds 180 --interval 0.25 \
  --scene "three remembered views and revisits; fixed base" \
  --power "unknown" --cooling "passive metal heatsink; no fan"
```

Describe actual power/cooling if different. Use a new `spatial-stalls-02` folder
on repeat; preserve earlier evidence and the two untracked benchmark summaries.
The app runs 180 seconds after server startup and then drains its recorder.
The observer allows startup/shutdown time and sends Ctrl+C to its owned preview
if its 220-second watchdog expires; a further 10-second grace precedes forced
termination. Slow OS I/O can delay the observer itself; this is not a real-time
termination guarantee. Ctrl+C stops the collector and its owned preview.
If startup fails, inspect `recordings/spatial-stalls-01/preview.log`.

## Mac browser and demonstration

Reuse a working tunnel, or start and leave this running:

```bash
ssh -N -o ExitOnForwardFailure=yes \
  -L 127.0.0.1:8766:127.0.0.1:8765 pi@ai-fusion.local
```

In a second Mac terminal:

```bash
open http://127.0.0.1:8766
```

Use the v1 sequence: once ready remember center, left, right; revisit center →
left → right → center without enrolling again. Hold each view about 8–10 s,
show a distinct unenrolled view, return to center and hold until the timer ends.
Use the existing safe view-changing method; do not force powered servo gears.
Record the actual sequence; precise timing is unnecessary. Do not restart just
because orientation becomes unknown: this is the event we want to capture.

## Collect and interpret

After the timer, on the Pi:

```bash
cat recordings/spatial-stalls-01/summary.json
```

On the Mac:

```bash
scp -r pi@ai-fusion.local:/home/pi/projects/edgexr/recordings/spatial-stalls-01 \
  /Users/ryanchoi/Desktop/
```

Files: `metadata.json` (observer provenance), `samples.jsonl` (raw host/task
samples), `preview.log` (app output), `summary.json` (collector outcome/overhead),
and `scene/` (existing image-backed scene evidence and final recorder counters).
Keep all images/logs outside Git. All event comparisons use the same Pi host
monotonic clock; file writes and HTTP polls are sequential observations, not
camera exposure timing. Up to 256 tasks per process are recorded with an explicit
truncation flag. A telemetry timeout never reuses a previous snapshot.

`child_exited` means the launched app exited; it is not an acceptance verdict.
Check its return code, scene error, recording status and IMU gap evidence.
Expected startup/shutdown HTTP failures are counted and timestamped. An app can
exit normally with partial recording or unknown orientation. Do not rerun or
relax thresholds to hide it. If no stall occurs, retain the run as a measured
observation; absence on one run is not a root-cause finding.

Next analysis: map IMU TID, compare CPU and runnable-wait deltas around each
gap, inspect contemporaneous scene/writer intervals and disk/pressure activity,
and assess observer delays. Only then select a focused scheduler/runtime/I/O
trace or optimization. Hardware-counter profiling and low-level kernel/BSP/
driver exercises follow with measured hypotheses and recoverable procedures.
