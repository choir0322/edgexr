# Bounded remembered-direction consistency check

## Purpose / big picture

One short check decides whether viewing directions are usable or need a focused
correction. User approved on 2026-11-04 and requested it not become prolonged.

## Context and orientation

User confirmed recognition, multiple references, direction signs, separation
display, counts and links. Angular magnitude remains unvalidated; an earlier
near-return image had 16.53° separation. Reuse servo demo and view-map math.

## Progress

- [x] Optional bounded still interval and full orientation checkpoints.
- [x] Local differences with unknown/epoch/freshness safeguards.
- [x] Single-run protocol and decision rule; no threshold tuning.
- [x] 191 regression tests pass, including fake-servo/clock schedule checks;
  CLI with the still option checked without importing hardware or moving motors.
- [x] Review/update pipeline and IMU source guide; diagram data flow unchanged.
- [ ] One Pi run, inspect images, make the next-step decision.

## Plan of work

Keep existing motor safety gates/path. Add --still-seconds (0–60, default 0),
use 30 here. Save before-still plus the three old checkpoints. Compare local
quaternions without declaring image agreement or applying gyro corrections.

## Concrete steps

Follow [DIRECTION_CONSISTENCY.md](../../DIRECTION_CONSISTENCY.md): fresh preview,
single ~one-minute run, automatic summary, SCP. No manual timing task.

## Validation and acceptance

Test argument bounds, default path, full saved orientation, local differences,
stale/invalid/restarted context. Mock hardware execution. Pi 4, requested 720p
MJPEG30, scene memory, detector off, 10 ms sleep; stationary textured indoor scene.
Use 5° only as a provisional coarse consistency tolerance after image review,
not ground truth. One valid run suffices for the next decision; repeat only
incomplete or physically invalid evidence. No total AP cost claim.

## Surprises and discoveries

Scene overlap is not equal pose. HTTP gyro/image values are independently timed;
settled checkpoints reduce but do not remove that limitation.

## Decision log

- 2026-11-04: Reuse ±20° confirmed movements; no live scheduling/model change.
- 2026-11-04: Save checkpoint reference rather than require manual re-enrollment.

## Outcomes and retrospective

191 hardware-independent tests passed; whitespace checks passed. No Pi or motor
was accessed during implementation. Existing fake-clock/fake-servo tests cover
the unchanged path; new tests cover still bounds and checkpoint differences.
Pi evidence pending. Map stays experimental; no angular validation claimed.
