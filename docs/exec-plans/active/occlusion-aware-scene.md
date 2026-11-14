# Paired, occlusion-aware scene recognition

## Purpose / big picture

Implement the user-approved clear reference, partial-background revisit, exact
detector/image pairing, finite Remember wait and geometric evidence display.
This repairs the spatial workload's scheduling contract; no new model/hardware.

## Context and orientation

`live_detector.py` owns completed detections; `live_scene.py` owns scene memory
and requests; `scene_memory.py` verifies ORB geometry; `preview.html` displays it.
Images use 1280x720 source and 640x360 ORB coordinates. Host times are not exposure
timestamps. Existing geometric/ambiguity checks remain, with an explicit new
partial-support policy rather than pretending thresholds are unchanged.

## Progress

- [x] 2026-11-09: user reviewed and approved behavior in conversation.
- [x] Pair one latest completed detector result with its source/context.
- [x] Bound enrollment waiting; require clear initial reference.
- [x] Add visible-background support with absolute evidence floors.
- [x] Show source-matched geometry, never paint matches on a newer frame.
- [x] Test failure modes and update PIPELINE / learning source map.
- [ ] Pi crossing/unknown-control validation (requires user hardware run).

## Plan of work

Keep one latest completed package, with maximum age 1.5 seconds. Scene target
remains 1 Hz. Requests use post-click sources only and expire after 8 seconds
waiting, including absent camera/detector or writer admission. Reject enrollment
with any nonempty person mask; ask for a clear background. Do not auto-retry.
Queries retain full references but assess support over visible pixels, with
minimum visible area, absolute hull area and grid-cell floors. Keep match count,
inlier ratio, RANSAC, footprint and ambiguity safeguards.

## Concrete steps

Run focused and full hardware-free tests using the existing temporary OpenCV
environment. Use the new run guide for a fresh Pi recording; never overwrite an
existing recording. No servo commands or dependencies are added.

## Validation and acceptance

Check exact source identity despite newer capture, stale packages, timeouts with
no frames, pre-click rejection, masked enrollment rejection, partial known,
tiny/unrelated/ambiguous unknown, matching coordinates and image-free telemetry.
Browser evidence must clear on stale/error and identify its source age. New
partial policy is experimental until a held-out Pi crossing and unknown control.

## Surprises and discoveries

See SPATIAL_FOREGROUND_REGRESSION.md: freshness phase can starve requests; full
frame support checks reject otherwise matching partial backgrounds.

## Decision log

2026-11-09: exact source pairing selected over widening mismatched-mask age.
Clear enrollment remains stricter than queries. Diagnostic overlay is explicitly
requested; it is bounded and not a new visualization site. Incremental AP cost
is not measured and must not be inferred from correctness tests.

## Outcomes and retrospective

2026-11-14: [Pi run reviewed](../../SCENE_OCCLUSION_RESULTS_01.md): three stored,
exact-source detector pairing, partial-background known and unknown cases, and
zero recording drops. A different-direction interval was unknown. Last samples
were still obscured/unknown; clear return and complete acceptance remain pending.
No matched A/B accuracy or isolated AP CPU comparison was performed. Pipeline
diagram reviewed; unchanged because this is evidence review only.

2026-11-10: implementation complete. All 224 Python tests passed with real
OpenCV 4.11.0; Node browser checks passed. Actual localhost browser fixture using
saved Pi pixels plus artificial occlusion displayed green inliers, amber mask,
exact query/reference panels and source age. Real POST showed pending then
expired with the button enabled again. No Pi enrollment/recognition result is
claimed from that fixture. [Run guide](../../SCENE_OCCLUSION_RETEST.md) includes
Pi launch, Mac tunnel/preview and SCP. Active plan remains open for Pi acceptance.
