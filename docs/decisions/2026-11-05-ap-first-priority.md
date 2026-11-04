# AP engineering is the primary project outcome

Date: 2026-11-05. Status: accepted user direction.

The user wants heavier emphasis on Application Processor learning than general
systems extension or finishing spatial features. The Pi application is the
workload through which processor behavior is investigated. Computer systems
remains a distinct supporting discipline. Preserve existing work and measurements.

Later clarification on the same date explicitly requests practical **kernel,
BSP and driver development** as part of AP learning. Plan a recoverable kernel
build/boot, board/device-tree configuration and a relevant driver/kernel change,
with source inspection and before/after measurement. No such work is claimed
complete, and the current profiler does not install a kernel or change drivers.

This refines the 2026-10-26 development order. Keep the bounded v1 acceptance
target, but use its current continuity/recording failures as the first profiling
case now. Do not require a perfected spatial application before observing CPU,
memory and scheduling behavior. Do not return to a mandatory lesson/benchmark
after every small code change; group experiments around a clear question.

## Milestone selection

Each milestone states the AP question, fixed workload, quality constraint,
measurements and decision. Include resource metrics that answer the question;
do not interpret CPU percentage as energy or wall time as CPU consumption.
Keep software versions, provenance and measurement overhead explicit. Hardware
counters, SIMD, supported power policies and measured energy are staged future
work. Kernel, BSP, drivers and accelerators are selected for a demonstrated need
or an explicit user specialization, rather than a list to complete by default.

## Approved spatial extension direction

Use the existing MobileNet-SSD to explore semantic view memory and foreground
exclusion. Class labels are priors: people are potentially dynamic; chairs and
other furniture are candidates for persistent view annotations, not guaranteed
fixed landmarks. Both can be movable or misdetected. No class label supplies
depth, verified identity or world position. The implementation plan must retain
timestamp/source alignment, missing-detection fallback and bounded storage.

First investigate v1 stalls with detector off. Then retain the detector-off
profile and compare detector-on, semantic and masking profiles with matched
inputs and separate quality/resource outcomes. This direction authorizes planning
the extension; the staged plan exposes the design before multi-module changes.
See [plan](../exec-plans/active/semantic-spatial-memory.md).

## Records

Maintain separate Computer Systems and AP sections, with AP driving the next
experiment. Keep evidence in `benchmarks/results/`, indexed by `STAGE_RECORDS.md`.
Update diagrams only when implementation changes. Preserve unknown/failure states
and keep private images out of Git. Detailed learning-site expansion remains
deferred unless requested.
