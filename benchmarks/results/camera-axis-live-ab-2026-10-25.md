# Pi 4 live camera-axis conversion A/B: feasibility result

Two user-operated, stationary full-workload runs compared the current IMU path
with an opt-in camera-axis projection after each valid gyro read. This is an
AP scheduling/quality check, **not** a precise causal estimate of the
conversion's CPU cost. The raw `samples.jsonl` files remain in ignored Pi
recordings and were not independently inspected on the Mac. Values below come
from the user-pasted collector summaries and metadata.

## Conditions and provenance

- Raspberry Pi 4, Linux `6.12.47+rpt-rpi-v8` aarch64, Python 3.11.2; commit
  `049d5311d35466b4849edf30834a2539a1329683` in both runs. Power supply
  was entered as `unknown`; cooling was a passive metal heatsink without fan.
  Pi RAM and ambient temperature were not reported.
- Same declared stationary well-lit desk scene with fixed base/head. Both
  metadata files report complete, **basic** tracking, 1280×720 MJPEG/30 camera
  **request**, 320×180 grayscale motion analysis, 2 OpenCV internal threads,
  2 Hz detector target, 120-second warm-up, 300-second measurement and 1-second
  collector interval. Negotiated camera mode, exposure/gain and browser state
  were not separately verified for these two runs.
- MobileNet-SSD graph SHA-256 was
  `2d180f723b3109e21f8287f6b3c691390d07b60eed998327cd3259ffa0e50608`;
  weights SHA-256 was
  `52eed8be80522c152a17fb56740de705b79881bde1a167e0e747310523685fc7`
  in both runs. A had `camera_axis_mode: off` and no basis; B had
  `camera_axis_mode: on` with the previously validated neutral-head basis.
- A measured 2026-10-25 00:49:16–00:54:16 UTC; B measured
  00:57:12–01:02:12 UTC. They ran in that order, roughly three minutes apart
  between measurement windows. Each summary contains 297 polls.

## Observations

| Metric | A: conversion off | B: conversion on | B − A |
|---|---:|---:|---:|
| Preview CPU median, % of one core | 187.48 | 187.32 | −0.16 percentage points |
| Preview CPU p95, % of one core | 192.13 | 192.55 | +0.42 points |
| FFmpeg CPU median, % of one core | 37.63 | 37.47 | −0.16 points |
| System CPU busy median, % all cores | 57.54 | 57.39 | −0.14 points |
| IMU read rate median | 18.883 Hz | 18.860 Hz | −0.023 Hz |
| Camera capture rate median | 30.090 fps | 30.091 fps | +0.001 fps |
| Motion analysis rate median | 26.124 fps | 26.103 fps | −0.022 fps |
| Motion estimator time median | 30.55 ms | 30.60 ms | +0.05 ms |
| Detector completion rate median | 1.999 Hz | 1.999 Hz | <0.001 Hz |
| Skipped decoded frames added in window | 1,212 | 1,208 | −4 |
| Camera-axis projections added in window | 0 | 5,638 | +5,638 |
| Temperature median | 66.71°C | 71.58°C | +4.87°C |

The B run's 5,638 projections over about 300 seconds mean roughly **18.8
projections/s**, matching its measured IMU read rate. All 297 polls in each
run reported camera `live`, IMU `ready`, detector `ready` and raw throttle flag
`0x0`. The preview RSS medians were 146.25 MiB (A) and 146.23 MiB (B);
FFmpeg RSS was about 158.1 MiB in each. These are process resident-memory
observations, not unique whole-system memory. The motion worker's skip counter
is not the detector's deliberate sampling count.

## Interpretation and decision

No throughput or readiness regression is apparent under this scene. The
preview CPU medians differ by only 0.16 percentage points of one core, less
than the variation these sequential runs can resolve. The negative sign does
**not** mean conversion saves CPU, and an indistinguishable A/B result does
**not** prove zero cost. The earlier isolated Pi microbenchmark measured about
28 microseconds per conversion, projecting only ~0.053% of one core at the
observed 18.8 Hz; this is below the practical resolution of the full-workload
comparison. B includes the opt-in branch's per-sample bias subtraction and
telemetry storage as well as the coordinate transform.

Thermal history is the main confounder. A's first/last measured-minute median
temperatures were **63.78→68.17°C**; B's were **70.60→71.58°C**. B started
much hotter, apparently after A had warmed the Pi. Both still showed sampled
`0x0` throttle flags, but these polls cannot rule out brief unobserved events.
Power, ambient temperature, negotiated camera mode and exposure/gain are also
unknown or unverified. These observations support a **provisional** scheduling
choice: keep one camera-axis conversion per valid IMU sample when a future
camera-rate feature uses this mounting, rather than decimate this cheap math.
The existing live option remains opt-in; these runs do not implement or
validate camera orientation, world heading, position, depth or spatial memory.

A repeat with matched starting temperature and reversed order or A/B/A would
be needed to estimate a small causal CPU difference more confidently. Such a
repeat is not required merely to show that the feature ran alongside the
current workload without an obvious quality loss.

Protocol: [live A/B instructions](../../docs/IMU_CAMERA_AXIS_AB.md) and
[active plan](../../docs/exec-plans/active/live-camera-axis-ab.md).
