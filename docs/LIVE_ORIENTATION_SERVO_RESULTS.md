# First logged live pan/tilt orientation sweep

The user transferred `servo-orientation-01` from the Pi on 2026-10-28. The
raw `servo_commands.jsonl`, `telemetry.jsonl` and `metadata.json` remain outside
Git in `/Users/ryanchoi/Desktop/servo-orientation-01`; they contain a live
scene's telemetry and are not an AP benchmark. The run used the separate
supervised servo process and the live preview with camera-axis quaternion mode.
The physical return of the lens has **not yet been confirmed** for this run.

| Observation | Value | Meaning / limit |
|---|---:|---|
| Logged commands | 162 | Initial 0° for each axis plus 160 one-degree steps; last tilt 0° command at Pi monotonic 336.369 s |
| Telemetry | 428 samples, 0 errors | Camera and IMU were `live`/`ready` in all saved snapshots; median reported IMU rate 19.04 Hz |
| Sampled peak relative angle | 28.99° | Occurred during the pan sweep at 324.418 s; this is relative to the preview's earlier still reference, not commanded shaft angle |
| Before pan | Camera rotation-vector Y ≈ −0.53° | Sample near 316.199 s, before moving |
| After pan return and pause | Camera rotation-vector Y ≈ −12.93° | Sample near 327.780 s, about 1.5 s after commanded pan 0°; the residual persisted during the pause |
| Last saved snapshot | Rotation vector ≈ (−8.32°, −11.93°, +0.56°), angle 14.56° | At 336.367 s, **1.5 ms before** the final tilt 0° command; it cannot establish settled final tilt orientation |

The roughly 12° pan-axis difference between before and after the pan sweep is
larger than the small change seen during the preceding still period. It could
reflect physical non-return, head/mount motion, or accumulated integration
error during motion; this telemetry alone cannot decide which. The tilt
return is unmeasured because logging stopped at the last command. Do not label
this trial a successful turn-and-return accuracy check. A visual confirmation
from the user and a repeat with a post-command settle window are needed.

The preview snapshots also reported median capture 30.09 fps, analysis
30.09 fps, and skipped decoded frames increasing from 2 to 3 during the
roughly 23-second logging period. These are descriptive telemetry, not a
controlled AP comparison; CPU, temperature and power were not measured.

The follow-up servo logger keeps recording for two seconds after final tilt
0°, and flags a run incomplete unless a live/ready orientation sample is
captured at least one second after that command. Repeat using a **new**
`recordings/` output name; never overwrite the first run.
