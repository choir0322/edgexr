# First live object IDs

## Purpose / big picture

Give each visible detector box a small, session-local numeric ID and keep that
ID when a matching box appears in the next detector update. In the SSH preview,
  the user should see labels such as `#3 person` that usually remain stable while
the object stays visible. This is a first tracking baseline, not recognition of
an object after it leaves view and not camera/IMU fusion.

## Context and orientation

`src/app/live_preview.py` captures frames, runs image-motion analysis and
combines latest results in `State.snapshot`. `src/vision/live_detector.py`
selects the newest 1280x720 grayscale frame for MobileNet-SSD at a target of
two starts per second. `DetectionState.publish` stores boxes with tracker IDs,
and `src/app/preview.html` draws those boxes with provisional ID labels. The
detector may miss an object;
boxes can be 260–800 ms old in the user's first live observation and are hidden
after 1.5 seconds. The IMU path is independent. No new model, dependency, servo
action, hardware setting or capture protocol is needed.

The working assumption for this first milestone is that a box with the same
class and enough overlap on the next detection update probably represents the
same object. It can fail when the camera turns quickly, objects cross, a box
jumps, or detections are missed. We must measure and report those failures,
not describe the ID as a proven real-world identity.

## Progress

- [x] 2026-10-17: Inspect current detection, browser, roadmap and documented
  Pi observations; define a bounded first milestone.
- [x] 2026-10-17: User approved proceeding from this plan with a check-in after
  each numbered step.
- [x] 2026-10-17: Implement the hardware-independent box matcher and track
  lifetime rules. Seven focused unit tests passed; no live wiring yet.
- [x] 2026-10-17: Own `BasicTracker` inside the sequential detector worker and
  attach IDs before publication. A synthetic worker test confirms ordered IDs,
  empty-update aging and unchanged input records. Pausing for the user's
  step-by-step review before browser labels.
- [x] 2026-10-17: Display provisional IDs in browser labels without changing
  capture, motion or IMU scheduling. A focused browser-script test checks
  label fallback, right-edge placement and stale/error suppression.
- [x] 2026-10-17: Review/update `docs/PIPELINE.md` and
  `docs/learning/OBJECT_DETECTION.md` for shapes, units, matching policy,
  clocks, rates, freshness, failure behavior and named code symbols. Add the
  tracker arrow now that it is truly in the worker; update the browser node and
  label explanation after adding the display.
- [x] 2026-10-17: Run and inspect local tests for this handoff: 57 unit tests
  passed, two optional-environment tests skipped; the focused browser-label
  and tracker-lesson JavaScript checks passed. No Pi observation yet.
- [ ] Hand off a Pi smoke test and results template after browser labels are
  implemented; record the Pi observation before declaring hardware acceptance.

## Plan of work

1. Create a small pure-Python tracker module in `src/vision/`. For each new
   detection result, associate boxes only with active tracks of the same class
   by intersection-over-union (IoU). Make one-to-one matches in descending IoU
   order above an explicit threshold. Increment a track's missed-update count
   when unmatched; retire it after a small bounded number of missed updates.
   New detections get monotonically increasing IDs that are not reused during
   one run. An empty valid detector result is still an update. Keep unmatched
   tracks internal; display only current detections, so there are no ghost boxes.
2. Own the tracker in the existing sequential detection worker and attach IDs
   before `DetectionState.publish`. This preserves source sequence and host
   receipt time. A detector error still hides boxes; camera and IMU continue.
   The tracker should hold only bounded metadata, never past image bytes.
3. Add `#ID` to preview box labels and a short explanation of the ID's scope.
   Retain the existing 1.5-second source-age cutoff and two-Hz target.
4. Add synthetic unit cases for overlap, different classes, multiple objects,
   competing matches, misses, empty detections, expiry, ID non-reuse and a
   camera-shift counterexample. Run the existing detection/preview tests too.
5. Update the live pipeline diagram and object-detection guide in the same
   change; document an SSH-only Pi observation protocol without changing the
   existing benchmark protocol.

## Concrete steps

After plan review, implement one focused code change, then run on Mac:

```bash
cd /Users/ryanchoi/Desktop/edgexr
PYTHONPATH=src python3 -m unittest discover -s tests/unit -v
git diff --check
git diff
```

This session's sandbox may forbid unit tests that create temporary directories
under Desktop `recordings/`; if so, identify those environment errors separately
and re-run the complete suite in a writable checkout or on Pi. Do not change
test semantics merely to disguise a filesystem restriction.

After review and push on Mac, on Pi stop the old preview, pull, run tests and
start the same live command:

```bash
cd ~/projects/edgexr
git pull --ff-only
PYTHONPATH=src python3 -m unittest discover -s tests/unit -v
PYTHONPATH=src python3 -m app.live_preview --device /dev/video0 --imu --detect
```

Reuse the existing SSH tunnel and inspect the page while still, during a slow
turn/return, and while one person briefly enters/exits. Do not force the pan
servo or pull the camera/IMU wires. Record when IDs hold, switch, or restart;
report detector box age, detection rate, motion frame rate/skips and IMU status.
Use a new result note for this trial so the earlier untracked baseline remains
distinguishable. Device path may differ from `/dev/video0` on another boot.

## Validation and acceptance

- Synthetic tests demonstrate deterministic one-to-one matching, same-class
  restriction, bounded expiry, no ID reuse, empty-update behavior and no
  mutation of the input box records.
- Existing camera/motion/IMU and detector tests remain valid. Capture request
  remains 1280x720 MJPEG at 30 fps; detection stays at target 2 Hz. There is no
  new dependency or model file.
- Browser shows current detections with visible IDs and still hides stale or
  errored results. The source frame sequence/age remain honest; ID stability is
  not represented as synchronized camera pose or permanent identity.
- A Pi smoke test demonstrates at least one stable ID across several still
  detections, reports any failures on a slow turn, and checks that camera and
  IMU stay live. This is observation, not a guarantee of zero ID switches.
- `docs/PIPELINE.md` and `docs/learning/OBJECT_DETECTION.md` match the actual
  implementation: inputs/shapes/units, association rule, scheduling, timestamp
  and freshness scope, errors, and source-file links. Record whether any other
  learning guide needed a change.

## Surprises and discoveries

The first live detector observation showed responsive preview but increasing
motion-worker skips and slightly lagging boxes. This makes a two-Hz, IoU-only
tracker a useful baseline, not a promise of robust tracking during turns. Local
full-suite execution in the current restricted session produced two
`PermissionError`s from tests creating Desktop `recordings/` temporary folders;
the other 44 tests passed and two optional-environment tests skipped.

The learning-contract audit currently reports an unrelated existing docstring
issue in `scripts/build_hann_fft_lesson.py:chunk`; the new tracker functions
have typed signatures and Args/Returns docstrings. Step 1's focused seven
tests pass without hardware, model assets or NumPy.

## Decision log

- 2026-10-17: Start with same-class, one-to-one IoU association and bounded
  missed-update lifetime. This is explainable and testable without new model
  assets; appearance embeddings and motion prediction are deliberately later.
- 2026-10-17: Do not use IMU or image-shift values to move boxes in this first
  tracker. Their clocks/coordinate frames are not calibrated for that claim.
- 2026-10-17: Keep ID scope to a single live process. IDs are not durable room
  memory or re-identification after an object leaves view.
- 2026-10-17: Use IoU at least 0.3 and retire after two consecutive unmatched
  completed detector updates. Keep a track hidden on the first miss. A later
  detection at a distant location receives a new ID even if physically the
  same object; this is an honest failure of the simple spatial matcher.

## Outcomes and retrospective

The isolated tracker and its eight synthetic unit cases are complete. The live
detector worker now publishes ID-bearing boxes to the API, with inference
timing and source age unchanged. All 57 local unit tests pass (two optional
environment checks skip). Browser labels and Pi observation remain pending the
user's step-by-step review.
