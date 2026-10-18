# Motion-estimator quality: four controlled recordings

## Purpose / big picture

Find when the existing 320×180 image-shift estimator reports a useful global
camera-view displacement, rejects an ambiguous pair, or mistakes local object
motion for camera motion. Keep this separate from the AP speed/thermal baseline.

## Context and orientation

The Pi 4 records OV9281 USB camera MJPEG at requested 1280×720/30 fps plus raw
camera-mounted IMU readings in `combined_capture.py`. `visual_motion.py`
decodes to 320×180, compares nine patches per adjacent frame pair, and pairs
its estimate with host-observed IMU readings. Pairing is approximate, not
exposure synchronization. `motion_quality.py` aggregates those CSV rows. No
tracking/detector changes, servo commands, model downloads or new dependencies.

## Progress

- [x] 2026-10-19: User asked to move on to this test; define four controlled
  conditions and implement an offline comparison without changing the live path.
- [x] 2026-10-19: Review `docs/PIPELINE.md` and `docs/learning/IMAGE_MOTION.md`;
  add offline-test links/limits if they need clarification.
- [x] 2026-10-19: Run and analyze four Pi recordings. The five analysis folders
  are now under ignored `recordings/`; summarize findings in
  `benchmarks/results/motion-quality-2026-10-19.md`.
- [x] 2026-10-19: Review the fast video. Several sharp sweeps coincide with
  visible blur/large view changes and four clusters of rejected pairs. Keep
  the estimator unchanged; a speed-controlled repeat or per-patch diagnostic
  is needed before selecting a threshold/algorithm change.
- [x] 2026-10-19: Add offline per-patch diagnostics; reproduce all 28 visual
  rejections in the fast clip. Most patch failures are weak correlation peaks,
  not low texture. Review/update `docs/PIPELINE.md` and the image-motion guide.
- [ ] Run a controlled turn-speed series, then select at most one targeted
  estimator change if a repeatable boundary justifies it.

## Plan of work

1. Preserve the current camera mode and estimator thresholds. Capture still,
   slow turn, fast but controlled turn, and a moving person with the rig still,
   one recording each. Begin every clip with at least one full second still.
2. Analyze all four with `visual_motion.py`. Rejected pairs must remain in the
   CSV, including a run with no accepted pair.
3. Compare visual coverage, displacement per pair and gyro coverage with
   `motion_quality.py`. Inspect per-second direction and the video before
   judging any mismatch. Movement timing is manually noted, not ground truth.
4. After reviewing the data with the user, pick exactly one improvement if
   the evidence justifies it, then repeat the relevant trial unchanged.

## Concrete steps

Follow `docs/MOTION_QUALITY.md`. Use new names for each retry, never overwrite
recordings. Confirm the camera head/IMU are rigid together and cables have
slack. No camera preview should have the device open during recording. Capture
files remain ignored by Git; share summaries and notes, not raw video by default.

## Validation and acceptance

- Hardware-free tests cover an all-rejected clip, missing gyro observations,
  and rejected pairs excluded from displacement statistics.
- Each Pi run records commit, camera mode, scene/light, approximate movement
  timing, duration and whether the mount moved relative to the camera.
- Still and person-motion trials are assessed for false global shift; turn
  trials for direction, coverage and rejection, not absolute angle accuracy.
- `docs/PIPELINE.md` and `docs/learning/IMAGE_MOTION.md` have been checked for
  accurate input shape, units, scheduling, freshness and links.

## Surprises and discoveries

The user reports roughly three or four quick sharp movements in the fast-turn
clip, not the single turn suggested in the protocol. Its 28 visual rejections
all occur around 5.04–7.30 s after the recording cue. This is a useful stress
test but not a one-turn comparison. The slow-turn clip also contains multiple
sign reversals, so its movement phases must be interpreted from the recorded
signals rather than the planned action alone. Earlier AP measurements showed
a sustained ~26 fps live motion-analysis rate, but this offline video analysis
is a different workload and must not be compared as a speed benchmark.
Visual review of the copied fast video shows blur, large scene replacement
between frames and a nearby object sweeping across the view. Corrected gyro Y
reaches about 794 degrees/s in one rejection cluster. These factors co-occur;
the present output cannot isolate the cause of each patch's rejection.
The offline patch report attributes 24 pair rejections to too few individually
valid patches and four to disagreement. Weak peaks appear in 219/252 patch
checks; no patch failed low texture. Some weak candidates also exceed the
displacement guard, but should not be treated as true displacement.

## Decision log

- 2026-10-19: Use existing saved-video and IMU tools before touching live
  motion logic. Report failures explicitly rather than filtering them away.
- 2026-10-19: A >1-pixel per-pair magnitude is a reporting aid for fixed-camera
  trials, not a correctness threshold or an algorithm setting.
- 2026-10-19: Keep a rejected extreme-motion estimate as unknown rather than
  relaxing thresholds without evidence. Use a speed-controlled repeat or
  per-patch rejection diagnostics for the next quality step.
- 2026-10-19: Reuse the exact existing patch gates with an optional detail
  record and run the report offline on saved video. Do not add per-patch
  serialization to the live worker or alter thresholds in this diagnostic step.

## Outcomes and retrospective

All four analysis outputs are available locally. The initial pattern supports
near-zero global shift for the still/person trials and strong coverage for a
slow turn. The repeated-fast-turn stress clip has four localized rejection
clusters. Its video has been reviewed, but there is still no measured camera
pose or causal attribution per rejected patch. The diagnostic narrowed the
failure to weak peak quality in most patches. No live estimator decision was
changed. Next is a controlled speed series, not immediate threshold tuning.
