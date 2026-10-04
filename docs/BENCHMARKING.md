# Benchmarking protocol

For the new simultaneous 720p/30 fps camera and raw IMU recording experiment,
see [COMBINED_CAPTURE.md](COMBINED_CAPTURE.md). Its stored video, disk writes,
and concurrent sensor polling make it a different workload from the camera-only
120 fps baseline below. Host receipt timestamps are not exposure timestamps.

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

## Camera-only baseline

`src/camera/capture_baseline.py` uses the installed FFmpeg command to request a
V4L2 MJPEG mode and decode frames. FFmpeg's `showinfo` filter reports each
decoded frame's input presentation timestamp. The tool reports both frames per
wall second and the rate derived from the timestamp span, plus median and 95th
percentile spacing between positive timestamps. Equal or backward timestamps
are counted separately; they do not by themselves prove repeated images.

This tool does not convert every frame to RGB, display video, run detection, or
measure end-to-end application latency. Its timestamp logging also adds some
overhead. Record its exact command, scene, duration, and Pi conditions alongside
any result. Do not compare its throughput directly with an application FPS.
