# Project brief

## Goal

**2026-10-26 sequencing update:** complete the fixed-base vision and spatial
memory application before systematic AP optimization, then develop detailed
learning materials. Correctness checks and concise records continue throughout.
The long-term AP learning objective remains; its dedicated phase is deferred.
See [the development-order decision](decisions/2026-10-26-development-order.md)
for the current functional completion criteria.

Priority clarified 2026-10-24: learn Application Processor workload and systems
engineering. Spatial perception supplies a meaningful workload for studying
timing, buffering, concurrency, compute/memory cost and quality/performance
tradeoffs on the Pi 4 CPU; no NPU is available. The AP handoff in
`exec-plans/active/EdgeXR_AP_Workload_Benchmark_Handoff.md` is a flexible anchor,
not a reset of the existing implementation. The next bounded application
milestone remains relative camera orientation and directional scene memory
with a stationary base. Full 3D mapping and visualization expansion are not
prerequisites for AP experiments or a successful project.

Build and understand a Raspberry Pi 4 workload that observes a small physical
scene through a USB global-shutter camera, tracks objects across frames, uses
IMU motion as context, and measures its own performance.

The XR connection is spatial perception: when the camera moves, the system
should reason that the viewpoint changed rather than immediately treating every
image change as object motion. This is a deliberately simplified learning model,
not a full SLAM or production AR system.

## Learning outcomes

By the end, the student should be able to explain camera capture, object
detection versus tracking, IMU orientation, frame latency, and the tradeoffs
between accuracy, frame rate, memory, CPU use, and thermal behavior.

## First success level

The baseline below is historical. The next success level is a measured turn-away
and return-to-view demonstration: report relative orientation with uncertainty,
remember previously observed directions, and validate revisits using scene
evidence rather than object identity alone. See the current
[orientation plan](exec-plans/active/orientation-aware-surroundings.md).

The minimum viable demonstration is a live camera view with labelled object
tracks, basic IMU readings, and an on-screen or logged measurement of FPS,
inference time, CPU use, memory use, and temperature. A later level can attempt
to associate an object that leaves and re-enters the view.

## Boundaries

This project does not begin by promising object recognition quality, persistent
3D mapping, custom model training, or cloud services. Each of those is an
optional later investigation only if the baseline is measured and understood.
