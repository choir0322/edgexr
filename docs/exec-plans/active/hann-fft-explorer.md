# Recorded image-motion website

## Purpose / big picture
Trace the user's recorded Pi images horizontally through the actual motion
pipeline: grayscale analysis frames, nine sampled patches, one detailed Hann
and Fourier calculation, nine-patch consensus, State, and the browser display.
The user can replay two recorded pairs and see why one publishes an arrow and
the other does not.

## Context and orientation
Source: docs/learning/HANN_FFT_WALKTHROUGH.md,
src/recording/visual_motion.py::patch_shift/image_shift, and
src/app/live_preview.py::analyze_latest/State. The local source recording is
combined-motion-02/camera.mkv; the repository stores only derived teaching
images and numerical intermediates. Pair 313→316 is the documented large
shift; pair 313→314 is an adjacent recorded pair that passes consensus.

## Progress
- [x] 2026-10-15: inspect reference design and estimator.
- [x] Build offline numerical dataset and explorer.
- [x] Check numeric results and navigation; review responsive CSS.
- [x] Review docs/PIPELINE.md and update learning links.
- [x] 2026-10-16: replace the earlier text-heavy page with the recorded pipeline.
- [x] 2026-10-16: verify two-pair calculations, controls and offline assets.
- [x] 2026-10-16: review docs/PIPELINE.md and update the learning guide.
- [ ] Browser visual QA: browser automation is not permitted in this environment;
  open locally at desktop and narrow viewport before calling layout verified.

## Plan of work
Generate compact derived assets for both recorded pairs. Build one stable
horizontal stage rail with step/play controls. Make each stage visibly transform
the recorded images. Verify calculations and playback, then link the lesson.

## Concrete steps
Open docs/learning/hann-fft-explorer.html locally. Pick an adjacent reliable
pair or the larger walkthrough pair, then use stage buttons or Play. No server,
model, camera or network connection is needed.

## Validation and acceptance
Check decoded-image provenance, 320×180/80×56 shapes, FFT sign, wrapped
indices, quality/subpixel results, nine-patch consensus, and replayed State
status. Exercise both pairs and every stage/control. Review source links and
retain existing scheduling/freshness semantics.

2026-10-15 results:
- `node --check docs/learning/hann-fft-explorer.js`: pass.
- `node tests/learning/test_hann_explorer.cjs`: all eleven stages, selected
  pixel, candidate peak, Y refinement, mode/play controls and five inverse-DFT
  candidate scores pass. DOM doubles exercise logic, not browser rendering.
- Python recomputation from saved A/B arrays matches the full correlation
  surface and actual patch_shift result within absolute tolerance 1e-12.
- Local HTML links exist; `git diff --check` passes.
- Browser visual inspection could not run: browser inventory was empty and
  native Chrome access returned "Computer Use permissions are not granted".
  Open locally and check at desktop/mobile widths before calling layout verified.
- docs/PIPELINE.md reviewed unchanged: this lesson adds no worker, changes no
  shapes/units, scheduling, freshness or live data flow. Source links identify
  patch_shift and image_shift without fragile line numbers.

2026-10-16 revision checks:
- `python3 scripts/build_hann_fft_lesson.py --video .../camera.mkv` recreates
  the same data bytes as the archived decoded-frame input (SHA-256
  `fe45ce6f1d554c0b551546cab750382f61c29128ed00dd67e8f7985ea1650248`).
- `node --check docs/learning/hann-fft-explorer.js` and
  `node tests/learning/test_hann_explorer.cjs` pass. The DOM test covers all
  eight stages, pair switching, Hann control, peak choice, consensus and
  reliable/unreliable State replay. It validates the local PNGs and scripts.
- `PYTHONPATH=src python3 -m unittest discover -s tests/unit -v` passes:
  48 tests, two environment-dependent skips.
- Actual generated frames 313 and 316 were inspected and show the recorded
  screen scene. Browser visual QA is still outstanding; the computer-use
  interface returned "Computer Use permissions are not granted."
- docs/PIPELINE.md remains correct: the lesson is offline and changes no live
  worker paths, rates, timestamps or reliability rules.

## Surprises and discoveries
Finite checks follow float conversion in actual code. Nine patches sample the
frame rather than exhaustively partitioning it.

2026-10-16: patch #8 of frames 313→316 has Q=51.93 and dx=-12.63, but
image_shift() returns None because fewer than four patches agree within 1.5
pixels of the median. Adjacent frames 313→314 pass with eight agreeing patches
and image shift (-3.5971,+0.0177). The website must show these distinct outcomes.

## Decision log
2026-10-15: use precomputed NumPy arrays with browser scalar inspections rather
than adding an FFT dependency. Explain this boundary explicitly. No CDN.

2026-10-16: preserve the exact walkthrough pair and add an adjacent successful
pair. Playback is an offline replay of calculations, not a captured live State
snapshot. Store no camera.mkv in Git.

## Outcomes and retrospective
The page now makes the user's recorded frame pair the continuous visual input,
lets the learner manipulate Hann weight and candidate displacement, and shows
why a high-quality patch need not become a whole-image result. Its numerical
replay is checked against source code and recording. A manual browser-width
review remains before moving this plan to completed.
