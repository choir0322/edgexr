# First live scene-memory trial — 2026-10-29

Source: user-transferred `live-scene-01`, 139 valid JSONL rows spanning
138.05 seconds, Pi revision `9ed8898` with dirty tree reported. Detection off,
10 ms post-read IMU sleep, unchanged scene thresholds. Full derived evidence:
[result JSON](../benchmarks/results/live-scene-01-2026-10-29.json).

The user enrolled View-1 at 67.01 seconds after the first logged frame.
Before that, 67 unknown/empty-memory results are expected, not failed returns.
After enrollment there were 43 known and 28 unknown observations. View-1 was
recognized again at 100.05 and 125.05 seconds following unknown periods; there
was also a one-observation known interval at 120.06 seconds. Without footage
or user movement annotations these are algorithm decisions, not verified
physical revisits or measured recognition accuracy.

24 of the 28 query rejections were concentrated support: correspondences
occupied too little image area or too few cells. At 119.07 s, reference hull
coverage was 10.92%; at 120.06 s it was 12.14%; at 121.06 s it was 11.72%.
The unchanged minimum is 12%. This explains the observed decision switch at
the acceptance boundary, but not whether the camera was physically returning.
Do not lower thresholds solely to make the label remain visible.

Scene cadence was 1.00 Hz. Median/p95 compute was 70.21/121.45 ms; median/p95
host receipt-to-completion was 90.44/145.89 ms. These are wall observations,
not CPU measurements or camera-to-display latency. Orientation was ready for
138 observations after one startup unknown; median/max preceding-sample lag
was 6.68/14.51 ms. Ready means continuous numerical integration, not accuracy.

**Unresolved orientation discrepancy:** at the known results around 100 and
125 seconds, relative quaternion differences from enrollment were 52.67° and
73.85°. The second match had 478 inliers from 481 descriptor matches spread
across eight cells. Strong image agreement does not prove exact same pose,
but this is sufficient reason not to call the attached orientation validated.
Possible causes cannot be distinguished without visual/movement evidence.
Scene matching currently does not use these angles to accept/reject a match.

Next: confirm whether the camera visibly returned to the taught direction,
and whether the final unknown period was an intentional turn away. If needed,
retain paired small reference/query images in the next explicitly recorded
trial to distinguish real view changes, matching errors and gyro disagreement.
No runtime, threshold or orientation-correction change follows from this log alone.
