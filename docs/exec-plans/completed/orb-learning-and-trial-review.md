# ORB learning explorer and first foreground-trial review

## Purpose / big picture

User requested a visual learning detour on 2026-11-08, explicitly alongside
foreground-trial review and FPGA purchase research. Build a local HTML page
modeled on hann-fft-explorer: horizontal stage rail, actual image overlays,
minimal interactions, numerical evidence rather than prose-only panels.

## Context and orientation

`SceneMemory.process`, `verify_view`, `spatial_support` define current behavior.
Use already committed small Pi-derived images for the public learning page;
do not publish newly transferred private room/person captures. Compute actual
ORB matches offline in the existing temporary OpenCV environment. Label its
version and the resized example; browser replays data, not a live detector.
The transferred `spatial-foreground-01` has 180 records at revision 729b080,
marked dirty. User tested crossing at left, not center; this is valid in intent.

## Progress

- [x] Review reference layout, skill and source contracts; inspect trial metadata.
- [x] Identify rejected View-2 enrollment (78% excluded; weak_image).
- [x] Record trial results/limits and reconstruction/FPGA decisions.
- [x] Build nine-stage ORB explorer with actual feature/match data.
- [x] Browser-check interactions, local assets, narrow layout and syntax.
- [x] Review PIPELINE and learning source map; prepare scoped commit/push.

## Plan of work

Nine stages: resize, find, describe, remember, compare, reject, geometry,
distribution, decide. One image pair persists; choose real adjacent frames or
an unrelated existing Pi-derived query to show unknown. Actual 256-bit
descriptors, Hamming distance, ratio/mutual filtering, RANSAC inliers and hull/
3×3 occupancy are replayed. Explanatory bit-test cartoons must be marked as
illustrations, not the exact OpenCV sampling coordinates. No runtime algorithm
or matching-threshold changes in this learning task.

## Concrete steps

Run the committed evidence-generation helper, JavaScript syntax/unit checks,
and a local static server for browser inspection. Record exact commands/results
below. No new model/package/hardware installations or purchases.

## Validation and acceptance

Verify all nine controls, Next/Play/Restart, example switch, descriptor display,
accepted/unknown outcomes, and local file assets. Keep explanations tied to
current numerical gates. Trial quality is not summarized as a success rate
without ground truth; lack of a stored left reference must be explicit.

## Surprises and discoveries

The left enrollment was rejected, not silently recognized under another ID.
There were only two foreground-age failures; lack of left reference dominates
interpretation. New footage stays local.

## Decision log

2026-11-08: user adds 3D reconstruction before FPGA, a substantial extension.
Propose calibrated offline sparse reconstruction with translated camera views,
not metric dense room SLAM by pan/tilt alone. Hardware choice and build host
compatibility require research; no purchase made.

## Outcomes and retrospective

Completed 2026-11-08. The explorer replays real computed data for two existing
public image pairs: a known query (349 matches, 337 inliers) and an unknown
query (two surviving matches; geometry explicitly not run). It does not run
ORB in the browser or expose new private trial images. Production thresholds
and runtime behavior are unchanged. Diagram reviewed; unchanged runtime flow,
with links and current/planned boundaries added to PIPELINE and learning guides.

Validation:

- `PYTHONPATH=src /private/tmp/edgexr-scene-memory-env/bin/python -m unittest discover -s tests/unit`: 218 tests passed.
- `node --check docs/learning/orb-scene-explorer.js`: passed.
- New replay-data test checks descriptor XOR distances, filter truth, counts,
  outcomes and referenced image assets. Python documentation contracts passed.
- Browser at a localhost static server: all nine stages, known/unknown example
  selector, Next, Play/Pause, Restart and exact-rule disclosure checked. Actual
  descriptor, geometry and support overlays visually inspected; no console
  errors/warnings. At 390 px width, no document overflow; stage rail scrolls.
- Direct `file://` navigation was denied by the browser tool security policy;
  direct-file interaction is not claimed as tested. The page uses local script
  and image assets without fetch, and localhost loading succeeded.
- No model, package, hardware installation or purchase in this task.

The foreground trial remains a limited measurement, not validation of improved
recognition: left was never enrolled. Its next action remains in the active
spatial-foreground plan. Reconstruction is a proposed bounded sparse endpoint;
dense/live scope and FPGA build/checkout validation remain future work, clearly
separated from completion of this learning/review task.
