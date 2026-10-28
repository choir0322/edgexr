# Recorded visual scene memory

## Purpose / big picture

Implement the approved next spatial milestone: remember view A, observe another
view, and recognize A when it returns. Begin with explicitly selected reference
and query frames from existing Pi recordings. A bounded memory returns a known
view or unknown with diagnostics. This directly advances surroundings awareness.

## Context and orientation

The Pi already has OpenCV 4.11 and NumPy. Reuse ORB image features, Hamming
descriptor matching and RANSAC homography verification. This first tool is
offline, has no camera/servo access, and does not alter live worker scheduling.
The input is a local recorded video; selected frames become 640×360 grayscale.
The IMU integration and visual angle correction remain separate at this stage.
The user approved the roadmap and implementation sequence on 2026-10-29.

## Progress

- [x] Inspect existing capture, matching conventions and recorded Pi inputs.
- [x] User approved a temporary Mac OpenCV environment for actual runtime tests.
- [x] Implement bounded feature memory and conservative geometric verification.
- [x] Implement chronological reference/query replay with new output folders.
- [x] Test returns, different views, weak evidence, ambiguity and eviction.
- [x] Exercise the tool on transferred Pi footage; label development results.
- [x] Review/update docs/PIPELINE.md and the scene-memory learning guide.
- [x] Provide a repeatable Pi command and review the implementation for commit/push.
- [x] Validate the replay on the Pi: enrolled A → unknown → known A.
- [x] Validate on a separate recording without threshold changes: combined-motion-01,
  A=2, queries 7/13, enrolled → unknown → known. Same room, not broad accuracy.
- [x] Add opt-in latest-frame live recognition, explicit enrollment and timestamped
  preceding-IMU orientation context; preserve unknown/stale/error behavior.
- [x] Test concurrency boundaries, enrollment, freshness and missing orientation;
  update pipeline/source guide and provide Pi commands.
- [ ] User validates the live behavior on the Pi; full AP measurement deferred.
  First transferred live log analyzed: 139 observations, 1.00 Hz, View-1 known
  after unknown periods. Physical movement confirmation remains pending, and
  52.67°/73.85° quaternion differences at two known observations are unresolved.
  See docs/LIVE_SCENE_RESULTS.md. No threshold change; diagram/source guide
  reviewed unchanged because this stage records evidence only.

## Plan of work

1. Extract bounded image features and compare all stored views (small fixed
   capacity). Reject too few matches, concentrated support, poor geometry and
   competing near-equal candidates. Unknown never automatically creates a view.
2. Explicit reference enrollment creates a session-local scene ID; matched
   queries refresh recency. Evict the least-recently-used view at capacity.
3. Replay user-selected times in chronological order, retaining requested and
   actual decoded video times. Do not let a future reference answer an earlier
   query. Write report and selected images only under ignored recordings/.
4. Test real OpenCV on synthetic transforms and existing Pi footage. Save
   small derived findings; actual images and descriptors remain outside Git.

## Concrete steps

The CLI will be `PYTHONPATH=src python3 -m spatial.scene_revisit VIDEO
--reference A=2 --query 7 --query 13 --output recordings/scene-revisit-01`.
Times are seconds from decoded video start, not servo cue times. Select times
from the actual clip. Output directories must be new. See the final run guide
for a checked example and interpretation; no new hardware movement is required.

## Validation and acceptance

Require a transformed A to retrieve A, an unrelated textured image and a blank
frame to return unknown, duplicate references to produce ambiguity, capacity
and monotonic timestamps to remain enforced, and existing output to be preserved.
Real-footage results are development evidence, not held-out recognition accuracy.
Log all thresholds and runtime versions; AP measurement is deferred. Confirm the
pipeline accurately separates offline scene recognition from live orientation.

## Surprises and discoveries

Mac Python lacks OpenCV although the Pi runtime already has it. An isolated
temporary environment is approved; existing Python installations remain intact.
The recorded `combined-motion-02` clip supplies an inspected A → B → A example
at about 2, 7 and 13 seconds. With thresholds chosen before this replay, the
turned-away view had seven matches and was rejected; the return had 324
geometric inliers across six cells. This is development evidence only.
A second replay taught B too; a later overlapping B view at 7.529 s had only
11 usable matches and remained unknown. Final A retrieval still succeeded.
Retain this coverage limitation without tuning against the same clip.
The repository-wide docstring/type audit reports existing violations in older
modules; audit the new files independently rather than expand this task into
an unrelated code cleanup.

## Decision log

- 2026-10-29 diagnostic extension: user confirmed repeated visible returns and
  not intentionally ending away. Preserve thresholds; opt-in canonical PNGs
  for every analyzed query and enrollment, with reference filenames in JSONL.
  Require a 10–600 s timer to bound this diagnostic capture. No motor commands.

- 2026-10-29: Live integration uses a target 1 Hz latest-frame worker and explicit
  browser enrollment, unchanged visual thresholds. Store preceding orientation
  within 200 ms of host frame receipt, not exposure pose; never correct gyro
  or reject visual matches based on drifting orientation. Optional non-image
  JSONL records preserve decisions and timestamps. New full-resolution pipe
  workload also applies without object detection; AP cost remains unmeasured.

- 2026-10-29: Begin with explicit reference enrollment. A failed match means
  unknown, not proof of a new place. Continuous automatic enrollment and IMU
  candidate ranking follow a successful recorded-input check.
- 2026-10-29: A homography verifies image correspondence but supplies no metric
  camera angle, depth or position. Require spatially distributed support to
  reduce false recognition from a small moving foreground object.

## Outcomes and retrospective

Image-backed Pi trial analyzed: 180 images/rows, all 56 post-enrollment unknown
frames visually reviewed, 31 few-matches / 24 concentrated-support / one
geometric rejection. Last 13 queries known; prior final unknown not reproduced.
See docs/LIVE_SCENE_IMAGE_RESULTS.md. Next: multiple distinct explicit reference
views, unchanged thresholds. Orientation accuracy unresolved. Pipeline and
learning guide reviewed unchanged because this is evidence-only work.

Image diagnostic extension: 176 tests passed, including pixel-exact saved PNG
comparison with the canonical ORB input. A ten-second synthetic live run stopped
automatically and saved ten JSONL rows linked to ten PNGs. Changed Python files
passed contract checks. Pipeline/source guide updated; real Pi diagnostic pending.

2026-10-29 live extension: separate-recording A → B → A passed without changes
to MemoryConfig. Implemented target-1-Hz worker, explicit same-origin enrollment,
preceding-IMU context, stale/error status and optional non-image JSONL. Added
mailbox, temporal association, actual ORB logging, HTTP origin and output
preservation tests. Full suite: 175 tests passed; changed Python files passed
the function-contract audit. Synthetic FFmpeg browser smoke verified empty memory,
button enrollment, later unknown results and telemetry updates without hardware.
Current pipeline/source map updated. Pi live recognition/orientation acceptance
is still pending; no actual motor, camera or IMU was operated on the Mac.

The offline module and CLI are implemented. The full suite ran 170 tests with
one skip, including actual OpenCV scene tests in the approved temporary Mac
environment. The live path is unchanged; the pipeline now depicts the separate
offline branch. The [run guide](../../SCENE_MEMORY.md) includes the Pi replay
command and output transfer. Pi reproduction succeeded on the same clip:
320/388 return matches were geometric inliers across six cells. Isolated
event compute was 90.87/56.60/110.06 ms; full AP metrics remain deferred.
The reported working tree was dirty, so preserve that provenance limitation.
Held-out scenes and live integration remain pending. No camera, IMU or motor
was operated during development. Diagram and learning guide reviewed;
unchanged because this records evidence, not a pipeline change.
