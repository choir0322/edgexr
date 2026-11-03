# Spatial walkthrough update — 2026-11-04

## Purpose / big picture

User requested a learning-directory update covering work since the previous HTML
walkthrough, a next-step recommendation and the AP/computer-systems relevance.
This is an explicitly requested documentation detour, not a new runtime feature.

## Context and orientation

Existing program-flow-explorer expands nodes in place. Its graph description
predated scene memory and still denied live orientation integration. Preserve
its renderer/design; extend contracts and branches rather than replace the site.

## Progress

- [x] Inspect old graph and current source/measurement records.
- [x] Add orientation, scene-memory, map, recording and validation nodes.
- [x] Correct full-source capture condition and configurable IMU polling.
- [x] Add chronological source/evidence guide and systems/AP interpretation.
- [x] Update roadmap; propose bounded application handoff, then exact AP baseline.
- [x] Review pipeline and learning source map; runtime diagram unchanged.
- [x] JavaScript syntax, 64 node references/source paths checked; browser scene
  expansion, nested map expansion and saved-ray inspection verified.

## Plan of work

Use declarative spatial graph additions, preserve older FFT/detector lessons,
add no dependencies or new private images, and keep numerical examples separate
from recorded results. Keep legacy animation scope explicit, not a fake full trace.

## Concrete steps

Open docs/learning/program-flow-explorer.html. Expand Scene memory + map, then
Session View Map. Expand IMU for axes/quaternion/context. Supporting paths contains
the bounded recorder and separate servo check. Companion markdown links evidence.

## Validation and acceptance

All child IDs resolve and source files exist; syntax checks pass. Local browser
confirms nested expansion remains in the same graph and inspector content updates.
Long labels receive taller cards to avoid overflow. No sensor or model executed.
Existing private captures remain outside Git; no hosting service added.

## Surprises and discoveries

Learning README still called scene memory offline-only. Both capture consumers
need full source pixels; scene memory must be included even with detector off.

## Decision log

- Preserve local files and incremental node expansion, per user preference.
- Do not claim exact tilt return, precision angles, room position or full SLAM.
- AP proposal is a future workload baseline, not an experiment already performed.

## Outcomes and retrospective

Updated local walkthrough and source-linked progress/systems guide. Diagram
reviewed; unchanged runtime data flow. Spatial application handoff remains next;
no AP measurements or algorithm changes in this documentation task.
