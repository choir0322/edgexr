# EdgeXR: working agreement for people and Codex

## Purpose

EdgeXR is a learning-first Raspberry Pi 4 spatial-perception project. It will
combine a USB global-shutter camera, IMU motion data, object detection/tracking,
and performance measurement. The goal is to understand each engineering choice,
not to produce opaque code quickly.

## Main goal and relevance checks

The primary learning goal is Application Processor (AP) workload and systems
engineering on a Raspberry Pi 4: understand scheduling, compute and memory cost,
latency, throughput, resource contention and measured quality/performance
tradeoffs. There is no NPU. Spatial perception is the meaningful application
workload, not an independent ambition to build production XR or full SLAM.

Use `docs/exec-plans/active/EdgeXR_AP_Workload_Benchmark_Handoff.md` as a flexible
anchor, not a rigid specification. The user's 2026-10-24 clarification and
verified repository/hardware facts take precedence over its proposed runtimes,
hardware assumptions, checklist and sequencing. Preserve existing progress;
do not restart the working Caffe/OpenCV MobileNet-SSD pipeline or add YOLO just
because the handoff suggests it. Use public sources/personal hardware only;
never introduce employer-confidential material or claim measured NPU results.

The current application milestone remains orientation-aware surroundings:
estimate where the camera looks and remember observed directions, beginning
with a fixed base. Do not claim 3D position, depth or SLAM from image shift or
gyro integration alone. Bound this milestone and tie it to AP learning.

Before each new milestone and after its results, revisit the anchor briefly:
state the AP question, bounded application outcome and measurement. Explain
whether work directly advances the goal, enables it, or is a less-relevant
detour. Explicitly remind the user when a request would
shift effort toward identity tuning, learning websites or cosmetic visualization.
Offer the goal-aligned next step and ask before expanding a detour. Respect an
explicit user choice to take it. Prefer minimal diagnostic displays and measured
spatial behavior over additional visualization features. Keep this reminder
brief; do not obstruct already-approved work with repeated confirmations.

## How to work here

Before changing code, explain in plain language what will change, why it is
needed, and how the result will be checked. Prefer a small, understandable step
over a large framework or a copy-pasted application. Do not silently add a
dependency, download a model, change hardware settings, or alter a benchmark
protocol. Ask before any action that needs credentials, network access, a paid
service, or a physical-hardware change.

After a change, summarize the files changed, the test or observation used to
check it, and one useful concept for the learner to understand next. If an
assumption is uncertain, label it and record the confirmation work in the
relevant documentation.

## Keep the learning map current

Explain code with comments above cohesive task groups, not line by line. Preserve
function docstrings and input/return types; retain focused explanations of units,
shapes, clocks, locks and other non-obvious constraints. Use the convention in
`docs/learning/CODE_CONVENTIONS.md` for source, tests, browser code and scripts.

`docs/PIPELINE.md` is the current-implementation diagram, not a future design.
For each implementation task, add an explicit task to review/update this diagram
and the relevant guide in `docs/learning/`. Check data flow, named functions,
array shapes, units, rates, timing scope, failure behavior and current versus
planned features. If nothing changes, record "diagram reviewed; unchanged" with
a reason in the task's validation summary. Update documentation in the same
commit as the relevant code. Do not silently add tracking/fusion arrows for
features that are only planned. Prefer repository-relative links and named
symbols over brittle line numbers in repository documentation.

## Record each technique and its AP evidence

At each meaningful stage, update `docs/STAGE_RECORDS.md` with a stable stage
name, status (planned/implemented/measured), the technique and its purpose,
exact source/config/learning-guide links, and the AP question. Link to the
small committed result under `benchmarks/results/` when Pi measurements exist.
That result should retain the device/commit, workload and camera mode, scene,
power/cooling, warm-up/duration, metric definitions and values, limitations,
and the resulting decision. Include quality or correctness evidence alongside
CPU/latency/rate/memory/temperature; write `not measured` instead of filling
gaps with assumptions. Keep the index concise and preserve detailed evidence
in linked documents. This structured trail is intended to support a later
project website, but do not build website features during a measurement stage
unless the user explicitly chooses that detour. Do not commit raw footage,
private images, large logs or model weights.

## Source layout

- `src/` contains small, focused application modules.
- `tests/` mirrors behavior that can be checked without physical hardware.
- `docs/` is the source of truth for scope, architecture, hardware, benchmarks,
  and project decisions.
- `benchmarks/` holds reproducible benchmark settings and shareable summaries.
- `scripts/` holds short, documented helper scripts; scripts must be safe to
  re-run and must not make hidden system changes.

Keep raw camera footage, trained-model files, secrets, and generated build
outputs out of Git. Keep small benchmark summaries, configurations, and code in
Git so results can be reproduced.

## Hardware rules

The camera is a vendor-described 720p USB industrial global-shutter module using
the OV9281 sensor, not the camera bundled with the SunFounder AI Fusion Lab Kit.
Treat advertised resolution, frame rate, pixel format, exposure controls, and
USB bandwidth as measurements to verify on the target Raspberry Pi. Do not
assume a particular device path such as `/dev/video0`.

## Testing and benchmarking

Make hardware-independent logic testable on a development computer first. Put
target-device checks in `tests/hardware/` or a documented script. Any performance
claim must state the device, software version, camera mode, scene, duration, and
metrics; follow `docs/BENCHMARKING.md`.

## Git and GitHub habits

Use small, coherent commits with an imperative subject, for example
`docs: document camera verification procedure`. Before committing, inspect the
diff and run the relevant check. At the end of each meaningful, working session,
show the user the commit-ready status and remind them to push their current
branch after they review the change. Never commit secrets, raw captures, or large
model artifacts. Do not create a remote repository or push without the user's
account access and explicit direction.

## Plans for larger work

For a feature spanning multiple modules, a significant refactor, or any task
that needs more than one focused session, create a living ExecPlan in
`docs/exec-plans/active/` and follow `.agent/PLANS.md`. Move it to `completed/`
only after its acceptance checks and retrospective are updated.
