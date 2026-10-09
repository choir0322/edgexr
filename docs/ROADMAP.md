# Roadmap

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

## Phase 4 — Application Processor: measure and optimize

Use the protocol in `BENCHMARKING.md` to establish a baseline. Test one
optimization at a time: capture mode, model choice, frame skipping, threading,
or display overhead. Explain each tradeoff in a committed result summary.

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

## Phase 5 — Demonstrate and reflect

Record a reproducible demo procedure, compare against the first baseline, and
write what the system can and cannot reliably claim.
