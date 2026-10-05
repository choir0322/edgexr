# Detect objects in one saved camera frame

The next question is whether a small detector recognizes useful objects in
our monochrome footage, and how much CPU time it needs on the Raspberry Pi 4.
This command reads an existing image, runs MobileNet-SSD with OpenCV DNN, and
saves labelled boxes plus a JSON report. It works through SSH without a display.
The live preview stays a separate experiment until this result is reviewed.

## Model choice and limits

Use the [upstream MobileNet-SSD VOC model](https://github.com/chuanqi305/MobileNet-SSD/tree/bb17b6c3eef36d80be441ae8e5339be66e8e3b7a).
OpenCV documents [loading this model through its DNN module](https://docs.opencv.org/3.4.2/d0/d6c/tutorial_dnn_android.html).
The [upstream demo](https://github.com/chuanqi305/MobileNet-SSD/blob/bb17b6c3eef36d80be441ae8e5339be66e8e3b7a/demo.py)
defines the labels and preprocessing. No Caffe installation is required.

Classes: aeroplane, bicycle, bird, boat, bottle, bus, car, cat, chair, cow,
diningtable, dog, horse, motorbike, person, pottedplant, sheep, sofa, train,
tvmonitor. Cups, phones and keyboards are not classes in this model.

Input is always converted to grayscale, then repeated into three channels.
The network receives a direct 300x300 resize, with `(pixel - 127.5) * 0.007843`.
The original 720p image is retained for drawing boxes. Square resizing changes
aspect ratio, following the upstream demo; x and y boxes map independently
back to the original image. Repeating grayscale channels cannot recover color.
Recognition quality on this camera must be observed, not assumed from upstream
accuracy figures. A confidence threshold of 0.5 filters model scores; it does
not mean that half or more of the displayed boxes must be correct.

## 1. Check the existing Pi runtime

After applying, reviewing and pushing on Mac, pull on Pi. Stop the live preview
to avoid adding its CPU workload to this experiment.

```bash
cd ~/projects/edgexr
git pull --ff-only
python3 -c "import cv2; print(cv2.__version__); print('DNN available:', hasattr(cv2, 'dnn'))"
```

If this fails, share the error before installing packages. OpenCV is optional
for the rest of EdgeXR; do not replace the working NumPy/Python environment
blindly. No installer is included. Use normal pi permissions, not sudo.

Confirmed by the user on 2026-10-05: OpenCV 4.11.0, DNN available. No additional
runtime package is required on that Pi for this first test.

## 2. Download the model explicitly

These commands contact GitHub and download about 23 MB plus the definition and
license. Run them only when ready for that download. They use a pinned commit.
The new-directory check prevents rerunning this block over an existing model.
If a transfer fails, keep its error and inspect the partial directory before
retrying; do not assume a partially downloaded model is usable.

```bash
mkdir -p models
mkdir models/mobilenet-ssd && \
curl --fail --location --output models/mobilenet-ssd/deploy.prototxt \
  https://raw.githubusercontent.com/chuanqi305/MobileNet-SSD/bb17b6c3eef36d80be441ae8e5339be66e8e3b7a/deploy.prototxt && \
curl --fail --location --output models/mobilenet-ssd/mobilenet_iter_73000.caffemodel \
  https://raw.githubusercontent.com/chuanqi305/MobileNet-SSD/bb17b6c3eef36d80be441ae8e5339be66e8e3b7a/mobilenet_iter_73000.caffemodel && \
curl --fail --location --output models/mobilenet-ssd/LICENSE \
  https://raw.githubusercontent.com/chuanqi305/MobileNet-SSD/bb17b6c3eef36d80be441ae8e5339be66e8e3b7a/LICENSE
```

Model loading detects unreadable/incompatible files; the report records their
SHA-256 hashes. Keep the upstream MIT license alongside the downloaded files.

## 3. Extract a frame from the existing recording

This uses combined-motion-03 at about two seconds into the file, in its initial
still period. Video file time and the terminal recording cue have different
origins. It reads the saved video without accessing the camera.

```bash
ffmpeg -hide_banner -loglevel error -n \
  -i recordings/combined-motion-03/camera.mkv \
  -ss 2 -frames:v 1 recordings/detection-input-01.png
```

`-n` refuses to overwrite an existing image. For a retry, reuse this image or
choose a new filename. A person, chair, bottle or monitor should be visible;
if none is in this scene, an empty detection result will not assess recognition
of those categories. Review the image before drawing conclusions.

## 4. Measure and save boxes

```bash
PYTHONPATH=src python3 -m vision.detect_image \
  --image recordings/detection-input-01.png \
  --output recordings/detection-01 \
  --notes "Pi 4; frame from combined-motion-03; add lighting, power and cooling"
```

Defaults: OpenCV CPU, two requested threads, three warm-up runs, twenty measured
runs, confidence threshold 0.5. Nothing downloads automatically. The output
directory must be new and under recordings/. Empty detections still produce
a valid annotated image and report. An error during saving can leave a partial
directory; keep it for diagnosis and use a new name on the next run.

The report contains input and model hashes, versions, Git state, thread setting,
temperature before/after when available, detections from the final run, and
individual/median/p95 timing samples. Inference timing includes setInput plus
forward; preprocessing includes grayscale channel replication and resizing;
postprocessing includes output validation and box decoding. The total is their
per-run sum. Model loading is timed separately. p95 uses nearest rank: with 20
measurements it is the 19th sorted sample, so this is a short baseline.

Image decoding, drawing, saving, camera capture and display are excluded.
These compute times cannot be called camera-to-screen latency or live FPS.
CPU utilization and memory are not measured here. Compare this run only with
the same image, model, settings, warm-up and Pi conditions.

## 5. Review from the Mac and share

Run this in a Mac terminal; choose a fresh destination if it already exists:

```bash
scp -r pi@ai-fusion.local:~/projects/edgexr/recordings/detection-01 \
  /Users/ryanchoi/Desktop/edgexr-detection-01
```

Open annotated.png and send that image and report.json. Describe any visible
supported objects that were missed and any incorrect labels/boxes. Share the
terminal error if inference fails. Do not change the threshold just to make a
result look better; record any later threshold experiment separately.

## Checks and next decision

```bash
PYTHONPATH=src python3 -m unittest discover -s tests/unit -v
```

Coordinate mapping, clipping/filtering, malformed outputs, empty detections,
timing statistics and no-overwrite behavior are tested independently of the
model. A preprocessing test uses OpenCV when available and otherwise skips.
Actual model inference and Pi recognition remain hardware acceptance checks.
After reviewing them, choose a detection cadence for the live preview; adding
tracking IDs is a later step. Raw images, models and reports remain outside Git.
