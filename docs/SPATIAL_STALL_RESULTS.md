# Spatial stall observation: spatial-stalls-01

2026-11-05 analysis of transferred metadata, 712 procfs samples, 180 scene
records and final recorder counters. [Machine-readable evidence](../benchmarks/results/spatial-stalls-01.json).
Private images and raw logs stay outside Git.

The user reports enrollment center, left, right; revisits with approximately
10-second holds; an unenrolled direction; then center until automatic completion.
The log identifies enrollment at about 7, 17 and 34 seconds after its first frame.
It recognizes center from 37 seconds, left from 53, right from 69, reports an
extended unknown interval from 91 to 109, then recognizes center through the end.
There are brief intermediate recognized labels during transitions: these are not
independently image-reviewed classifications. Do not claim 100% recognition accuracy.

## Application and systems evidence

- 180 accepted/written records, zero drops or pending records; queue high-water 1
  of 4 waiting slots. No scene error.
- 13,860 IMU polls, no gap above 200 ms, maximum midpoint gap 32.484 ms.
  179 scene rows have ready orientation; the first row is unknown during startup.
- Three views enrolled with ready orientation. Final view is center (View-1).
  Its estimated pointing separation is 4.841 degrees: continuity does not prove
  angular accuracy, exact physical return, or absence of drift.
- PNG median 15.654 ms but maximum 1,858.333 ms; JSON maximum 1,962.492 ms;
  maximum queue wait 979.431 ms. A complete recording is not stall-free recording.

## AP evidence and limits

Pi 4 / Linux 6.12.47 / Python 3.11.2 / OpenCV 4.11.0, revision 125a518;
requested 720p MJPEG30, detector off, scene 1 Hz at 640x360, IMU pause 10 ms,
two OpenCV threads, passive heatsink/no fan, power unknown. No separate warmup.
Tracked code was unchanged; two untracked benchmark summaries explain dirty status.

Observer CPU: 18.002 seconds over 184.362 wall seconds, approximately 9.76% of
one core (not the whole Pi). Its samples file is 48,360,943 bytes. This is material
instrumentation overhead and extra write traffic, not a free observer.
Preview sampled CPU median is 107.95% of one core; this is not the whole-pipeline
CPU total. Temperature median/max are 55.991/59.887 C; no energy measured.
Scene compute wall median is 135.492 ms versus scene-thread CPU median 124.982 ms.
Their difference is not a direct measurement of scheduler or GIL waiting.

The largest observer gap spans host 2527.383946–2529.361055 seconds. It overlaps
the app JSON write at 2527.399617–2529.362108. The preceding collection took only
25.737 ms and the observer used about 26.656 ms CPU between sample starts.
Most elapsed delay was therefore outside measured collection and not observer CPU
execution. Serialization, write blocking and delayed wake-up are not separately
timed in this profiler; storage contention is a hypothesis, not a proven cause.
Other long writer intervals overlap observer gaps too.

Scheduler statistics and task delay accounting are disabled (both settings 0).
Pressure interfaces are absent, and perf/trace-cmd/pidstat are not installed.
Do not interpret unavailable scheduling/I/O evidence as zero waiting.
The three HTTP failures occur at startup and shutdown, not mid-run.

## Decision and next bounded step

The earlier IMU failure did not recur; it is not diagnosed or declared fixed.
Recording tail delays remain, but the background writer successfully isolates
this run from dropped records and broken IMU continuity.

Next instrument the observer's serialization, log-write and sleep/wake intervals,
then repeat once with unchanged scene settings. This separates observer blindness
from app pauses before selecting deeper scheduler/storage tracing. Do not enable
kernel accounting, install tools or change policies silently. Kernel/BSP/driver
exercises remain explicit later milestones. Pipeline reviewed; unchanged because
this stage analyzes existing recordings, not a new application path.
