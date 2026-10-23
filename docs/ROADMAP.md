# Roadmap

## Priority clarification — 2026-10-24

AP workload/systems engineering is the primary learning objective. Spatial
awareness remains the current bounded application task, not a prerequisite to
finish full mapping before learning AP engineering. Use the
[AP handoff](exec-plans/active/EdgeXR_AP_Workload_Benchmark_Handoff.md) flexibly:
retain verified hardware facts and existing Caffe/OpenCV MobileNet-SSD, IMU,
tracking, capture and profiler work. No NPU is available. Review the AP question,
bounded feature and measurements at each milestone; avoid indefinite identity,
mapping or learning-website expansion.

## Phase 0 — Know the equipment

Verify the Pi environment, USB camera modes, and raw IMU readings independently.
Produce a short hardware record and a commit that explains what was observed.

## Phase 1 — Capture a trustworthy frame stream

Create the smallest camera capture path that timestamps frames and reports the
negotiated mode. Add a hardware check and a small computer-only test for any
format-selection logic.

## Phase 2 — Add visible perception

Run a documented object detector on individual frames, then add a tracker that
shows IDs. Compare behavior on a static scene and during camera motion.

## Phase 3 — Add IMU context

Display calibrated or clearly labelled raw motion/orientation alongside the
camera feed. Only then explore whether it helps reject camera-induced motion or
improve tracking stability.

## Phase 4 — Orientation-aware surroundings (current priority)

Keep the base stationary first. Establish IMU-to-camera axes, timing and
short-term drift; estimate relative viewing orientation; then remember observed
scene regions by direction and validate revisits. Preserve uncertainty and reject
unsupported motion rather than inventing a position. Follow the
[orientation-aware surroundings plan](exec-plans/active/orientation-aware-surroundings.md).
Translation, metric depth and full 3D mapping require a separate later scope.
The [research review](SPATIAL_AWARENESS_RESEARCH.md) supports a calibrated visual
compass, gyro assistance and bounded scene keyframes before a full SLAM stack.
The immediate gate is sensor/camera calibration and timestamp validity, not
another identity or visualization feature.

### Supporting branch — Object re-identification (paused 2026-10-23)

The implementation below remains available, but further tuning is not a
prerequisite for directional scene memory. The latest
[trial checkpoint](REID_CROWD_GALLERY_CHECKPOINT.md) records unresolved findings.

Build a bounded, session-local object memory so a returning object can keep its
old ID after the short-term track has retired. This is a new re-identification
problem, not an extension of box overlap alone: compare appearance and class,
handle competing lookalikes conservatively, and allow an **unknown/new ID**
outcome. Evaluate departures and returns in recorded trials before enabling it
in the live preview. The camera is monochrome; a matching appearance is not
proof of real-world identity. Follow the
[active re-identification plan](exec-plans/active/re-identification.md).

## Phase 5 — Application Processor: measure and optimize

Use the protocol in `BENCHMARKING.md` to establish a baseline. Test one
optimization at a time: capture mode, model choice, frame skipping, threading,
or display overhead. Explain each tradeoff in a committed result summary.
The earlier sustained, unchanged basic-tracking measurement in
[`ap-baseline.md`](exec-plans/active/ap-baseline.md) remains a historical
reference. It was collected **before** re-identification and is not a fair
final-workload optimization baseline. AP measurement accompanies current work;
full spatial mapping is not a gate for model/thread/runtime experiments. After
the bounded orientation-input checkpoint, explicitly choose the next feature or
controlled AP comparison. Establish a baseline for each exact workload before
tuning. Model/runtime candidates in the handoff require compatibility and license
checks; preserve the working detector as one reference. No new tuning experiment
has started as part of this direction update.

Explicit future objective: **find the best detector configuration for this Pi
and EdgeXR's requirements**, including model efficiency and whole-application
behavior. MobileNet-SSD is the measured starting baseline, not a final winner.
Follow [the AP optimization agenda](AP_OPTIMIZATION.md): compare small YOLO and
other suitable models, runtime/input-size/thread choices, quantization, pruning,
and fine-tuning on representative monochrome scenes. Define accuracy and
responsiveness targets before selecting a winner; measure supported optimized
artifacts on the real Pi. Training/export may occur on a separate computer.

- [ ] Build a labelled evaluation set with separate training/calibration/test data.
- [ ] Compare baseline and candidate detectors on accuracy and complete Pi workload.
- [ ] Evaluate model/input/runtime/scheduling efficiency and thread settings.
- [ ] Evaluate quantization (PTQ; QAT if justified) with measured accuracy changes.
- [ ] Evaluate deployable pruning; verify actual Pi speedup rather than parameter counts.
- [ ] Evaluate fine-tuning for the camera's grayscale scenes and required classes.
- [ ] Document the selected configuration and rejected alternatives reproducibly.

## Phase 6 — Demonstrate and reflect

Record a reproducible demo procedure, compare against the first baseline, and
write what the system can and cannot reliably claim.
