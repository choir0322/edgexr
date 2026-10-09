# Future Application Processor work: choose the detector for EdgeXR

Requested 2026-10-06. This is a future experiment agenda, not authorization to
download/install/train new models or change the current hardware protocol.
Keep MobileNet-SSD as the reproducible baseline while finishing initial IDs.

## Define what best means

Choose required classes, acceptable missed/false detections, ID stability,
responsiveness, memory limits and sustained thermal conditions before ranking
models. There may be multiple useful accuracy/latency tradeoffs instead of one
universal winner. Include the complete camera/motion/IMU workload on Pi 4.

Current reference: same-image detector median total 195.90 ms, CPU/OpenCV two
threads; combined live 2 Hz detector, 25–26 motion fps, 210–256 ms latest detector
compute, 260–800 ms box source age. These have different measurement scopes.
See DETECTION_RESULTS.md and LIVE_DETECTION_RESULTS.md when available. Latest
UI numbers are observations, not sustained p95 latency or power measurements.

## Experiments in order

1. Collect representative monochrome scenes with labelled object boxes. Include
   still scenes, camera turns, small objects, occlusion and varied lighting.
   Separate train/validation/test by scene/session so adjacent frames do not
   leak across sets. Keep a representative quantization calibration subset.
2. Compare the existing MobileNet-SSD with selected small YOLO variants and
   other practical candidates. Fix scene data and test protocol. Compare common
   classes fairly; separately report coverage of newly required categories.
3. Explore supported model input resolutions and runtime/export combinations.
   Check artifact compatibility, model provenance and preprocessing. Compare
   camera mode, early/late resizing, memory copies, detector cadence and
   OpenCV thread settings one variable at a time. Two threads was a starting
   choice, not an experimentally established optimum.
4. Quantization: evaluate supported lower-precision formats, starting with
   post-training quantization (PTQ). Use calibration data when required. If
   accuracy loss warrants the extra work, evaluate quantization-aware training
   (QAT). Record model size, accuracy, CPU time and actual backend execution;
   a smaller artifact or lower precision does not alone prove a speedup.
5. Pruning: investigate structured channel/filter removal first where the
   model/export/runtime supports it. Unstructured zeros may not accelerate a
   dense implementation. Fine-tune as required and benchmark the exported
   artifact on Pi rather than relying only on parameter or operation counts.
6. Fine-tuning: adapt a chosen model to this camera's monochrome scenes and
   needed categories using labelled data. Train on a suitable development
   machine if necessary; inference is evaluated on the Pi. Separate domain
   adaptation accuracy gains from efficiency changes. Keep the test set held out.
7. Re-run the full live workload for promising candidates, including tracking.
   Measure sustained behavior and document why the final choice fits EdgeXR.

## Required comparison record

Record model/version/hash, runtime/version, precision, input shape and
preprocessing, required classes, thresholds, camera mode, detector cadence,
threads, Pi OS/RAM/power/cooling, warm-up and duration. Use the same labelled
test set and show precision/recall and an agreed detection metric such as mAP.
Include slow motion and missed-object examples, not only an aggregate score.

Separate preprocessing, inference and postprocessing median/p95; measure
whole-application rates, skipped motion frames, box age, CPU use, memory and
temperature/throttling. End-to-end latency needs a defined measurement method;
host receipt age is not exposure-to-display latency. Measure energy only with
an appropriate method; do not infer power draw from CPU utilization.

Keep raw images/models out of Git. Commit concise benchmark tables, repeatable
settings, source/hash manifests and decisions. Prepare an ExecPlan before
starting implementation; select a small first comparison instead of running
all optimization techniques together.

## Explicit future checklist (requested 2026-10-07)

- [ ] Compare OpenCV thread settings 1, 2 and 4 under the same complete live
  workload. Two is the current baseline, not a proven optimum. Measure detector
  latency, motion throughput/skips, IMU timing, CPU use and temperature; threads
  are not reserved CPU cores. Repeat runs with consistent warm-up and cooling.
- [ ] Reduce camera frame rate using verified supported modes, keeping resolution
  and detector cadence fixed. Measure capture/decode cost and the effect on
  motion estimation, responsiveness and detection freshness.
- [ ] Compare supported camera resolutions, including 1280x720 and 1280x800
  where negotiated successfully. Hold other settings fixed; do not assume
  lower frame rate enables arbitrary resolutions or more detector detail.
- [ ] Compare supported detector input resolutions and/or a different model.
  Treat this separately from camera resolution. Check model compatibility and
  preprocessing rather than changing the existing fixed 300x300 input blindly.
- [ ] Evaluate detection on selected image crops for small-object detail.
  Measure coverage, missed objects outside crops, coordinate mapping and total
  compute if multiple crops require multiple inference calls.
- [ ] Compare full 720p transfer with an intermediate image such as 640x360 or
  separate prepared outputs. Measure resampling quality, memory/pipe traffic
  and full-pipeline performance before choosing an alternative.
