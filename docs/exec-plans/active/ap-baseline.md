# Historical Pi application-processor baseline; tuning deferred

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
- [x] 2026-10-18: User ran the 120-second warm-up and 300-second basic-tracking
  Pi measurement; add its concise result under `benchmarks/results/`. Raw
  time-series logs remain outside Git.
- [ ] Confirm power supply, inspect thermal trend and decide whether a
  thermally stabilized repeat is needed before a future tuning comparison.
- [x] 2026-10-20: Preserve this pre-re-identification result as a reference;
  user moved AP optimization after object memory in the roadmap. Do not use
  this unchanged basic-tracking workload as the final tuning baseline.

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
The first basic run sustained about 30.09 capture fps, 26.16 motion fps and
2.00 detector Hz, with 1,203 skipped decoded frames during 300 seconds. Its
thermal-zone median rose about 4.38°C from the first to last measured minute;
all 297 sampled throttle flags were `0x0`. The user subsequently identified
passive metal-heatsink cooling with no fan; power supply, ambient and Pi RAM
remain unreported. See `benchmarks/results/ap-baseline-basic-2026-10-18.md`.

## Decision log

- 2026-10-18: Establish a two-thread full-workload baseline before tuning one
  variable. Do not infer CPU or thermal behavior from detector compute alone.
- 2026-10-18: Keep basic tracking as the baseline mode; defer motion-aware
  tuning and appearance re-identification during this AP measurement.
- 2026-10-18: Add read-only PID telemetry for the exact Python and FFmpeg
  processes, then observe `/proc`, thermal zone and firmware throttle flags
  from a second process. Do not save camera pixels or change preview scheduling.
- 2026-10-18: Preserve the completed first run with its incomplete conditions;
  do not treat rising temperature as a settled thermal baseline or compare
  future thread settings against it without matching/stabilizing conditions.
- 2026-10-20: Postpone tuning until re-identification is implemented and
  measured. A new full-workload baseline will include its actual runtime cost.

## Outcomes and retrospective

Collector, learning notes and first Pi result are recorded. It verifies one
five-minute operating window, not thermal equilibrium. Confirm remaining physical
conditions and decide on a stabilized repeat before closing this plan or
starting the OpenCV-thread comparison.
