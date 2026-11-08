# First person-exclusion trial: 2026-11-08 review

The user tested a person crossing the **left** view, not center. That is a valid
variant if left was successfully enrolled. The important discovery is that it
was not: three clicks produced only two stored views. This is not user blame;
the UI made it too easy to miss a rejected enrollment.

Source: local `Desktop/spatial-foreground-01`, 180 PNG/JSONL observations,
metadata and timing-final. Small [structured result](../benchmarks/results/spatial-foreground-01.json)
contains provenance, timing distributions and limits. Private images stay out
of Git and out of the public learning page.

## Enrollment evidence

| Seconds from first frame | Request | Outcome |
| --- | --- | --- |
| 11.01 | View-1 / intended center | Stored, scene ID 1 |
| 22.01 | View-2 / intended left | Rejected: weak_image; 249 usable points; 77.92% box-mask area |
| 31.02 | View-3 / intended right | Stored, scene ID 2 |

View-2's source image `frame-00000663.png` visibly contains a nearby person/arm
on the left. The logged person boxes cover [0,3,502,360] and [0,0,104,323] in
640×360 coordinates. Source lag is 465 ms. Removing these boxes and overlapping
descriptor neighborhoods leaves concentrated evidence: 249 exceeds the minimum
60 points, but count is only one of the weak-image gates; hull area/cell support
must pass too. No reference was saved by this request. View-3 is a label, not
proof that three entries exist; its numeric scene ID is 2.

Later left-view observations compare only against center/right. Therefore
their unknown results do not establish failure to recognize an enrolled left
view, nor does this run validate improved occlusion robustness. The last 20
observations are unknown, consistent with ending on the reported unenrolled
view. Selected image review agrees with that description; this is not complete
frame-by-frame ground truth or a false-positive-rate estimate.

## Availability, workload and evidence quality

- Decisions: 2 enrolled, 7 known, 171 unknown. These are NOT an accuracy fraction.
- Fresh detector evidence: 178/180; one startup missing, one stale at ~505 ms.
- 58 observations carry person boxes. Weak-image rejection occurs 20 times.
- All 180 records written, no drops, queue high water 1/4; no scene error.
- IMU: zero gaps over 200 ms, maximum gap 35.50 ms.
- Scene compute median/p95/max: 65.55 / 190.32 / 220.42 ms.
- Scene-thread CPU median/p95/max: 51.44 / 149.34 / 166.55 ms.
- Image-write maximum 53.74 ms; queue-wait maximum 6.78 ms.

The metadata names revision 729b080 but marks the Pi worktree dirty; the exact
change is not recorded. OpenCV 4.11.0/Python 3.11.2, detector enabled, IMU10ms.
No paired unmasked run, global CPU/RSS/temperature/energy comparison exists.
Do not compare this directly to the detector-off storage workload.

## Decision and next bounded correction

Do not loosen recognition or freshness thresholds based on this run. First
make enrollment success/failure persistent and unmistakable in the live UI,
including requested label and stored-view count. Do not silently retry a weak
enrollment on a later direction. Then repeat a short fixed-left crossing after
explicitly confirming the left reference is stored. Include clear-background
and unenrolled controls. This review does not modify runtime policy; semantic
memory and 3D remain subsequent scoped work.
