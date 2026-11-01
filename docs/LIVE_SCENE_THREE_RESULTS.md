# Three-view live trial — 2026-11-02

User confirmed enrollment order center=View-1, left=View-2, right=View-3,
followed by revisits and an upper-left excursion. Inspected transferred
`live-scene-three-01`: 208 JSONL rows and all 208 linked images present.
Reference, transition, upper-left and endpoint images were visually reviewed.
Private images remain outside Git. Pi revision d16d628 reported dirty.

## Functional outcome

Enrollments occurred approximately 96.90, 115.45 and 131.54 seconds after the
first frame. Later center/left/right recognition is visible in both images and
decisions: around 137.52/147.53/162.56 s, then 179.70/188.72/195.73 s.
The final 26 observations are known View-3 and visibly show the right region.
There are 81 known observations (23 center, 15 left, 43 right), three enrolled,
93 empty-memory observations and 31 other unknowns. No ambiguous_views result.
These counts are not a calibrated accuracy score, and transition views overlap.

The upper-left excursion does **not** provide a clean all-unknown negative test.
At 154.54 s the tilted image is unknown, but at 157.53 s a visibly tilted image
matches View-2 (74 inliers, 18.84%/18.64% coverage); at 160.56 s a tilted image
matches View-1. Those images retain real features of the stored regions.
Current scene labels mean verified visual overlap, not exact orientation bins.
An untaught direction is not necessarily an unseen visual region. Do not call
this a proven false scene match or claim directional localization is complete.

## Recognition flicker

The right region intermittently reports unknown around 170.70, 175.72 and
177.72 s despite recognizable overlap. At 170.70 s, 159 inliers pass other
tests but cover 11.88% of the query, below the 12% minimum. At 175.72 s,
query coverage is 11.04% and only three cells (minimum four). These explain
the rejection paths; no thresholds have been lowered. Weak evidence should
remain explicit even if a later display policy retains a separately aged label.

## Orientation continuity and stalls

Orientation is ready for 94 observations, startup-unknown for one, and
unknown for the final 113 with `IMU stale; rotation continuity unknown`.
The first logged unknown occurs at 100.15 s, immediately after a scene
computation taking 2216.30 ms. This is correlation, not proof that feature
extraction caused sensor starvation. There is no raw per-read trace or CPU/
storage profiling sufficient to determine the exact cause.

One diagnostic PNG operation took 5844.32 ms, followed by a 5.95 s interval
between analyzed source frames. PNG writes run synchronously in the scene
worker, so this directly delays its next iteration; it does not prove that
the same operation delayed the separately threaded IMU. Median/p95 image write
was 14.13/31.30 ms. Median/p95 scene compute was 86.75/155.18 ms.
Overall 207 intervals across 220.759 s yield about 0.938 scene updates/s.
These are wall timings, not CPU cost or exposure-to-display latency.

Visual recognition continued when orientation became unknown, as designed.
Do not claim successful orientation-backed spatial validation for this run.
The current estimator intentionally does not bridge a missing interval or
silently restart its reference. This fail-closed behavior should be preserved.

## Next bounded work

First investigate the live scheduling/recording stalls and IMU freshness path,
using explicit per-read gap and task timing evidence. Separate diagnostic
image I/O from scene processing with a bounded queue/drop policy if implemented;
never introduce an unbounded queue or silently omit image evidence. This is a
functional reliability blocker with direct AP relevance, not a detour into a
full optimization campaign. Then repeat the multi-view check with valid
orientation context. Do not tune recognition thresholds or add hard gyro
gating from this run. Three-view visual memory is demonstrated; exact pointing
direction, orientation reliability and full spatial pose remain unfinished.
