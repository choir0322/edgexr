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

Open `docs/learning/edgexr-worker-rates.html` in a browser. Read static mode
left to right, switch to dynamic mode, walk the checkpoints with ◀/▶ (or the
←/→ keys), scrub and play/pause. Review frame IDs in the example JSON response.
No hardware, model downloads or network needed.

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
- 2026-10-14: lay the five stages out left to right (sources, capture, workers,
  snapshot, delivery) and trim node prose; below 1100 px the page falls back to
  one vertical column. Static policy lists keep only the acceptance thresholds.
- 2026-10-14: slow playback from 0.1× to 0.025× real time so one 40 ms motion
  job fills 1.6 s on screen (full run 72 s). Replace one-way "Next checkpoint"
  with ◀/▶ step arrows, a step counter, ←/→ keys and an outline on the node
  each checkpoint describes. Removed the footer link to the nonexistent
  `WORKER_RATES.md`. `docs/PIPELINE.md` reviewed; unchanged, because this is a
  presentation change and the simulated data flow and timings are the same.
- 2026-10-14: redraw as a directed graph in one SVG (`NODES`/`EDGES` in
  viewBox units): small circular nodes, curved labelled edges, details hidden
  until a node is hovered/focused (or clicked to pin). Rate nodes (camera,
  motion, detector, IMU reader, browser) show a circular progress ring: blue
  while working, orange during a deliberate wait. Edges animate briefly at
  handoffs. Narrow screens scroll the graph sideways instead of reflowing.
  Diagram reviewed; `docs/PIPELINE.md` unchanged for the same reason as above.
- 2026-10-14: force a dark theme (`color-scheme:dark`). Playback now loops
  from 1800 ms back to 0 until paused, so the Restart button was removed.
- 2026-10-14: add three focus modes (`FOCUS`), each with its own choices.
  Branch (horizontal): Motion, Detection or IMU path, source to browser; only
  edges inside the path stay lit. Stage (vertical): Sources, Capture, Workers,
  Snapshot or Delivery, shown with a column band plus the edges in and out.
  Worker: one node with its direct edges. Unfocused parts dim in place; edge
  far-ends show at half strength. While a focus is active, ◀/▶ visit only
  checkpoints about focused nodes ("Focused n / m"); "All" restores the normal
  13-step walk. A focus with no checkpoints (e.g. Sources) falls back to all.
- 2026-10-14: move all controls into a sticky left panel (View, Focus,
  Walkthrough) beside the graph so focus and stepping never need page
  scrolling; the title, legend and timing note sit in the right column. Checked
  to fit a 1440×820 window in Worker mode (the most chips). Below 1000 px the
  panel stacks above the graph.

## Outcomes and retrospective

Implementation and validation in progress.
