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
- [ ] Implement and validate bounded background recording in a follow-on step;
  retain diagnostics for the unresolved older IMU interruption.

## Plan of work

Instrument first. Run the same stationary textured view with one enrollment
for 120 seconds in each mode. Keep browser polling, lighting, detector off,
10 ms sleep and scene reference count consistent. Restart to reset orientation.
If results differ, reverse run order before causal claims or scheduling changes.

## Concrete steps

See docs/LIVE_SCHEDULING_DIAGNOSTICS.md for complete commands. No motor commands.
Use new output directories; transfer JSON evidence without uploading images to Git.

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
Diagram reviewed; unchanged because this update records evidence only.

Instrumentation implemented; underlying root cause and scheduling remedy pending.
No physical hardware was accessed during local validation. Image saving,
recognition thresholds, freshness limits and polling sleep policies are unchanged.
