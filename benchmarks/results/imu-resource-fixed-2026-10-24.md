# Fixed IMU polling resource results — 2026-10-24

Instrumented commit: `ff07a974aae1b127d7763e8641969a27c75ef921`.
Source: user-provided completed four-run comparison report. Raspberry Pi 4,
Linux 6.12.47+rpt-rpi-v8 aarch64, Python 3.11.2, passive metal heatsink,
power source recorded as unknown. Requested camera mode: 1280x720 MJPEG/30.
Scene: fixed base, same lit scene, camera-head IMU; commanded pan channel 2
0 → −20 → +20 → 0 degrees at 5 commanded °/s. Tilt channel 3 at safe zero.

Each capture requested 21.5 s. Observed CPU windows were 21.420–21.443 s,
excluding startup, shutdown and offline visual diagnostics. Both modes used
the same approximately 1 Hz observer. CPU seconds include observer work and
all recorder threads; FFmpeg is separate; servo parent and power are unmeasured.

| Run in order | Sleep | Recorder CPU s | FFmpeg CPU s | IMU reads/s after bias | Final rotation residual |
|---|---:|---:|---:|---:|---:|
| 50ms-01 | 50 ms | 0.42 | 7.70 | 18.83 | 14.32° |
| 10ms-01 | 10 ms | 0.89 | 7.61 | 77.62 | 0.82° |
| 10ms-02 | 10 ms | 0.88 | 7.70 | 77.35 | 0.76° |
| 50ms-02 | 50 ms | 0.41 | 7.74 | 18.85 | 7.23° |

Median recorder CPU work rose from 0.415 to 0.885 s, an additional **0.470 CPU s**
per trial. Mean recorder utilization rose from **1.94% to 4.13% of one logical
CPU**, a 2.19 percentage-point difference. Combined recorder+FFmpeg work rose
from 8.135 to 8.540 CPU s (about 5.0%); FFmpeg's small negative median difference
is run variation, not evidence of an FFmpeg optimization. CPU time is not energy.

Median apparent return residual fell from **10.77° to 0.79°**. This is a
gyro-only IMU-frame estimate using each run's own initial two-second bias window;
physical angles/returns were not independently calibrated in this report.
Camera PTS rate excluding startup was approximately 30.08 fps in every run.
Recorder sampled RSS was about 37.9 MiB and FFmpeg about 153.5 MiB. Observed
initial/final temperatures ranged from 46.251 to 52.095 C; every adjacent
firmware flag was `0x0`. Trials were short and thermally unequal; two repeats
per mode are screening evidence rather than a statistical significance claim.

## Decision

Carry 10 ms forward as the quality reference. Implement the approved simple
servo-command-driven 50 ms idle / 10 ms active policy, then measure all three
configurations under one software revision and identical movement/observer.
Only about four seconds of this short workload can use idle reads while
preserving the motion/settling window. Expected savings are modest, and pipe
coordination itself adds CPU work; measure rather than promise a reduction.
Unexpected base movement during idle remains a limitation of this first policy.
