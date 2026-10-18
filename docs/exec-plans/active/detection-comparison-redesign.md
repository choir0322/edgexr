# Simplify the convolution comparison lesson

## Purpose / big picture

Replace eleven control-heavy scenes with an immediately visible side-by-side
comparison of standard convolution and depthwise plus pointwise convolution.
The user approved this layout and requested explicit channel/kernel/filter
grouping before implementation. Keep a compact MobileNet-to-SSD continuation.

## Context and orientation

The local lesson uses `docs/learning/detection-architecture.html`, its CSS and
JavaScript, and existing saved Pi image/sample assets. The three input channels
contain identical grayscale values. The fixed teaching example has 4×4 input,
3×3 kernels, stride one, no padding, and two output channels. Following the
user's addition, illustrative biases are enabled: two standard, three depthwise
and two pointwise biases, each reused across its output channel. The actual
MobileNet backbone has convolution bias disabled. Its
illustrative weights are not actual network parameters.

## Progress

- [x] User reviewed and approved the side-by-side design and requested explicit
  channels, kernels and filters.
- [x] 2026-10-18: Implement grouped filters, channel lanes, intermediate maps,
  shared playback, calculations and compact SSD overview.
- [x] Update the object-detection study guide. Diagram reviewed; unchanged in
  `docs/PIPELINE.md` because the live processing, workers and rates are unchanged.
- [x] Check known convolution outputs and playback/selection/restart behavior.
- [ ] Visual browser review: Computer Use reports permissions are not granted.

## Plan of work

1. Use one fixed three-input/two-output teaching example on both sides.
2. Make the standard filter's three spatial kernels distinct from three
   independent depthwise kernels and two 1×1×3 pointwise filters.
3. Synchronize select, multiply, sum, pointwise mix and output-write stages.
4. Update local checks and source guide; report any visual verification limit.

## Concrete steps

Open `docs/learning/detection-architecture.html` locally. Both routes are visible
without pressing a button. Play advances through four output positions; Next
step pauses and advances once; Restart clears the output maps. Filter selection
pauses playback and changes the shared calculation panel; Enter/Space support
keyboard selection. Narrow screens stack the two routes.

Run `node tests/learning/test_detection_ui.cjs`,
`node tests/learning/test_detection_math.cjs`, and `git diff --check`.

## Validation and acceptance

Hand-calculated fixtures check spatial sums and pointwise weighted sums.
Interaction checks exercise both SVG routes, keyboard selection, pause,
completion, replay, reset and tab-hide pause. They do not verify browser layout.
Only three transport buttons remain. Actual model details distinguish stored
weights from repeated operations and describe the initial standard convolution.

## Surprises and discoveries

The saved sample already provides a small real-image grid; subsampling it keeps
the example tied to the Pi while avoiding new assets or model execution.
Browser automation could not run because Computer Use permission was denied.

## Decision log

- 2026-10-18: Keep existing standalone detection math helpers and their tests;
  the simplified lesson only needs its small fixed convolution calculation.
- 2026-10-18: Preserve real saved detection boxes in the SSD continuation and
  explicitly label schematic feature maps and illustrative weights.

## Outcomes and retrospective

The page is implemented and local interaction/arithmetic checks pass. Visual
layout needs a human browser review. No live detector code changed; no commit
or push was performed during this redesign.
