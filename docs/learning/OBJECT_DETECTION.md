# Study 2: object detection, newest image to labelled boxes

This guide follows [the live diagram](../PIPELINE.md). Detection asks which of
the model's known categories occur in an image and where. It does not preserve
an object's identity across frames, correct boxes for camera motion, or train
the model while the preview is running.

## Source reading route

| Order | File | Symbols to read |
|---|---|---|
| 1 | [live_preview.py](../../src/app/live_preview.py) | `main`, its `build_detector` callback, `camera_command`, nested `capture`, `State.publish_frame` |
| 2 | [live_detector.py](../../src/vision/live_detector.py) | `detect_latest`, its `detection_frame_ready` callback, `CpuDetector.__init__`, `CpuDetector.__call__` |
| 3 | [detect_image.py](../../src/vision/detect_image.py) | `infer_once`, `LABELS`, `parse_detections` |
| 4 | [live_detector.py](../../src/vision/live_detector.py) | `DetectionState.publish`, `DetectionState.snapshot`, `fail` |
| 5 | [live_preview.py](../../src/app/live_preview.py) | `State.snapshot`, `make_handler` |
| 6 | [preview.html](../../src/app/preview.html) | `render` detector status and box loop; `poll` |

## 1. Optional setup and dependency boundary

`main()` imports OpenCV only when `--detect` is selected, requests two OpenCV
threads and disables OpenCL. It starts one application detection thread whose
target is `detect_latest`. OpenCV's internal parallel threads are not two
detector workers or reserved CPU cores. Two threads and 2 Hz are unrelated
choices; their optimization is future work in [the AP agenda](../AP_OPTIMIZATION.md).

`CpuDetector.__init__(cv, prototxt, weights)` receives the imported OpenCV module
and two path-like arguments. It verifies the files exist, loads them with
`cv.dnn.readNetFromCaffe`, and selects `DNN_BACKEND_OPENCV` plus `DNN_TARGET_CPU`.
The `.prototxt` describes the computation graph; `.caffemodel` supplies pretrained
parameters. Missing files produce a detector error rather than an automatic
download. See [the setup record](../DETECTION_BASELINE.md) for provenance.

MobileNet feature extraction and SSD box/category prediction are operations
described in that external graph and executed by OpenCV. They are not separate
handwritten Python functions in this repository. When studying deeper, inspect
the already-downloaded `deploy.prototxt` locally: look for convolution layers,
depthwise `group` values, prior boxes, localization/confidence heads and the
DetectionOutput layer. The project calls that graph; it does not implement
OpenCV's convolution kernels. This is inference, not backpropagation/training.

## 2. Keep a separate full-resolution source slot

With detection enabled, FFmpeg outputs 1280x720 grayscale. The capture reader
stores a small image for motion and the original full bytes for detection.
`State.detection_frame` is `(sequence: int, receipt_seconds: float, pixels: bytes)`.
Its 921,600-byte image is independent of the 57,600-byte motion image.

This avoids preparing the 300x300 detector input from an already reduced 320x180
image. It is a design choice, not a requirement that all detectors receive
720p. It increases internal pipe/resize work even on frames the detector never
uses. A single latest slot replaces older waiting frames; a running detector
still holds the frame it selected.

## 3. Select frames at a target two updates/second

In `detect_latest(state, factory, clock)`, `factory` is a zero-argument callable
that constructs the detector once. `clock` is a zero-argument monotonic-seconds
callable, injectable for tests. The loop waits until the next eligible start,
then selects the newest not-yet-processed source frame under the state condition.
It releases the condition before inference so capture can keep publishing.

`build_detector()` and `detection_frame_ready()` now name the original anonymous
callbacks. Naming them adds documentation and editor navigation; their evaluation
timing and expressions are unchanged. The latter tests stop/error/new sequence,
not a motion trigger. Detector shapes/units also appear directly in docstrings.

```python
started = clock()
due = started + .5
if started - frame[1] > MAX_AGE:
    continue
boxes = detector(frame[2])
finished = clock()
```

Line by line: measure this attempt's start; schedule the next eligible start
500 ms later; reject a source already older than the freshness limit; run the
detector on its bytes; measure completion. The target limits expensive work
while the other workers continue. Inference itself is not interrupted at 500 ms.

For 230 ms compute, there is roughly 270 ms until the next eligible start.
For 800 ms compute, the next attempt can begin after completion, not in parallel,
and there are no catch-up bursts. Two Hz is a target ceiling, not a guarantee.
The skipped motion-frame counter does not count this deliberate detector sampling.

## 4. Prepare exactly what the network expects

`CpuDetector.__call__(pixels)` reshapes the byte string into a `uint8` NumPy array
with shape `(720,1280)`, then calls `infer_once(cv, net, gray)`.

`infer_once` performs these exact operations:

```python
bgr = cv.cvtColor(gray, cv.COLOR_GRAY2BGR)
blob = cv.dnn.blobFromImage(bgr, scalefactor=0.007843, size=(300, 300),
                           mean=(127.5, 127.5, 127.5), swapRB=False, crop=False)
net.setInput(blob)
output = net.forward()
```

- `cvtColor`: replicate each gray intensity into three channels. This does not
  invent color. The resulting image has height/width/channel shape `(720,1280,3)`.
- `blobFromImage`: directly resize to 300x300, subtract the per-channel mean and
  multiply by the scale; prepare a float input blob with batch/channel/height/
  width shape `(1,3,300,300)`. `crop=False` uses direct resizing rather than
  letterboxing; the 16:9 image is stretched to square at the model boundary.
- The numeric transform is `(pixel - 127.5) * 0.007843`. Values span approximately
  -1 to +1; they are not restricted to -1, 0 and +1. Intensity 100 becomes about
  -0.216. This preprocessing belongs to these pretrained weights, not every
  model carrying the MobileNet/SSD name.
- `setInput`: assign the prepared tensor to the network.
- `forward`: execute the pretrained graph on the selected CPU backend. The
  graph includes its output processing; our Python parser is not an additional
  implementation of non-maximum suppression.

`infer_once` checks for output shape `[1,1,N,7]` and returns the `N x 7` rows plus
nanosecond timing boundaries. Each row is batch index, class ID, score, left,
top, right, bottom. Box coordinates are relative to image width/height.

## 5. Filter and map predictions

`parse_detections(rows, width, height, threshold)` accepts numeric seven-element
rows, positive image dimensions and a threshold in `[0,1]`. It validates shape,
finite values, scores and class IDs, skips the no-detection sentinel/background,
and rejects scores below the threshold. Live `CpuDetector` passes threshold 0.5.

Left/top are clipped to the image and rounded down; right/bottom are clipped
and rounded up. Empty boxes are removed. For normalized coordinates
`[0.25,0.25,0.75,0.75]` at 1280x720, the pixel box is `[320,180,960,540]`.
Each returned dictionary contains `class_id`, `label`, `confidence` and
`box_xyxy` (four integer coordinates). A score is not a calibrated probability.

`LABELS` contains background plus 20 object classes: aeroplane, bicycle, bird,
boat, bottle, bus, car, cat, chair, cow, diningtable, dog, horse, motorbike, person,
pottedplant, sheep, sofa, train and tvmonitor. Threshold changes do not add new
categories such as keyboard or cup.

## 6. Publish a result without pretending it is current

`DetectionState.publish(frame, boxes, cost_ms, finished)` saves the source
sequence, its receipt time, the boxes and elapsed compute cost. This live cost
surrounds the detector call, including preprocessing/parser, but excludes model
construction, camera capture and display. A bounded deque records completions.

`snapshot(now, camera_live)` calculates result-source age from frame receipt,
not completion, and completion rate from recent timestamps. It hides boxes
when disabled, failed, stale (over 1.5 seconds), or the camera isn't live. A
loading/startup timeout is separate. No detection boxes is a valid ready result,
not automatically a detector failure. A detector failure does not stop capture.

## 7. Display an older box on the latest motion image

`State.snapshot` inserts detector state into the HTTP JSON. In `preview.html`,
`render` displays update rate, compute ms and source age. Its box loop scales
source x coordinates by `640 / detector.width` and y by `360 / detector.height`
for the overlay canvas. That canvas and the 320x180 image occupy the same visual
rectangle. Dashed amber boxes mark older predictions; they may lag while turning.

The image shift and gyro do not modify these boxes. No track IDs or remembered
objects are generated by this inspected implementation. Browser/network delay
adds to perceived age but is not included in Pi-side source-age numbers.

## Separate saved-image benchmark

In [detect_image.py](../../src/vision/detect_image.py), `main()` parses arguments
and `run(args, cv)` loads one saved grayscale image and the model, performs warmup
and measured runs, then writes an annotated image and JSON report to a new local
recordings directory. `timing_summary()` computes median and nearest-rank p95;
`sha256()`, `git_info()` and `cpu_temperature()` record reproducibility context.
The saved-image command shares `infer_once` and `parse_detections` with live
detection, but its same-image timings exclude loading/drawing/disk/display.
They are not live camera-to-screen latency or accuracy over a labelled dataset.

## Tests and study exercises

Read [test_detection_baseline.py](../../tests/unit/test_detection_baseline.py)
for coordinate mapping, filtering, invalid output, timing and safe output paths.
Read [test_live_detection.py](../../tests/unit/test_live_detection.py) for newest
frame selection, slow inference scheduling, freshness and isolated failures.

Explain why the next inference after an 800 ms run does not start at 500 ms;
why a ready result can contain no boxes; and why 2 Hz detector updates, two
OpenCV threads and a 0.5 score threshold are three independent settings.
Trace the example normalized box through parser and browser overlay scaling.
