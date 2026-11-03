# From the earlier walkthrough to a bounded spatial application

Updated 2026-11-04. Companion to [the expandable HTML walkthrough](program-flow-explorer.html).
The original graph data last changed on 2026-10-23; this update covers the
subsequent spatial work through direction-consistency-01. All new teaching files
are under `docs/learning/`; no private captures were copied into Git or a website.
The HTML remains a local explanation, not a connection to the Pi.

## What was added, in order

| Stage | What changes in the data | Exact implementation | Evidence / limit |
|---|---|---|---|
| Recorded relative orientation | Timestamped gyro rates → integrated unit quaternion | [relative_orientation.py](../../src/spatial/relative_orientation.py) | Gyro-only rotation, not position; bias and gaps matter |
| Polling/resource experiments | Fixed 50 ms, fixed 10 ms, command-driven polling | [servo_motion_quality.py](../../src/recording/servo_motion_quality.py), [results](../../benchmarks/results/imu-resource-three-policy-2026-10-24.json) | Fewer reads did not establish recorder CPU savings; don't attribute the cause without isolation |
| Camera-axis mapping | IMU XYZ rates → camera XYZ rates via fitted basis | [camera_axes.py](../../src/spatial/camera_axes.py), [basis](../../configs/camera_axes_neutral.json) | Camera X right, Y down, Z forward; direction fit is not shaft-angle calibration |
| Conversion-cost checks | Isolated cost, then full live A/B | [camera_axis_cost.py](../../src/profiling/camera_axis_cost.py), [A/B](../../benchmarks/results/camera-axis-live-ab-2026-10-25.md) | About 28 µs/conversion; no clear live throughput penalty, not proof of zero cost |
| Live bounded orientation | Adjacent corrected rates + dt → incremental rotation → quaternion | [live_orientation.py](../../src/spatial/live_orientation.py), [live_reader.py](../../src/imu/live_reader.py) | Startup reference, gap/stale rejection, no visual drift correction |
| Automated return evidence | Safe pan/tilt commands + HTTP telemetry + checkpoint images | [servo_orientation_demo.py](../../src/spatial/servo_orientation_demo.py), [polling comparison](../LIVE_IMU_POLLING_AB.md) | 10 ms pause improved observed return behavior; requested sleep is not achieved sample period |
| Offline scene memory | Gray image → ORB keypoints/descriptors → verified candidate | [scene_memory.py](../../src/spatial/scene_memory.py), [held-out result](../../benchmarks/results/scene-revisit-heldout-2026-10-29.json) | Explicit references, bounded LRU, unknown on insufficient/ambiguous evidence; not person re-ID |
| Live recognition and timed context | Latest full frame + preceding gyro context → independent scene result | [live_scene.py](../../src/spatial/live_scene.py), [three-view result](../../benchmarks/results/live-scene-three-01-2026-11-02.json) | Target 1 Hz; ≤200 ms preceding orientation context, not exposure synchronization |
| Stall diagnostics | Thread/process timing, I2C gaps, PNG/JSON durations | [live_scene.py](../../src/spatial/live_scene.py), [A/B](../../benchmarks/results/scheduling-ab-2026-11-02.json), [reverse order](../../benchmarks/results/scheduling-ba-2026-11-03.json) | Observed disk-write stalls; not a proven OS-level root cause for all timing issues |
| Bounded background recording | Nonblocking submission → bounded FIFO → writer | [scene_recorder.py](../../src/spatial/scene_recorder.py), [result](../../benchmarks/results/scheduling-background-2026-11-03.json) | Four waiting + one active, drop query evidence on full, defer enrollment, explicit drain/error counters |
| Session View Map | Scene labels + immutable enrollment orientations → viewing rays/history | [view_map.py](../../src/spatial/view_map.py), [result](../../benchmarks/results/view-map-2026-11-04.json) | 12 nodes / 132 links maximum; reset at restart. Edges are label transitions, not physical paths |
| Bounded direction check | Four settled images + local quaternion comparisons | [checkpoint_summary](../../src/spatial/servo_orientation_demo.py), [review](../DIRECTION_CONSISTENCY_RESULTS.md) | Still 1.12°, pan 0.15°, combined 1.04°; final tilt image differs by ~9 px. No precise angle claim |

## Read the graph without conflating the branches

The camera sends compressed MJPEG. FFmpeg decodes to gray. When **either**
detection or scene memory is enabled, Python receives 1280×720 gray and OpenCV
makes the 320×180 motion copy. Detection independently makes its 300×300 model
input; scene memory independently uses 640×360 ORB. Otherwise FFmpeg can supply
the small motion frame directly. Newest-slot replacement avoids a growing queue
of stale work, but does not cancel a job already running.

IMU reads are a separate physical input. Corrected rates may be converted to camera
axes and integrated. A quaternion has four rotation components, not XYZ position
plus time. The scene input carries preceding host-timed orientation from bounded
history. ORB recognition does not wait for a valid angle: it can recognize a view
while angular context is unknown. The gyro is not currently corrected by images.

Expand the scene branch: select source → ORB → geometric verification →
known/enrolled/unknown → view map → enqueue evidence/publish result. The actual
PNG/JSON writes run independently after admission, not as a blocking final
recognition step. Browser snapshots collect independently aged results; they
do not synchronize exposure, gyro and detector timestamps.

The saved forward ray is expressed in the current camera frame. Look left and
the remembered center lies right; look up and it lies below. Separation is the
unsigned angle between forward rays. A→B means the recognized label changed;
overlap/flicker can produce a link without movement. None of these quantities
give meters, world coordinates or a route through the room.

## The strongest computer-systems / AP story

The project is already systems work—not merely choosing an AI model.

| Systems area | What this project demonstrates | Evidence and next measurement |
|---|---|---|
| Heterogeneous workloads on a shared CPU | FFmpeg child process, Python workers, NumPy FFT, OpenCV native work, I2C and HTTP compete for resources | [historical AP baseline](../../benchmarks/results/ap-baseline-basic-2026-10-18.md); collect a new exact spatial-workload baseline before optimization |
| Scheduling and admission policy | Different cadences, newest-frame slots, optional adaptive IMU polling | [polling trial](../../benchmarks/results/imu-resource-three-policy-2026-10-24.json); compare useful quality/resource outcomes, not read counts alone |
| Backpressure and latency isolation | A bounded writer queue keeps storage delay off the recognition path | [background result](../../benchmarks/results/scheduling-background-2026-11-03.json): recognition continued during a 1.335 s PNG write, 120 records, zero drops |
| Memory/data movement | Full gray frame 921,600 bytes versus small copy 57,600 bytes; bounded descriptors/history/queues | Trace copies, buffers and RSS; 16× payload ratio is not a measured 16× CPU penalty or zero-copy design |
| Timing and observability | Monotonic clocks, source ages, service time, sample gaps, wall/thread/process CPU scopes | Existing telemetry distinguishes these; no hardware timestamp synchronization or glass-to-glass latency measurement |
| Resource–quality tradeoffs | Faster reads versus drift; resize/model/cadence choices versus recognition quality | Use image-confirmed behavior and missed/false recognition alongside CPU/latency/temperature |
| Experimental method | Fixed workloads, reverse-order trials, repeatable commands, provenance, failure limits | Isolated conversion microbenchmark + live A/B avoids treating microbenchmarks as application results |
| Reliability and bounded state | Unknown/stale states, LRU eviction, reference epochs, recording loss counters and bounded shutdown | Unit tests plus Pi evidence; a failed/old sensor is never represented as a valid zero |

An accurate portfolio description is: **“Built and instrumented a concurrent
camera–IMU spatial-perception workload on Raspberry Pi 4; implemented bounded
state and asynchronous evidence recording, and measured quality/resource tradeoffs.”**
The strongest concrete before/after story is moving blocking evidence I/O off
the scene worker while bounding backlog and exposing loss. Avoid claiming an
NPU implementation, kernel/driver development, hard real-time guarantees, proven
power savings, full SLAM or precision tracking. Those have not been demonstrated.

## Next step: close the bounded application, then freeze the AP workload

Do **not** add room positioning, depth, cross-session map persistence or more
identity tuning by default. The original fixed-base, session-local target is
substantially implemented. Next prepare a reproducible application handoff:
one launch configuration, a compact acceptance checklist using existing evidence,
known limitations (especially long-session drift), and the precise feature set
that will define the first spatial AP benchmark. Only address a remaining actual
functional blocker; do not reopen the completed direction test.

Then measure the unchanged spatial profile (camera + motion + IMU/orientation +
scene memory) with recording explicitly on/off, and treat detector-enabled load
as a separate optional profile. CPU/RSS, median/tail timing, useful rates, skipped
work, recorder loss, temperature and quality belong together. Choose one bottleneck
from that baseline before changing thread count, cadence, resize or runtime.
This is the proposed next milestone, not a benchmark already run or a claim that
angular accuracy has been validated.
