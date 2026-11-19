# Fixed-base spatial awareness: directions, object memory, prediction, near/far

## Purpose / big picture

Turn the existing components into one program that knows the space around a
fixed pan/tilt head. The demonstration: a bottle is seen at one head direction;
the head turns away; while turning back the program states where the bottle
should reappear, then reports *same object as expected*, *missing* or *moved*.
It also orders visible objects as nearer or farther. The program is a vehicle for
AP/systems learning; each step names the processor question it adds. See
[the decision record](../../decisions/2026-11-16-spatial-awareness-integration.md).

## Context and orientation

- Raspberry Pi 4, passive heatsink, OV9281 USB camera at 1280x720 MJPEG 30 fps,
  SH3001 IMU rigid beside the lens, pan servo channel 2 and tilt channel 3
  (safe commanded range pan ±40°, tilt ±25°).
- Built: `spatial.live_orientation` (gyro quaternion relative to a still start),
  `configs/camera_axes_neutral.json` (IMU-to-camera axes), `recording.visual_motion`
  (phase-correlation image shift), `vision.detect_image` / `live_detector`
  (MobileNet-SSD, VOC classes), `vision.basic_tracker` (short-term IoU IDs),
  `spatial.scene_memory` / `view_map` (ORB views keyed by head direction),
  `spatial.servo_orientation_demo` (supervised sweeps).
- Calibration: `benchmarks/results/camera-calibration-screen-01.json`;
  fx ≈ 733.6 px, cx ≈ 670.3 px at 1280x720, status `needs_review`.
- Terms: **bearing** = direction from the fixed base (pan/yaw, tilt/pitch) in
  degrees; **head orientation** = gyro estimate of where the camera points.

## Progress

- [x] 2026-11-16 User approved the specification; bottle as first test object.
- [x] 2026-11-16 Decision record written; third-view plan deferred.
- [x] 2026-11-19 Recalibration 02 reviewed: centre fit improved, corners still uncovered and model still folds ([summary](../../../benchmarks/results/camera-calibration-screen-02.json)).
- [x] 2026-11-19 Recalibration 03 reviewed; joint 02+03 fit with k3 = 0 adopted as the
  working calibration, status `needs_review` ([review](../../../benchmarks/results/camera-calibration-joint-02-03.json)).
  Preset coverage checks still fail; step 1 must flag directions outside the region
  covered by detected board points as extrapolated.
- [x] 2026-11-20 Step 1 implemented: `spatial.bearing`, `--bearings`, detector frame/gyro
  pairing, browser label, `configs/camera_calibration.json`; 240 unit tests pass on the Mac.
- [x] 2026-11-20 Step 1 trial 01: failed fixed criteria (false positives, edge-cut boxes,
  placement); yaw bearings stable ([results](../../STEP1_BEARING_RESULTS_01.md)).
- [x] 2026-11-20 Step 1 trial 02 passes ([results](../../STEP1_BEARING_RESULTS_02.md)); limits: drift ~3°
  over setup minutes, few moving samples, false detections. Step 1 complete.
- [x] 2026-11-20 Step 2 implemented (`spatial.object_map`, `--object-memory`); 254 unit tests pass.
- [ ] Step 2 Pi trial: stay / removed / moved ([procedure and fixed expectations](../../STEP2_OBJECT_TRIAL.md)).
- [ ] Step 3: drift correction from phase-correlation shift and ORB view anchors.
- [ ] Step 4: monocular depth CNN for near/far (needs approval of a specific model).
- [ ] Step 5: whole-program per-stage Pi profile (CPU, latency, memory, temperature).
- [ ] Review/update `docs/PIPELINE.md` and the relevant `docs/learning/` guide each step.

## Plan of work

1. **Bearings.** Undistort the box centre with the calibration, convert to a
   camera-frame ray, rotate it by the head quaternion sampled nearest the frame's
   receipt time, report pan/tilt degrees. Check: synthetic rays and known
   rotations; on the Pi, a bottle's bearing should stay nearly constant while the
   head pans (report spread in degrees). AP question: frame/IMU timestamp skew.
2. **Object memory.** Store class, bearing, appearance descriptor, last-seen time
   and depth rank. On each update predict which remembered objects should be in
   view and where in the image; match by class + bearing window + appearance.
   Check: servo sweeps with the bottle present, removed and moved; count
   matched/missing/moved outcomes. AP question: memory bound and lookup cost.
3. **Drift correction.** Compare gyro rotation with phase-correlation shift
   (1 px at 320 wide ≈ 0.31°) and re-anchor on recognised ORB views. Check: return
   residual with and without correction over repeated sweeps. AP question:
   multi-rate workers, freshness and scheduling on four cores.
4. **Near/far.** Small monocular depth network on the CPU at a low rate; per-box
   relative depth. Check: ordering against a hand-measured layout. AP question:
   convolution compute, memory traffic, float versus int8.
5. **Profile.** One documented integrated run with per-stage CPU, latency
   percentiles, memory and temperature; rank kernels for NEON/FPGA work.

## Concrete steps

Step-1 scene (fixed before implementation, 2026-11-17): base on a table, head at
neutral; one bottle upright about 1–2 m away at bearing −30° (left of straight
ahead): place it a forward distance F from the lens and 0.58 × F to the left
(1.0 m → 0.58 m, 1.5 m → 0.87 m, 2.0 m → 1.15 m), roughly at lens height. With the
existing ±20° servo sweep it is visible for pan below about +13° and out of view
beyond, so the sweep both keeps it in view and takes it out. Mark positions with tape.

Each step adds tests under `tests/unit/` first (hardware-free), then a Pi trial
with a written protocol that includes the Mac SSH-tunnel/browser commands for the
live preview. New recording folders each time; nothing raw is committed.

## Validation and acceptance

Final acceptance: in a scripted sweep with a bottle, the program predicts its
reappearance and reports the correct outcome in most trials for present, removed
and moved cases (counts reported, not a single anecdote); near/far ordering is
correct for a measured two-object layout; the step-5 profile exists with the
benchmark fields required by `docs/BENCHMARKING.md`.

## Surprises and discoveries

2026-11-16, while building the camera-geometry learning page (derived, checked
against OpenCV 4.11.0): the provisional lens polynomial has a negative k3 and
folds at normalized distorted radius 0.973 (47.6° off-axis). Pixels farther from
the principal point have no inverse; `cv.undistortPoints` silently returns a wrong
ray there (top-left corner: 44 px round-trip error even after 100 iterations).
Affected: three image corners and a strip of the left edge (11 of 576 sampled
40-px cells). Step 1 must flag bearings from that region, or the camera must be
recalibrated with the board reaching the corners (board centres covered only
≈37% of width/height). Also: the view is 82.5° × 51.5° through the centre, so with
±40° pan an object leaves view only if it sits well to one side; place the test
bottle about 20° or more off centre.

## Decision log

2026-11-19: Deviation from the recalibration acceptance plan, recorded explicitly.
No recording met the preset corner-coverage checks. Rather than a fourth capture,
use the joint 02+03 fit with k3 fixed at zero: held-out median/p95 0.16/0.44 px,
interleaved-half focal lengths within 0.10%, cross-session p95 0.35–0.59 px, and
the model inverts at three corners (bottom-left 8 px). k3 = 0 was chosen after
seeing 03's fold, so it is a post-hoc model choice; directions outside the measured
region (≈1–2° model disagreement at the corners) are flagged, not trusted.

2026-11-16: Fixed-base spatial awareness replaces offline reconstruction as the
pre-FPGA endpoint; rotation cannot provide depth, so near/far comes from a depth
network rather than multi-view geometry. Distance sensor and stereo camera were
considered; they need hardware changes and add less AP-relevant compute.

## Outcomes and retrospective

(pending)
