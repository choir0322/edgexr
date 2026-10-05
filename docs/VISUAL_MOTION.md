# Compare video movement with the gyro

This offline experiment measures displacement of image content, then compares
its pattern with the mounted IMU's Y angular rate. It does not estimate camera
pose, perform object detection, or drive the servos.

## What the algorithm does

1. Verify the recording's metadata and CSVs using analyze_capture.py.
2. Compare every video frame timestamp with the recorded frame log, after
   removing their respective origins. Require matching counts, contiguous frame
   indices and relative PTS within 2 ms (the container uses millisecond ticks).
3. Decode to 320x180 grayscale. Compare nine fixed patches in each adjacent
   frame pair using phase correlation: a Fourier-based way to estimate shift.
4. Reject flat/weak patches, implausibly large shifts and disagreement. Require
   at least four agreeing patches. Report their median displacement. Divide by
   camera PTS interval to get pixels/second at the analysis resolution.
5. Subtract this run's first-second stationary gyro mean. Interpolate gyro at
   the midpoint of the pair's host receipt times, without extrapolating or
   bridging gaps greater than 150 ms. The user must verify initial stillness.
6. Report both signals separately, with per-second medians and an exploratory
   Pearson correlation against gyro Y. No fitted delay or scale is applied.

Positive image X means content moves right. Gyro Y uses the board's own axis
convention. Opposite signs are expected in the reviewed recording, but this
does not establish compass direction or a complete camera/IMU transform.

## Dependencies and commands

This optional tool needs NumPy plus existing ffmpeg and ffprobe. The chart also
needs Matplotlib. They were already present in the Mac analysis environment;
no packages were installed. Capture scripts remain independent of NumPy and
Matplotlib. Check the Python environment before running:

```bash
python3 -c "import numpy; print(numpy.__version__)"
ffmpeg -version
ffprobe -version
```

If a dependency is missing on the Pi or your selected Mac Python, stop and
choose an environment/install plan explicitly. No download occurs automatically.
Run from the repository root on the Mac, where these recordings were copied:

```bash
PYTHONPATH=src python3 -m recording.visual_motion /Users/ryanchoi/Desktop/combined-still-01 --output recordings/visual-still-01
PYTHONPATH=src python3 -m recording.visual_motion /Users/ryanchoi/Desktop/combined-motion-02 --output recordings/visual-motion-02
PYTHONPATH=src python3 -m recording.plot_visual_motion recordings/visual-still-01 recordings/visual-motion-02 --output recordings/visual-comparison.png
```

On Pi use the corresponding recordings/combined-* paths. No sudo is needed
to analyze readable files. Use new output names for retries. Each analysis
saves summary.json and motion.csv in a Git-ignored directory. Rejected rows
stay in the CSV; absent values are empty, not zero. The chart is an optional
PNG. Short recordings only: maximum 3000 frames, decoded in memory.

Run hardware-independent tests with:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests/unit -v
```

Five visual tests skip explicitly if NumPy is absent; a skip is not a pass of
the image-analysis checks. Test known shifts, flat/unrelated patches, an
outlier patch, timestamp mismatches and bounded gyro interpolation.

## Limits and acceptance

Host receipt is later than exposure and includes decoding/logging delay. IMU
read midpoint is not an internal sensor sample timestamp. Video PTS matching
validates file/log association, not clock synchronization. The first startup
interval is excluded explicitly. Do not interpret the correlation as timing
calibration, pixels-per-degree calibration or a performance benchmark.

Patch translation is an approximation under camera rotation. Moving objects,
parallax, repeated patterns and low texture can cause false or rejected matches.
Thresholds (patch stddev >=3 grayscale levels, peak ratio >=8, maximum shift
one quarter patch width/height, agreement within 1.5 pixels) are initial fixed
choices. Quality scores are not probabilities. Rejected intervals must remain
visible; do not tune thresholds or baseline duration to improve the final score.

First acceptance: stationary control close to zero; motion shows opposing
phases consistent with the gyro; report rejected samples and timing assumptions.
See VISUAL_MOTION_RESULTS.md for the observed results. Next useful work is a
minimal live preview/feature-motion display with measured runtime; precise
camera-motion compensation still needs camera intrinsics, mounting alignment
and timing calibration. Do not infer those from this one video.
