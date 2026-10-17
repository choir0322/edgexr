# Basic tracker learning graph

## Purpose / big picture

Build a local, interactive learning page that follows one detector result from
live-worker setup through inference, the nine decisions of
`BasicTracker.update()`, and publication. It should resemble the direct flow of
`edgexr-worker-rates.html`: one connected path, one moving payload token, and
concise details on hover or click. It is a teaching page, not a new live worker.

## Context and orientation

`src/vision/basic_tracker.py` is the source of truth for ID decisions. The
live handoff in `src/vision/live_detector.py` now creates one tracker beside
the detector, calls `tracker.update(boxes)`, and publishes identified boxes.
Input is a list from `parse_detections()` via `CpuDetector.__call__`, containing
`class_id`, `label`, `confidence`, and `box_xyxy` in source-image pixels.
Prior calls leave compact `_tracks` memory:
ID, class, latest matched box, and missed-update count. Following one token is
a visual focus only; matching still considers all current detections and all
remembered tracks.

## Progress

- [x] 2026-10-17: Confirm tracker inputs, matching order, one-to-one rule,
  misses, retirement, and monotonic ID assignment against Python tests.
- [x] 2026-10-17: Build an initial interactive page and verify its fixtures.
- [x] 2026-10-17: User clarified that the page should be a minimal single-edge
  linear graph like the worker-rates illustration, not a photo-led dashboard.
- [x] 2026-10-17: Replace it with one token traversing nine code-order nodes;
  update the page checks and object-detection learning guide.
- [x] 2026-10-17: Review `docs/PIPELINE.md`; diagram unchanged because this
  educational page adds no runtime data path.
- [x] 2026-10-17: User approved adding the live worker handoff. Add four
  selectable context stops around the unchanged nine-node tracker graph:
  create once, infer boxes, match IDs, publish. Update interaction checks and
  the object-detection guide. Review `docs/PIPELINE.md` again; unchanged here
  because the live arrow was already added with the worker integration.
- [x] 2026-10-17: User requested one integrated dark graph, not two separate
  flows. Connect Match IDs downward to the nine decisions and Return upward
  to Publish. Keep Match IDs → Publish as a dotted collapsed overview only.
  Verify the 13-stop executable route and update this plan and the guide.
- [ ] Human visual/interaction check in a browser; browser automation is not
  available in this session.

## Plan of work

The single dark graph follows: Create once → Infer newest frame → Match IDs ↓
Input → Validate → Compare → IoU → Rank → Claim → Age old → Assign ID → Return
↑ Publish. These are 13 sequential selectable stops joined by 12 solid
execution edges. A dotted Match IDs → Publish edge is explicitly marked as a
collapsed overview, not a bypass or a path followed by Play. The payload
label changes from worker to frame to boxes to illustrative `d₀` to IDs;
the real matcher processes the whole list. Hover temporarily previews details;
click pins them. Reset returns to a sparse graph.

The four outer nodes belong to `detect_latest()`, while the nine expanded
nodes belong to `BasicTracker.update()`. An empty detector result still ages
tracks; compute_ms stops before matching; the API carries IDs and ready/live
browser labels now display provisional `#ID`.

At each node, show the rule, concrete example values, outcome, and named code
location. Use a checked teaching fixture with two current chair boxes
competing for old #1; the loser gets #3. Explain that a different-class or
below-threshold *pair* is rejected, not the current detection. An invalid
record aborts the entire update. A separate derived empty-update example at
the aging node shows one miss retained/hidden and two misses retired. Retired
IDs are not reused. Do not imply those illustrative boxes are saved model
outputs; the browser label status should agree with the current implementation.

## Concrete steps

1. Keep the teaching arithmetic aligned with `box_iou()` and the greedy
   assignment order in `basic_tracker.py`.
2. Render an SVG line of decision nodes and one `d₀` token, without photo,
   image overlay, persistent data lanes, or unrelated interface controls.
3. Test token traversal, hover/click details, Reset, IoU, one-to-one claiming,
   invalid input, and two-miss retirement with Node and Python tests.
4. Review the relevant learning guide and `docs/PIPELINE.md` for current versus
   future runtime behavior; obtain a browser visual check when available.
5. Test the integrated 13-stop traversal, the downward Match IDs → Input edge,
   the upward Return → Publish edge, the dotted non-executable overview and
   Reset/Play behavior.

Run from the repository root:

```bash
node --check docs/learning/basic-tracker.js
node tests/unit/test_basic_tracker_page.js
PYTHONPATH=src python3 -m unittest discover -s tests/unit -p 'test_basic_tracker.py' -v
git diff --check
```

## Validation and acceptance

The page must have one solid route whose token starts at Create once, enters
all nine tracker decisions from Match IDs, and goes from Return directly to
Publish. The dotted overview must not be a second executable path. Details
must make it clear that the whole detection list participates even though only
`d₀` is visually followed within the tracker. Class mismatch, IoU threshold, candidate ranking,
one-to-one claim, unmatched old-track aging, and fresh-ID creation must agree
with the Python algorithm. Tests can establish behavior and math; a human
browser check is still needed for layout and animation quality. The worker
nodes must match the code order in `detect_latest()` and distinguish the
tracker's ID return from the subsequent browser display.

## Surprises and discoveries

The original page made the photo, box overlays, multiple lanes, and controls
more prominent than the sequence of operations. The user clarified that this
obscured the desired single-object path. Also, old `_tracks` is not literally
the previous detector-output list; its box can be older than one update.

## Decision log

- 2026-10-17: Follow one illustrative `d₀` through a batch algorithm without
  hiding the competing detection when it affects the ID decision.
- 2026-10-17: Use a single SVG graph with hover/click detail and Play/step
  controls; no new dependency, model asset, or camera capture.
- 2026-10-17: Keep the separate missing-track example in the Age old detail
  rather than drawing a misleading branch off the single-token path.
- 2026-10-17: Replace the separate worker strip with one dark, connected
  graph. The visible dotted top edge is only a summary; Return connects to
  Publish directly so the animation does not falsely loop back through Match.

## Outcomes and retrospective

The local page is now a graph-based explanation of the tracker code. Its
checked example returns IDs `[1, 3, 2]` and the missing-track example ages an
old ID from zero to one to retirement at two completed detector results.
The live-tracking integration is recorded in `basic-tracking.md`; the lesson
now shows one connected current handoff without running live inference itself.
Browser visual QA remains to be completed by a person when opened locally.
