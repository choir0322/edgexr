# EdgeXR technique and AP evidence register

2026-11-06 — **Measured: kernel I/O run 02; trace partially overwritten.**
[Review](KERNEL_IO_RESULTS_02.md), [summary](../benchmarks/results/kernel-io-02.json).
All 180 scene records saved, no IMU gaps above 200 ms; observer write 2.870 s,
image write 2.049 s. Retained late MMC request 2.236 s overlaps journal and
user-space writes. CPU 0 overwrote 88,730 events; no sole-cause attribution.
Next propose storage-host filtering for trace retention before kernel tuning.
Pipeline diagram reviewed; unchanged because this is evidence-only work.

2026-11-06 — **Implemented; Pi check pending: private kernel I/O trace.**
[Source](../src/profiling/kernel_io_trace.py), [protocol](KERNEL_IO_TRACE.md),
[tests](../tests/unit/test_kernel_io_trace.py), [plan](exec-plans/active/spatial-stall-profiling.md).
User inventory confirms ext4/JBD2/block/MMC events, including buffer-stall event;
root nop/tracing_on=1 and 86 GB free. Separate root helper requests 2 MiB/CPU
private ring (32 MiB total limit), mono clock, 210 seconds, stopped export capped
64 MiB. Retains formats, loss/cleanup and root-state observations. Normal-user
app workload remains separate. AP question: correlate file-write tails with
journal/buffer and storage activity. Kernel tracing overhead not yet measured;
no diagnosis or Pi runtime pass claimed. Pipeline/source map updated.

2026-11-06 — **Observed: recording storage and tracing mounts.**
[Inventory and next command](SPATIAL_STALL_RESULTS_02.md#confirmed-target-inventory--2026-11-06).
User confirms recordings on ext4 /dev/mmcblk0p2 (root), parent mmcblk0;
tracefs and debugfs mounted. App and profiler share storage. Media health and
device latency unknown. Next inspect kernel event availability; no trace enabled
or filesystem setting changed. Application pipeline unchanged.

2026-11-06 — **Measured: observer phase attribution and kernel recording waits.**
[Review](SPATIAL_STALL_RESULTS_02.md), [summary](../benchmarks/results/spatial-stalls-02.json).
Observer 740.461 ms sample gap includes 714.929 ms buffered write; serialization
2.601 ms and wake lateness 0.101 ms in that cycle. App PNG max 3.612 s, recorder
sampled D/__lock_buffer; 180 written, zero dropped, queue high-water 3/4.
Raw IMU has no >200 ms gaps, but initial gyro check failed and orientation stays
unknown. No direct CPU comparison or orientation acceptance claim. Arm entering
rightmost view excluded from recognition diagnosis. Next inspect mount/backing
device and select bounded filesystem/block tracing. Pipeline/source guide reviewed;
unchanged because this stage adds evidence only.

2026-11-06 — **Implemented; repeat measurement pending: observer phase timing.**
[Source](../src/profiling/spatial_stalls.py), [protocol](SPATIAL_STALL_PROFILING.md).
Schema 2 separates serialization/write wall and CPU, work overrun, sleep and
wake lateness; retains final-cycle timing. Same application workload and buffered
I/O policy. AP question: which observer phase hides events during sampling gaps?
Fake-clock tests cover normal sleep, write overrun and write failure. No new Pi
performance claim. Pipeline and learning guide reviewed/updated.

2026-11-05 — **Measured: first Linux spatial-stall capture.**
[Results](SPATIAL_STALL_RESULTS.md), [summary](../benchmarks/results/spatial-stalls-01.json).
180 records, no drops; no IMU gaps above 200 ms. Writer tails still approach
two seconds and overlap observer gaps. Observer costs 18.002 CPU seconds in
184.362 wall seconds; scheduler-delay accounting disabled. No causal finding.
Next distinguish observer write/wake delays before deeper Linux tracing.

2026-11-05 — **Implemented; Pi measurement pending: spatial stall profiler.**
[Source](../src/profiling/spatial_stalls.py), [protocol](SPATIAL_STALL_PROFILING.md),
[plan](exec-plans/active/spatial-stall-profiling.md), [source guide](learning/SCENE_MEMORY.md).
AP question: CPU execution, runnable waiting and I/O activity around IMU lateness
and image-write backlog. Standard-library observer launches the timed spatial
profile and reads per-task procfs counters, host pressure/frequency/temperature
and existing telemetry. New worker names/native IDs identify Linux tasks.
No scheduler/sysctl/driver changes. Observer CPU and collection/sample delays
are recorded; extra I/O is a confound. Hardware counter/energy measurements are
not yet made. Low-level kernel/BSP/driver practice is explicitly added to the
AP roadmap. Pipeline/source guide updated; Pi diagnosis remains pending.

2026-11-05 — **AP-first priority clarified; semantic extension planned.**
[Decision](decisions/2026-11-05-ap-first-priority.md),
[AP-led sequence](SYSTEMS_AND_AP_EXTENSIONS.md),
[semantic plan](exec-plans/active/semantic-spatial-memory.md). AP profiling of
current stalls takes precedence; systems work supports the processor question.
Planned semantic observations for furniture and same-source person feature masks
are class priors, not motion/position ground truth. Proposed S0–S3 comparisons
isolate inference, metadata and masking cost/quality. Implementation/measurements
pending. Pi follow-up shows two untracked benchmark summaries, no tracked diff;
preserve historical dirty flag without implying modified application code.
Pipeline/source guide reviewed; unchanged because no runtime path was added.

2026-11-05 — **Pi run reviewed; acceptance needs investigation: Spatial v1.**
[Review](SPATIAL_V1_ACCEPTANCE_RESULTS.md),
[structured result](../benchmarks/results/spatial-v1-acceptance-2026-11-05.json).
172 saved decisions/images, three enrollments, four map links; partial recorder
with eight query drops. One 878.9 ms IMU gap invalidates subsequent orientation.
Ready/unknown contexts 14/158; fail-closed behavior works but continuity goal fails.
Longest PNG write 9.24 s; gap overlaps slow scene wall interval, not slow PNG.
Cause unresolved; dirty Pi checkout prevents clean-revision attribution.
Computer systems next: thread scheduling/I/O attribution; AP total CPU/RSS/thermal/
energy not measured. [Extension sequence](SYSTEMS_AND_AP_EXTENSIONS.md) records
user direction and optional semantic detection discussion. No runtime change.
Pipeline and learning source map reviewed; unchanged because this records evidence.

2026-11-05 — **Profile defined; packaged Pi acceptance pending: Spatial Application v1.**
[Guide](SPATIAL_APPLICATION_V1.md), [active plan](exec-plans/active/spatial-application-v1.md),
[source map](learning/SCENE_MEMORY.md). Packages existing CLI, scene memory,
timestamped orientation, session view map and bounded recorder into one
180-second detector-off image-backed demo. No runtime or threshold change.
Computer systems: bounded concurrency, freshness and recording failure contracts.
Application processor: exact spatial-workload CPU/RSS/thermal baseline deferred;
no new measurements. Existing component evidence remains linked, not relabelled
as a new v1 acceptance result. Pipeline reviewed; unchanged.

2026-11-04 — **Learning update requested by user; no runtime change.**
[HTML walkthrough](learning/program-flow-explorer.html) now includes camera-axis
conversion, quaternion history, ORB/geometric verification, scene map and bounded
writer. [Progress and systems guide](learning/SPATIAL_PROGRESS_AND_SYSTEMS.md)
links source and measured evidence, distinguishes unresolved accuracy, and proposes
application handoff then a fixed spatial AP workload. No new benchmark claimed.

2026-11-04 — **Bounded Pi check complete; qualified consistency: direction check.**
User confirmed scene/map functional behavior (recognition, multiple references,
direction signs, separation display, query counts and links), not angular accuracy.
[Servo diagnostic](../src/spatial/servo_orientation_demo.py) adds an optional
stationary baseline and local checkpoint quaternion comparisons before one pan/
tilt return. [Protocol](DIRECTION_CONSISTENCY.md),
[plan](exec-plans/completed/direction-consistency.md), [guide](learning/IMU.md).
No estimator correction or model change. AP question remains quality versus
sampling/workload; total CPU/energy/thermal cost not measured in this short check.
[Results](DIRECTION_CONSISTENCY_RESULTS.md) and
[structured record](../benchmarks/results/direction-consistency-2026-11-04.json):
still 1.12°, pan return 0.15°, combined 1.04°; 994 ready polls, zero errors.
Still/pan images align closely; tilt is displaced ~9 pixels, so exact return and
angular accuracy are unvalidated. No repeats; proceed with experimental context.

2026-11-04 — **Pi bookkeeping verified; angular accuracy unvalidated: lightweight view map.**
[ViewMap](../src/spatial/view_map.py) links explicit references, saved relative
orientation and observed label changes; no distance/position or gyro correction.
Bounded to scene memory capacity, with unknown angular context kept explicit.
AP question: cost of node/edge updates and angular comparisons at scene cadence;
`view_map_update_ms` records update wall time, not overall CPU. [Plan](exec-plans/active/lightweight-view-map.md),
[protocol](VIEW_MAP.md), [source guide](learning/SCENE_MEMORY.md). Local replay
uses prior decisions, not new accuracy evidence. [Live review](VIEW_MAP_RESULTS.md)
and [small result](../benchmarks/results/view-map-2026-11-04.json): 180 snapshots,
three nodes/five links, zero drops, median map-update wall time 0.4733 ms.
Final center imagery is close but gyro pointing separation is 16.53°; do not
claim angle accuracy. Total CPU/memory/temperature not measured. Preview now
places the non-collapsible map before the image/metrics; ready/stale browser checked.

2026-11-03 — **Measured on Pi: bounded scene recorder.**
[SceneRecorder](../src/spatial/scene_recorder.py) owns PNG/JSON writes outside
the scene worker, with four queued jobs, counted query drops and deferred
enrollment admission. Separate error status and bounded shutdown preserve
honest evidence completeness. AP question: does isolating slow writes prevent
scene stalls without IMU regression? [Protocol](BOUNDED_SCENE_RECORDING.md),
[source guide](learning/SCENE_MEMORY.md), [pipeline](PIPELINE.md), and
[completed plan](exec-plans/completed/live-scheduling-diagnostics.md).
[Pi evidence](../benchmarks/results/scheduling-background-2026-11-03.json):
120 rows/PNGs, zero drops, recognition completed during a 1.335 s image write;
maximum source gap 1.035 s, no IMU continuity failure. Total CPU/memory/thermal
benefit not measured; queue overflow remains locally tested, not Pi-stressed.

2026-11-03 — **Measured: reverse-order recording diagnostics.** B then A
reproduced a 2.04 s synchronous image-save stall, but no IMU interruption.
118/120 scene observations; all post-enrollment observations known. Enrollment
timing differed (19/5 s). [Findings](LIVE_SCHEDULING_RESULTS.md) and
[structured evidence](../benchmarks/results/scheduling-ba-2026-11-03.json).
Next: bounded background recording; not yet implemented. No new AP optimization
claim or threshold change. Existing pipeline/source guides remain unchanged.

This index connects what the Pi learned to do with the cost and quality
evidence collected for it. It is a stable source for a future project website,
not a dashboard or a substitute for detailed results. `Measured` means the
linked conditions were actually reported, not that a technique is accurate in
every scene. `Implemented` without a Pi result is not a measured optimization.

2026-10-26: [Development order changed](decisions/2026-10-26-development-order.md)
to functionality first, then AP engineering, then detailed learning material.
Keep this register current throughout; absent AP measurements may be labelled
`deferred — AP phase`. Existing results retain their original workload scope.

| Stage | Technique and code route | AP/quality evidence | Status and limit |
|---|---|---|---|
| USB camera capture | OV9281 MJPEG capture and decoded-frame timing; [camera code](../src/camera/capture_baseline.py), [hardware record](HARDWARE.md) | [benchmark protocol](BENCHMARKING.md); 720p MJPEG at 120 fps was demonstrated in V4L2 streaming, while decoded Python throughput was lower | Measured in distinct workloads; camera fps is not full-pipeline fps |
| Image-motion analysis | 320×180 grayscale nine-patch Hann-windowed phase correlation; [estimator](../src/recording/visual_motion.py), [study guide](learning/IMAGE_MOTION.md) | [motion-quality findings](MOTION_QUALITY.md), [visual results](VISUAL_MOTION_RESULTS.md) | Implemented/measured; shift is pixels between analyzed frames, not camera angle |
| CPU detection and tracking | OpenCV DNN MobileNet-SSD and basic/motion-aware box association; [live worker](../src/vision/live_detector.py), [tracker](../src/vision/basic_tracker.py) | [first sustained AP baseline](../benchmarks/results/ap-baseline-basic-2026-10-18.md) | Measured for one scene/model; object IDs are not a room map |
| Camera-head IMU polling | Raw SH3001 gyro, per-run still offset and timestamped samples; [live reader](../src/imu/live_reader.py), [guide](learning/IMU.md) | [fixed/adaptive polling findings](IMU_POLLING_FINDINGS.md) | Measured quality/resource tradeoff; no trusted accelerometer position estimate |
| Offline relative IMU rotation | Timestamped gyro integration into a quaternion; [offline integrator](../src/spatial/relative_orientation.py), [result](RELATIVE_ORIENTATION.md) | Stationary drift and pan-return residuals reported in the linked result | Measured on specific recordings; IMU axes and drift, not camera/world pose |
| Camera-axis mapping | Fit neutral-head camera XYZ directions from pan/tilt sweeps; [axis code](../src/spatial/camera_axes.py), [basis](../configs/camera_axes_neutral.json) | [independent direction checks and isolated cost](IMU_CAMERA_AXES.md) | Measured/validated for the unchanged mounting; not camera position |
| Live camera-axis rates | Optional projection of each valid gyro sample into camera axes; [live reader](../src/imu/live_reader.py), [A/B protocol](IMU_CAMERA_AXIS_AB.md) | [full-workload A/B result](../benchmarks/results/camera-axis-live-ab-2026-10-25.md): 5,638 projections in 300 s with no apparent rate regression; hotter B start limits CPU attribution | Implemented and measured as a feasibility check; rate is deg/s, not accumulated orientation |
| Live relative camera orientation | Opt-in bounded gyro-only quaternion from camera-axis rates; [estimator](../src/spatial/live_orientation.py), [active plan](exec-plans/active/live-relative-camera-orientation.md) | Synthetic and historical saved-gyro replay match offline math; Pi live drift, return quality and AP cost **not yet measured** | Implemented, pending Pi validation; not world pose or image/IMU fusion |
| Supervised live pan/tilt demonstration | Separate [one-shot servo controller](../src/spatial/servo_orientation_demo.py) commands ±20° sequentially; [run guide](LIVE_ORIENTATION_SERVO_TEST.md) | [Logged trials](LIVE_ORIENTATION_SERVO_RESULTS.md): trial 03 recorded 5.49° pan and 7.26° tilt start-to-settled-return estimated changes despite visible returns; all 464 snapshots ready. AP cost deferred | Measured as diagnostics, not validated orientation accuracy; commanded degrees are not measured camera angles and ~19 Hz reads may miss motion detail |
| Live IMU return A/B | Opt-in 10 or default 50 ms post-read sleep with three small grayscale view checkpoints per attended servo run; [preview](../src/app/live_preview.py), [servo logger](../src/spatial/servo_orientation_demo.py), [protocol](LIVE_IMU_POLLING_AB.md) | [Four-run Pi comparison](LIVE_IMU_POLLING_AB_RESULTS.md): 10 ms whole-run gyro residuals 1.07°/1.25° versus 50 ms 5.65°/11.75°; AP cost **not measured** | Two repeats/setting; user confirms visible return after both axes in all four valid runs. Exact physical angle and absolute orientation remain unmeasured. Raw images/logs stay out of Git |

## Recorded visual scene memory — 2026-10-29

Implemented: [bounded ORB feature memory](../src/spatial/scene_memory.py) and
[chronological video replay](../src/spatial/scene_revisit.py), with explicit
reference enrollment, geometric verification, ambiguity rejection and LRU
eviction. [Run guide](SCENE_MEMORY.md), [source map](learning/SCENE_MEMORY.md),
[development result](../benchmarks/results/scene-revisit-development-2026-10-29.json).
Real OpenCV synthetic checks and one Pi-recorded A → B → A clip passed on the
Mac. [Pi reproduction](../benchmarks/results/scene-revisit-pi-2026-10-29.json)
also returned enrolled A → unknown → known A, with 320 geometric inliers on
return. Three isolated event times were 90.87/56.60/110.06 ms, excluding decoding
and I/O; these are not sustained performance measurements. The Pi reported a
dirty working tree. Held-out recognition remains pending. AP question: how do
feature count, reference capacity and query cadence affect quality, latency
and memory? Dedicated cost measurements are deferred. This is scene recognition,
not calibrated pose or live image/IMU fusion.

## Record format for subsequent stages

Scheduling A/B measured — [findings](LIVE_SCHEDULING_RESULTS.md),
[result JSON](../benchmarks/results/scheduling-ab-2026-11-02.json).
Image/JSON stalls directly blocked the scene loop; B delivered 108 versus A's
120 updates. No IMU gap exceeded 35 ms and no continuity loss occurred in either
run. Prior IMU failure remains unresolved. No optimization or threshold change;
reverse-order confirmation and bounded recording isolation are next candidates.

Scheduling diagnostics — 2026-11-02: bounded polling interval/read/publication/
wake-delay evidence plus scene wall/thread/process CPU and recording intervals.
[Protocol](LIVE_SCHEDULING_DIAGNOSTICS.md), [IMU source](../src/imu/live_reader.py),
[scene source](../src/spatial/live_scene.py). Implemented, Pi measurement pending.
Thresholds and scheduling unchanged. AP question: are observed stalls inside
sensor reads, late wake-ups, scene computation or recording, and do they overlap?
No causal attribution or performance improvement claimed yet.

Three-view trial (2026-11-02): [findings](LIVE_SCENE_THREE_RESULTS.md),
[metrics](../benchmarks/results/live-scene-three-01-2026-11-02.json).
Center/left/right enrollment and revisits demonstrated. Upper-left retains
overlapping visual matches; exact direction is not established. Orientation
became unknown after a stale-reading event; image writes reached 5.84 s.
Next priority is reliability of scheduling/diagnostics, without threshold tuning.

Image-backed follow-up: [diagnosis](LIVE_SCENE_IMAGE_RESULTS.md) and
[machine-readable result](../benchmarks/results/live-scene-images-01-2026-10-29.json).
All 180 linked images present; 56 post-enrollment unknowns primarily reflected
limited overlap/support with the sole reference. Final 13 decisions were known.
Final quaternion difference from enrollment was 9.63° despite similar views;
exact pose unmeasured. Keep thresholds; expand explicit reference coverage next.

### Live visual scene memory — 2026-10-29

[Separate-recording validation](../benchmarks/results/scene-revisit-heldout-2026-10-29.json)
passed with unchanged thresholds. Implemented [live worker](../src/spatial/live_scene.py),
explicit enrollment and bounded preceding-IMU context; [run guide](LIVE_SCENE_MEMORY.md),
[source map](learning/SCENE_MEMORY.md). Known views are not room position.
Hardware-free tests and synthetic browser checks validate wiring.
[First Pi live log](LIVE_SCENE_RESULTS.md) demonstrates 1.00 Hz scene updates,
one enrolled view and later known decisions. Physical revisit correctness and
orientation consistency remain unverified; large quaternion disagreement with
the reference needs investigation. Sustained AP CPU/memory/thermal measurements
remain pending; isolated live wall compute is recorded in the result JSON.
AP question: query cadence/reference count versus recognition quality and contention.
Diagnostic extension: opt-in timed scene PNGs link each decision to the selected
image and stored references. User reports visible returns in live-scene-01 and
not ending away; final unknown is a suspected miss. Image-backed Pi evidence
pending; no thresholds changed. Diagnostic I/O is extra workload, not an AP
optimization or comparable baseline.

Add one concise row above and link its detailed technique guide, source/config,
ExecPlan and measured result. In the measured result, keep these fields easy to
find so a later website can render them without guessing:

1. **Capability and status:** what actually runs, what remains planned, and
   input/output units and timing scope.
2. **Technique:** the physical or algorithmic reason it works, exact code
   boundaries, assumptions and failure behavior.
3. **AP question and protocol:** comparison variable, Pi/OS/commit, camera
   request and negotiated mode if known, scene, power/cooling, warm-up,
   duration, sampling method and model/config identity.
4. **Measurements:** quality/correctness plus relevant CPU, latency, rate,
   skipped work, RSS, temperature and throttle values. Explicitly distinguish
   observed numbers from projections and missing numbers.
5. **Decision and limits:** what the evidence supports, confounders, and the
   next bounded check. Keep raw captures and large traces outside Git.

The [current live pipeline](PIPELINE.md) shows *implemented* flow; this index
may also name planned stages when clearly marked planned. The AP goal remains
primary; visualizations are downstream consumers of evidence, not replacements
for reproducible measurements.
