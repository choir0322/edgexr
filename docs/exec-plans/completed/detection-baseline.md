# First object detector on a saved frame

## Purpose / big picture

Label recognizable objects in one existing camera frame and measure inference
cost on the Pi 4. Review the boxes before adding detection to the live preview.

## Context and orientation

The camera is monochrome, 1280x720 MJPEG. The live motion estimator analyzes
320x180 images near 30 fps. Detection is a separate workload. Use OpenCV DNN
on CPU with the MobileNet-SSD VOC model (300x300 input, 20 object categories).
No Caffe installation is required. The user confirmed Pi OpenCV 4.11.0 with DNN.
Model files are an explicit external download and are excluded from Git.

## Progress

- [x] 2026-10-05: Review project and upstream model preprocessing/labels.
- [x] 2026-10-05: Implement saved-frame runner, tests, and documented setup.
- [x] 2026-10-05: User confirmed Pi OpenCV 4.11.0 with DNN support.
- [x] 2026-10-05: Local logic tests and starter structure check pass. Patch
  applicability is checked against the clean Desktop checkout before handoff.
- [x] 2026-10-05: User downloaded the model and ran inference; all 44 tests pass on Pi.
- [x] 2026-10-05: Reviewed labelled image/report. Table and left chair plausible;
  right chair missed. Median total 195.90 ms. See docs/DETECTION_RESULTS.md.

## Plan of work

1. Read one image as grayscale, replicate it into three model input channels,
   resize to 300x300, subtract 127.5 and multiply by 0.007843.
2. Run CPU inference, filter scores at 0.5, and map normalized boxes back to
   the original image. Preserve valid empty detections.
3. Warm up three times, then measure 20 repeated runs on that same image.
   Report preprocessing, inference and postprocessing separately and together.
4. Save annotated.png and report.json under a new recordings/ directory.
   Record model/image hashes, versions, Git revision, threads and conditions.
5. Test output validation, box mapping, timing statistics and failure paths.

## Concrete steps

Follow docs/DETECTION_BASELINE.md. Use normal pi permissions. The tool reads a
saved frame and never starts the camera. Retry with a new output directory.
Model download and any runtime installation are separate, explicit steps.

## Validation and acceptance

Local tests must pass. Real Pi acceptance requires a readable annotated image,
plausible boxes checked by the user, and timings from the same input after
warm-up. Empty detections are a result to investigate, not a program failure.
Twenty repeated inferences are a short compute baseline, not application FPS,
end-to-end latency, or an accuracy evaluation. Hardware: Pi 4, Bookworm
aarch64/Python 3.11.2 previously reported; record current versions and scene.

## Surprises and discoveries

The 30-second combined-motion-03 test accepted 901/902 visual/gyro pairs with
correlation -0.965. User timing differed from the suggested schedule; actual
logged movement defines the phases. See docs/MOTION_03_RESULTS.md.

## Decision log

- 2026-10-05: Start with one saved frame to isolate model behavior and CPU cost.
- 2026-10-05: Use upstream's direct square resize and normalization. This
  distorts aspect ratio; map x/y independently back to the full image.
- 2026-10-05: Keep grayscale explicit, even for a color test image. Replication
  satisfies the three-channel model interface but cannot restore color cues.
- 2026-10-05: Keep OpenCV optional; existing camera/IMU commands do not need it.

## Outcomes and retrospective

The Pi completed real inference and all 44 tests. Twenty repeats on one frame
showed median 195.90 ms total compute; this supports trying live detection at
2 Hz while measuring resource contention. Monochrome recognition is useful but
incomplete (missed right chair). Confidence is not accuracy and same-frame CPU
time is not live FPS. Local runtime limitations were resolved by target checks.
