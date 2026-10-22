# Project brief

## Goal

Priority clarified 2026-10-23: understand and remember the space the camera
observes, rather than maximize object-ID continuity or build learning websites.
The next milestone is relative camera orientation and directional scene memory
with a stationary base. Existing perception and profiling remain supporting
tools. Full 3D position and mapping are later questions, not current claims.

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
