# Live scheduling and recording diagnostics

## Purpose / big picture

Distinguish sensor-read, polling wake-up, publication, scene compute and recording
stalls before changing architecture. Direct AP relevance; fixes a functional
reliability blocker rather than launching the deferred optimization campaign.

## Context and orientation

Three-view trial contained 2.22 s scene compute and 5.84 s image-write wall
intervals, with stale IMU orientation. Correlation alone cannot identify the
IMU interruption. Keep recognition and 10 ms polling settings unchanged.

## Progress

- [x] Add bounded IMU slow-event memory and cumulative maxima, no IMU disk writes.
- [x] Add scene CPU/wall clocks and timestamped image/log intervals.
- [x] 178 tests passed; changed source contract checks passed. Ten-second
  synthetic run saved ten rows and verified the final log-write interval.
- [x] Update pipeline and source guide.
- [x] Compare Pi stationary trials: synchronous image/JSON writes block scene
  progress, but neither run lost IMU continuity. See docs/LIVE_SCHEDULING_RESULTS.md.
- [x] 2026-11-03: Reverse-order B/A analyzed: PNG stall recurred (2.04 s),
  no IMU interruption; unequal enrollment timing documented in results.
- [x] Implement bounded background PNG/JSON recording with explicit counters,
  enrollment admission, isolated errors and five-second shutdown drain.
- [x] 2026-11-03: 183 tests passed with real OpenCV, including blocked image
  write, bounded overflow and deferred enrollment/reference preservation.
  Changed-file contract checks, browser script syntax and diff checks passed.
- [x] Ten-second synthetic CLI recording auto-stopped and drained: ten rows,
  ten PNGs, zero recording drops, no pending records. No physical hardware used.
- [x] Update pipeline diagram and scene-memory source guide for schema 2.
- [x] 2026-11-03: Pi image-enabled verification passed: 120 saved observations,
  no drops; scene recognition completed during a 1.335 s PNG write. Maximum
  source gap 1.035 s, IMU gap 33.24 ms, no stale event. Retain diagnostics for
  the unresolved older IMU interruption; it is not claimed solved.

## Plan of work

Instrument first. Run the same stationary textured view with one enrollment
for 120 seconds in each mode. Keep browser polling, lighting, detector off,
10 ms sleep and scene reference count consistent. Restart to reset orientation.
If results differ, reverse run order before causal claims or scheduling changes.

Approved follow-on implementation (2026-11-03): one recorder thread owns PNG
and JSON writes. Four waiting jobs plus one active operation bound memory.
Drop new query evidence when full, count it, and keep recognition running.
Leave enrollment requests pending until a slot is available. FIFO preserves
reference-before-query evidence. Separate recording errors from scene health.
Drain accepted work for up to five seconds on stop; missing final file or
timeout is incomplete. No polling or recognition threshold changes. Test slow
writes, overflow, reference ordering, immutable snapshots, errors and shutdown.
Update pipeline and learning guide in the same commit. Repeat image-enabled
120-second Pi trial as a new schema-2 workload, not a byte-identical baseline.

## Concrete steps

See docs/LIVE_SCHEDULING_DIAGNOSTICS.md for complete commands. No motor commands.
Use new output directories; transfer JSON evidence without uploading images to Git.
For the new implementation, follow docs/BOUNDED_SCENE_RECORDING.md instead:
one image-enabled stationary trial using a new `scheduling-background-01` folder.

## Validation and acceptance

Unit-check separate read/publish/wake durations, bounded events and final logging.
Existing behavior tests must pass. Pi evidence must retain unknown orientation
instead of silently bridging gaps. CPU clocks have explicit scopes; clocks do
not prove a specific kernel scheduling or SD-card fault.

## Surprises and discoveries

The prior PNG operation demonstrably blocked the scene worker, but whether it
blocked the IMU is unresolved. Snapshot itself invalidates stale orientation;
capture its first observation time/sample age rather than guessing.

## Decision log

- 2026-11-02: Preserve synchronous recording for this comparison. Introducing
  a writer queue first would change the workload before diagnosing it.
- 2026-11-02: Slow event thresholds are diagnostic only (read/publish/wake >20 ms
  or midpoint gap >200 ms); they do not alter sample acceptance or integration.
- 2026-11-03: User approved the bounded recorder after both trial orders showed
  synchronous recording stalls. Use four queued records as a small explicit
  initial bound, not a measured optimal setting. A failed writer does not
  invalidate valid scene recognition; its independent status reports evidence loss.

## Outcomes and retrospective

First Pi A/B analyzed: 120 versus 108 scene updates; median compute approximately
116/118 ms, PNG maximum 5.20 s, JSON maxima 1.51/2.23 s. Maximum IMU gaps
31.96/34.92 ms, no stale event. Prior IMU failure not reproduced. Preserve
causal distinction: synchronous scene blocking demonstrated, hardware/storage
root cause unknown. Pipeline/learning guide reviewed unchanged: evidence only.

Reverse-order B/A: 118/120 observations, longest IMU gaps 37.35/33.97 ms,
no stale events. Multi-second JSON stalls did not recur. PNG blockage is
repeatable across order; severity varies. Enrollment at 18.98/4.99 s prevents
treating compute medians as precisely matched workloads. No more identical
stationary repetitions required before a bounded-recorder implementation.
The reverse-order analysis itself left the diagram unchanged; the subsequent
recorder implementation updates both diagram and source guide.

Instrumentation and bounded recorder implemented and Pi-validated.
The source test proves the scene producer can publish another real ORB result
while PNG writing is blocked. With the queue full, enrollment stays pending,
then its image and reference links are saved after capacity returns. Error and
timeout tests reject successful-recording claims; no-record shutdown is valid.
Underlying storage/scheduler cause and earlier IMU interruption remain unknown.
No physical hardware was accessed during local validation. PNG format,
recognition thresholds, freshness limits and polling sleep remain unchanged;
recording scheduling and schema changed explicitly.

Pi validation demonstrates decoupling under an actual slow write, not merely
a stall-free smoke test: next recognition starts and finishes inside the prior
PNG write interval. All 120 rows/images drained successfully, with no recording
drops. Queue high-water was one; large overflow remains locally tested rather
than Pi-measured. Full resource optimization remains deferred. Results and
limitations are in docs/LIVE_SCHEDULING_RESULTS.md and
benchmarks/results/scheduling-background-2026-11-03.json. Milestone complete;
underlying storage mechanism and the separate earlier IMU failure remain open.
Pipeline/source guide reviewed unchanged for this evidence-only update.
