# Timestamp-aware foreground exclusion

## Purpose / big picture

Add an opt-in person-region exclusion to the bounded spatial workload, not a
new identity system or 3D mapper. User approved this integration 2026-11-08.
Freeze the existing recognition thresholds. AP target: quantify the extra
detector/masking workload versus recognition under foreground occlusion.

## Context and orientation

`scene_memory.py` uses 640×360 ORB features and homography verification.
`live_scene.py` owns enrollment/query processing at target 1 Hz; the independent
detector publishes source timestamps and 1280×720 boxes at target 2 Hz.
The IMU remains timestamped context, not a visual-match override.

## Progress

- [x] Inspect current feature matching and detector mailbox contracts.
- [x] Add opt-in source-age-gated masking and diagnostics; defaults unchanged.
- [x] Test coordinate conversion, stale/future/missing detections, coverage and enrollment.
- [x] Review/update PIPELINE and learning source map.
- [ ] Run image-backed Pi trial; no accuracy or AP improvement claim before review.

## Plan of work

First isolate a bounded mask helper, then connect the existing detector mailbox
to the scene worker. Require --detect with --scene-exclude-people. Maximum
detector-source lag is 0.5 s relative to the scene source; future results are
unusable. This is a provisional policy, not exposure synchronization or motion
compensation. Unusable detector evidence produces unknown, not silent unmasked
recognition; enrollment remains pending. Empty fresh detections permit ordinary
recognition but do not prove absence of people. Do not add semantic scoring yet.

## Concrete steps

Run the focused unit tests and full existing suite. Follow
`docs/SPATIAL_FOREGROUND.md` for a new image-backed Pi run and Mac preview.
No motor changes, new packages, model downloads or threshold tuning.

## Validation and acceptance

Check person-only boxes, clipping/scaling, finite timestamps, future/stale
rejection, original pixels unchanged, feature suppression and weak-image
unknown. Record detector source sequence/age, mask area, policy, feature count
and matching reason. Retain existing geometry/ambiguity gates. Pi acceptance
requires actual background recognition and false-match review, not just masks.

## Surprises and discoveries

ORB descriptors use neighborhoods, not single pixels; mask intersecting
keypoint support as well as centers. Asynchronous fresh boxes can still be
misaligned during motion; this limitation remains explicit.

## Decision log

2026-11-08: person class only; furniture semantics deferred. One pair of RAM
measurements closes the storage case with evidence limits, not a causal proof.
Bound the spatial integration before later FPGA/AP work; no hardware purchase.

## Outcomes and retrospective

Implemented opt-in flag, mask helper, atomic detector evidence copy, scene-worker
gating, original-image preservation and telemetry diagnostics. Real ORB tests
check masked enrollment/query and weak evidence. Worker test checks pending
enrollment with missing detection and enrollment with fresh boxes. Existing
thresholds remain unchanged. Live quality/resource evidence pending; no claimed
occlusion-accuracy or CPU improvement. Structured storage result recorded and
its plan closed separately. PIPELINE and learning source map match new flow.
Validation on Mac: 217 unit tests passed, including real OpenCV tests and local
HTTP checks. Changed-file documentation/type contracts, preview JavaScript
syntax and git whitespace checks pass. No physical-hardware trial performed.
