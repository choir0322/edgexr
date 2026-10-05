# Optional live object detection

## Purpose / big picture

Show labelled boxes alongside camera motion and IMU readings. Target two
detections/second and measure the combined workload on Pi 4.

## Context and orientation

Saved-frame baseline: median 195.90 ms total on Pi 4/OpenCV 4.11.0, two threads.
The table and left chair were detected; the right chair was missed. Existing
preview analyzes 320x180 motion near 30 fps. See DETECTION_RESULTS.md.

## Progress

- [x] Inspect current preview and saved-frame detector.
- [x] Add optional worker, UI, tests and instructions.
- [x] Local suite: 48 tests, 46 pass, two environment skips. Synthetic 720p
  pipe/fake detector and browser state checks pass. Patch checked before handoff.
- [ ] Measure real Pi combined performance and inspect browser boxes.

## Plan of work

With --detect, decode 1280x720 grayscale to Python and resize for the existing
motion worker. Keep one latest full frame for a separate detection worker.
Start inference at most every 0.5 seconds; skip intermediate frames and never
queue a backlog. Reuse saved-frame preprocessing and box parsing. Publish source
frame age and completion rate. Hide boxes on stale data, camera or detector error.

## Concrete steps

Follow docs/LIVE_DETECTION.md: stop preview, pull reviewed changes, run tests,
restart with --imu --detect, then observe still/turn/return for a minute.
No new dependencies or model downloads; use the already-tested assets.

## Validation and acceptance

Tests cover independent latest-frame storage, rate limiting, overload skipping,
stale/error suppression and valid empty detections. Existing preview tests must
pass. Pi acceptance: meaningful boxes while still, visible age/rate/cost,
camera and IMU continue, and no unbounded delay during motion. Report skipped
frames and rates; 30 fps is a measurement target, not a guarantee.

## Surprises and discoveries

The existing FFmpeg pipe carries only 320x180 gray. Detection mode must increase
it to 1280x720 to retain baseline input detail. Python now does motion resizing;
the changed path adds overhead even between detector runs.

## Decision log

- 2026-10-05: Explicit --detect; disabled mode keeps the old camera path.
- 2026-10-05: OpenCV CPU with two threads, fixed 0.5 confidence, 2 Hz target.
- 2026-10-05: Source age uses frame receipt on Pi, not exposure time. Hide boxes
  after 1.5 seconds or camera failure; current frames can differ from box frames.
- 2026-10-05: No tracking or IMU-based compensation; expose lag honestly.

## Outcomes and retrospective

Implementation and local checks complete. Pi performance remains to be measured.
