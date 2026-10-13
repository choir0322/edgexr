# Worker rates illustration

## Purpose / big picture

Replace the dense timing chart with a standalone learning page: a static flow
diagram and a dynamic, narrated simulation that follows named frames through
capture, motion, detection, independent IMU reads, snapshots and browser delivery.

## Context and orientation

Source policies live in `src/app/live_preview.py`, `src/vision/live_detector.py`,
`src/vision/detect_image.py`, `src/imu/live_reader.py` and
`src/recording/visual_motion.py`. This is teaching material, not a Pi benchmark.
The user requested implementation, placement in `docs/learning`, commit and push.

## Progress

- [x] 2026-10-14: inspect source policies and confirm clean Desktop checkout.
- [ ] Build both modes with readable spacing, source identity and acceptance rules.
- [ ] Verify simulation events, playback, small-screen layout and source links.
- [ ] Review/update `docs/PIPELINE.md` and the learning index.
- [ ] Commit and push the reviewed documentation.

## Plan of work

Use one dependency-free HTML page. Static mode explains sources, stores and
workers; dynamic mode highlights the same flow as a simulated clock advances.
Represent skipped source frames, rejected motion estimates and filtered boxes
as different outcomes. Keep IMU samples distinct from camera frames.

## Concrete steps

Open `docs/learning/edgexr-worker-rates.html` in a browser. Read static mode,
switch to dynamic mode, use Next event, scrub and play/pause. Review frame IDs
in the example JSON response. No hardware, model downloads or network needed.

## Validation and acceptance

Check motion uses the latest frame without a fixed rate; detection starts at
least 500 ms apart; IMU read duration precedes its 50 ms pause. Check startup
warm-up and IMU calibration, rejection examples and different source ages.
Check two modes, keyboard controls, responsive layout and coherent web delivery.
All simulated values and timings must be labelled; map rules to source symbols.

## Surprises and discoveries

The former diagram mixed frame selection, result validity and display freshness.
Those must be taught separately. Snapshot creation happens on a browser request.

## Decision log

- 2026-10-14: use a standalone HTML document for offline opening and GitHub storage.
- 2026-10-14: reuse one spatial layout across modes so changing time does not
  change the learner's mental map. No automatic playback.

## Outcomes and retrospective

Implementation and validation in progress.
