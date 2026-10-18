# Explain SSD in the existing detection lesson

## Purpose / big picture

Extend the approved detection-architecture.html design so a learner can trace
one default box through class/offset prediction, decoding and filtering, then
see how proposal-based detection differs. Use the existing Pi image and dark,
minimal visual style. Explain why MobileNet-SSD is a practical measured Pi
baseline without claiming it outperforms untested alternatives.

## Context and orientation

The convolution comparison already works. The SSD section currently has four
static cards. `detection-math.js` contains tested graph-specific prior/decode/NMS
helpers; `images/detection-lesson-data.js` contains real saved final detections.
The graph has six feature scales and 1,917 priors. Intermediate teaching
predictions are illustrative; this page does not run the pretrained network.

## Progress

- [x] 2026-10-18: User reviewed the SSD trace design and requested a proposal-
  based contrast while retaining the existing structure and design.
- [x] Read current HTML/JS, math tests, source guide and primary model papers.
- [x] Build the SSD stage view and compact Faster R-CNN comparison.
- [x] Verify arithmetic, all scale/prior combinations, six-stage navigation and
  independent existing convolution controls using a local document double.
- [ ] Verify browser rendering and layout: Computer Use Accessibility/Screen
  Recording permission was unavailable, so visual verification remains pending.
- [x] Review `docs/PIPELINE.md` and update the object-detection learning guide.

## Plan of work

Keep the top comparison intact. Replace the SSD overview with a six-stage
stepper and one shared image/detail panel. Show six grid choices, priors at a
selected location, class scores plus four offsets, decoded geometry, score/NMS
decisions and source-pixel mapping. Add two compact architecture paths and a
small card linking actual Pi baseline numbers. Keep details behind disclosure
controls; avoid unrelated sliders or playback that implies inference timing.

## Concrete steps

Edit the HTML/CSS and add a focused `detection-ssd.js` module using the existing
math helpers. Run `node tests/learning/test_detection_math.cjs`, JavaScript
syntax checks, `git diff --check` and browser interaction/layout checks. Open
the same local HTML file; no server or downloaded dependency is required.

## Validation and acceptance

All six stages and scale/prior selections update the graphic and numbers.
Background, low scores, same-class NMS and the app cutoff are distinguished.
Illustrative predictions stay separate from saved measured detections.
Default priors are not described as proposals or image crops. Faster R-CNN
shares backbone features; its RoI stage does not rerun a full backbone on each
image crop. Existing convolution playback remains functional. The Pi claim
links the real run, with its settings and limitations. Review the runtime
pipeline diagram and state whether any execution path changed.

## Surprises and discoveries

The older math module already models this graph's three/six priors per cell
and CENTER_SIZE decoding. It can support the new lesson without new packages.
Native Chrome is present but browser automation surfaces were unavailable and
Computer Use reported missing permissions. No browser screenshot/layout claim
is based on the document-double test.

## Decision log

- 2026-10-18: Use Faster R-CNN as one concrete proposal-based comparison;
  distinguish architectural motivation from an unmeasured Pi speed ranking.
- 2026-10-18: Keep static structure visible and reveal one computation at a
  time. Use the saved Pi photograph for overlays and schematic feature grids.

## Outcomes and retrospective

Implemented the six-stage lesson, exact prior geometry and decoding, illustrative
class scores/filtering, measured final result, proposal-based comparison and Pi
baseline context. The original convolution comparison retains its controls and
design. `test_detection_math.cjs` and `test_detection_ssd.cjs` pass, along with
JavaScript syntax and diff checks. Browser visual verification remains pending.

Diagram reviewed; unchanged: the lesson executes locally in the browser and
adds no inference worker, runtime threshold or scheduling change. The guide
now names `detection-ssd.js` and distinguishes its illustrative state from
real saved Pi detections. Changes are ready for review; no commit/push made.
