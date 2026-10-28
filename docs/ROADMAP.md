# Roadmap

## Current development order — 2026-10-26

1. Finish the bounded vision/spatial-awareness application: fixed-base relative
   orientation, bounded scene memory, verified revisits and explicit unknown states.
2. Measure and optimize the completed workload on the Pi; retain prior AP
   measurements as historical evidence with their original workload conditions.
3. Build the detailed learning guides and visual explanations from the records.

Keep functional tests, experiment logs and source/pipeline documentation current
during implementation. Performance work is brought forward only if it blocks
usable functionality. Do not interrupt every small feature with an AP experiment
or lesson. [Completion criteria and next implementation](decisions/2026-10-26-development-order.md).

## Forward milestones — reviewed 2026-10-28

Camera capture, image-motion analysis, CPU detection/tracking, live IMU,
camera-axis conversion, gyro-only orientation, servo logging and initial AP
profilers are implemented. The [four live polling trials](LIVE_IMU_POLLING_AB_RESULTS.md)
now have user confirmation of visible return after both axes. Explicit 10 ms
polling is the proposed reference for upcoming spatial work; residual drift
still requires uncertainty handling. As of 2026-10-29 the
[offline scene-memory tool](SCENE_MEMORY.md) is implemented and exercised on
one existing Pi recording. Live integration and held-out recognition remain pending.

1. **Remember views on recorded input — first implementation complete.** Store a bounded
   set of representative scene frames and features. Use the existing plan's
   OpenCV ORB features and geometric verification to demonstrate A → B → A:
   recognize a previously observed region, distinguish a new one, and return
   unknown for weak or ambiguous evidence. Evaluate on separate footage with
   similar-looking regions and moving foregrounds.
2. **Combine scene memory with live direction context.** Attach timestamped
   relative orientation to stored views and use direction to rank candidates.
   Visual evidence verifies a revisit; permit visual recovery when orientation
   is uncertain. Add memory limits, eviction/reset and known/new/unknown states
   to the live preview. Scene recognition alone does not provide a precise
   quaternion correction. Use explicit 10 ms polling for the proposed reference
   configuration; this roadmap changes no runtime defaults.
3. **Finish the fixed-base spatial demo.** Validate repeated observe/turn/return
   cycles, blank walls, repeated patterns, moving people, fast turns, occlusion
   and sensor gaps. Record false/missed revisits, unknowns, recovery and memory
   growth. Lens calibration and validated geometry/timing are required before
   claiming calibrated visual angle correction; add that work before completion
   only if needed for the functional requirements. Completion means a repeatable
   directional scene-memory demo with bounded resources and documented limits.
4. **Measure and optimize the completed AP workload.** Freeze representative
   inputs/configurations and quality targets. Measure stage timing, total CPU,
   memory, throughput, latency/age, skipped work, temperature and throttling.
   Test polling/scheduling, image copies/resizing, CPU threads and detector
   models/runtimes one change at a time. Evaluate quantization, deployable pruning
   or fine-tuning when justified. Keep quality and resource results together;
   historical benchmarks do not replace a baseline for the completed workload.
5. **Build detailed learning and portfolio material.** Use the maintained
   source, decisions and results for code tours, the website, AP comparison
   charts and a reproducible demonstration, including rejected hypotheses.

Room position, metric depth and a 3D map remain a separate potential extension.
They require camera calibration, translation-aware visual odometry or SLAM,
scale/pose validation and a Pi feasibility study; visual-inertial fusion also
requires camera/IMU timing and extrinsic validation. Gyro integration alone
does not supply position. Re-identification tuning and learning-site expansion
remain supporting branches rather than prerequisites for scene memory.

At each stage, retain the technique, source/config links, conditions, quality
results and available AP metrics in [STAGE_RECORDS.md](STAGE_RECORDS.md).
Label unmeasured AP cost as deferred. Keep raw imagery outside Git and commit
and push completed coherent changes under the standing user direction.

## Background objective — 2026-10-24, sequencing superseded above

AP workload/systems engineering is the primary learning objective. Spatial
awareness remains the current bounded application task, not a prerequisite to
finish full mapping before learning AP engineering. Use the
[AP handoff](exec-plans/active/EdgeXR_AP_Workload_Benchmark_Handoff.md) flexibly:
retain verified hardware facts and existing Caffe/OpenCV MobileNet-SSD, IMU,
tracking, capture and profiler work. No NPU is available. Retain the records
needed for the later AP phase at each milestone; avoid indefinite identity,
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
The next implementation is bounded scene memory on recorded input. Maintain
timestamp validity; camera calibration gates calibrated angular correction,
rather than conservative visual scene recognition.

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
final-workload optimization baseline. Begin systematic AP comparisons after
the bounded vision/spatial-memory application is complete; full 3D mapping
is outside that completion target. Establish a baseline for each exact workload before
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

## Phase 6 — Detailed learning material and reflection

Record a reproducible demo procedure, compare against the first baseline, and
write what the system can and cannot reliably claim. Build detailed code tours,
algorithm explanations and learning visualizations from the preserved records.
