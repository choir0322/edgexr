# Lightweight session-local view map

## Purpose / big picture

Connect explicitly remembered views and their timestamped enrollment orientation.
Show which view is visually recognized, estimated angular directions to stored
views, and observed label transitions. Directly advances bounded fixed-base
spatial awareness. No position, metric depth, navigation or gyro correction.

## Context and orientation

`SceneMemory.process` supplies enrolled/known/unknown decisions and LRU eviction.
`scene_latest` associates preceding IMU context and owns the new map. Up to 12
references already exist. Recognition thresholds and recorder policy stay fixed.
The camera frame is X right, Y down, Z forward; quaternions map current camera
axes into the run's initial reference axes. IMU integration drifts.

## Progress

- [x] Pure bounded map: enrollment nodes, reference-safe eviction, observed edges.
- [x] Validate quaternion/time/reference context before calculating bearings.
- [x] Integrate live rows, compact browser status and background recordings.
- [x] 2026-11-04: 187 tests passed; signs, roll, q/-q, unknowns, epochs, eviction
  and recorder ownership covered. Prior three-view decision replay checked.
- [x] Synthetic ten-second CLI run saved ten schema-1 map snapshots and drained
  the recorder cleanly. No physical sensors or motors accessed.
- [x] Update pipeline/source guide, stage records and runnable Pi instructions.
- [ ] Pi three-view verification; keep unknown orientation distinct from recognition.

## Plan of work

Reuse scene IDs; never auto-enroll or merge views. Retain enrollment orientation
without overwriting it on later recognition. If it was unavailable, say so.
Compute the saved lens axis in the current camera frame only when both contexts
are valid and share the same gyro reference epoch. Expose signed horizontal
right/up angles and angular separation, not meters or geographic headings.
Track directed changes in observed scene labels, counting intervening unknown
observations explicitly. Edges mean observation history, not traversable routes.
Keep at most 12 nodes and 132 directed non-self edges; prune on reference eviction.

## Concrete steps

Implement `src/spatial/view_map.py`, integrate into the single scene worker,
test hardware-free, replay available three-view evidence, then run the live
three-view protocol in `docs/VIEW_MAP.md`. No new dependency or servo commands.

## Validation and acceptance

Known synthetic rotations give expected bearing signs; roll changes full
rotation difference but not a forward-axis pointing separation. Invalid,
nonfinite, future, stale or different-reference orientations produce unknown
angular context without changing visual decisions. Unknown matches remain
unknown. Full-queue recording cannot mutate map snapshots. References and edges
remain bounded. Full tests and a synthetic live CLI run precede Pi instructions.

## Surprises and discoveries

Visual overlap need not mean identical camera direction. Bearing differences
must remain independent diagnostics, never corrections or rejection thresholds.

## Decision log

- 2026-11-03: User approved this bounded map after recorder validation. No learned
  embedding, marker distance, moving-base mapping or new learning website.
- 2026-11-03: Use observed label changes without new smoothing thresholds;
  document that recognition flicker can create edges. Require the same IMU epoch.

## Outcomes and retrospective

Implementation and local verification complete; Pi three-view verification pending.
Replay of 208 existing three-view observations yields three nodes, five directed
links and nine observed label changes. 94 orientations are ready and 114 unknown;
final angular contexts remain unknown rather than being filled in. This replays
decisions, not new visual inference or ground truth. Stationary recorder replay
produces one node and no transition edges. The ten-second CLI smoke test checks
startup, row schema and shutdown; it does not measure real sensor accuracy.
Source-contract, browser JavaScript syntax and diff checks pass. A real browser
visual check and Pi data remain pending. AP cost is exposed as map-update wall
time; total workload CPU/memory studies remain deferred.
