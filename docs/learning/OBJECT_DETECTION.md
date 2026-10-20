# Study 2: object detection, newest image to labelled boxes

This guide follows [the live diagram](../PIPELINE.md). Detection asks which of
the model's known categories occur in an image and where. A basic tracker now
assigns provisional IDs across completed detection results using class and
box overlap. An optional mode uses measured image shift to help ID association
during turns. Neither mode establishes permanent identity, moves displayed
boxes to compensate for motion, or trains the model while preview is running.

For the separate first-ID algorithm, open the offline
[basic tracker graph](basic-tracker.html). One dark connected path shows
detector creation, inference, a descent from Match IDs through the nine
`BasicTracker.update()` decisions, and a direct return to publication. Its
dotted Match IDs → Publish edge is only a collapsed overview, not a skipped
call. Hovering or selecting a node reveals its input, rule, result, and code.
The graph exposes the other boxes where they affect matching. Its example
values are teaching data, not saved detector outputs. The live worker now
assigns IDs, and browser labels show them for ready boxes with a live camera.
The graph depicts **baseline** matching; study the optional
[motion-aware code path](MOTION_AWARE_TRACKING.md) separately.

Open [Inside MobileNet–SSD](detection-architecture.html) for the interactive
architecture lesson. Standard convolution and depthwise-plus-pointwise appear
side by side, sharing one playback sequence. Three channel colors, grouped
kernels and two output filters show exactly where channel mixing occurs.
Select a filter to inspect its arithmetic. The six-stage continuation below
traces a prior through SSD and ends with the recorded Pi result. The fixed 4×4
teaching grids subsample the saved chair-region sample; weights and activations
are illustrative. Bias is added once per output value with one shared scalar
per output channel. These teaching biases are enabled for explanation; the
actual backbone disables convolution biases. Actual model dimensions appear
in an expandable explanation.

## Experimental return matching

With `--detect --reidentify`, the same detector worker uses each current
1280×720 grayscale source frame and its source-coordinate box to form a
mean-centered 8×8 brightness-grid descriptor. Tiny or nearly flat crops have
no descriptor and cannot enter memory. `BasicTracker.update()` still gives
active same-class IoU matches first priority. At the second missed detector
update, a track with a usable descriptor moves into a worker-local retired-ID
memory (32 entries maximum; 10 seconds since last sighting). An otherwise
unmatched same-class current box may claim one old ID if its cosine score is
at least 0.85 and exceeds the runner-up by at least 0.05. Those numbers are
**provisional test settings**, not calibrated accuracy thresholds. A `↺` label
marks an appearance-based restore; a new ID is the abstain outcome. No raw
crop or descriptor is sent to the browser or saved to disk.
If multiple *current unmatched* boxes have the same class, the first
experiment abstains from appearance restoration for all of them rather than
letting list order decide who inherits the old ID.

This is not face recognition or verified identity. Similar clothes, lighting,
pose and background inside a box can create false matches or misses. The IMU
and visual-motion history do not yet participate in this memory decision.
See [`object_memory.py`](../../src/vision/object_memory.py),
[`basic_tracker.py`](../../src/vision/basic_tracker.py), and the
[Pi trial](../LIVE_DETECTION.md) before drawing conclusions from one ID hold.

## Where MobileNet ends and SSD prediction begins

The pinned graph's SHA-256 matches the saved Pi baseline report:
`2d180f723b3109e21f8287f6b3c691390d07b60eed998327cd3259ffa0e50608`.
MobileNet supplies learned feature tensors, including `conv11` (19×19×512)
and `conv13` (10×10×1024). SSD attaches prediction heads to those tensors and
adds further convolutional layers for 5×5×512, 3×3×256, 2×2×256 and 1×1×128
feature maps. A map is spatially arranged feature values, not an object list
or a smaller photographic image.

For every selected feature-map location, the heads predict four box offsets
and 21 class scores per default box. The first grid has three priors per cell;
the other five grids each have six. This configuration has 1,917 priors in total.
These dimensions describe this specific MobileNet-SSD graph; other SSD variants
use different grids and counts. The model includes softmax, CENTER_SIZE box
decoding, score filtering at 0.25 and class-wise NMS at IoU 0.45. The Python
application then applies its own 0.5 score filter to the graph's output.

MobileNet and SSD are connected within the model loaded by
`cv.dnn.readNetFromCaffe`; one `net.forward()` executes the graph. There is no
separate Python call that hands an image from a MobileNet program to an SSD
program. The graph definition and pretrained parameters provide those operations.

The lesson's source is split into readable pieces:

- `detection-architecture.html` and `.css`: side-by-side convolution layout,
  six-stage SSD walkthrough and a compact comparison with Faster R-CNN.
- `detection-architecture.js`: fixed convolution arithmetic, SVG diagrams and
  shared playback with filter selection.
- `detection-ssd.js`: independent SSD stage/scale/prior selection, image
  overlays and teaching score/box calculations. `current()` chooses a prior,
  `draw()` renders its geometry, and `explanation()` exposes the corresponding
  values. The final stage renders the saved Pi detections instead of toy boxes.
- `detection-math.js`: shared teaching helpers for priors, CENTER_SIZE decoding,
  softmax and class-wise NMS, now loaded by the SSD section.
- `images/detection-lesson-data.js`: derived image sample and saved final detections.
- `scripts/build_detection_lesson.py`: validates the saved image/report pairing
  and regenerates the compact teaching assets with the existing FFmpeg tool.

The actual final detections come from the user's saved report. The SSD section
lets you select one of six grids and one reference shape, inspect four fixed
illustrative offsets plus 21 example scores, decode the candidate and inspect
filtering decisions. NMS runs on four illustrative candidates; no pretrained
network runs in the browser. The photograph is the user's Pi image, while the
grid overlay is a spatial guide rather than captured feature activations.

The final stage explains normalized-to-source coordinates and the later tracker
handoff. The proposal comparison shows Faster R-CNN sharing backbone features:
an RPN predicts objectness/regions, then RoI features feed classification and
box refinement. Its reference anchors and learned region proposals are distinct.
The Pi suitability card links the measured five-minute workload; there is no
claim of superiority over an untested detector. Primary references are linked
in the page. Use `node tests/learning/test_detection_math.cjs` to check the
underlying arithmetic.

2026-10-18 diagram review: `docs/PIPELINE.md` reviewed; unchanged because this
offline lesson adds no live inference, worker, threshold or scheduling change.

## Source reading route

| Order | File | Symbols to read |
|---|---|---|
| 1 | [live_preview.py](../../src/app/live_preview.py) | `main`, its `build_detector` callback, `camera_command`, nested `capture`, `State.publish_frame` |
| 2 | [live_detector.py](../../src/vision/live_detector.py) | `detect_latest`, its `detection_frame_ready` callback, `CpuDetector.__init__`, `CpuDetector.__call__` |
| 3 | [detect_image.py](../../src/vision/detect_image.py) | `infer_once`, `LABELS`, `parse_detections` |
| 4 | [basic_tracker.py](../../src/vision/basic_tracker.py) | `BasicTracker.update`, `box_iou` |
| Optional | [motion_history.py](../../src/vision/motion_history.py) and [live_preview.py](../../src/app/live_preview.py) | `MotionHistory.displacement`, `State.motion_between`, `State.publish_result` |
| 5 | [live_detector.py](../../src/vision/live_detector.py) | `DetectionState.publish`, `DetectionState.snapshot`, `fail` |
| 6 | [live_preview.py](../../src/app/live_preview.py) | `State.snapshot`, `make_handler` |
| 7 | [preview.html](../../src/app/preview.html) | `detectionLabel`, `render` detector status and box loop; `poll` |

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
identified = tracker.update(boxes, frame[1], source_shift if motion_mode else None)
state.detector.publish(frame, identified, (finished - started) * 1000,
                       finished, tracker.last_stats)
```

Line by line: measure this attempt's start; schedule the next eligible start
500 ms later; reject a source already older than the freshness limit; run the
detector on its bytes; measure inference completion; match those current boxes
to remembered tracks (optionally looking up image shift) and publish the
ID-bearing result with match counts. `motion_mode` abbreviates the actual
`state.motion_aware_tracking` flag here; `source_shift` is the callback inside
`detect_latest`, not a second detector. The target limits
expensive work while the other workers continue. Inference itself is not
interrupted at 500 ms.

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

## 6. Attach provisional IDs, then publish without pretending boxes are current

`detect_latest` creates one `BasicTracker` alongside its detector in the same
sequential worker. After each completed inference it calls `tracker.update`
before publication. All `box_xyxy` values are in the original 1280×720 source
pixel system. Same-class pairs with IoU at least 0.3 compete for a one-to-one
match. An unmatched current box gets the next never-reused integer ID. An empty
result ages unmatched old tracks once; one miss is hidden but remembered, and
two consecutive misses retire an old track. In baseline mode this uses raw
overlap only. `--motion-aware-tracking` additionally allows a predicted overlap
from the timestamped image-shift history; missing shift falls back to raw
overlap. Neither mode uses the IMU. See [the tracker graph](basic-tracker.html)
for baseline decisions and [the optional-mode guide](MOTION_AWARE_TRACKING.md)
for interval lookup, units, prediction, and limitations.

`DetectionState.publish(frame, boxes, cost_ms, finished, tracking_stats)` saves
the source sequence, receipt time, ID-bearing boxes, elapsed compute cost and
latest match counts. This
live cost surrounds the detector call, including preprocessing/parser, but
excludes tracking, model construction, camera capture and display. A bounded
deque records inference completions. Source receipt time and the 1.5-second
freshness rule are unchanged by tracking.

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

The image shift and gyro do not modify the displayed box coordinates. Optional
image shift can affect **which ID** the box receives; gyro does not. `track_id` in the API box
record is displayed as a provisional `#ID` before the category and confidence.
The browser retains the prior label format if an ID is absent and clamps a long
label into the canvas. A remembered missing track is not a visible ghost box.
Browser/network delay adds to perceived age but is not included in Pi-side
source-age numbers.

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
