# Stationary recording A/B findings — 2026-11-02

Inputs: user-transferred `scheduling-no-images-01` (A) and `scheduling-images-01`
(B), JSONL and final timing counters. Same Pi commit e9a032b (dirty reported),
Python 3.11.2, OpenCV 4.11.0/two threads, detection off, 10 ms IMU sleep,
same camera-axis basis and scene thresholds. User followed the stationary
protocol. A has no images to independently verify identical scenery.
Enrollments occurred 3.59/3.99 s after the first logged frame. One reference
per run. Requested duration was 120 s each; reported spans below are between
first and last processed source frames, not complete process lifetimes.

| Metric | A: JSON only | B: JSON + PNG |
|---|---:|---:|
| Scene observations | 120 | 108 |
| Observed source span | 119.64 s | 118.67 s |
| Scene update rate | 0.995 Hz | 0.902 Hz |
| Post-enrollment known / unknown | 116 / 0 | 103 / 0 |
| Scene wall compute median / p95 | 116.15 / 126.04 ms | 118.14 / 127.57 ms |
| Scene wall compute maximum | 150.73 ms | 130.66 ms |
| Scene-thread CPU median | 105.81 ms | 106.96 ms |
| App-process CPU during scene compute, median | 189.41 ms | 190.59 ms |
| JSON serialization/write/flush median / max | 0.54 / 1512.46 ms | 0.50 / 2231.62 ms |
| Image resize/encode/write median / p95 / max | not enabled | 14.34 / 22.96 / 5201.55 ms |
| IMU polls | 9,263 | 9,272 |
| Maximum IMU midpoint gap | 31.96 ms | 34.92 ms |
| IMU gaps over 200 ms | 0 | 0 |
| First stale observation | none | none |

P95 uses nearest rank. Process CPU includes all app threads in the measured
interval; it can exceed wall time and is not scene-only CPU. FFmpeg child CPU
is excluded. No full-process CPU utilization, memory, temperature, power,
storage-health or kernel scheduling trace was collected.

## Demonstrated cause of scene delay

Four image-saving intervals in B lasted approximately 5.202, 3.863, 2.465 and
2.245 s; the following source-frame gaps were 5.321, 3.959, 2.565 and 2.356 s.
The synchronous code finishes image writing before selecting the next frame,
so these operations directly block scene progress. Another B gap coincides
with its 2.232 s JSON operation. A also had a 1.512 s JSON operation.
Thus the issue is not exclusively PNG compression: JSON recording can stall
too. The measurements include wall delay inside serialization/encoding/write
operations; they do **not** identify an SD-card fault, OS writeback, GIL delay,
or another particular underlying mechanism.

## What was not reproduced

Neither run lost IMU continuity. After the first startup-unknown frame, all
logged orientation contexts were ready (119 in A, 107 in B). B had one driver
read taking 23.33 ms, still far below the orientation gap limit. Maximum late
wake was 15.74/17.96 ms and publication was 3.77/3.68 ms respectively.
The final cumulative counters cover polling during the scene stalls as well:
no >200 ms midpoint gaps, and no stale observer event. Therefore recording
stalls in these trials did **not** reproduce the prior IMU failure. Ready is
still not a statement of orientation accuracy. The older failure remains open.

## Decision and limits

Keep thresholds and polling interval unchanged. Before changing scheduling,
repeat in reverse order (B then A), as specified by the diagnostic plan; this
checks repeatability/order effects rather than repeatedly testing recognition.
The evidenced design risk is synchronous optional recording on the scene
worker. The candidate remedy is a separate bounded recorder handling **both**
PNG and JSON writes, with explicit drop counts and reference-image protection.
Do not add an unbounded queue or silently omit diagnostic evidence. A writer
thread cannot guarantee removal of CPU/GIL/storage contention, and must be
verified under injected slow writes and on the Pi. No code changes in this
analysis. No claim of solving the separate IMU problem or improving performance.

Both runs are a single A→B pair, with dirty working trees and unrecorded
power/cooling/thermal conditions. Raw logs/images stay outside Git. See the
[small result record](../benchmarks/results/scheduling-ab-2026-11-02.json).
