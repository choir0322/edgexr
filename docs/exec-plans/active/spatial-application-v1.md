# Spatial Application v1 handoff

## Purpose / big picture

Package the existing bounded spatial application into one reproducible profile
and short acceptance demo. Directly advances application completion before AP
optimization; no new vision algorithm or physical control is authorized here.

## Context and orientation

`app.live_preview` already connects `LiveScene`, `ViewMap`, `LiveImu`, relative
orientation and `SceneRecorder`. The Pi 4 uses the existing monochrome camera
and camera-head IMU mounting. See `docs/SPATIAL_APPLICATION_V1.md` for exact
commands, safety limits, scope, source policies and an evidence template.

## Progress

- [x] 2026-11-05: Review implemented flags, freshness, orientation and recorder contracts.
- [x] 2026-11-05: Define one 180-second image-backed, detector-off profile and demo.
- [x] 2026-11-05: Link existing component evidence without claiming a new Pi pass.
- [x] 2026-11-05: Review pipeline and learning source guide; no data-flow change.
- [x] 2026-11-05: All 191 unit tests passed in 5.296 s on Mac (OpenCV 4.11.0);
  guide links resolve and `git diff --check` passes. Not a Pi benchmark.
- [x] 2026-11-05: Inspect transferred run and images; verdict needs investigation:
  three views, partial recorder (eight drops), 878.9 ms IMU gap, dirty provenance.
- [ ] Diagnose scheduling pause and recording backpressure, then repeat affected checks.
- [x] 2026-11-05: Pi status follow-up shows two untracked result summaries and
  no tracked diff; this explains how dirty can be true without code edits.
  Historical state not independently proven; retain flag, proceed with profiling.
- [ ] Freeze accepted revision/profile and hand off to a separate spatial AP baseline.

## Plan of work

Documentation-only packaging: reuse working CLI and measured components, expose
the final evidence gap, run regressions, then ask for one concise live demo.
Do not repeat previous calibration or change recognition thresholds.

## Concrete steps

Follow `docs/SPATIAL_APPLICATION_V1.md` for Pi launch, Mac tunnel/browser, output
inspection and SCP. Use a new recording directory each time. Run local unit
tests with `PYTHONPATH=src python3 -m unittest discover -s tests/unit -v` using
an existing environment with NumPy/OpenCV; no silent dependency installation.

## Validation and acceptance

The guide's six-row checklist governs packaged acceptance. Include actual
scene, software and camera mode; existing hardware is Pi 4, passive heatsink,
no fan, but record actual setup rather than assuming it stayed unchanged.
Missing or partial final evidence is not a clean pass. Unknown/stale fault
contracts are checked in unit tests, not by unsafe live disconnects. Review
pipeline inputs/shapes/units/scheduling and source links. AP baseline deferred.

## Surprises and discoveries

All six requested features already exist. README still called Pi three-view
validation the next step despite newer evidence; update that stale guidance.

## Decision log

- 2026-11-05: Use the existing CLI as the configuration, not a new wrapper or
  duplicate config parser. Detector remains off; images enabled to review misses.
- 2026-11-05: Separate computer-systems contributions from AP measurements.
  Ready gyro context is not guaranteed angular accuracy.

## Outcomes and retrospective

Profile and acceptance procedure defined. Packaged run reviewed in
`docs/SPATIAL_V1_ACCEPTANCE_RESULTS.md`; acceptance blocked by continuity/loss
with provenance follow-up documented (untracked summaries, no current tracked
diff). Leave plan active. No thresholds relaxed. The user prioritizes
AP performance over general systems extension; investigate this concrete
failure first. Pipeline and learning map reviewed; diagnostic evidence only,
no new data flow. Raw recordings remain private.
