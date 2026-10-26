# Development order: functionality, AP engineering, learning material

Date: 2026-10-26. Status: accepted user direction.

The user replaces the repeated feature → lesson → AP experiment cycle with
three larger phases. AP systems engineering remains the eventual learning
objective. Preserve existing implementation and measurements.

## First completion target

With the Pi base fixed and camera/IMU moving together, show the live scene and
relative orientation, remember observed scene regions within a session, and
recognize returns using visual evidence. Show known/new/unknown states and
recover after poor observations when adequate evidence returns. Existing object
detection/tracking remain supporting features. Full metric 3D mapping, room
position, depth and further identity tuning are outside this initial scope.

## Immediate next milestone

Build bounded visual scene memory and revisit verification on saved Pi footage,
then integrate it into the live preview. Reuse installed OpenCV ORB features
to describe recognizable image points; compare candidate keyframes and reject
inconsistent matches with geometric verification. Retain a fixed-capacity set
of representative frames/descriptors and timestamps. Associate valid relative
orientation using nearby host timestamps with explicit uncertainty.

The end-to-end demonstration is: observe A, turn to B, return to A, and identify
the previous scene region. Gyro direction may prioritize candidates; visual
agreement must establish the revisit. If orientation becomes unknown, visual
recognition may still identify a scene, but must not fabricate its current angle.
Calibrated visual rotation/drift correction requires camera calibration and
timing validation; FFT pixel displacement cannot directly supply that angle.

Test memory bounds, eviction/reset, ambiguity and timestamps without hardware.
Use existing footage for development and separate labelled clips for evaluation.
Check repeated patterns, moving foregrounds, blank walls and fast turns, then
validate the complete live behavior on the Pi. Record false/missed revisits,
unknowns and recovery. Address performance early only when it blocks usable
functionality. Correctness checks remain required throughout.

## Subsequent phases and records

After functional completion, freeze a reproducible workload and compare CPU,
memory, latency, throughput, skipped work, temperature and quality while tuning
scheduling, polling, data movement and model/runtime choices. Preserve historical
AP results with their original workloads. Detailed learning guides and visual
explanations follow the AP phase.

At every meaningful milestone, update `docs/STAGE_RECORDS.md`, implementation
records and `docs/PIPELINE.md` as needed. Keep source/config links, reasons,
tests, observed outcomes and limitations. Mark absent metrics `deferred — AP
phase`; never invent measurements. Keep existing learning docs factually correct
with concise edits, but do not add a lesson after each change. Raw videos and
private images stay outside Git. This decision does not claim scene memory is
already implemented or validated.
