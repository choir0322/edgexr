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
- [ ] Browser display and SSH connection verification (local bind is blocked).
- [ ] User runs on Pi; record camera mode, scene, runtime metrics and usability.

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
the frame, arrow state and metrics render. Pi acceptance remains pending until
the user confirms stream and records rates/cost under target conditions.

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

Local non-network checks passed. The execution sandbox rejected binding to
127.0.0.1 with Operation not permitted, so the actual browser display/SSH
integration and Pi performance remain unverified. In-memory HTTP route and
JavaScript rendering tests do not substitute for that integration check.
This workload differs from offline analysis and earlier capture-only baselines.
Record scene/lighting, power, cooling, warm-up, versions and metrics on the Pi.
