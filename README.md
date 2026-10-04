# EdgeXR

EdgeXR is a learning-first spatial-perception and performance project for a
Raspberry Pi 4. The intended system will use a USB global-shutter OV9281 camera,
an IMU from the SunFounder AI Fusion Lab Kit, object detection/tracking, and
careful measurement of latency, CPU use, memory use, and temperature.

This repository is deliberately starting with documentation and verification
tools rather than a large codebase. Each addition should answer a question,
explain its tradeoffs, and be tested or observed.

## What EdgeXR will demonstrate

Move the camera around a small scene. The system should detect and track visible
objects, use IMU information to distinguish camera motion from scene motion,
and report how its workload performs on the Raspberry Pi.

Read [the project brief](docs/PROJECT.md), [architecture](docs/ARCHITECTURE.md),
[hardware guide](docs/HARDWARE.md), and [benchmark protocol](docs/BENCHMARKING.md)
before adding a feature.

## Start in VS Code

1. Open this root folder in VS Code: `code .`
2. Read `AGENTS.md` and `docs/ROADMAP.md`.
3. Run `bash scripts/check_project.sh` to confirm the starter layout is intact.
4. Work through Roadmap Phase 0: verify the Pi, USB camera, and IMU separately
   before integrating them.

The included VS Code recommendation only suggests the Python extension; it does
not install anything or choose a Python environment for you.

## GitHub workflow

This folder is initialized locally on the `main` branch. Create an empty GitHub
repository named `edgexr` (do not add a README or `.gitignore` there), then add
it as this repository's `origin`:

```bash
git remote add origin https://github.com/YOUR-ACCOUNT/edgexr.git
git push -u origin main
```

For each small, working unit of progress:

```bash
git status
git diff
bash scripts/check_project.sh
git add <specific files>
git commit -m "docs: describe the first camera check"
git push
```

Use a short branch for experiments or a feature, and merge it only after its
documentation and checks are current. Push at the end of a meaningful session;
do not treat an unpushed local commit as a backup. Never add passwords, tokens,
raw video, or large model files to commits.

## Current status

The first Pi check identified a 1280x720 MJPEG mode near 119 decoded frames per
second. The observation and remaining unknowns are in `docs/HARDWARE.md`.
To repeat a timestamped capture/decode baseline on the Pi:

```bash
python3 src/camera/capture_baseline.py --device /dev/video0 --seconds 10
```

Choose the device reported by `scripts/hardware_inventory.sh`; `/dev/video0`
was correct for the first check but is not guaranteed. The tool requires FFmpeg,
which was already available on the tested Pi. It requests 1280x720 MJPEG at
120 fps by default and does not save footage. Use `--help` to see mode options.
Run hardware-independent checks with:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests/unit -v
```

The Pi must still run this new tool, and the sample image needs visual review.
After that, verify the exact IMU hardware before camera/IMU integration.
