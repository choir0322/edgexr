# SSH browser camera preview

## Purpose / big picture

Show the Pi camera and an image-motion arrow in a Mac browser over an SSH
tunnel. Measure the processing cost of the existing image_shift estimator.
No IMU, servo control, detection or recording in this first live version.

## Context and orientation

Pi 4 with USB MJPEG camera, requested 1280x720 at 30 fps. FFmpeg decodes to
320x180 grayscale. NumPy is already required by the offline estimator; verify
it is installed in the Pi's selected Python before running. Python's standard
HTTP server and browser canvas avoid adding a web framework or image encoder.
This is a local development preview, not an internet service.

## Progress

- [x] 2026-10-05: Read repository instructions and offline motion estimator.
- [x] 2026-10-05: Implement bounded latest-frame capture, analysis and loopback HTTP UI.
- [x] 2026-10-05: 30 tests pass: packet reads, skips, stale/errors and in-memory
  HTTP responses. One live-socket test skips due to sandbox permission denial.
- [x] 2026-10-05: Real FFmpeg synthetic capture/analysis/shutdown smoke test
  passed (63 frames processed). JavaScript render logic passed with live,
  stale and error payloads; these are functional checks, not Pi benchmarks.
- [x] 2026-10-05: User opened the Pi preview on Mac through SSH local forwarding
  after selecting Mac port 8766 (8765 was already occupied). The live image
  appeared; the arrow appeared on turning, reversed on opposite motion,
  and disappeared after stopping.
- [x] 2026-10-05: User reported approximately 30.1 analyzed frames/s, latest
  estimator times 29.0 ms stationary and 27.3 ms during a slow turn, and zero
  skipped decoded frames across two observations ten seconds apart and motion.
  NumPy 1.26.4 was confirmed on the Pi. Scene, lighting, temperature, warm-up,
  power and cooling were not recorded for this measurement.

## Plan of work

1. FFmpeg reader continuously replaces one latest decoded frame; analysis uses
   the newest available frame so it cannot accumulate a Python processing queue.
2. Reuse image_shift; show unreliable estimates explicitly. Count frames skipped
   between analysis steps. Host receipt time is not camera exposure time.
3. Serve one page and a latest-frame JSON endpoint at 127.0.0.1:8765. Browser
   requests sequentially at up to 5 updates/s, displays grayscale and an arrow.
4. Display decode receipt rate, analyzed rate, estimator duration and result
   age separately. None is end-to-end camera latency. Do not promise 30 fps.

## Concrete steps

See docs/LIVE_PREVIEW.md for two-terminal SSH commands. Confirm NumPy and FFmpeg
first. Stop other camera readers. Request 720p MJPEG/30 fps, analyze 320x180.
Start still in a well-lit textured scene, then gently turn the whole robot base
without forcing servo gears. Stop with Ctrl+C. No footage or sensor settings
are saved. Port may be selected locally, but bind address cannot be expanded.

## Validation and acceptance

Local unit tests exercise partial pipe reads, frame replacement, skipped counts,
valid/unreliable/stale results and route restrictions. A synthetic FFmpeg source
tests the real reader/analysis/server path and cleanup. Browser check verifies
the frame, arrow state and metrics render. The user confirmed these behaviors
on the Pi and reported rates/cost under the requested 720p/30 fps mode. Actual
negotiated mode, long-run stability and complete benchmark conditions remain
unverified, so these numbers are an initial observation, not a benchmark.

## Surprises and discoveries

Grayscale bytes are sent as base64 (~77 KB per frame) and rendered in canvas.
At five updates per second this is roughly 0.4 MB/s before protocol overhead,
not a bandwidth-optimized video stream. Analysis and browser refresh are separate.

## Decision log

- 2026-10-05: Use existing NumPy/FFmpeg plus standard library HTTP. No installs.
- 2026-10-05: Bind only loopback; access remotely via SSH local port forwarding.
- 2026-10-05: Keep a single decoded frame and single analyzed result. Display
  skipped frames rather than hiding overload behind buffering.
- 2026-10-05: Arrows describe scene content displacement between analyzed frames
  in 320x180 pixels, not camera angles or optical-flow velocity per exposure.

## Outcomes and retrospective

The real Pi and Mac SSH tunnel passed the first usability check. Initial
analysis stayed near the requested 30 fps, with zero counted frame skips in
the short observation. The latest estimator times were 27.3-29.0 ms, leaving
only about 4-6 ms of the nominal 33.3 ms frame period for the other Pi work.
That margin is illustrative, not a worst-case bound: the page shows only the
latest estimator duration, not its distribution, and it excludes decode,
transport and display. Thus no end-to-end latency or thermal claim follows.

The first Mac tunnel attempt failed because local port 8765 was in use; port
8766 worked without changing the Pi port. The local development sandbox's
socket restriction did not apply on the Pi. No camera settings, exact scene,
power/cooling or temperature were recorded, so benchmark reproducibility is
incomplete. A sustained run with percentile estimator cost, CPU/temperature,
and explicit camera mode would be needed for a performance comparison.

The camera-only live-preview milestone is usable. Next compare live gyro
readings with the image movement, while preserving separate sensor metrics.
