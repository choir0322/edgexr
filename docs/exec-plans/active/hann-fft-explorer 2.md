# Interactive Hann–FFT explorer

## Purpose / big picture
Explain the real patch_shift calculation through a stable workflow map and
eleven inspectable stages, borrowing the worker-rates page's static/dynamic
navigation. No camera, detector or IMU behavior changes.

## Context and orientation
Source: docs/learning/HANN_FFT_WALKTHROUGH.md and
src/recording/visual_motion.py::patch_shift. Use recorded frames 313/316 and
their existing 80×56 teaching patch, not a synthetic replacement.

## Progress
- [x] 2026-10-15: inspect reference design and estimator.
- [ ] Build offline numerical dataset and explorer.
- [ ] Check numeric results, navigation and layout.
- [ ] Review docs/PIPELINE.md and update learning links.

## Plan of work
Export reference arrays; build stable stage navigation with focused numerical
inspections; verify outputs against patch_shift; link the lesson.

## Concrete steps
Open docs/learning/hann-fft-explorer.html locally. Use Overview to orient,
then Step through to inspect one computation at a time. No server or downloads.

## Validation and acceptance
Check shapes/units, FFT sign, wrapped indices, quality and subpixel output.
Exercise every stage and selected-pixel/frequency/displacement controls.
Review source links and retain existing scheduling/freshness semantics.

## Surprises and discoveries
Finite checks follow float conversion in actual code. Nine patches sample the
frame rather than exhaustively partitioning it.

## Decision log
2026-10-15: use precomputed NumPy arrays with browser scalar inspections rather
than adding an FFT dependency. Explain this boundary explicitly. No CDN.

## Outcomes and retrospective
Pending implementation and validation.
