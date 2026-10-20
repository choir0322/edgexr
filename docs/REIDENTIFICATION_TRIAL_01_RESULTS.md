# Re-identification trial analysis

Trial: `reid-person-bottle-01` (private recording retained outside Git).
Recorded/current source commit: `49145eb3e84d2b0277ec70c11a67d8634c6844be`.

## Method

Reviewed all 117 saved detector-input frames and their recorded boxes. Recomputed
descriptors from the lossless PNGs and replayed the actual tracker in detector-update
order. Every replayed ID and match-source marker matched the recording. These are
the exact inputs used for the decisions, not guesses from the displayed overlay.
Times below are host receipt seconds relative to recording start, not exact video PTS.

## All seven person returns

| Return time | Previous ID → resulting ID | Gap since last detection | Appearance score | Outcome |
|---|---|---|---|---|
| 11.95 s | 4 → 6 | 3.86 s | 0.721 | Failed |
| 19.44 s | 6 → 7 | 4.49 s | 0.790 | Failed |
| 26.45 s | 7 → 8 | 3.49 s | 0.369 | Failed |
| 33.96 s | 8 → 8 | 4.49 s | 0.943 | Restored |
| 41.84 s | 8 → 9 | 3.89 s | 0.082 | Failed |
| 47.86 s | 9 → 9 | 3.49 s | 0.873 | Restored |
| 54.87 s | 9 → 9 | 4.02 s | 0.878 | Restored |

The appearance threshold is 0.85, not a probability. All four failures were
`below_threshold`; the relevant preceding ID remained in memory. Neither the
10-second timeout nor ambiguity caused these failures. Three of seven returns
restored the immediately preceding ID; this is a single-trial count, not a general
accuracy measurement.

## What limits success

1. `grayscale_grid_descriptor()` in [object_memory.py](../src/vision/object_memory.py) describes a crop using an 8×8 spatial brightness
   grid. This is not a learned person-identity representation. Changing how much
   torso, trousers, hand or background is inside the box changes that grid.
2. `BasicTracker.update()` in [basic_tracker.py](../src/vision/basic_tracker.py) replaces the stored descriptor with every valid
   latest descriptor. Valid means sufficiently large/non-flat, not a complete or
   reliable view. Immediately before 8→9, row 73 at 37.95 s shortened to an upper-body
   box. The returning box includes light trousers. Their similarity is 0.0816.
   The earlier row 72 at 37.45 s instead scores 0.9100 against the same return.
3. The unmatched-detection branch of `BasicTracker.update()` immediately allocates a fresh ID after an
   unsuccessful memory lookup. Once subsequent frames match that new active track
   by IoU, memory is not reconsidered for it. A bad first-return comparison can
   therefore persist as a different ID.

Retrospectively taking the best earlier view in each preceding uninterrupted
visible segment gives scores 0.721, 0.832, 0.582, 0.943, 0.910, 0.948, 0.932 for
the seven first-return frames. Thus keeping earlier views could address the
8→9 case, but is not evidence that a gallery alone fixes the other three failures.
This is an optimistic retrospective comparison, not a validated selection policy.

## Additional findings

Initial continuous visibility also fragmented person IDs 2→3→4. Consecutive-box
IoUs were approximately 0.183 and 0.213, below the active match threshold 0.30.
These are active-tracking failures, separate from the seven return events.

Recorded detections contain 63 person boxes and 113 tvmonitor boxes, with no
bottle boxes. This trial therefore cannot evaluate bottle re-identification;
its bottle problem occurs before memory matching. IDs are shared across classes,
so other objects can consume numbers between successive person IDs.

## Recommended next implementation experiment

Keep a small bounded gallery of quality-selected appearances per ID instead of
blindly replacing a single template. Add explicit crop-quality diagnostics and
test degraded last-view regression cases, especially the observed 8→9 case.
Then evaluate a short tentative return window and/or a more robust appearance
representation for the remaining failures. Do not simply lower the similarity
threshold to accept these examples: unrelated people need negative tests too.
Preserve one-to-one assignment, memory bounds, and explicit tentative identity
language. Replay this trial for regression and use a separate trial with another
person to test false restorations before claiming improvement.

No production algorithm changes were made in this analysis.
