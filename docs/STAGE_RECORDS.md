# EdgeXR technique and AP evidence register

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
Mac. Pi runtime and held-out recognition remain pending. AP question: how do
feature count, reference capacity and query cadence affect quality, latency
and memory? Dedicated cost measurements are deferred. This is scene recognition,
not calibrated pose or live image/IMU fusion.

## Record format for subsequent stages

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
