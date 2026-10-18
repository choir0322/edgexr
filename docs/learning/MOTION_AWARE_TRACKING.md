# Study: motion-aware ID matching

This optional mode helps the short-term tracker keep an ID during a moderate
camera turn. It uses **image-content shift**, not the IMU, to predict where a
previously detected box might appear. It does not move the displayed box or
recognize an object after its track has retired.

Run it with `--detect --motion-aware-tracking`. Without the second flag,
`BasicTracker` uses the original same-class IoU rule. See the
[live pipeline](../PIPELINE.md) and [Pi comparison procedure](../LIVE_DETECTION.md).

## Read the code in data-flow order

1. [`State.publish_frame()`](../../src/app/live_preview.py) gives each captured
   frame a sequence and host-monotonic receipt time. With detection active it
   keeps a 1280×720 grayscale source slot and a separate 320×180 motion slot.
   These times are **not** camera exposure timestamps.
2. [`analyze_latest()`](../../src/app/live_preview.py) selects the newest small
   frame and calls [`image_shift()`](../../src/recording/visual_motion.py) on
   the previous analyzed frame and this one. Skipped frames mean a pair can
   span more than one camera frame.
3. [`State.publish_result()`](../../src/app/live_preview.py) records the pair's
   two receipt times and either its reliable `(dx, dy)` shift or `None` in
   [`MotionHistory.add()`](../../src/vision/motion_history.py). The bounded
   history holds at most 180 pairs. A pair longer than 0.12 s, an invalid
   estimate, or a gap breaks usable coverage; unknown is never zero motion.
4. [`detect_latest()`](../../src/vision/live_detector.py) independently selects
   the newest full-size source frame, runs MobileNet-SSD, and calls
   [`BasicTracker.update()`](../../src/vision/basic_tracker.py). For each old
   track, the optional callback asks `State.motion_between()` for the interval
   from that track's **last matched detector source time** to the new detector
   source time. `MotionHistory.displacement()` requires continuous reliable
   coverage and linearly prorates a first or last partial pair. This assumes
   roughly uniform shift within each measured pair; it is an approximation.
5. The callback multiplies dx and dy by four, converting 320×180 motion pixels
   to 1280×720 detector-source pixels. `BasicTracker` translates the *old box
   for comparison only* and computes both predicted and raw IoU. It uses the
   larger overlap, with the same label, IoU ≥ 0.3, and greedy one-to-one rules.
   A missing or implausible prediction falls back to raw overlap. A current
   detection that does not match receives a new never-reused ID. One unmatched
   detector update hides but retains an old track; two retire it.
6. [`DetectionState.publish()`](../../src/vision/live_detector.py) stores the
   ID-bearing boxes and per-update counts. [`State.snapshot()`](../../src/app/live_preview.py)
   merges independently timed results for the HTTP response;
   [`preview.html`](../../src/app/preview.html) displays them. `covered_tracks`
   counts old tracks with usable interval shift, `fallback_tracks` counts old
   tracks using raw-only overlap, and `motion_only_matches` counts ID holds
   where predicted IoU passed but raw IoU did not. These are counts for the
   latest detector update, **not** cumulative totals or proof of correct IDs.

Example: an old person box is at x=100–200. Between its old and new detector
frames, the motion worker measures +50 pixels in the 320-wide image. That
becomes +200 source pixels. If the new person box is at x=300–400, raw overlap
is zero, but the translated old box overlaps it. This is a candidate ID hold,
provided the interval estimate is reliable and no competing same-class box
wins the one-to-one match.

Image shift describes the scene, not each individual object. A moving person,
parallax, lighting changes, estimator errors or sparse analysis can make the
prediction misleading. Raw overlap remains eligible even with motion coverage,
which helps when foreground motion differs from background shift. The IMU is
shown alongside this result but is **not fused** into the matching decision.
Departure and later re-entry still need a separate appearance-based memory
feature; this mode does not provide re-identification.

For hardware-free checks, read
[`test_motion_history.py`](../../tests/unit/test_motion_history.py),
[`test_basic_tracker.py`](../../tests/unit/test_basic_tracker.py), and
[`test_live_detection.py`](../../tests/unit/test_live_detection.py).
