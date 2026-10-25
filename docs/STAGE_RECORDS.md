# EdgeXR technique and AP evidence register

This index connects what the Pi learned to do with the cost and quality
evidence collected for it. It is a stable source for a future project website,
not a dashboard or a substitute for detailed results. `Measured` means the
linked conditions were actually reported, not that a technique is accurate in
every scene. `Implemented` without a Pi result is not a measured optimization.

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

## Record format for each new stage

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
