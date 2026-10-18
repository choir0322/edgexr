# Motion-estimator quality: first four Pi trials (2026-10-19)

## Provenance and conditions

The user ran four 15-second `combined_capture.py` recordings on the Raspberry
Pi 4, analyzed each with `recording.visual_motion`, and compared the resulting
CSVs with `recording.motion_quality`. The copied analysis outputs live under
the Git-ignored `recordings/quality-analysis-{still,slow,fast,person}-01/` and
`recordings/quality-comparison-01/`. The fast-turn `camera.mkv` was later copied
to ignored `recordings/quality-fast-01.mkv` for visual review; no raw video is
tracked in Git.
The experiment's requested camera mode was 1280×720 MJPEG/30 fps, analyzed at
320×180 grayscale. The analysis JSON reports NumPy 1.26.4. The actual
negotiated mode, Pi OS/build, ambient lighting, source commit, power and
cooling for these specific clips are not in the copied outputs, so they remain
unverified. These are **quality trials**, not throughput or thermal benchmarks.

The user estimates movement began about two seconds after executing each
capture command; execution time is not the same as the recording cue. Exact
start/stop times were not logged. For the fast clip, the user specifically
reports **roughly three to four quick sharp turns**, not one. The slow-turn
signal changes sign several times, so it also should not be treated as a
single monotonic turn. Video review is still needed to label action windows.

## Results

| Trial | Visual pairs / inspected | Visual coverage | Median shift (px/pair) | p95 shift (px/pair) | >1 px/pair estimates |
|---|---:|---:|---:|---:|---:|
| Still | 452 / 452 | 100% | 0.0020 | 0.0049 | 0 |
| Slow turn | 451 / 451 | 100% | 1.1633 | 3.2104 | 252 |
| Repeated fast turns | 423 / 451 | 93.8% | 0.0028 | 1.3497 | 25 |
| Moving person, camera fixed | 451 / 451 | 100% | 0.0031 | 0.0094 | 0 |

These are magnitudes of accepted 320×180 image displacements **per adjacent
pair**, not camera angles or pixels/second. The >1 px cutoff is only a
reporting aid. Rejected pairs lower coverage; they are not counted as zero
shift. Whole-clip medians are dominated by the stationary portions and are
especially misleading for the brief fast-turn action.

The still clip has 451 visual-plus-gyro paired observations, with one gyro
interpolation gap; the slow clip has 450, also one gap; the fast clip has 423;
the moving-person clip has 451. In the fast clip, all 28 rejected visual pairs
fall between approximately **5.04 and 7.30 seconds after the recording cue**.
Seconds 5, 6 and 7 retain 22, 20 and 20 visual estimates,
respectively, versus about 30 per second outside this interval. This is
consistent with the quick-turn stress interval being harder for the patch
matcher, but the output does not assign each rejection to a particular turn.

Inspection of the fast video shows several sharp sweeps, substantial scene
replacement between nearby frames, visibly blurred frames during some sweeps,
and a nearby object traversing much of the view. The 28 rejected pairs form
four short clusters, approximately 5.04–5.10, 5.83–6.14, 6.73–6.90 and
7.04–7.30 seconds after the cue. Corrected gyro Y is often hundreds of
degrees/second in these clusters, reaching about 794 degrees/second in the
interpolated CSV near 7.04 seconds. At a nominal 30-fps interval, such rapid
motion can dramatically alter the patch contents; it is not comparable with
the slow-turn run. Because gyro is host-paired and the video has no exposure
timestamps, that peak must not be converted into an exact per-frame camera
angle. The current logs cannot separate excessive displacement, blur, and
near-field occlusion as causes of individual patch rejections.

An offline [per-patch diagnostic](../../docs/PATCH_DIAGNOSTICS.md) was then run
on all 28 visually rejected pairs using the copied video. It reproduced all
28 rejections. Twenty-four pairs had fewer than four individually valid
patches; four had at least four valid patches but fewer than four agreeing
within 1.5 pixels. Across 28 × 9 = 252 patch checks, **219 flagged weak
correlation peaks**, 16 flagged an over-limit horizontal candidate, five
flagged an over-limit vertical candidate, and **none** failed the initial
texture check. Flags can overlap, and a candidate shift from a weak peak is
not a trustworthy displacement. The result points primarily to ambiguous
phase-correlation matches during these rapid sweeps, not a shortage of
texture. Video blur, drastic view replacement and near-field occlusion remain
plausible contributors, but the diagnostics cannot isolate one physical
cause. Full per-pair records stay in ignored
`recordings/quality-patch-diagnostics-fast-01/`.

In the slow clip, per-second median dx is positive around seconds 4–7, negative
around 8–11, and positive again around 12–14. Gyro Y has the opposite sign in
these phases, matching the previously observed axis relationship. The
exploratory whole-clip horizontal-motion/gyro-Y correlation is −0.831; it is
**not** a synchronization, pose-accuracy or calibration score. The stationary
and moving-person trials retain near-zero global-shift estimates; without the
source video, we cannot verify how large the moving person appeared in frame.

## Interpretation and next check

This run provides evidence that the estimator rejects some rapid-motion pairs
while remaining stable in the two nominally fixed-camera conditions. The
video review narrows the fast-turn problem to extreme view change with visible
blur/occlusion. The subsequent per-patch report identifies weak correlation
as the dominant check failure, without proving its physical cause. Do not
loosen thresholds merely to increase
coverage: an invented displacement during a ~794-degrees/second sweep may be
worse than an explicit unknown. The next controlled experiment should vary
turn speed in measured bands, using the same diagnostics to locate the
repeatable failure boundary. Keep raw video and detailed CSVs out of Git; do
not tune from a whole-clip median.
