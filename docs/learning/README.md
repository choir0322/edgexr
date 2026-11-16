# EdgeXR learning pages

Start with **[index.html](index.html)**: open it in a browser
(`open docs/learning/index.html` on the Mac). Every page works offline from a
clone: no server, camera, network or model download. A bar at the top of each
page follows the study path; previous/next links sit at the bottom.

These pages explain what the program computes, how it runs on the Pi's
processor and how its models work, using real Pi recordings and committed
measurements wherever they exist.

| # | Page | Question it answers |
|---|---|---|
| — | [Start here](index.html) | What is built, measured and planned; the five-step plan |
| 1 | [Program map](program-flow-explorer.html) | What runs, and what talks to what? |
| 2 | [Image motion](hann-fft-explorer.html) | How does the program know the picture shifted (and by how many degrees)? |
| 3 | [Detector model](detection-architecture.html) | How does MobileNet-SSD find a bottle, and where do its 1.12 billion operations go? |
| 4 | [Tracker IDs](basic-tracker.html) | How do boxes keep an ID, and why is it lost when the head looks away? |
| 5 | [Head orientation](orientation-explorer.html) | How does the gyro become a direction, why does it drift, what does polling cost? |
| 6 | [Pixel → direction](camera-geometry.html) | Which way is a pixel? Calibration, lens distortion, step-1 preview |
| 7 | [Scene memory](orb-scene-explorer.html) | How does a view become familiar, and what does matching cost? |
| 8 | [3D from two views](sparse-scene-01.html) | How do two photos give depth, and why can't a pan/tilt head do it? |
| 9 | [Workers & storage](edgexr-worker-rates.html) | How do threads, queues and the microSD card interact? |
| 10 | [Processor evidence](processor-evidence.html) | Where do the four cores and the milliseconds go? |

[calibration-screen.html](calibration-screen.html) is a tool, not a lesson: the
full-screen checkerboard used for camera calibration.

## Evidence labels

Pages mark numbers and drawings as **measured** (recorded on the Pi, with a
linked file in `benchmarks/results/`), **derived** (calculated from measured or
configured numbers, not timed), **illustrative** (teaching drawing or
simulation) or **planned** (not built yet).

## Code guides

The Markdown guides name the exact functions in the source; read them in VS
Code or on GitHub. In VS Code, open a linked file and use symbol search
(`Cmd+Shift+O`). Line numbers are deliberately not hard-coded.

1. [Image motion](IMAGE_MOTION.md): camera bytes → image arrays → displacement → arrow.
   Numerical detail: [Hann/FFT walkthrough](HANN_FFT_WALKTHROUGH.md).
2. [Object detection](OBJECT_DETECTION.md): newest image → model → scored boxes → overlay.
3. [Motion-aware ID matching](MOTION_AWARE_TRACKING.md): image shift history → box tracker.
4. [IMU](IMU.md): driver reading → timestamp → offset → angular-rate display.
5. [Scene memory](SCENE_MEMORY.md): images → ORB → verified view or unknown → view map.
6. [AP baseline collector](AP_BASELINE.md): how Linux counters are sampled without
   changing the workers ([Pi procedure](../AP_BASELINE.md)).
7. [Spatial progress and systems log](SPATIAL_PROGRESS_AND_SYSTEMS.md): chronological changes.

For background reading, the [CS:APP reading plan](CSAPP_READING_PLAN.md) maps
book chapters to EdgeXR measurements from mid-November to April/May.

[Code conventions](CODE_CONVENTIONS.md) explains the comment, type and docstring
notation. [The live pipeline diagram](../PIPELINE.md) is the compact reference for
the current implementation.

## Shared files

| File | Role |
|---|---|
| `learning-nav.js` | Study-path list; inserts the top bar and previous/next links |
| `learning-site.css` | Look of the hub and the newer pages (same tokens as the older pages) |
| `learning-charts.js`, `learning-charts.css` | Offline SVG charts with tooltips and table views; styles scoped to `.chart-frame` |
| `camera-geometry-math.js`, `orientation-math.js`, `tracker-example.js` | Page arithmetic, loadable in Node for checks |
| `images/` | Small derived images and precomputed data; no private recordings |

## Checks without hardware

From the repository root:

```bash
node scripts/check_learning_pages.js      # page arithmetic vs OpenCV / tracker rules
node scripts/check_sparse_learning.js     # sparse-scene page data and controls
PYTHONPATH=src python3 -m unittest discover -s tests/unit -v
python3 scripts/check_learning_contracts.py
```

`scripts/learning_geometry_fixtures.py` regenerates the OpenCV reference values
(needs OpenCV, which is not a project dependency). These checks do not replace
looking at the pages in a browser, and they say nothing about Pi timing.

## Terms used across the pages

- Process: a separate running program; FFmpeg is separate from EdgeXR Python.
- Thread: work inside one process sharing memory; live workers are threads.
- Shape: array dimensions. NumPy uses `(height, width)`; OpenCV resize takes `(width, height)`.
- Hz: updates per second. Milliseconds measure duration or age, not frequency.
- Monotonic time: a clock for intervals, not the calendar time.
- Latest slot: replace stale waiting work instead of keeping an unbounded queue.
- Bearing: direction from the fixed base (pan/yaw, tilt/pitch), used from step 1 on.

## Reading the whole repository

| Files | Role and guide |
|---|---|
| `src/app/live_preview.py`, `preview.html` | Shared live orchestration and browser; all guides |
| `src/recording/visual_motion.py` | Motion math plus offline comparisons; image-motion guide |
| `src/vision/detect_image.py`, `live_detector.py`, `basic_tracker.py`, `motion_history.py` | Detection and ID matching; detection and tracking guides |
| `src/imu/raw_baseline.py`, `rotation_test.py`, `live_reader.py` | Sensor checks and live values; IMU guide |
| `src/spatial/` | Orientation, camera axes, calibration, scene memory, view map, sparse reconstruction |
| `src/recording/combined_capture.py`, `analyze_capture.py` | Separate recording/analysis workflow |
| `src/profiling/ap_baseline.py` | Read-only sustained AP collector; AP baseline guide |
| `tests/unit/` | Fake-data contracts, invalid-input and failure checks |
| `scripts/` | Read-only inventory, project and learning checks |

Update this map, the page list in `learning-nav.js` and [the diagram](../PIPELINE.md)
when responsibilities change.
