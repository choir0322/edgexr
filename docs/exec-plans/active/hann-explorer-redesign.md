# Simplify the recorded Hann/FFT lesson

## Purpose / big picture

Follow the same two recorded Pi frames through eight visible stages. Keep the
actual patches, Hann map, FFT maps, correlation surface and acceptance rules
while removing controls that distract from the computation.

## Context and orientation

`docs/learning/hann-fft-explorer.html`, its JavaScript and new CSS display
precomputed arrays from `images/hann-fft-data.js`. The images come from the
user's recording. `src/recording/visual_motion.py` remains the reference for
the estimator; the browser replays its computed results.

## Progress

- [x] User approved the proposed visual pipeline and reduced interaction.
- [x] 2026-10-18: Implement one eight-node thumbnail route, shared Play/Next/
  Restart, and one accepted/rejected recorded-example selector.
- [x] Preserve original/centered/weighted patches, before/after seams, magnitude
  and phase maps, normalization, inverse FFT, refinement and consensus.
- [x] Update the walkthrough and image-motion guide. Diagram reviewed; unchanged
  in `docs/PIPELINE.md` because no live worker, timing or estimator changed.
- [x] Check recorded numerical outcomes and navigation using the local harness.
- [ ] Visual browser review: Computer Use permission is unavailable in this session.

## Plan of work

1. Make the complete structure visible with thumbnails of the actual data.
2. Give each selected stage one focused image-based explanation, with exact
   validation and source references in its details.
3. Remove sliders and duplicate navigation; compare Hann and alignment states
   side by side. Keep the recorded rejection example as the single optional
   scenario change.
4. Check both pairs and ensure only reliable whole-image results draw arrows.

## Concrete steps

Open the local HTML. Play visits all eight stages and stops; Next pauses and
advances once; Restart returns to the inputs. Select any stage directly. The
example selector retains the current stage while replacing all recorded data.
Run `node tests/learning/test_hann_explorer.cjs` and `git diff --check`.

## Validation and acceptance

Tests check real image dimensions, strongest correlation peaks, eight versus
three agreeing patches, reliable/unreliable State fields, changed Hann pixels,
changed alignment pixels, all navigation, playback completion and tab-hide
pause. DOM doubles cannot verify visual layout. The lesson must state that
displacements are analysis pixels per processed pair, and that FFT magnitude
images alone do not encode the phase comparison used for estimating motion.

## Surprises and discoveries

The wider-spaced pair has a strong individual patch peak yet fails whole-frame
consensus. Retaining that example teaches why peak quality alone is insufficient.

## Decision log

- 2026-10-18: Keep patch 8 fixed for detailed arithmetic; show all nine measured
  votes at consensus. Removing patch-selection buttons prevents suggesting that
  every selected region has corresponding detailed FFT arrays in the page.
- 2026-10-18: Preserve generated data and source estimator; simplify only the
  presentation and interactions. No network, model or video regeneration needed.

## Outcomes and retrospective

Implemented locally. Numerical/interaction checks pass; visual browser review
remains pending because Computer Use permission was denied. No commit or push.
