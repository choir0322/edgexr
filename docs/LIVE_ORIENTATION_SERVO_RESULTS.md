# Logged live pan/tilt orientation sweeps

## Trial 03: settled pan and tilt returns

The user transferred `servo-orientation-03` on 2026-10-28 and confirmed that
the lens and browser image visibly returned to their starting direction after
**both** sweeps. The raw logs remain outside Git at
`/Users/ryanchoi/Desktop/servo-orientation-03`. This qualitative visual check
does not measure the exact return angle. The saved relative-orientation
reference began about 9.25 s before servo logging; the metadata does not
independently prove how the preview process was started.

The supervised run completed all 160 one-degree steps plus two initial 0°
commands. It saved 464 telemetry snapshots, all with camera `live` and IMU/
orientation `ready`, zero HTTP/logger errors, and a live/ready sample 1.96 s
after the final tilt 0° command. The maximum sampled IMU age was 56 ms; median
reported IMU rate was 19.04 Hz. No decoded frames were reported skipped during
the log. These checks establish a usable record, not orientation accuracy.

| Comparison | Approximate sample times (Pi monotonic) | Quaternion-relative rotation vector, camera XYZ | Magnitude |
|---|---|---|---:|
| Before pan → settled after pan | 928.015 → 938.082 s | (+0.54°, +4.02°, +3.71°) | 5.49° |
| Before tilt → settled after tilt | 938.082 → 947.870 s | (+7.20°, −0.90°, +0.16°) | 7.26° |
| Before pan → settled after both | 928.015 → 947.870 s | (+7.76°, +3.35°, +3.60°) | 9.19° |

Each row computes `inverse(start_quaternion) × end_quaternion`; it does not
subtract the browser's scalar angles. Nearby 0.7 s still-window medians of
the displayed rotation-vector components are consistent with the selected
endpoint samples. The metadata's final **9.42°** is instead relative to the
preview's earlier startup reference, so it is not the start-to-end error of
this trial. The sampled peak relative to that startup reference was 26.69°.

The persistent estimated changes across both visibly returning sweeps mean
the current gyro-only orientation estimate is **not yet validated** as a
repeatable camera-direction memory signal. This does not prove exact physical
return or isolate the cause. There were no reported dropouts, but ~19 Hz IMU
reads could still be too sparse during motion; bias change, vibration,
calibration/mapping error, or mount flex are also possible. This trial saves
neither independent shaft angle nor video, so it cannot rank those causes.
The next controlled diagnostic should compare the same sweep with faster live
IMU polling while retaining the same visual-return and settled-log checks;
measure the added AP cost separately after the vision behavior is established.

Median telemetry capture and analysis rates were 30.08 and 30.09 fps. These
are not a controlled AP benchmark; CPU, temperature and power were not logged.

## Trial 01: no final settle window

The user transferred `servo-orientation-01` from the Pi on 2026-10-28. The
raw `servo_commands.jsonl`, `telemetry.jsonl` and `metadata.json` remain outside
Git in `/Users/ryanchoi/Desktop/servo-orientation-01`; they contain a live
scene's telemetry and are not an AP benchmark. The run used the separate
supervised servo process and the live preview with camera-axis quaternion mode.
The user subsequently confirmed that both the lens and browser image visibly
returned to their starting direction after the **pan** sweep. This is a
qualitative observation, not a measured shaft or camera angle.

| Observation | Value | Meaning / limit |
|---|---:|---|
| Logged commands | 162 | Initial 0° for each axis plus 160 one-degree steps; last tilt 0° command at Pi monotonic 336.369 s |
| Telemetry | 428 samples, 0 errors | Camera and IMU were `live`/`ready` in all saved snapshots; median reported IMU rate 19.04 Hz |
| Sampled peak relative angle | 28.99° | Occurred during the pan sweep at 324.418 s; this is relative to the preview's earlier still reference, not commanded shaft angle |
| Before pan | Camera rotation-vector Y ≈ −0.53° | Sample near 316.199 s, before moving |
| After pan return and pause | Camera rotation-vector Y ≈ −12.93° | Sample near 327.780 s, about 1.5 s after commanded pan 0°; the residual persisted during the pause |
| Last saved snapshot | Rotation vector ≈ (−8.32°, −11.93°, +0.56°), angle 14.56° | At 336.367 s, **1.5 ms before** the final tilt 0° command; it cannot establish settled final tilt orientation |

The roughly 12° pan-axis difference between before and after the pan sweep is
larger than the small change seen during the preceding still period. Because
the user saw the lens and scene return, the estimate disagrees with the
observed pan return. The qualitative view cannot prove exact angular return
or isolate the cause: gyro integration, sparse reads during movement, bias
change, or relative motion of the IMU mount remain possible. It is **not**
evidence that the servo itself failed. The tilt return is unmeasured because
logging stopped at the last command. Do not label this trial a successful
turn-and-return orientation-accuracy check; repeat with a post-command settle
window and retain the visual return observation.

The preview snapshots also reported median capture 30.09 fps, analysis
30.09 fps, and skipped decoded frames increasing from 2 to 3 during the
roughly 23-second logging period. These are descriptive telemetry, not a
controlled AP comparison; CPU, temperature and power were not measured.

The follow-up servo logger keeps recording for two seconds after final tilt
0°, and flags a run incomplete unless a live/ready orientation sample is
captured at least one second after that command. Repeat using a **new**
`recordings/` output name; never overwrite the first run.
