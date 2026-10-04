# Camera and IMU recording

## Purpose / big picture

Save a short video and timestamped IMU readings together, so visible movement
can later be compared with measured rotation. This is a recording and timing
experiment, not synchronized sensor fusion or a camera pose estimator.

## Context and orientation

Pi 4, Bookworm aarch64 (previously reported kernel 6.12.47+rpt-rpi-v8),
USB OV9281 vendor-described camera, and SH3001 accessed via sunfounder_imu.
The IMU is taped firmly beside the camera on the moving head. Mounted pan
mostly projects onto Y, with an X component; the exact transform is unknown.
Use existing FFmpeg and SunFounder installations, plus Python standard library.

## Progress

- [x] 2026-10-04: Record mounted stillness, opposite turns, and return test.
- [x] 2026-10-04: Define separate camera PTS and host receipt timestamps.
- [x] 2026-10-04: Implement recorder; all 16 unit tests pass. Synthetic MJPEG
  smoke run saved 34 frame records and 21 fake IMU samples; saved video decoded
  successfully. This is a Mac functional check, not a Pi performance result.
- [ ] Run on Pi and review usable video, logs, overlap, and timing gaps.

## Plan of work

1. Save MJPEG packets in Matroska without recompressing them. Decode a second
   FFmpeg output to obtain showinfo frame PTS. Log each line's host receipt time.
2. Read raw acceleration and gyro in parallel; bracket each read with monotonic
   times and record its midpoint and duration. Preserve raw values.
3. Save metadata, counts, and completion state. Preserve partial failed runs.
4. First hardware run: 15 seconds still, 1280x720 MJPEG requested at 30 fps.
   Then a separate run: still 3 seconds, slowly turn the whole base and return,
   remain still. Use a well-lit textured scene; remove lens cap. Record actual
   scene, lighting, power, cooling, servo state, exposure/gain and warm-up in notes.

## Concrete steps

Run from repository root after applying the patch and pushing/pulling:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests/unit -v
sudo python3 src/recording/combined_capture.py --device /dev/video0 --seconds 15 --output recordings/combined-still-01 --notes "Still; describe scene, lighting, warm-up and power here"
```

Confirm the camera path using hardware_inventory.sh if it has changed. Close
other camera readers first. Output directory must be new; use a new name for
each retry. Ctrl+C stops capture and leaves partial files with failure status.
Allow startup before the printed RECORDING cue. This test changes the requested
camera mode to 30 fps and writes footage; earlier baseline tools remain separate.

## Validation and acceptance

Local tests check timestamp parsing, finite arguments, common clock conversion,
and FFmpeg output configuration. Pi acceptance requires successful completion,
nonzero frames and IMU samples, playable video, increasing timestamps and
coverage of the motion window. Inspect ffmpeg.log for negotiated mode and errors.
Hardware performance and playback remain unverified until the user runs it.

## Surprises and discoveries

IMU polling previously produced approximately 18.4 samples/s with a 50 ms sleep.
Host receipt time includes decode, buffering and scheduling delay. Camera PTS
has its own origin and must not be equated to the IMU clock. These logs can expose
gaps and approximate co-occurrence, but cannot establish exposure timing or
camera-IMU time offset. Packet video and decoded logs may differ at shutdown.

## Decision log

- 2026-10-04: Use 30 fps, preserving 720p, for a modest first combined workload.
- 2026-10-04: Retain raw sensor readings and both timestamp types; defer offset
  estimation, interpolation, axis transform and synchronization to later work.
- 2026-10-04: Store all run artifacts under Git-ignored recordings/. Footage is
  local and must not be committed. No new dependencies or servo commands.

## Outcomes and retrospective

Local tests and a real FFmpeg synthetic-input smoke test passed, including
decoding the saved video. Pi experiment remains pending. A successful recording
alone will not demonstrate sensor fusion accuracy or synchronized capture.
