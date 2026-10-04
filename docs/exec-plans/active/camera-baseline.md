# Camera capture baseline

## Purpose / big picture

Make the first camera measurement repeatable and easy to explain. Success is a
Pi run that reports the negotiated video mode, decoded frame count, wall-rate,
and inter-frame timestamp spacing, followed by inspection of a sample image.

## Context and orientation

The user's Raspberry Pi 4 runs Linux `6.12.47+rpt-rpi-v8`. Its USB camera is
reported as `DECXIN CAMERA` on a 480 Mb/s connection. The first working mode is
1280x720 MJPEG at 120 requested fps. `docs/HARDWARE.md` records the observations.
The source code uses the FFmpeg installation already tested on the Pi; Python
adds no third-party package. The scene, lighting, power, cooling, and exact
sensor identity have not yet been recorded.

## Progress

- [x] 2026-10-04: Record USB, V4L2, and initial decode observations.
- [x] 2026-10-04: Add a small capture/decode timestamp tool and parser test.
- [ ] Run the tool on the Pi and record its summary and exact scene conditions.
- [ ] Inspect the sample PNG for focus, exposure, and image appearance.
- [ ] Verify raw IMU readings independently.

## Plan of work

1. Check the parser with synthetic FFmpeg output on a development computer.
2. Run the tool on the Pi with the already verified camera mode and device path.
3. Save a concise result summary under `benchmarks/results/` with conditions.
4. Review one image, then choose the next capture integration step.

## Concrete steps

From the repository root, run:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests/unit -v
python3 src/camera/capture_baseline.py --device /dev/video0 --seconds 10
```

Confirm the device path with `scripts/hardware_inventory.sh` first. The second
command opens the camera, requests 1280x720 MJPEG at 120 fps for 10 seconds,
decodes frames, and writes no video file. Close any other camera app before
running it. A failed run can be retried without cleanup.

## Validation and acceptance

The parser tests pass. On the Pi, the tool reports a negotiated input line and
more than zero decoded frames, and the timestamp anomaly counts are explicit.
The image is reviewed separately. A Pi result is not considered complete until
the scene, duration, power/cooling, and any limitations are recorded.

## Surprises and discoveries

The first FFmpeg run reported non-monotonic output DTS warnings while still
decoding 1,181 frames in about 10 seconds. The PNG conversion reported no
accelerated YUV-to-RGB conversion. Neither warning by itself establishes a
camera hardware failure.

## Decision log

- 2026-10-04: Use the FFmpeg tool already installed on the Pi and parse
  `showinfo` timestamps. This avoids adding an image library before capture
  behavior is understood. The output is a baseline, not a detector-ready frame
  API; the later integration step can choose that API with new measurements.

## Outcomes and retrospective

The initial camera and decode checks support proceeding with this hardware.
The new tool still needs a target-Pi run, and image quality is pending review.
