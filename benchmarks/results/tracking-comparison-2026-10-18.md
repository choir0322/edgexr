# Pi 4: basic versus motion-aware ID matching

Two user-operated, 60-second SSH preview trials on 2026-10-18 tested whether
image-shift prediction helped the short-term box tracker. This is an exploratory
behavior comparison, **not** a controlled accuracy or end-to-end latency
benchmark. The full JSONL logs remain outside Git; this is the shareable
summary derived from the transferred `basic-01` and `aware-01` trial folders.

## Conditions and provenance

- Both runs: Raspberry Pi 4, Linux `6.12.47+rpt-rpi-v8` aarch64, software commit
  `1f2b887b4a98af56b525775159b21efea1dd2356`, one person as the selected
  target class, approximately the same lit room and whole-base turn/return
  route. The preview requested 1280×720 MJPEG at 30 fps, MobileNet-SSD CPU
  detection at a target 2 Hz, with IMU enabled. The actual negotiated mode,
  exposure, model-file hash, power/cooling and ambient temperature were not
  recorded in these trial logs.
- Each run lasted 60 seconds: approximately 10 seconds still, 40 seconds
  turning and returning, and 10 seconds still. The user moved the rig by hand,
  so turn speeds and exact viewpoints were not paired. The recorder polled
  `/api/telemetry` at 10 Hz, retained distinct observed detector sequences,
  saved no images, and reported zero poll errors in either run.
- `box source age` begins at Pi host frame receipt and is sampled at the
  recorder's first poll of each detector result. It excludes camera exposure
  timing and browser/SSH delay. `analysis fps` is the motion worker's recent
  throughput, not camera frame rate.

## Observations

| Metric | Basic IoU | Motion-aware |
|---|---:|---:|
| Distinct detector updates observed | 121 | 122 |
| Target visible / missing / ambiguous updates | 120 / 0 / 1 | 118 / 4 / 0 |
| Observed adjacent target-ID changes | 1 | 2 |
| Median motion-analysis rate | 25.87 fps | 26.01 fps |
| Median detector compute | 229.87 ms | 229.57 ms |
| Median box source age at first recorder poll | 291.95 ms | 285.26 ms |
| Skipped decoded-frame counter increase | 262 | 255 |
| Median absolute gyro Y during turn phase | 11.99°/s | 32.77°/s |

In the motion-aware run, 60 old-track comparisons had continuous usable
image-shift history and 64 fell back to raw overlap: **48.4% coverage overall**.
During the turn/return phase, coverage was 23 versus 61 fallbacks, or about
27.4% of those comparisons. Predicted overlap was greater than raw overlap in
25 assignments, but `motion_only_matches` was **zero**: none of the observed
ID assignments needed prediction to cross the 0.3 IoU threshold. These counts
include all detected classes, not just the selected person.

Both motion-aware target-ID changes occurred during the turn phase, at
approximately 43.42 s and 45.52 s. Each update recorded zero covered tracks
and one fallback track. Some immediately preceding latest-motion snapshots
were marked unreliable; that is consistent with missing interval coverage,
but the saved snapshots cannot isolate every pair that caused fallback. The
person boxes around those events were very large and moved sharply across the
source image. Without labelled footage, the logs cannot establish whether
each new ID represented the same physical person.

The basic run's single adjacent person-ID change followed an update with two
`person` boxes. That ambiguity makes it unsafe to score the change as a
verified identity error. Also, the motion-aware run's turn-phase median gyro
rate was about 2.7 times the basic run's; its higher observed ID-change count
must **not** be presented as evidence that the algorithm is worse.

## Decision and limits

Keep motion-aware matching **opt-in**. These runs show no necessary ID hold or
measurable throughput advantage under the tested conditions, while ordinary
basic IoU maintained IDs well in typical turns. They do not establish that
motion-aware matching never helps, nor that it hurts accuracy: the routes
were not speed-matched and no ground-truth identity annotations were collected.
Do not tune the IoU threshold or force sharper turns just to raise a counter.

The next project milestone can proceed without more tracker tuning. If this
feature is revisited, first investigate why interval coverage drops during
turns, then evaluate it on labelled, repeatable scenes where raw IoU actually
fails while image shift remains reliable. Follow
[`docs/TRACKING_TRIAL.md`](../../docs/TRACKING_TRIAL.md) for the recorder protocol
and [`docs/learning/MOTION_AWARE_TRACKING.md`](../../docs/learning/MOTION_AWARE_TRACKING.md)
for the distinction between available motion, prediction-selected matching,
and an ID hold that truly needed motion.
