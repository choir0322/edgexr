# Read the EdgeXR code from end to end

These guides explain the currently inspected implementation, not an idealized
replacement. Start with [the live diagram](../PIPELINE.md). Then study:

1. [Image motion](IMAGE_MOTION.md): camera bytes -> image arrays -> displacement -> arrow.
2. [Object detection](OBJECT_DETECTION.md): newest image -> model -> scored boxes -> overlay.
3. [IMU](IMU.md): driver reading -> timestamp -> offset -> angular-rate display.

Each guide names exact functions in linked source files. In VS Code, open the
linked file and use symbol search (`Cmd+Shift+O` on Mac) or search the function
name. Relative links work after committing to GitHub and when the repo is
cloned to the Pi. Line numbers are deliberately not hard-coded because the
comment/layout revisions can move them.

## How to study a step

For each function, write down: caller, input type/shape/units, output, side
effects, thread, timestamp meaning and failure path. Follow one actual value
through the next call. Read the named test next: its assertions are concrete
examples of the contract. Do not start with the entire neural network or all
Fourier mathematics at once; understand the data crossing each boundary first.

Terms used here:

- Process: separate running program; FFmpeg is separate from EdgeXR Python.
- Thread: work running inside that process with shared memory.
- Worker: a responsibility; our live workers are threads, not independent Python processes.
- Shape: array dimensions. NumPy uses `(height, width)` for grayscale images;
  OpenCV resize takes `(width, height)`. Confusing these swaps the dimensions.
- Hz: updates per second. Milliseconds measure duration or age, not frequency.
- Monotonic time: a clock for intervals that is not the calendar date/time.
- Latest slot: replace stale waiting work instead of keeping an unbounded queue.
- Lock/condition: coordinate shared state; expensive work runs outside its lock.

## What is and is not being refactored

The refactor covers first-party Python source and tests, browser JavaScript
and shell scripts. It does not rewrite OpenCV, FFmpeg, NumPy, SunFounder's driver
or the pretrained network. Their internals are dependency boundaries, explicitly
labelled in the guides. Python functions now include input/return annotations,
Args/Returns docstrings and task-group explanations. Browser functions use
JSDoc; shell scripts describe inputs, outputs and grouped operations. Read
[the code conventions](CODE_CONVENTIONS.md) to understand the notation.

Read [the active learning-refactor plan](../exec-plans/active/learning-refactor.md)
for code-comment/type/docstring milestones and validation status.

## Testing without hardware

From the repository root, use the existing environment:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests/unit -v
python3 scripts/check_learning_contracts.py
bash scripts/check_project.sh
```

Tests use fake inputs and do not prove physical hardware timing. Some tests need
NumPy/OpenCV or a loopback socket and can skip without them. Detection report
tests create temporary files under `recordings/`, so the checkout must be
writable. Do not run camera programs concurrently against the same device or
install dependencies simply to make all optional tests run.

## Reading the whole repository

| Files | Role and guide |
|---|---|
| `src/app/live_preview.py`, `preview.html` | Shared live orchestration and browser; all three guides |
| `src/recording/visual_motion.py` | Shared motion math plus offline comparisons; image-motion guide |
| `src/vision/detect_image.py`, `live_detector.py` | Saved/live detection; object-detection guide |
| `src/imu/raw_baseline.py`, `rotation_test.py`, `live_reader.py` | Sensor checks and live values; IMU guide |
| `src/recording/combined_capture.py`, `analyze_capture.py`, `plot_visual_motion.py` | Separate recording/analysis workflow; image-motion and IMU guides |
| `src/camera/capture_baseline.py` | Initial camera decode/PTS baseline; image-motion guide |
| `tests/unit/` | Fake-data contracts, invalid-input and failure checks |
| `scripts/hardware_inventory.sh`, `check_project.sh` | Read-only inventory and repository layout checks |
| `src/*/__init__.py` | Package descriptions; no background service starts here |
| `src/_contracts.py` | Shared type vocabulary: Frame, MotionShift, sensor vectors and read-only Sensor interface |
| `scripts/check_learning_contracts.py` | Dependency-free syntax audit of named function annotations and docstring sections |
| `.codex/config.toml`, `.vscode/extensions.json`, `.gitignore` | Development configuration, not runtime sensor paths |

Update this map and [the diagram](../PIPELINE.md) when those responsibilities change.
