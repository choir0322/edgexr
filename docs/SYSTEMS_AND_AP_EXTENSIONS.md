# Embedded Linux and AP extensions

User-selected sequence, 2026-11-05. Spatial application remains the workload.
The [v1 acceptance review](SPATIAL_V1_ACCEPTANCE_RESULTS.md) exposes a scheduling
and recording issue to investigate before a clean application handoff.

## Computer systems engineering

First correlate thread scheduling, sensor continuity and recording backpressure
in the existing application. Then assess one architectural change from evidence.
Follow with reproducible embedded Linux deployment/BSP work if useful: pinned
boot/kernel configuration, device descriptions and application startup. A kernel
or IIO sensor-driver extension is a later specialization, contingent on existing
driver support, sensor documentation and accessible wiring. Building a kernel
alone does not demonstrate a driver or scheduler implementation. Real-time work
begins with measured deadline misses; hard guarantees require bounded behavior
throughout the chosen path. Full OS design remains a separate substantial branch.

## Application processor performance engineering

Characterize the fixed spatial workload after resolving blocking reliability
issues. Extend the historical detector-specific profiler to validate this exact
scene/orientation configuration; do not reuse it unchanged (it requires a ready
detector). Measure total/per-process CPU, RSS, rates, latency tails, temperature
and throttling. Then inspect available hardware counters and profile a proven
bottleneck. Evaluate native/SIMD changes only against optimized library baselines.
Add measured energy and supported frequency-policy experiments when equipment
is available. Accelerator integration/scheduling is later optional work requiring
compatible hardware/runtime; no NPU result is claimed on this setup.

Do not install dependencies, change kernel/driver/frequency policies, add hardware
or launch motor tests implicitly as part of this roadmap. Retain reproducible
settings and quality outcomes for each comparison.

## Optional semantic spatial memory — discussion, not implemented

MobileNet-SSD can attach timestamped category, confidence and image-box context
to a recognized view: for example, a bottle was observed in View-2. Preserve
detector source sequence/time and only associate sufficiently fresh compatible
results; asynchronous latest results are not inherently the same frame. A
view-level semantic record is simpler than an object identity or 3D landmark.
Repeated labels such as chair are weak evidence for distinguishing views.

A later experiment could exclude potentially moving foreground boxes from ORB
feature extraction. Boxes include background, people can stand still and
non-person objects can move. Detection misses, box age and camera motion make
masking fallible. Compare moving-person clips with/without masking on the same
frames, retaining enough background features and using explicit unknowns.
Do not let object labels override geometric verification or repair gyro gaps.

Depthwise and **1×1 pointwise** convolution make the MobileNet feature extractor
efficient; SSD predicts classes and boxes from feature maps. These operations
do not independently supply position, depth or a persistent spatial map.
Learned place descriptors would be a separate model/representation experiment.

First freeze the working detector-off spatial baseline. Semantic annotation can
then become an explicit optional workload profile, with measured CPU, latency,
memory and recognition-quality changes. No detector integration is authorized
by this consultation alone. Sources supporting the concepts:

- [MobileNet paper](https://arxiv.org/abs/1704.04861): depthwise separable features.
- [SSD paper](https://arxiv.org/abs/1512.02325): category/box predictions.
- [DynaSLAM](https://arxiv.org/abs/1806.05620): research precedent for excluding
  dynamic content; its segmentation/geometry pipeline is more capable than
  simple MobileNet-SSD box masks, and its results do not transfer to this Pi.
