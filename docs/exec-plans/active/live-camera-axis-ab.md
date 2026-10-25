# Live camera-axis conversion A/B

## Purpose / big picture

Test whether projecting every valid live IMU gyro sample into the validated
neutral camera axes adds meaningful AP load under the real detection/motion
workload. This enables a future bounded orientation feature; it does not add
camera pose today. The AP question is compute cost under contention versus
camera/IMU quality.

## Context and orientation

The Pi 4 has an OV9281 USB camera, head-mounted SH3001 IMU, passive heatsink
and no NPU. The camera request is 1280x720 MJPEG/30. The existing basic live
preview uses MobileNet-SSD CPU at target 2 Hz, motion analysis at 320x180 and
50 ms post-read IMU polling. `camera_components` costs about 28 microseconds
per call in the isolated Pi test. The neutral-head basis was independently
checked on pan and uncovered-lens tilt. See [the run protocol](../../IMU_CAMERA_AXIS_AB.md).

## Progress

- [x] 2026-10-25: User approved controlled current-versus-conversion live runs.
- [x] Add opt-in basis and per-valid-sample conversion without altering control mode.
- [x] Add collector mode preflight and conversion-count telemetry.
- [x] Review/update `docs/PIPELINE.md` and `docs/learning/IMU.md` for the new
  optional live rate branch, including units and freshness.
- [ ] Run A and B on the Pi with the same scene, power, cooling and durations.
- [ ] Compare complete summaries and temperature trends; record a cautious
  scheduling decision in `benchmarks/results/`.

## Plan of work

1. Test basis loading, opt-in conversion, stale/error handling and collector
   mode checks without hardware. Preserve sensor-axis rates.
2. Run the existing AP collector in control and conversion modes with the
   same 120-second warm-up and 300-second measurement.
3. Compare CPU, IMU/camera/motion/detector rates, skipped decoded frames,
   temperature and throttle flags. If thermal history differs, repeat.

## Concrete steps

Follow [IMU_CAMERA_AXIS_AB.md](../../IMU_CAMERA_AXIS_AB.md). It gives the exact
two-terminal Pi commands and safe retry names. `--camera-axis-basis` selects
the B run; `--camera-axis-mode` makes the collector reject a mismatched run.

## Validation and acceptance

Unit tests pass; both collectors must write complete metadata/summary on the
same code commit. B must report conversion-count growth, A zero. Neither may
be stale, error, throttled or in motion-aware tracking mode. Compare trends,
not a single last reading. Camera-axis rates are deg/s and not integrated pose.
The live diagram and learning guide must match actual optional data flow and
not imply use by image motion, detector or tracker.

## Surprises and discoveries

Pending Pi A/B measurement. The conversion-mode branch computes the corrected
gyro at sample time; the control branch still computes it when a snapshot is
requested. Therefore A/B measures the opt-in implementation path, not solely
the three dot products.

## Decision log

- 2026-10-25: Use the validated basis as an explicit opt-in JSON config; do
  not silently change the current `--imu` behavior or use gyro as camera pose.
- 2026-10-25: Reuse the existing full-workload AP collector, rather than add a
  second camera opener or a new model. Keep its warm-up/measurement protocol.

## Outcomes and retrospective

Implementation and hardware-free checks are ready. Pi evidence is pending.
