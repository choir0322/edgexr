# Kernel I/O and spatial workload: run 02

Reviewed 2026-11-06 from Desktop `kernel-io-02` and `spatial-io-02`.
Raw trace, samples and images remain outside Git.

## Configuration and validity

Pi 4, Linux 6.12.47+rpt-rpi-v8 aarch64, Python 3.11.2, commit
`d72e335b3bae86578eae5f153a27cc62a30d5458`. Passive metal heatsink, no fan;
power and ambient conditions unknown. Requested camera 1280x720 MJPEG 30 fps,
negotiation not measured. Three remembered views/revisits, fixed base;
10 ms IMU sleep, scene memory and images enabled, detector off.
No explicit benchmark warm-up. App requested 180 s; observer elapsed 184.453 s.
Private mono-clock trace covers 404.631–614.632 host seconds and encloses
the profiler's 412.232–596.685 interval.

Trace export completed without truncation (17,149,034 bytes); cleanup succeeded.
However CPU 0 overwrote 88,730 events. Its earliest retained event is at
569.923453 s; the other CPUs report zero overruns. Thus the early stall is only
partially covered. Late events after that boundary support local analysis;
whole-run event counts/rates and missing-event arguments are invalid.
`dropped events: 0` does not negate `overrun: 88730`.

## AP evidence

All 180 accepted scene records written; zero drops, queue high-water 2/4.
179/180 scene records have ready orientation; the first has no preceding
orientation within 200 ms during startup. No IMU midpoint gaps above 200 ms;
maximum 32.479 ms across 13,840 polls. This does not prove scene recognition
accuracy or camera exposure synchronization.

Observer CPU: 18.397 s over 184.453 s, about 10% of one core on average.
Largest observed sampling gap: 2.916 s. Largest buffered write: 2.870479 s
(451.091884–453.962363), with only 0.625906 ms process CPU during that write.
Maximum serialization wall time 8.062 ms and wake lateness 5.112 ms.
The long gap is therefore dominated by the write interval, not serialization.
Wall time includes descheduling; process CPU is not a direct I/O-wait measure.

Second observer write: 582.960914–585.174267, 2.213353 s;
scene image write overlaps at 583.140175–585.189649, 2.049474 s.
Largest scene JSON write: 81.363 ms. The background queue absorbed the delays
in this run while IMU polling continued. No new CPU optimization, electrical
energy, thermal comparison or tracing-overhead claim is established.

## Computer-systems evidence

In the retained late interval, pair MMC start/done by host plus request token,
consuming each start once; do not pair block events by sector alone.

- mmc0 request token `000000001ec7efce`, opcode 25, tag 21:
  582.367895–584.604139 s = 2.236244 s; 1032 x 512 bytes requested,
  528384 transferred, command/data/stop/SBC errors zero.
- Another mmc0 request, token `000000003fbfa516`, tag 19:
  580.091397–582.343355 s = 2.251958 s; 294912 bytes transferred,
  reported errors zero.
- JBD2 transaction 16486 on device 179,2: start 582.708296,
  end 585.182156 = 2.473860 s. It overlaps the later observer and image writes.
- In host interval 582–586, retained events include 305 block requeues.
  Requeues are not equivalent to 305 failed writes or lost data.
- Recorder TID 2409 was sampled in D state with `do_get_write_access`
  at 453.963, 557.152 and 567.161 s. These samples are not wait durations.

This supports storage-path latency concurrent with user-space write stalls.
It does not isolate SD-card firmware, controller, driver, journal dependencies,
or scheduler effects as the sole cause. A completion emitted in an ffmpeg task
context does not establish that FFmpeg issued the I/O.
No `jbd2_lock_buffer_stall` was retained; this is not proof of no journal wait.
The trace also includes substantial mmc1 traffic: keep it distinct from mmc0
storage and do not interpret all MMC events as SD-card file writes.

## Decision and next bounded experiment

Preserve the successful bounded writer and IMU scheduling. Next improve trace
retention by filtering MMC events to the verified storage host mmc0, retaining
block and filesystem events. Validate filter application and loss accounting
before another same-workload capture; protocol change remains proposed.
Then distinguish recorder latency from observer-generated storage contention
with a separately specified observer-output control. Do not replace hardware
or tune kernel writeback parameters based on this single partial trace.

Validation: parsed both JSONL streams and trace, checked capture overlap,
per-CPU loss, ready counts, write intervals and MMC start/done payloads.
Application code unchanged. Pipeline diagram and learning map unchanged:
this adds measurement evidence, not a new application data path.
