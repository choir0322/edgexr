# Session-local object memory and re-identification

Status 2026-10-23: paused by the user in favor of
[orientation-aware surroundings](orientation-aware-surroundings.md).
Implementation is retained; crowd accuracy and spatial-cue validation are not
complete. See the [latest trial checkpoint](../../REID_CROWD_GALLERY_CHECKPOINT.md).
Do not resume identity tuning as the default next step.

## Purpose / big picture

When a person or object leaves the OV9281 camera's view long enough for
`BasicTracker` to retire its short-term track, a later detection currently gets
a new ID. Build a conservative, bounded memory that can *attempt* to restore
the old session ID on re-entry. The user should be able to see when an ID was
restored, when a new ID was chosen, and why. This is evidence-based matching,
not proof of physical identity, face recognition or cross-session recognition.

## Context and orientation

`src/vision/live_detector.py` receives a 1280×720 grayscale camera frame and
uses MobileNet-SSD to produce `class_id`, confidence and source-coordinate
`box_xyxy` at a target of two inference starts per second. `BasicTracker.update`
matches current boxes to active same-class tracks by IoU, optionally using
recent image shift. After two missed *detector updates*, an active track is
deleted; it holds no appearance pixels or descriptor. A skipped camera frame
does not count as a miss. `DetectionState.publish` sends only current boxes to
the browser. The camera-mounted IMU is independent and cannot identify an
object. Existing model files are local and remain outside Git.

The working hypothesis is that a small grayscale appearance descriptor from
the detected crop, combined with class and a short retention window, can help
some returns. Monochrome clothing, pose and lighting changes, similar objects,
occlusion and detector box errors can defeat it. The matching threshold and
memory lifetime are **not yet established**; they must be chosen from held-out
examples, not from one successful demonstration.

XR context is a second, separate hypothesis: accumulated reliable image shift
and camera-mounted gyro rotation could predict where a remembered object
*might* reappear after a pan. The image estimate is 2D displacement, the gyro
is angular rate, and neither alone supplies depth or proves identity. The IMU
is currently displayed/recorded but is not fused into tracking. Do not treat
servo commands as measured camera pose. Calibrate camera field of view, IMU
axis/sign, timing and drift before using rotation as a matching gate. Unknown
motion must remain unknown rather than an assumed zero.

## Progress

- [x] 2026-10-22: Resume after the learning explorer; evaluate galleries,
  temporal retries, learned appearance and weak-detection association.
- [x] 2026-10-22: Implement four-view galleries, confidence/relative-area
  enrollment checks, duplicate suppression and gallery preservation on restore.
- [x] 2026-10-22: Replay 117 recorded updates: first-return continuity improves
  from 3/7 to 4/7; the recorded 8→9 becomes 8→8. Keep the three unresolved failures.
- [x] 2026-10-22: Update PIPELINE.md and the detection guide/program graph.
- [ ] Validate gallery behavior with a new Pi trial containing a second person;
  measure false restores and runtime overhead before calling it reliable.
- [x] 2026-10-23: Add opt-in two-second provisional retry and image-motion
  spatial tie-break, with separate flags and hardware-free tests. Replay the
  old 117-update development trial; one previously failed person return is
  restored on a later update. This is not new live crowd validation.
- [x] 2026-10-23: Review/update `docs/PIPELINE.md`, detection learning guide
  and program flow map for the new optional paths.
- [ ] Run the new two-person Pi gallery trial, label true identities, and
  compare the same recorded detector updates with retry off/on.
- [ ] Run a separately labelled camera-pan trial and measure spatial coverage,
  correct/false claims and Pi compute overhead.

- [x] 2026-10-20: User chose re-identification before AP optimization; reorder
  the roadmap and preserve the older AP measurement as a historical baseline.
- [x] 2026-10-20: Inspect current detector/tracker path and define a bounded,
  uncertainty-aware first milestone in this plan.
- [x] 2026-10-20: User reviewed the plan, then requested an explicit path from
  appearance memory to camera-motion/IMU-assisted spatial matching.
- [x] 2026-10-20: Implement `vision.object_memory` as a hardware-independent,
  bounded retired-ID memory core with explicit score and ambiguity gates.
  Four new unit tests pass; no live behavior or threshold choice was added.
- [ ] Build a small offline set with both genuine returns and same-class
  lookalikes; decide descriptor, thresholds and retention time from evidence.
- [x] 2026-10-20: Add an experimental `--reidentify` live-preview flag,
  provisional 8×8 grayscale descriptor and retired-ID matching after active
  overlap. Default basic and motion-aware modes remain unchanged.
- [x] 2026-10-20: Update `docs/PIPELINE.md`, the object-detection learning
  guide and Pi instructions for the new optional memory branch: 1280×720
  source pixels, 8×8/64-value descriptor, detector-update cadence, 10 s
  monotonic age, no IMU fusion, browser marker and source links.
- [x] 2026-10-20: Review the live pipeline and object-detection guide for the
  offline core step. No diagram change is warranted yet: the new module is
  not imported by a worker, sends nothing to the browser, and has no image
  shape or runtime cadence. Revisit both when the live path is wired.
- [ ] Run a supervised Pi trial, inspect ID holds and false matches, and
  record runtime cost before the deferred AP optimization phase.
- [x] 2026-10-21: Add persistent, image-free reasons and scores for experimental
  re-ID decisions after the user's first trial showed repeated new person IDs.
  Lower the separate **live detection score cutoff** from 0.50 to 0.30 after
  the stationary bottle's detection box flickered. Keep re-ID's provisional
  0.85 cosine threshold unchanged so the two failure modes remain separable.
- [ ] Repeat the bottle-and-person Pi trial and record detector rate, box
  flicker, retirement count, memory/expiry counts, best return scores, new IDs,
  tentative restores and any false claims. Do not infer cause without these data.
- [x] 2026-10-21: Add opt-in timed trial capture with one FFmpeg camera input,
  continuous MJPEG packet-copy video, exact detector-selected grayscale PNGs,
  per-update boxes/IDs/diagnostics, and partial/complete metadata. Review and
  update `docs/PIPELINE.md` and the object-detection learning guide for the
  recording branch; no new tracking or fusion path is implied.
- [ ] Inspect the recorded successful and failed returns together, label
  physical continuity by eye, and compare bottle detection misses separately
  from person appearance-match decisions. Retune only from those cases.
- [ ] Compare appearance-only, appearance + reliable image motion, and
  appearance + validated IMU rotation on the same labelled pan/return cases.
  Report when spatial evidence helps, hurts or is unavailable.
- [ ] Calibrate the provisional 0.85 similarity/0.05 margin and 10 s retention
  against labelled genuine returns and same-class lookalikes; until then,
  report the Pi run as exploratory rather than an identity accuracy result.

## Plan of work

1. Define success and failure cases: one object exits and returns after at
   least two missed detector results; two similar same-class objects exchange
   places; lighting or pose changes; no return; and multiple stored candidates.
   Keep raw clips under ignored `recordings/`, with small labelled outcomes
   and summaries in Git. A correct **new/unknown** decision counts as success
   when the evidence is ambiguous.
2. Prototype appearance comparison offline from the same 1280×720 grayscale
   source and detector boxes. Start with a small, explainable descriptor and
   same-class gating; measure positive and negative score distributions before
   setting a threshold. No new pretrained model, package, download or training
   is authorized by this plan. Reject low-information crops and near-tied
   candidates rather than claiming identity.
3. Keep active IoU/motion-aware matching first. Only unmatched *current*
   detections may seek retired IDs. Store a bounded number of retired tracks
   for a bounded monotonic-time interval, with class, descriptor, last-seen
   time and ID but no raw crop. Claim each retired ID at most once; never reuse
   it after expiry. Restarting the preview starts fresh IDs and empty memory.
4. Add an explicit opt-in live mode, visible match-source/uncertainty telemetry
   and unit tests for expiry, ties, one-to-one claims, class mismatch, empty or
   invalid crops, camera turns and unchanged default behavior. Keep descriptors
   internal; do not send raw crops or descriptor vectors to the browser.
5. Compare labelled Pi trials with and without memory under the same scene and
   movement. Count true restored IDs, missed restores and false old-ID claims;
   report added compute time and full-live frame/box freshness. An ID hold
   alone is not ground-truth correctness.
6. In a separate opt-in experiment, add spatial context to candidate ranking:
   first use only continuously reliable image-motion history, then evaluate
   camera-mounted gyro rotation if its axis, bias, timestamps and camera field
   of view have been checked. Predict a *region*, not an exact point; object
   motion, parallax, estimator gaps and IMU drift require an abstain/fallback
   path. Compare the same labelled trials against appearance-only before
   retaining any spatial gate. This is scene-relative memory, not a 3D map.

## Concrete steps

The user has reviewed this plan. Begin with a pure memory core using synthetic
descriptors: it accepts explicit retention, capacity, score and ambiguity
settings so tests do not accidentally establish production thresholds. No
camera crop or live worker is changed in this first code step. Then select a
small set of representative
recorded return/lookalike clips and manually label object continuity. Use the
existing Raspberry Pi 4 running the recorded Raspberry Pi OS Bookworm build,
with the OV9281 requested at 1280×720 MJPEG/30 fps. Propose two 60-second
well-lit trials with fixed scene, power and cooling notes: one clear return
and one same-class lookalike challenge. Agree on the final conditions and
duration before recording. Keep raw camera data ignored. Implement pure
matching logic with synthetic descriptors and hardware-free tests before wiring
image crops into the Pi worker. Run all unit tests on Mac; run the opt-in live
mode on Pi only after code review, push/pull and a clear observation protocol.
If a trial gives a false ID claim, preserve its summary, tighten or abstain,
and repeat the same case; do not silently change thresholds mid-comparison.

## Validation and acceptance

- Default basic and motion-aware tracking retain their current behavior.
- A labelled return after retirement can restore an ID when evidence passes;
  a competing similar object and a near tie must not both claim that ID.
- Memory is bounded by count and monotonic age; no raw crops, model weights or
  personal identity records enter Git or the web API.
- Hardware-free tests cover expiry, one-to-one claims, class mismatch,
  ambiguity, invalid crops, and stream restart.
- The Pi trial reports false matches as well as successful restores and added
  runtime cost. The result is not described as reliable person identity.
- Spatial-context trials report coverage, false spatial exclusions, and
  appearance-only versus motion/IMU-assisted ID outcomes. A missing or
  uncalibrated signal cannot silently become a confident spatial match.
- `docs/PIPELINE.md` and learning guides reflect actual inputs, pixel shapes,
  timing/freshness, units, outputs and source files after implementation.

## Surprises and discoveries

The present track remembers one missed detector update but deletes the ID at
the second; the optional motion shift does not preserve an appearance. The
quick pan quality test supports image-motion estimates in its tested scene,
but that alone does not solve object re-entry after track retirement.
The first memory module deliberately accepts precomputed vectors. It does
not establish which grayscale crop descriptor or score cutoff is reliable.
The user requested a quick Pi re-entry run before a labelled calibration set
exists. The live flag therefore uses explicit provisional settings and an
on-screen restore marker. This is useful for observing the mechanism, not
for claiming that a matching number proves a correct identity.
In the first live trial, a stationary bottle's detection box flickered and its
ID sometimes increased; a person leaving for approximately 3–5 seconds and
returning 2–3 times always received a higher ID. These are user observations,
not yet a timestamped ground-truth dataset. The changed live score cutoff may
recover weaker boxes but could add false positives. Persistent diagnostic
reasons are needed before changing the appearance threshold.
The user subsequently observed that re-entry sometimes succeeds and sometimes
fails. Browser telemetry alone cannot preserve the visual evidence, so the
opt-in trial records both the continuous camera stream and exact detector
input frames with decisions. This is not an exposure-synchronized benchmark.
The 2026-10-23 offline replay with a two-second retry window restores a person
on detector row 51 after row 50 first assigned a provisional new ID. Earlier
ID changes cascade into later numbering, so compare physical continuity by
video, not the literal numbers across runs. Rows 21 and 36 still fail. One
tvmonitor also receives a retry restore; this is not labelled ground truth.
The saved trial has no motion-history samples, so it cannot measure spatial
coverage or evaluate IMU-assisted association.

## Decision log

- 2026-10-22: User authorized implementation after review of trial failures.
  Retain at most four diverse vectors per ID; preserve the first eligible
  anchor and rotate three other slots. Enrollment requires detector confidence
  ≥0.50 and box area ≥60% of the largest accepted area. Similarity ≥0.98
  suppresses duplicate views. These are provisional heuristics; area cannot
  prove crop completeness and a distant object may stop adding new views.
  Matching remains ≥0.85 with a ≥0.05 margin between IDs, using each ID's best
  gallery score. Carry galleries across restores. See REIDENTIFICATION_IMPROVEMENTS.md.
  Defer temporal retries (which revise already-issued IDs), weak-detection
  association (which changes detector/tracker boundaries), learned embeddings
  (new model and CPU cost), and spatial gates (calibration still required).

- 2026-10-23: User requested crowd validation, temporal retries and spatial
  cues. Keep gallery-only as the first live crowd condition. A failed first
  return may hold a visible provisional new ID for a configurable short time;
  a later strong match can revise it. Image motion supplies only a small
  positive ranking bonus for already strong candidates when interval coverage
  is reliable. Unknown/contradictory motion adds nothing. No IMU fusion or
  servo movement is implied. See REIDENTIFICATION_NEXT_TRIAL.md.

- 2026-10-20: Prioritize the missing product behavior over AP tuning. Preserve
  the earlier AP data; remeasure the complete workload after memory exists.
- 2026-10-20: Start with bounded, session-local, explainable appearance
  matching and an abstain path, not an unapproved model download or a claim
  of persistent identity.
- 2026-10-20: Keep appearance-only as the first measurable baseline, then test
  2D image motion and calibrated camera-mounted gyro as separate spatial cues.
  Neither cue identifies a physical object or establishes metric 3D geometry.
- 2026-10-20: Permit a separate, opt-in exploratory live check before score
  calibration because the user requested immediate observation. Do not enable
  memory by default or describe one successful return as validated re-ID.
- 2026-10-21: Preserve inference and matching settings during the next
  diagnosis. Record only under ignored `recordings/` when requested; avoid a
  second camera opener and avoid committing footage of people.

## Outcomes and retrospective

The plan, hardware-independent memory primitive and optional live appearance
path are in place. The default tracker and hardware protocol are unchanged.
Production descriptor and matching thresholds still depend on labelled
positive and lookalike examples; spatial gates additionally depend on
motion/IMU validation.
The new retry and spatial options passed the 117 hardware-independent unit
tests (two optional runtime checks skipped), CLI help and diff whitespace
checks on the Mac. No new live Pi crowd or pan trial has yet been performed.
