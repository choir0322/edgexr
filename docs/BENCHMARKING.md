# Benchmarking protocol

## Principle

A number without conditions is not a result. Every EdgeXR benchmark must say
what was run, where it ran, how long it ran, and how the camera was configured.
Keep the first benchmark simple enough to repeat.

## Baseline record

For each run, capture:

- Git commit ID and configuration file.
- Raspberry Pi model, RAM, OS version, power supply, cooling, and ambient
  conditions when known.
- Camera identity, negotiated resolution, pixel format, requested and measured
  frame rate, exposure/gain, and scene description.
- Detector/tracker version and model file identity, if used.
- Run duration and warm-up duration.
- Median and 95th-percentile end-to-end latency, FPS, CPU usage, memory use, and
  CPU temperature, including how each metric was measured.

## Method

1. Confirm the device is in a stable thermal state or state that it is not.
2. Run a warm-up period without counting it in the result.
3. Measure the same static, well-lit scene for a fixed duration.
4. Save raw machine logs outside Git when large; commit a small CSV or Markdown
   summary under `benchmarks/results/`.
5. Change one variable at a time (for example resolution *or* detector model),
   then compare against the baseline.

Never compare results from different camera modes, cooling setups, or run
durations as if they were the same experiment. Document the limitation instead.
