# Live IMU polling: four attended camera-head returns

The user transferred four complete Pi runs on 2026-10-28 to
`/Users/ryanchoi/Desktop/edgexr-imu-ab/`. The transferred telemetry, motor
commands, and three 320×180 grayscale checkpoints per run remain outside Git.
The earlier `servo-orientation-ab-50a` is excluded: its duplicate `after_pan`
checkpoint inserted an unintended mid-sweep pause. These four runs used the
corrected final-pan trigger. All recorded 162 commands (two initial center
commands plus 160 one-degree steps), all three checkpoints in order, ready
orientation at every telemetry poll, zero logger/HTTP errors, and a final
orientation poll about two seconds after the last tilt command. The three
checkpoints followed the final pan or tilt command by about 1.4 or 2.0 s.
The preview PID differs between runs, consistent with a fresh process for
each trial. On 2026-10-28 the user confirmed that the lens and Mac preview
visibly returned to their starting direction after both pan and tilt in all
four valid runs. This is qualitative return evidence; the exact physical
return angle was not measured.
The rig is a Raspberry Pi 4 with the camera-head IMU and passive heatsink.
The protocol requested the same fixed-base scene and lighting for every
run, but the transferred files do not independently verify scene, cooling,
power, Git commit, or exact servo shaft motion. This is a quality diagnostic,
not a controlled AP power or thermal benchmark.

## Calculation

For each checkpoint's Pi host-poll midpoint, select the nearest ready
`telemetry.jsonl` poll (at most 41 ms away in these files). Compute the
relative quaternion as `conjugate(q_start) × q_end`, then express it as the
shortest camera-XYZ rotation vector and its magnitude. **This is a residual
change reported by gyro-only integration, not ground-truth camera angle or
the scalar angle relative to preview startup in `metadata.json`.** The
`before_pan → after_pan` and `after_pan → after_tilt` legs use the settled
camera checkpoint times; `before_pan → after_tilt` measures the complete run.
The quaternion helpers are in `src/spatial/relative_orientation.py`.

| Run / post-read sleep | Actual median IMU rate | Pan return vector XYZ, magnitude | Tilt return vector XYZ, magnitude | Whole-run residual | Preview capture / analysis median | Skipped decoded frames during log |
|---|---:|---|---|---:|---|---:|
| `50a-r1` / 50 ms | 19.02 Hz | (−0.02°, +1.16°, −1.24°), **1.70°** | (+5.55°, −0.85°, +0.12°), **5.62°** | **5.65°** | 30.09 / 30.08 fps | +1 |
| `10a` / 10 ms | 80.35 Hz | (−0.12°, −0.34°, −0.34°), **0.49°** | (−0.38°, +0.04°, −0.56°), **0.67°** | **1.07°** | 30.09 / 30.08 fps | +1 |
| `10b` / 10 ms | 80.22 Hz | (+0.13°, −0.44°, −0.52°), **0.69°** | (−0.70°, +0.05°, −0.52°), **0.88°** | **1.25°** | 30.10 / 30.08 fps | +1 |
| `50b` / 50 ms | 18.99 Hz | (−0.07°, +12.20°, +2.39°), **12.43°** | (−0.36°, −0.75°, +0.18°), **0.85°** | **11.75°** | 30.10 / 30.10 fps | +0 |

The 10 ms runs have smaller estimated whole-run residuals in both repeats.
The metadata's integrated-interval counters include time before servo logging
and must not be interpreted as interval counts within the sweep alone.
The gyro offset estimates differed between restarted runs,
but the estimated rotation during the final approximately one-second still
window was only 0.03°–0.17°; this does not explain the 5.65° or 11.75°
whole-run residuals by post-stop drift alone. The 50 ms trials differed
substantially from each other, particularly in which leg accumulated error.

As a separate, coarse view check, `recording.visual_motion.image_shift` was
run on each pair of saved **display-size** PGM checkpoints. The estimated
content shifts from `before_pan` to `after_tilt` were (−0.19, +1.39),
(−0.09, −0.05), (+0.03, −0.31), and (+0.25, +1.46) pixels in table order.
Before-to-after-pan shifts were (−0.06, +0.01), (−0.07, +0.01),
(+0.03, +0.02), and (+0.70, +0.04) pixels. At least seven patches agreed
for each estimate. All start/end views appear broadly similar; the
`50b` before/after images were also inspected visually. Pixel shifts are
**not** camera angles and do not prove identical physical pose; illumination,
scene movement, perspective, and the unknown lens calibration limit this
check. Checkpoint frame ages ranged from 33 to 72 ms, and camera frames and
IMU polls were not exposure-synchronized.

## Decision and limits

In these four runs, 10 ms polling was **associated with smaller and more
similar gyro-only return residuals** under the same commanded schedule. It does
not establish absolute orientation accuracy, quantify missed physical motion,
prove sampling is the sole cause, or measure CPU/power/temperature cost.
There are only two repeats per setting. The ~30 fps preview rates and 0–1
skipped decoded frames show no obvious short-run camera slowdown, but are
not a full AP benchmark. The user's visual-return confirmation completes this
diagnostic comparison. Use explicit 10 ms polling as the proposed reference
configuration for the next spatial scene-memory work; the CLI default remains
50 ms. Per the accepted development order, dedicated AP cost comparisons
follow the functional spatial demo unless performance blocks its usability.
The next functional milestone is bounded visual scene memory and verified
revisits, with gyro direction as uncertain context.
