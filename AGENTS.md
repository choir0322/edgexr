# EdgeXR: working agreement for people and Codex

## Purpose

EdgeXR is a learning-first Raspberry Pi 4 spatial-perception project. It will
combine a USB global-shutter camera, IMU motion data, object detection/tracking,
and performance measurement. The goal is to understand each engineering choice,
not to produce opaque code quickly.

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
