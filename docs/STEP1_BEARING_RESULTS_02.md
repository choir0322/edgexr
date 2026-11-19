# Step 1 bearing trial 02: results (2026-11-20)

**Verdict: PASS** on the criteria fixed before trial 01, using the two analysis
filters fixed after trial 01 and before this trial (`--max-box-width-fraction 0.4
--exclude-edge-clipped`). Summary: [bearing-trial-02.json](../benchmarks/results/bearing-trial-02.json).

| Check | Result | Pass |
|---|---|---|
| ≥20 bearings while head yaw spans ≥15° | 59 bearings; head yaw −16.3° to +3.7° | yes |
| Yaw spread (5–95%) ≤4° | 2.6° (median −31.7°) | yes |
| Pitch spread ≤4° | 3.6° (median +0.3°) | yes |
| Still-head yaw spread ≤3° | within limit (51 still readings) | yes |
| First vs last still yaw within 2° | −31.4° vs −32.2° | yes |

During the pan the bottle's image direction swung from −30° to −15° and back to
−36° while its bearing stayed between −31.4° and −33.8°. During the tilt its image
pitch moved from −11° to +8° while its bearing pitch stayed between −0.1° and +2.5°.

## Limits found

- **Few moving samples.** The detector runs at 2 Hz, so only about 7 readings came
  from the head while it was turning; most evidence is from settled poses.
- **False detections.** Five oversized "bottle" boxes were removed by the preset
  filter. At 23.0 s a false "bottle" box outscored the real bottle and gave −42.7°
  (outside the 5–95% range). Choosing the right object is step 2's job.
- **Gyro drift.** The head did not move before the sweep, yet the gyro said it had
  turned 3.3°. The bottle read about −30° when placed and −31.7° during the run; its
  true direction from the centred head (calibration only) was −34.9°. Bearings share
  the gyro's slowly drifting reference: step 3 must re-anchor it.
- **AP: frame-to-gyro delay.** Turn-direction offsets suggest roughly 135 ms
  (4 + 3 samples; trial 01 gave about 95 ms). The delay is of order 0.1 s and lies
  mostly before the program receives the frame (pairing lag median 7.4 ms). Not
  yet separated into exposure, USB and decode parts.
