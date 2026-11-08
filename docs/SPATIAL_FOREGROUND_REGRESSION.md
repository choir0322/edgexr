# Foreground enrollment and recognition diagnosis — 2026-11-09

Status: mechanisms reproduced; latest reported Pi failure not yet attributed.
Runtime code and recognition thresholds are unchanged by this investigation.

## What changed

Before person exclusion, the scene worker could select a fresh image and attempt
enrollment or recognition directly. Commit `729b080` added an optional dependency
on fresh detector evidence, then person-region masking. Commit `5306b43` made
enrollment receipts persistent; it did not introduce a second confirmation or
change recognition thresholds. A remembered view is still stored after one
successful feature-quality check, not after a second recognition pass.

The original trial's left-view request was received and rejected as `weak_image`.
It was not merely a missed Remember click. Improving receipt visibility alone
did not resolve the underlying exclusion behavior.

## Pending: asynchronous workers can repeatedly miss the age gate

`src/spatial/live_scene.py:scene_latest` runs at a target of one query per second.
With exclusion enabled it calls `person_mask` before consuming an enrollment
request. `src/spatial/foreground.py:person_mask` requires detector source time
to precede the scene image by no more than 0.5 seconds. The detector retains its
latest completed result and targets two updates per second.

A deterministic example using the actual mask gate demonstrates the problem:

- Detector starts at 0, 0.5, 1.0 seconds, etc.; assumed compute is 250 ms.
- Scene checks at 1.1 seconds: detection from 1.0 is not complete, so the latest
  completed source is 0.5. Its 600 ms lag fails the 500 ms gate.
- Checks at 2.1, 3.1, etc. repeat the same rejection. All ten example checks fail.
- Moving scene checks to 1.4, 2.4, etc. gives 400 ms lag; all ten pass.

This is a hypothetical scheduling demonstration, not a measured timing trace of
the latest Pi run. It establishes that a working detector can repeatedly fail
the gate. There is no request deadline/cancel path: enrollment can remain pending,
and queries become `unknown / foreground_evidence_unavailable` without running
ORB matching. Camera freshness and recorder capacity are additional deferral
conditions; the latest log is needed to distinguish them.

## Same image: masking can remove necessary evidence

On Mac with OpenCV 4.11.0, replayed 58 saved canonical images with logged person
boxes from `spatial-foreground-01` (Pi revision `729b080`, dirty). For each image,
used a fresh production `SceneMemory`, enrolled it unmasked, queried identical
pixels unmasked, then queried those pixels with their recorded person mask.
Thresholds were unchanged. Separately attempted masked enrollment.

Of 57 images that enrolled and recognized themselves unmasked, 19 became unknown
with masking: 18 failed image-support checks and one failed match distribution.
Across all 58, masked queries produced 38 known results and masked enrollment
stored 39. These are diagnostic counterfactuals, not live accuracy scores: an
unmasked reference may itself contain a person and should not automatically be
accepted as reliable background memory.

The previously rejected left enrollment (`frame-00000663.png`) had about 78% of
its area excluded by person rectangles. With keypoint-center masking alone,
515 features occupied a 9.30% convex hull and three grid cells. Additional
descriptor-neighborhood exclusion reduced this to 249 features, a 6.12% hull,
and three cells. The existing minimums are 12% hull coverage and four cells.
It therefore fails even without the extra neighborhood margin. Many surviving
features are insufficient if concentrated in a narrow region.

Relevant boundaries: `scene_memory.py:SceneMemory.process` applies masking and
support gates; `verify_view` also checks spatial distribution of matching
features. Masks remove entire detection rectangles, not segmented silhouettes.
Asynchronous boxes may also be misaligned with the selected scene image.

## Limits, repair direction, and AP lesson

The latest failed run is not present on this Mac. The earlier trial had only one
stale and one missing detector observation, so it does not demonstrate prolonged
pending. Its writer completed all 180 records, with queue high-water one.
Do not attribute the latest failure to storage, detector false positives, or
specific scheduler timings without its evidence. No Pi CPU/latency improvement
was measured in this investigation.

Proposed repair, not implemented: use a bounded detector-result/source-image
handoff with matching timestamped orientation context; add a finite enrollment
wait with an explicit outcome; distinguish unavailable detector evidence from
actual visual non-recognition. Review mask support with clear-background and
crossing images before choosing a fallback. Do not silently loosen geometry
thresholds or treat a heavily occluded view as known.

For a baseline comparison, omitting `--scene-exclude-people` restores the
ungated/unmasked scene path; `--detect` may remain enabled. This is not validation
of foreground exclusion. AP lesson: independently healthy periodic workers can
fail an inter-worker freshness contract; adequate throughput alone is not enough.

Structured counts: [diagnostic summary](../benchmarks/results/foreground-regression-2026-11-09.json).
Private images remain outside Git. PIPELINE and learning diagrams were reviewed;
no runtime-flow change is claimed, so this diagnosis does not redraw them.
