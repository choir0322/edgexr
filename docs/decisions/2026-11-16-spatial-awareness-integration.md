# Integrate existing components into fixed-base spatial awareness before FPGA

## User direction

On 2026-11-16 the user clarified what "spatially aware" means for EdgeXR and
approved a final application specification. Their example: the pan servo looks
at a cup, looks away, and when it turns back and the cup comes into view again,
the program knows it is the same cup in the same place. They want near/far
awareness and expectation ("what should I see if I turn back to centre?"), not
another object-detection demo.

The user also restated the project's purpose: **the application is a vehicle.**
It exists to give realistic workloads for learning systems, application-processor
(AP) and later FPGA engineering. The Tang Primer 20K board is ordered (about two
weeks away); the application should be finished in that window.

## Decision

Replace the 2026-11-08 endpoint ("offline sparse reconstruction before FPGA")
with an integrated fixed-base spatial-awareness application built from existing
components:

1. Remember what was seen in each head direction (exists: view map).
2. Predict what should be seen before turning to a remembered direction, then
   report *matched / changed / unknown* and score how often expectations hold.
3. Estimate which objects are nearer or farther (relative ordering, not meters)
   and store that with the object's remembered direction.

Every existing component has a job: gyro quaternion orientation (where the head
points), Hann-window phase correlation (a second opinion on rotation and a blur
flag), ORB/Hamming scene memory (absolute anchors that correct gyro drift),
MobileNet-SSD (what and where in the image), camera calibration (pixel to angle),
servo control (repeatable test sweeps). A monocular depth CNN is the one new
model; downloading it requires explicit user approval of the specific model,
size and license.

## Why reconstruction is no longer the endpoint

The camera sits on a pan/tilt head on a fixed base, so it rotates but does not
translate. Rotation alone cannot reveal distance (near and far points shift
together), which is why `reconstruct()` rejects pure rotation. The sparse
reconstruction worked only because the user moved the whole rig by hand. Third-
view registration would localize a camera that moves through space, which this
rig does not do. The completed two-view work remains a measured experiment and
an available numerical workload; the third-view ExecPlan is deferred, not deleted.

## Bounds

- First test object is a **bottle**: MobileNet-SSD's VOC classes include
  `bottle` but not `cup`. A wider-class model would need a download.
- "Same object" means same class, remembered direction and similar appearance.
  Two identical objects swapped in place cannot be distinguished.
- Near/far is relative ordering, not metric distance. Lens offset from the pan
  axis causes a small, measurable direction error for very near objects.
- No SLAM, room map, world heading or camera-position claims.

## AP link

Each step is chosen for the processor question it adds: frame/IMU timestamp
alignment (step 1), memory structures and lookup cost (step 2), multi-rate
workers on four cores (step 3), heavy convolution compute and int8 versus float
(step 4) and a whole-program per-stage profile that ranks kernels for CPU
optimization and FPGA offload (step 5). See the
[ExecPlan](../exec-plans/active/spatial-awareness-integration.md).
