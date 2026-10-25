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
- [x] 2026-10-25: Run A and B on the Pi with matching declared scene, power,
  cooling, code commit, detector/model, tracking mode and durations; metadata
  reports both complete. Negotiated camera mode and ambient temperature were
  not independently checked.
- [x] 2026-10-25: Compare summaries and temperature trends; record a cautious
  [feasibility result](../../../benchmarks/results/camera-axis-live-ab-2026-10-25.md).
- [ ] Optional: repeat with matched starting temperature/reversed order if a
  tighter causal estimate of the small CPU difference becomes necessary.

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

The conversion-mode branch computes the corrected
gyro at sample time; the control branch still computes it when a snapshot is
requested. Therefore A/B measures the opt-in implementation path, not solely
the three dot products. Both runs reported 297 ready/live polls without
sampled throttling; B performed 5,638 conversions over five minutes. The B
run's first measured-minute median was 70.60°C versus A's 63.78°C, so the
sequential A/B order carried a large thermal-history difference.

## Decision log

- 2026-10-25: Use the validated basis as an explicit opt-in JSON config; do
  not silently change the current `--imu` behavior or use gyro as camera pose.
- 2026-10-25: Reuse the existing full-workload AP collector, rather than add a
  second camera opener or a new model. Keep its warm-up/measurement protocol.
- 2026-10-25: Treat the A/B result as a feasibility check, not proof of zero
  conversion cost. Preserve per-valid-sample conversion as an opt-in candidate;
  do not add a decimation scheduler or make it default solely from this pair.
  A thermally matched repeat is optional if exact incremental CPU attribution
  becomes important.

## Outcomes and retrospective

Implementation and hardware-free checks passed. Both Pi runs completed on
commit `049d531` with equal requested settings except the conversion switch.
Preview CPU medians were 187.48% (A) and 187.32% (B) of one core; motion and
IMU rates, skips and readiness were practically similar. B's warmer start
limits causal interpretation. The AP lesson is to separate isolated operator
cost from integrated workload observations and to inspect thermal/order effects
before crediting a tiny median difference to code. No camera pose or live
spatial memory is claimed.
