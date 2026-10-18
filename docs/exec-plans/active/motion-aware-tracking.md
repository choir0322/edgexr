# Motion-aware matching for short-term object IDs

## Purpose / big picture

Preserve a provisional object ID when a moderate camera turn moves the object's
box too far for raw box overlap, while keeping the existing IoU-only tracker as
the safe fallback. This is short-term geometric matching, not recognition after
an object leaves the view. The user has already observed that a visible person
keeps one ID during slow motion, but receives a new, higher ID after leaving
the frame and returning; that is expected for the current basic tracker.

The proposed visible test is a controlled turn where a person stays in the
frame. Compare the baseline and motion-aware modes using the same scene and
similar movement. Count ID switches, detection rate, motion-estimate coverage,
source age, and any false ID holds. Do not promise improvement before measuring.

## Context and orientation

`src/app/live_preview.py` receives 1280x720 grayscale frames for detection and
resizes them to 320x180 for `analyze_latest()` in the motion worker.
`image_shift()` in `src/recording/visual_motion.py` returns image-content dx/dy
between two analyzed frames, in **320x180 pixels**, or `None` when unreliable.
The motion worker and detector worker run independently; the detector targets
one start every 0.5 seconds and uses the newest available full-size frame.
`src/vision/live_detector.py` owns a `BasicTracker` that currently compares
same-class 1280x720 boxes with raw IoU >= 0.3. An old track can survive one
missed detector result, so its box may be more than one detector interval old.

Camera receipt timestamps are host monotonic observations, not exposure times.
Image shift is scene translation, not measured camera pose or a guaranteed
per-object movement. A person walking, parallax, a failed patch consensus, or a
long image-analysis gap can make a prediction unsafe. The IMU is separately
sampled and is **not** an input to this first matching change. Model files,
camera mode, inference cadence, freshness cutoff, servo behavior and browser
ID display remain unchanged.

Object re-identification is a separate future feature: it would retain a
bounded appearance description of a retired object and compare it to later
detections. This plan stores no such descriptors or image crops and does not
extend ID lifetime after departure from view.

## Progress

- [x] 2026-10-17: Record the user's Pi observation of stable in-view IDs and a
  new ID after complete departure and re-entry as the basic-tracker baseline.
- [x] 2026-10-17: Inspect tracker, detector and motion worker boundaries and
  write this plan before a cross-module implementation.
- [x] 2026-10-18: User reviewed this plan and asked to proceed, including the conservative fallback
  and what counts as a fair comparison.
- [x] 2026-10-18: Implement/test a bounded, timestamped history of reliable image shifts.
- [x] 2026-10-18: Implement/test predicted-box IoU using each track's last matched source
  time; preserve one-to-one, class, miss and ID-nonreuse rules.
- [x] 2026-10-18: Wire the tracker to motion history with an observable fallback status.
- [x] 2026-10-18: Review/update `docs/PIPELINE.md` and relevant `docs/learning/` guides in
  the same change. Check source symbols, shapes, units, rates, timing, errors
  and current-versus-planned behavior; explicitly record if a diagram remains
  unchanged and why.
- [x] 2026-10-18: Run local unit/browser checks and `git diff --check`.
- [ ] Run controlled Pi comparison and record actual outcomes.
- [x] 2026-10-18: User observed stable IDs in both modes during ordinary turns;
  motion-aware coverage was nonzero but the browser's motion-only match count
  stayed at zero. Add a metrics-only two-run recorder before making any
  performance or accuracy claim.
- [x] 2026-10-18: Implement and hardware-free test the trial recorder, the
  no-image telemetry route, and side-by-side report reader. Review/update
  `docs/PIPELINE.md` and the motion-aware learning guide for this extra process.
- [ ] Run the recorded basic and motion-aware Pi trials and inspect samples.

## Plan of work

1. Establish a small hardware-free motion-history component. Record each
   analyzed pair's start/end receipt times, sequence numbers, and dx/dy or a
   missing/unreliable marker in a bounded buffer. A lookup over an interval
   returns a displacement only if the interval has sufficiently fresh,
   continuous, reliable coverage. Because detection frames can fall between
   analyzed frames, define and test a conservative endpoint/interpolation
   policy before consuming the lookup. A missing result means **unknown**, not
   zero movement.
2. Add an opt-in prediction to box association. Remember the source receipt
   time of each track's last matched detection. For a current detection, ask
   for the scene shift from that old time to the current frame's receipt time;
   convert 320x180 dx/dy to 1280x720 box pixels (factor four on each axis),
   translate the old box, then calculate IoU. If the shift is unavailable or
   implausible, use the original unshifted box. Keep the existing 0.3 IoU
   threshold, same-class constraint, greedy one-to-one claim, two-miss expiry,
   and monotonic IDs. Do not mutate detector boxes or change their coordinates.
3. Connect this lookup only to the sequential detector worker. Expose a small
   diagnostic count for predicted versus fallback matches so a browser or
   result note can distinguish actual use of motion from an unchanged ID that
   happened without it. Keep image-analysis and detector compute timings
   separately scoped; do not silently fold tracking work into inference ms.
4. Update the live pipeline diagram, tracking/object-detection study guides,
   tests and Pi trial instructions. Compare against IoU-only behavior with
   matched camera mode, scene, lighting and movement. Record ID switches and
   false matches, not just throughput.

## Concrete steps

Start with focused synthetic tests: no camera or IMU is needed. Use boxes that
do not overlap before compensation but do overlap after a known image shift;
also test the reverse direction, multiple competing objects, one missed
detector update, unreliable motion, a history gap, a moving foreground object,
and a return from outside the view. The last case must still receive a new ID
after retirement. Then run the full unit suite and `git diff --check` on Mac.

After code review, push from Mac and pull on the Pi. Use the existing SSH-only
preview instructions and existing model files; no download or hardware change.
For the Pi 4 on the currently reported Raspberry Pi OS Bookworm system, request
1280x720 MJPEG at 30 fps. In a well-lit scene with a visible person or chair,
observe at least 30 seconds still and 30 seconds of repeated gentle whole-base
turns that keep the target in view. Run the same protocol in baseline and
motion-aware modes. Report the actual software commit, achieved rates, source
age, motion coverage, ID switches and obvious false ID holds. Stop rather than
force the pan servo or pull camera/IMU wiring. Record differences in scene or
lighting if a matched trial is impossible.

## Validation and acceptance

- Pure tests prove the pixel-scale/sign conversion, time-interval lookup,
  rejection of unknown/unreliable motion, predicted-box IoU, one-to-one
  assignment, misses and ID non-reuse.
- The original tracker behavior remains available for comparison and as the
  per-interval fallback. No estimated shift is silently treated as exact pose.
- Pi observations say how often compensation was available, whether it reduced
  in-view ID switches, and whether it introduced false matches. An unchanged ID
  alone is not proof the compensation helped.
- Camera capture, motion preview, IMU status, 2 Hz detector target, 1.5-second
  box-source freshness and error hiding still work as before.
- `docs/PIPELINE.md` and the learning guide name the actual data source,
  coordinate scale, monotonic-clock scope, synchronization limitation and
  fallback. Re-identification remains explicitly future work.

## Surprises and discoveries

The motion worker currently publishes only its latest browser result; the
detector needs an interval of shifts, not that one dx/dy. Detector source frames
also need not have been selected by the motion worker. These timing boundaries
must be solved and measured before the matcher can safely consume motion.
The user's initial Pi observation showed that reliable motion coverage alone
is not an improvement: during ordinary turns the raw IoU baseline also kept
IDs, so `motion_only_matches` stayed zero. A separate metrics-only endpoint
avoids fetching image bytes at a higher logging rate, though HTTP polling can
still miss a result and adds some CPU work.

## Decision log

- 2026-10-17: Scope this first step to image-motion-based box prediction, not
  IMU fusion or appearance re-identification. This makes the source of any
  improvement testable and avoids calling a gyro rate a pixel displacement.
- 2026-10-17: Keep IoU-only matching as an explicit baseline/fallback. A
  missing image-shift estimate is not evidence that the camera stayed still.
- 2026-10-18: Store at most 180 analyzed pairs; reject pair gaps over 0.12 s.
  Prorate covered interval endpoints linearly. Preserve raw IoU even when
  prediction exists, because independently moving foreground can violate
  background image shift. Reject nonfinite or over-frame-size source shifts.
  These are conservative starting policies, not measured optima.
- 2026-10-18: Compare two separate 60-second trials through `/api/telemetry`,
  excluding image bytes. Log every successful poll plus a summary of distinct
  observed detector sequences. Use one unique target category; ambiguity or a
  missing target breaks the ID-change chain. Counts are observational proxies,
  not labelled ground-truth accuracy.

## Outcomes and retrospective

Implementation is local and opt-in. The camera, model, detector cadence, IMU
reader and drawn box coordinates are unchanged. On Mac, the full hardware-free
unit suite passed (65 tests, two existing environment-dependent skips); preview
label and both learning-page JavaScript checks passed; `git diff --check` passed.
These do not establish real Pi identity accuracy. A matched baseline/aware
hardware comparison is still pending; do not mark complete until it is recorded.
The learning-contract audit reports one pre-existing missing docstring section in
`scripts/build_hann_fft_lesson.py`; this unrelated lesson-builder file was not
changed for tracking. New tracking code and tests satisfy that audit.
The new read-only comparison tooling passes the full Mac unit suite (70 tests,
two environment-dependent skips), including fake telemetry and the no-image
HTTP route. `git diff --check` passes. It has **not** yet been run on the Pi;
the remaining acceptance step is the paired 60-second user trial documented
in `docs/TRACKING_TRIAL.md` and manual review of any false ID holds.
