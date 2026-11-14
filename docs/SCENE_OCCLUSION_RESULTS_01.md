# Paired-source partial-background trial: spatial-occlusion-01

Reviewed 2026-11-14 from the Mac copy of the Pi recording. Times below are
seconds relative to the first recorded source frame (host monotonic 1065.917 s),
not time since the shell command or exact exposure time. Original PNGs and logs
remain private outside Git. Review sampled source images with recorded boxes,
not reconstructed continuous video; 179/179 linked images are present.

## Enrollment and timing

Run metadata reports revision `405a6994a9a073b3671f5b96afd9e59f1bea67cb` and
`dirty: true`; the cause of the dirty status is not identified by this evidence.
Pi Linux 6.12.47, Python 3.11.2, OpenCV 4.11.0, two OpenCV threads, detector
enabled, 10ms IMU sleep, 1280x720 grayscale source and 640x360 saved frames.
The exact camera mode negotiation, scene lighting, power, cooling and warmup
were not independently measured here. User requested an approximately 180s
run; recorded source span is 177.4s across 179 rows.

View-1 enrolled at 22.6s (frame 685), View-2 at 40.7s (1228), View-3 at
55.7s (1679). Each reported zero masked area, 600 features and STORED. Request
to completion times were approximately 0.87, 1.02 and 1.08s respectively.
There are no recorded failed/expired requests. This supports normal enrollment
in this run; it does not exercise timeout or detector failure on the Pi.

## Recognition and image review

The three stored PNGs show distinct directions. After enrollment, View-1 was
known in five logged queries, View-2 in two, and View-3 in 72. This counts
outputs, not accuracy; camera dwell time and ground-truth directions are uneven.
The most informative sampled crossing section is approximately 56.7–138.4s,
where the source images mainly show the View-3 living-room background and people
passing or occupying parts of it. Of 62 records in this interval with at least
one person box, 49 were known, nine unknown for insufficient visible background
and four unknown for no verified match. Boxes are detector outputs and sometimes
overlap, include background, or could be false positives. This subset was chosen
from observed behavior after capture, has no independent per-frame labels and
must not be described as a recall or accuracy percentage.

Examples from the saved image and corresponding decision:

- 59.7s, frame 1801: unknown, 54.7% boxed, remaining features in only two grid
  cells. At 60.7s, frame 1831: known View-3 with 33.6% boxed and 436 geometric
  inliers. The person remains partially visible; matching uses background.
- 78.7s, frame 2373: unknown, 50.1% boxed, 39 usable features. Frame 2403 a
  second later is known again. Other unknowns similarly recover, although recovery
  depends on the selected 1Hz observations rather than an exact reaction time.
- 125.9s, frame 3790: unknown even with 100 candidate geometric inliers: their
  supported area represented about 11.1% of visible query area, below the 12%
  experimental requirement. At 126.4s frame 3805, View-3 is accepted.
- From 139.9–158.4s, 20 saved observations are unknown with no person boxes.
  Inspected frame 4212 shows a different direction dominated by a chair/cabinet;
  this is consistent with the requested unenrolled-direction control, but the
  user's exact intended sequence has not been confirmed.
- At 166.9s (5025) and 174.9s (5266), View-3 is known with a person present.
  The final three samples are unknown; frame 5341 still has a person box and
  View-3 inliers, but their geometry occupies too little area to pass support.
  The final image differs in framing from the stored reference. We cannot infer
  whether it would recover after the person leaves because the run ends there.

The comparison cannot show whether the new policy improved live accuracy over
the previous implementation; no matched A/B trial was recorded. The previous
trial also had different enrollment, scene and timings. Green dots indicate
verified feature correspondences on the accepted reference/query images; they
are not object detections, whole-area verification or ground-truth correctness.
The lower live camera preview and motion arrow have their own source times.

## Continuity and AP observations

178 of 179 rows have available paired detector evidence. In all 178, detector
source sequence and timestamp equal the selected scene source; the one missing
result is the first startup row. The writer accepted and wrote all 179, dropped
zero, and queue high-water was one of four waiting slots. IMU: 13,083 polls,
zero midpoint gaps over 200ms and max gap 36.41ms. These are observed values,
not proof of sensor-level losslessness or synchronized exposure timestamps.

Across 179 records, scene-worker compute wall time median 176.62ms, empirical
p95 335.61ms, max 390.94ms. Evidence image encoding wall time median 23.47ms,
p95 55.12ms, max 124.20ms. Those encoding times are included in scene compute;
do not add them together. Scene-thread CPU median 143.56ms. Process CPU recorded
during the same interval includes concurrent threads and can exceed elapsed
wall time; it is not isolated scene-worker CPU or a processor utilization rate.
Total CPU utilization, RSS, temperature, power/energy and per-component isolated
cost were not measured by this run. The workload includes detection and image
recording; it is not directly comparable to unrelated earlier baselines.

## Next bounded step

Confirm the user's intended movement sequence and whether View-3 was the planned
crossing view. Inspect further frames if required. The trial establishes several
successful person-masked recognitions and explicit abstentions, while return
recovery at the end remains unproven. Prioritize completing the existing spatial
application; choose a specific quality or AP question before another trial.

Structured summary: [spatial-occlusion-01.json](../benchmarks/results/spatial-occlusion-01.json).
