# EdgeXR — AP Workload Analysis & Object Detection Benchmark

> **Handoff for the existing EdgeXR Codex/VS Code session**
> Status: proposed scope update; integrate into the existing repository rather than rebuilding it.
> Primary objective: learn AP-oriented software and performance engineering by **comparing real object detection models**, while preserving EdgeXR's camera/IMU/tracking experience.

## 0. Instructions to Codex: read this first

This document is a **project direction and implementation brief**, not authorization to replace existing work.

1. Inspect the current repository, especially `AGENTS.md`, `.agent/PLANS.md`, `README.md`, `docs/PROJECT.md`, `docs/ARCHITECTURE.md`, `docs/HARDWARE.md`, `docs/BENCHMARKING.md`, and `docs/ROADMAP.md` if present.
2. Report what has already been implemented and what is missing. **Preserve working code and established decisions.** Propose a minimal integration plan, showing which files will change.
3. Follow existing repository conventions and ExecPlans for multi-session changes. Do not introduce a large framework before there is a demonstrated need.
4. Make the user an active learner: explain **what**, **why**, **alternatives**, **how to verify**, and **what the measurements mean** before substantial implementation. Prefer small, runnable increments. Never silently solve every exercise for the user.
5. Do not fabricate benchmark numbers, NPU measurements, hardware compatibility, successful tests, or accuracy results. Report actual observed values and relevant caveats.
6. Use only publicly available code/models and personal hardware. **Do not use Samsung internal code, documentation, architecture data, tools, or results** in this public project.
7. Keep Git history readable. After validated milestones, suggest a descriptive commit and push; **do not push, force-push, publish datasets, or change remotes without the user's approval**. Do not commit secrets, giant model files, recordings with private information, or raw generated data by default.

**Requested change from the earlier project discussion:** Replace the experiment *“standard convolution vs depthwise vs pointwise convolution”* as the primary comparison with **complete object detection models**, particularly **SSD MobileNet versus lightweight YOLO variants**. Operator-level studies may later be used to *explain* model behavior, but are not the project's centerpiece.

---

## 1. Motivation and desired career alignment

**Career target:** Samsung DX/MX AP Solutions-style work, based on the following role descriptions supplied by the user:

- `소프트웨어 분석 엔지니어링`: NPU-executed AI model analysis; NPU simulator integration/development; MLPerf; NPU performance measurement and solutions.
- `시스템 전력 및 성능 최적화`: NPU simulator/model analysis, performance profiling, workload analysis.

The project should demonstrate transferable fundamentals without an NPU:

- AI **model-level** workload analysis: graphs, operators, input shapes, parameter counts, estimated MACs/FLOPs, intermediate activations and memory traffic (with clearly labeled assumptions).
- Real-device profiling: inference and pipeline latency, throughput, CPU utilization, RAM, temperature, frame drops and bottlenecks.
- Reproducible benchmarking and accuracy/latency trade-off analysis.
- Systems engineering: camera capture, buffering, concurrency, resource allocation, profiling, ARM CPU behavior and possibly optimized CPU backends.
- Optional **analytical/educational NPU performance model**, with no claim of representing Samsung or any commercial NPU.

**Not a priority:** training a new neural network, implementing a production XR headset, or merely showing bounding boxes without performance analysis.

---

## 2. Actual equipment and boundaries

### Known hardware

- **Raspberry Pi 4** (not Raspberry Pi 5).
- **SunFounder AI Fusion Lab Kit**, potentially including motion/IMU sensors and pan/tilt hardware.
- **OV9281 USB industrial global-shutter camera module**, advertised as 720p and up to 120 fps in particular modes. **This replaces the camera bundled with the SunFounder kit.**
- Development computer may be used for model conversion, offline analysis and coding, but all statements about Pi 4 performance must come from tests on the Pi 4 itself.
- **No NPU available.** Do not assume a Coral TPU, Hailo HAT, CUDA GPU, or Raspberry Pi 5.

### Verify before implementation

- Raspberry Pi OS version, kernel, `aarch64` vs `armhf`, RAM capacity and power supply.
- Camera behavior using `v4l2-ctl --list-devices`, `v4l2-ctl --list-formats-ext`, and a minimal OpenCV/V4L2 capture test.
- Enumerated USB pixel formats, resolutions and delivered frame rates. The **advertised 120 fps is not a guarantee for every format, resolution, USB setting or host application**.
- Actual IMU model, wiring and sample rate, rather than assuming a particular sensor or precision.
- Python and library/runtime versions compatible with the installed OS/architecture.

The camera's **global shutter** may help reduce motion distortion during tracking experiments, but doesn't supply depth or full 3D pose by itself.

---

## 3. What the finished product does

**A live spatial-perception demonstrator and performance-analysis laboratory.**

1. The OV9281 camera streams a live view of a desk/room to the Raspberry Pi.
2. A selected detector (e.g., SSD MobileNet or a small YOLO model) recognizes objects and draws labeled boxes.
3. A tracker assigns object IDs and tries to preserve them through short motion/occlusion; optional scene memory supports cautious reacquisition when the camera returns.
4. Optional IMU readings show camera rotation/motion and can inform tracking/scheduling experiments.
5. A dashboard displays live model identity, measured FPS, latencies, CPU/RAM, temperature, drops and inference cadence.
6. A benchmark runner replays **the same labeled images or recorded video** through multiple models and produces an interpretable comparison report.
7. Optional simulator experiments explore hypothetical performance under different compute, bandwidth and memory constraints.

### Example user-facing modes

- **Live Demo:** Camera feed + current model + boxes + IDs + system metrics.
- **Compare Models:** Run SSD MobileNet and YOLO on the same input sequence; show trade-offs in speed, accuracy and resource use.
- **Analyze Model:** Show graph/operator summary, computational estimates and likely bottlenecks.
- **AP Experiment:** Change input size, CPU thread count, inference interval, buffering policy, or backend and measure effects.

**Terminology discipline:** Bounding boxes, 2D tracking and IMU readings do **not** automatically constitute metric 3D spatial mapping or SLAM. Persistent object IDs are *hypotheses*, not a guaranteed 3D map. Do not display invented object XYZ coordinates or distances.

---

## 4. Detection model comparison — core experiment

### Initial model candidates

| Candidate | Role | Preferred first deployment path | Notes |
|---|---|---|---|
| **SSD MobileNet V2** (or a verified MobileNet V1 SSD package) | Small mobile-oriented detector | LiteRT/TFLite CPU | Prefer a reputable pretrained model with clear class mapping and preprocessing requirements. |
| **YOLO nano-family** (e.g., YOLO11n; substitute a current small stable version after verifying compatibility) | Modern lightweight YOLO reference | NCNN/ONNX Runtime CPU where supported | Export and postprocessing compatibility must be verified on Pi 4. |
| **EfficientDet-Lite0** (optional third candidate) | Another mobile deployment design | LiteRT/TFLite CPU | Include only if time and runtime support permit. |

**Do not hard-code unverified versions or packages.** Before committing to specific weights, document their publisher, version, license, expected input layout, class labels, pretrained dataset, output format, quantization and runtime requirements.

### Comparisons must separate two different questions

**Study A — Practical deployment comparison (primary):**

> "Which complete model + supported runtime is the best fit for an actual Raspberry Pi 4 detection application?"

Allow each model a **reasonable production-style optimized CPU runtime**, and disclose the differences (e.g., TFLite for SSD and NCNN for YOLO). This answers a practical engineering question but **cannot attribute all performance differences to model architecture**.

**Study B — More controlled model comparison (optional):**

> "How much of the difference comes from model characteristics versus inference backend?"

Where practical, rerun models using a shared runtime (e.g., verified ONNX CPU paths) or test multiple backends for the **same model**. Note unsupported operators, export differences, quantization and preprocessing. Do not force misleading equivalence if parity is impossible.

### Fair benchmarking rules

- Use **the same input image/video frames**, rather than collecting different live scenes for each model.
- Record camera capture resolution separately from neural network input resolution; a 1280×720 source does not mean the network operates at 720p.
- Describe resizing/letterboxing, normalization, RGB/BGR, output thresholds, NMS, class labels and pre/postprocessing per model.
- Record **native-input results** first; optionally add a matched-input-resolution study when both models support it correctly.
- Compare accuracy only using **common class definitions, the same ground-truth annotations, and the same evaluation procedure**. Do not directly compare mAP numbers from unrelated datasets or incompatible label sets.
- Benchmark cold start separately from steady state; warm up, then run repeated trials with fixed frame sets and logged system conditions.
- Record Pi OS, hardware/RAM, software/model versions, git commit, CPU thread count, clock/governor if available, temperature range and any background processes that may skew measurements.
- Do not describe an increased **display FPS** as improved detector throughput when detections occur only every N frames. Show display FPS and actual detector invocations/sec separately.

### Required measurements

| Category | Metrics |
|---|---|
| **Latency** | preprocess, model inference, postprocess/NMS, tracking, end-to-end per-frame processing; p50/p95 (and mean when useful) |
| **Throughput** | model inferences/sec, processed frames/sec, displayed frames/sec, dropped/stale frames |
| **Resources** | per-process CPU, approximate per-core activity, peak/RSS memory, Pi temperature, throttling flags |
| **Model** | file size, parameters, graph/operator inventory, estimated MACs/FLOPs when tool supports accurate coverage |
| **Quality** | mAP/precision/recall on consistently labeled data; or explicitly labeled qualitative/demo results if no valid quantitative dataset is ready |
| **Responsiveness** | frame age/queue wait and processing-stage timing; do not claim physical camera-to-screen latency without measuring it |
| **Energy** | optional only if a real power meter is available; CPU percentage or temperature is **not a power measurement** |

Suggested CSV/JSON fields:

```text
run_id,git_commit,device,os,model_name,model_version,model_format,
runtime,runtime_version,precision,source_resolution,model_input_resolution,
threads,num_frames,warmup_frames,preprocess_ms_p50,inference_ms_p50,
inference_ms_p95,postprocess_ms_p50,tracking_ms_p50,
processing_ms_p50,processing_ms_p95,inferences_per_sec,
processed_fps,display_fps,drop_count,cpu_percent,peak_rss_mb,
temperature_c_start,temperature_c_end,throttling_status,
accuracy_dataset,accuracy_metric,accuracy_value,notes
```

A benchmark should produce (1) machine-readable results, (2) charts/tables, and (3) a short explanation of the observed trade-offs and their limitations. Empty or unavailable fields should be represented honestly rather than filled with guesses.

---

## 5. AP-specific analysis beyond FPS

For each model, investigate and explain:

1. **Model structure:** Backbone, detection head, convolution/activation/operator families, tensor dimensions, parameter count, and major activation sizes.
2. **Arithmetic:** Approximate computational cost, recognizing that "FLOPs" counting conventions and operator-tool coverage differ.
3. **Memory:** Model footprint, intermediate tensor sizes, where copies/allocations occur, and whether the working set stresses caches/RAM.
4. **Execution:** CPU thread scaling, inference backend differences, quantization effects, preprocess/postprocess overhead, and bottlenecks.
5. **System behavior:** Under sustained runs, what happens to temperature, CPU frequency/throttling and latency variation?
6. **Scheduling:** Does running detection every N frames plus lightweight tracking give a better accuracy/responsiveness/resource trade-off than detecting every frame?

**Preferred experimental method:** Baseline → hypothesis → controlled change → repeatable measurement → interpretation → written conclusion.

Sample research questions:

- Is SSD MobileNet measurably faster than small YOLO on *this Pi 4 under these runtimes*, and at what cost in detection quality?
- How much of end-to-end time is model inference versus resizing and NMS?
- How do one, two and four CPU inference threads affect throughput, per-frame latency and heat?
- Does INT8 inference help on the actual backend, or does conversion/operator support change the outcome?
- Does a smaller model always improve application responsiveness? Why or why not?
- Under a fixed latency or CPU budget, which model gives the best task-specific accuracy?

Operator-level explanations such as depthwise vs standard convolution are **secondary diagnostic studies**, not the primary deliverable.

---

## 6. Optional simplified NPU simulator — AFTER real profiling works

Implement only if the model comparison and real Pi benchmarks are stable. Start with an **analytical performance estimator**, not a fake cycle-accurate emulator.

Inputs:

- Model-derived operator shapes and estimated work.
- Hypothetical accelerator configuration: effective operations/sec, memory bandwidth, on-chip SRAM capacity, data precision, and explicitly stated utilization/overhead assumptions.

Potential output:

```text
Operator | estimated ops | estimated bytes | compute-bound time |
         memory-bound time | simplified lower-bound estimate
```

Possible first approach:

`operator_time_lower_bound = max(ops / effective_compute_rate, bytes / effective_memory_bandwidth)`

This is a **roofline-style simplified bound**, not a measured or calibrated cycle-accurate prediction. It omits many details: mapping, tiling, DMA contention, caches, fusion, synchronization, scheduling and real kernel efficiency. Avoid fabricated simulator-to-silicon validation; the Pi CPU is not a stand-in for an NPU.

Useful experiments:

- Compare SSD MobileNet and YOLO modeled demands under multiple **hypothetical** compute-to-bandwidth ratios.
- Explore model activation and weight footprint relative to small/large modeled SRAM.
- Identify conditions under which one architecture could be more bandwidth-sensitive.
- Analyze the sensitivity of predictions to modeling assumptions.

Only later consider a more detailed event-based model or studying an existing open-source simulator.

---

## 7. Phased roadmap and acceptance criteria

### Level 1 — Working benchmark (core, first priority)

- [ ] Verify USB OV9281 camera modes and document the Pi environment.
- [ ] Integrate or preserve the current live camera demo.
- [ ] Get **one** pretrained SSD MobileNet detector running on recorded frames and live OV9281 video.
- [ ] Add a **lightweight YOLO-family** detector with a compatible CPU runtime.
- [ ] Define a common detection output adapter: boxes, labels, scores, timestamps.
- [ ] Run both on the same saved input frames and store reproducible latency/throughput/resource metrics.
- [ ] Produce a model comparison table and explain at least three meaningful trade-offs.

**Done when:** another developer can reproduce the comparison on equivalent Pi 4 hardware from documented commands/configuration, and the user can explain what each timing number represents.

### Level 2 — Strong EdgeXR + AP systems portfolio

- [ ] Multi-object tracker with persistent short-term IDs.
- [ ] IMU integration with timestamping and a live orientation/motion indicator.
- [ ] Optional careful object reacquisition, with a documented success/failure test.
- [ ] Reusable test clips and labeled evaluation subset or a documented public dataset.
- [ ] Controlled studies: resolution, inference interval, CPU threads, runtime/backend, sustained thermal behavior.
- [ ] Adaptive detector cadence or pipelined capture/inference/tracking with a fair baseline comparison.
- [ ] Model graph/operator summary and plausible, explicitly limited memory/compute interpretation.
- [ ] Reproducible charts, methodology and limitation section.

**Done when:** the project makes an evidence-based model selection recommendation for the Pi 4 under an explicitly stated workload and performance/quality budget.

### Level 3 — Stretch: NPU performance-modeling relevance

- [ ] Simplified hypothetical-accelerator performance estimator.
- [ ] SSD-versus-YOLO operator/workload mapping into the estimator.
- [ ] Compute-versus-bandwidth sensitivity experiments and assumptions documented.
- [ ] Optional EfficientDet-Lite0 third-model comparison.
- [ ] Optional C++ reimplementation or ARM/NEON optimization **only when a measured bottleneck justifies it**.

**Done when:** the user can articulate which parts of the output are measured, calculated, and hypothetical—and why the simulator cannot be treated as actual NPU data.

**Scheduling guidance:** This is designed for a full-time employee with a limited weekly budget. Complete Level 1 before ambitious scene-mapping or simulator work. Do not make Level 3 a dependency for an impressive and finished portfolio.

---

## 8. Architecture guidance — adapt the existing project

Suggested responsibilities, not a demand to recreate the repository:

```text
camera/          OV9281 acquisition; timestamps; recorded-frame replay
models/          model metadata, manifests, conversion instructions (not weights in Git)
vision/          detector adapters, common outputs, tracking, evaluation
imu/             optional sensor capture and orientation processing
scene/           visibility and object-state hypotheses
runtime/         CPU/backend configuration, queues, scheduling policies
profiling/       stage timers, system sensors, reproducible benchmark runner
analysis/        model-graph/operator analysis; optional NPU estimator
visualization/   live overlays and benchmark-result viewer
benchmarks/      configurations, documented input datasets, result summaries
scripts/         environment checks, reproducible experiments
```

Keep model-specific pre/postprocessing encapsulated so the benchmark API remains uniform without pretending all models are internally equivalent.

For **performance analysis**, recorded-frame replay is more scientifically controlled than a moving live camera. Keep both: **offline replay for comparison** and **live OV9281 feed for demo**.

---

## 9. Learning-first workflow — required for Codex

Every substantial implementation should follow:

1. **Teach:** Give a concise conceptual explanation (for instance, SSD vs YOLO, runtime vs model, inference latency vs FPS, mAP, NMS, or memory-bound vs compute-bound).
2. **Plan:** State the smallest next milestone and how it will be tested.
3. **Implement incrementally:** Prefer one observable feature at a time; invite the user to examine or implement important functions rather than writing an opaque large codebase.
4. **Inspect:** Explain important code paths and non-obvious API/architecture choices.
5. **Validate:** Share runnable commands; show exactly which tests were executed and what could not be tested remotely.
6. **Reflect:** Ask the user to explain what changed and why the result did or did not match expectations. Add findings to project notes.

Never infer understanding merely because a Codex-written program runs. Encourage manual inspection of one key algorithm/data transformation per milestone.

---

## 10. GitHub workflow

- Use the **existing** local Git repository. Confirm current branch, status and remote before making changes.
- Keep code, config, measurement methods, **small reproducible summary results**, diagrams and write-ups versioned.
- Put models, raw capture recordings, heavyweight datasets, large profiler traces, Python virtual environments and private data in `.gitignore` or an appropriate external storage workflow; keep documented retrieval instructions and hashes where helpful.
- Update `README.md`, `docs/ROADMAP.md`, benchmarking methodology and model manifests as the implementation evolves.
- Prefer frequent coherent commits (e.g., `feat: add SSD MobileNet inference adapter`; `bench: compare YOLO and SSD on fixed clips`; `docs: explain detector throughput vs display fps`).
- At the end of each tested milestone, **propose** a commit and push to the user's personal GitHub repository. Obtain permission for remote writes, and never commit employer information.

---

## 11. Suggested first Codex task in the existing session

> Read `EdgeXR_AP_Workload_Benchmark_Handoff.md` and inspect the current EdgeXR repository before changing anything. Summarize the repo's existing state and identify the smallest necessary changes to shift the AP work toward **SSD MobileNet vs small YOLO object-detector comparison** while preserving the existing XR camera/tracking scope. Update the project roadmap/architecture/benchmarking docs as needed, propose model/runtime candidates that actually work on Pi 4, and create the first small ExecPlan. Teach me the relevant concepts and guide me through each milestone instead of implementing the whole project without my understanding. Do not assume NPU hardware and do not fabricate benchmark results.

---

## 12. Public references to consult as needed

- Raspberry Pi 4 specifications: https://www.raspberrypi.com/products/raspberry-pi-4-model-b/specifications/
- Google / MediaPipe object detection reference (includes SSD MobileNetV2 and EfficientDet Lite): https://developers.google.com/mediapipe/solutions/vision/object_detector
- TensorFlow Lite object detection example / model lineage: https://github.com/tensorflow/examples/tree/master/lite/examples/object_detection
- Ultralytics Raspberry Pi deployment (verify current model and export compatibility): https://docs.ultralytics.com/guides/raspberry-pi/
- Ultralytics model export documentation: https://docs.ultralytics.com/modes/export/
- ONNX model format and graph concepts: https://onnx.ai/onnx/intro/concepts.html
- MLPerf Tiny benchmark context (methodology inspiration, not a claim of official compliance): https://mlcommons.org/benchmarks/inference-tiny/

**Bottom line:** A convincing AP Solutions-aligned portfolio is not simply "YOLO vs MobileNet: which is faster?" It is **a controlled, reproducible examination of why different complete detection workloads behave differently on a constrained ARM SoC, what those trade-offs mean for a real product, and how an accelerator-performance model might reason about them**.
