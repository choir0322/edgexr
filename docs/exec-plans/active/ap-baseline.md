# Phase 4 first step: sustained Pi application-processor baseline

## Purpose / big picture

Measure the existing full EdgeXR live workload on the Raspberry Pi 4 before
changing threads, camera rate, model or input size. The first question is not
"what is fastest?" but "where does time and CPU capacity go, and does the
application remain stable after warming up?" A documented baseline makes
later one-variable experiments meaningful.

## Context and orientation

The current preview requests the OV9281 USB camera at 1280×720 MJPEG/30 fps,
decodes through FFmpeg, analyzes a 320×180 grayscale copy for image motion,
runs MobileNet-SSD via OpenCV CPU with two internal threads at a target 2 Hz,
and optionally polls the camera-mounted IMU. Basic IoU tracking should be the
default for this baseline; motion-aware matching stays off because the first
Pi comparison showed no necessary ID hold and turn intensity was unpaired.

The recent tracking trial measured motion-analysis rate, detector compute and
box source age, but **not** sustained CPU load, memory, temperature, throttling
or true camera-to-display latency. Host frame receipt age is not sensor
exposure latency. See `docs/BENCHMARKING.md` and `docs/AP_OPTIMIZATION.md`.

## Progress

- [x] 2026-10-18: Finish and document the first basic-versus-motion-aware
  tracker comparison without claiming an accuracy winner.
- [x] 2026-10-18: User asked to proceed with this plan; implement the collector
  and documentation. Cooling/power details and safe long-run conditions are
  still unknown, so do not start the Pi measurement without the user's review.
- [x] 2026-10-18: Add a read-only collector for CPU, memory,
  temperature/throttling and existing telemetry, with hardware-free tests.
- [x] 2026-10-18: Update `docs/PIPELINE.md` and the learning guide with data
  sources, units, sampling rates, freshness and limitations.
- [ ] Run a warmed-up sustained baseline on Pi and commit a concise result
  summary; leave raw time-series logs outside Git.

## Plan of work

1. Define one unchanged workload: existing model files, 1280×720 MJPEG/30 fps
   request, `--detect --imu`, basic IDs, OpenCV two-thread setting, one stable
   well-lit scene. Record Pi OS, RAM, model hash, power, cooling and actual
   negotiated camera mode where available. Do not download models or change
   hardware in this step.
2. Build a read-only sampling tool that joins existing `/api/telemetry` values
   with Linux process/host observations. Label scopes separately: FFmpeg versus
   Python CPU, resident memory, Pi temperature, throttling flags, detector
   compute, source age, motion/IMU rates and decoded-frame skips. Use bounded
   output and a monotonic sampling clock. Do not imply these are synchronized
   exposure-to-display measurements.
3. Warm up before the measured window, then measure long enough to expose
   thermal drift. Proposed starting protocol: two minutes warm-up followed by
   five minutes of a mostly static, repeatable scene. Confirm that duration
   and safe cooling/power conditions with the user before running. A separate
   movement trial can follow, but must not be mixed with the static baseline.
4. Report medians/p95s and time trends, not isolated latest UI values. Commit
   a small table, versions, conditions and caveats under `benchmarks/results/`.
   Only after that select one optimization variable, such as OpenCV threads
   1/2/4, and keep all other settings fixed.

## Concrete steps

Begin by reading the existing timing definitions and checking which Linux
interfaces are available on this Pi; use fake fixture text for unit tests.
Run the full hardware-free suite on Mac. After code review/push/pull, follow
the exact Pi commands in `docs/AP_BASELINE.md`. Stop if temperature/throttling
indicates a safety or stability problem. Keep raw logs ignored and share only
a concise summary plus any anomalies needed for diagnosis.

## Validation and acceptance

- The collector labels each measurement's source, units, process scope and
  sampling interval, and handles unavailable sensors honestly.
- The workload and software commit are fixed across repeats; no silent model,
  camera or system configuration change occurs.
- A Pi result includes warm-up, measurement duration, achieved rates, CPU,
  memory, temperature/throttling and source-age distributions, with limitations.
- `docs/PIPELINE.md` and the learning guide match the code; raw footage and
  large machine logs remain out of Git.

## Surprises and discoveries

The tracking comparison had similar detector compute and motion throughput in
both modes, but its 60-second hand-moved runs were too short and too different
in turn rate to establish sustained AP capacity or a tracking winner.
The user's current motion-aware preview had already run for about 10–15 minutes.
That is useful stability evidence, but it is not this basic-tracking baseline;
the collector deliberately rejects motion-aware mode.

## Decision log

- 2026-10-18: Establish a two-thread full-workload baseline before tuning one
  variable. Do not infer CPU or thermal behavior from detector compute alone.
- 2026-10-18: Keep basic tracking as the baseline mode; defer motion-aware
  tuning and appearance re-identification during this AP measurement.
- 2026-10-18: Add read-only PID telemetry for the exact Python and FFmpeg
  processes, then observe `/proc`, thermal zone and firmware throttle flags
  from a second process. Do not save camera pixels or change preview scheduling.

## Outcomes and retrospective

Collector and learning notes implemented locally; Pi protocol review and the
actual Pi measurement remain. No sustained performance claim yet.
