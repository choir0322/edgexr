# Pi 4: first sustained basic-tracking AP baseline

This is one user-operated, stationary full-workload run on 2026-10-18. It is a
reference for later one-variable comparisons, **not** a claim of thermal
steady state, model accuracy or camera-to-screen latency. The raw
`recordings/ap-baseline-basic-01/samples.jsonl` remains on the Pi and is not
tracked in Git. Values below come from the shared `summary.json`,
`metadata.json` and `v4l2-ctl` output; the raw trace was not independently
inspected on the Mac.

## Conditions and provenance

- Raspberry Pi 4; Linux `6.12.47+rpt-rpi-v8` aarch64, glibc 2.36; commit
  `30f62d773d55701c1ff392dd903ca50e8197429d`. Cooling was clarified
  after the run as a standard passive metal heatsink with no fan; the
  metadata entered at run time still says `unknown`. Pi RAM, ambient
  temperature and power supply were not reported.
- Camera `/dev/video0`: V4L2 reported negotiated 1280×720 MJPEG at 30 fps.
  Exposure/gain were not recorded. Scene: stationary, well-lit desk; camera
  head still. Whether a browser was open during the run was not recorded.
- Live preview `--detect --imu` with **basic** tracking, 320×180 grayscale
  motion analysis, MobileNet-SSD CPU detector targeting 2 Hz with two OpenCV
  internal threads. No motion-aware matching. Local graph SHA-256:
  `2d180f723b3109e21f8287f6b3c691390d07b60eed998327cd3259ffa0e50608`;
  weights SHA-256:
  `52eed8be80522c152a17fb56740de705b79881bde1a167e0e747310523685fc7`.
- Warm-up 120 seconds; measurement 300.008 seconds from approximately
  05:07:44 to 05:12:44 UTC. The read-only collector targeted one poll/second
  and completed 297 samples. Camera, detector and IMU reported `live`,
  `ready`, `ready` in all 297 polls.

## Observations

| Metric | Median | Sample p95 | Scope |
|---|---:|---:|---|
| Camera capture rate | 30.09 fps | 30.22 fps | Recent app rate |
| Motion analysis rate | 26.16 fps | 26.86 fps | Recent app rate |
| Motion estimator time | 30.98 ms | 53.55 ms | Latest worker compute at poll |
| Python preview CPU | 188.39% | 192.92% | 100% = one logical core |
| FFmpeg CPU | 34.54% | 35.74% | 100% = one logical core |
| Aggregate system CPU busy | 56.93% | 58.46% | 100% = all-core capacity |
| Python preview RSS | 145.90 MiB | 145.93 MiB | Resident process memory |
| FFmpeg RSS | 158.12 MiB | 158.12 MiB | Resident process memory |
| Thermal-zone-0 temperature | 70.60°C | 72.55°C | Linux thermal reading |
| Detector completion rate | 2.00 Hz | 2.01 Hz | Recent completed results |
| Detector compute | 226.39 ms | 243.65 ms | 297 distinct results observed |
| Box source age at first poll | 429.76 ms | 706.98 ms | From frame host receipt |
| IMU read rate | 18.87 Hz | 18.97 Hz | Recent host read rate |

The motion worker's cumulative skipped-decoded-frame counter increased by
1,203 over the measured interval, approximately four per second. This is
consistent with capture near 30 fps and analysis near 26 fps; it does not
mean the detector missed exactly 1,203 objects or frames. The collector saw
297 distinct detector sequences because it polled around once per second,
while detection completed near twice per second. Its first-polled box-age
distribution therefore does not cover every detector result.

Thermal-zone-0 median rose from **67.68°C in the first measured minute** to
**72.06°C in the last** (about +4.38°C); the last-minute p95 was 73.04°C.
Every one of the 297 sampled firmware throttle flags was raw `0x0`. The
upward temperature trend means the 120-second warm-up did not establish a
demonstrably flat thermal state. `0x0` at these poll times does not prove that
no brief condition occurred between polls.

## Interpretation and next decision

The complete workload sustained the requested capture rate and the configured
detector cadence in this scene, while motion analysis skipped some decoded
frames. Python plus FFmpeg consumed roughly 2.23 logical-core equivalents at
their median sampled CPU rates; their process CPU values must not be compared
as if each were a percent of the entire four-core Pi. Summing process RSS is
not a precise unique-memory figure because shared pages may overlap.

Before claiming a thermally stable baseline or ranking OpenCV thread settings,
identify the power supply and ambient conditions, inspect temperature and skip
trends (raw trace remains on the Pi), and repeat with the same scene after
adequate thermal stabilization. Change only one setting in any later
optimization experiment. These observations do not measure electrical power,
camera exposure timing, browser/SSH delay, true end-to-end latency, detection
accuracy or identity-tracking correctness.

Protocol: [AP baseline procedure](../../docs/AP_BASELINE.md) and
[active plan](../../docs/exec-plans/active/ap-baseline.md).
