# Step 1 bearing trial 01: results (2026-11-20)

**Verdict against the criteria fixed before the trial: FAIL.** The bearing
computation itself behaved as designed for yaw; the failures come from what was
measured, not from the gyro/calibration arithmetic. Summary:
[bearing-trial-01.json](../benchmarks/results/bearing-trial-01.json).

| Check (fixed beforehand) | Result | Pass |
|---|---|---|
| ≥20 bearings while head yaw spans ≥15° | 35 bearings over 19.6° | yes |
| Yaw spread (5–95%) ≤4° | 51.5° | **no** |
| Pitch spread ≤4° | 22.0° | **no** |
| Still-head yaw spread ≤3° | 1.6° | yes |
| First vs last still yaw within 2° | −29.9° vs −29.1° | yes |

## What the data show

- **Yaw held steady while the image moved.** The bottle's image direction changed
  by 13–42° across the run, but its bearing stayed near −29.6°. When the servo
  script centred the head (~4 s in: +4.8° yaw, +12.9° pitch), the bearing went
  from −29.6° to −29.7°.
- **Yaw failure = detector false positives.** While the real bottle was out of
  view (16–19 s), the detector labelled four huge regions "bottle" (576–1280 px
  wide) at bearings +10° to +37°. Excluding boxes wider than 40% of the image
  (post hoc) leaves a yaw spread of 2.4°.
- **Pitch failure = cut-off boxes.** The bottle extended past the left and bottom
  image edges in most frames, so the box centre moved with the cut, not with the
  bottle. Boxes not touching an edge: yaw spread 2.2°, pitch spread 2.9°, but only
  14 of them, below the 20 required.
- **Placement.** Seen from the centred head the bottle was 39.1° left and 11.3°
  below the lens axis (box cut off at the left edge), not 30° left at lens height.
  Bearings are measured from the head direction when the preview started, which was
  not the centred pose (the preview started before the servo script centred it).
- **AP: frame-to-gyro delay.** Bearings shifted with turn direction by an amount
  that suggests a delay of about 90–100 ms between a frame's exposure and the gyro
  reading paired with it (tentative: 6 turning-right and 4 turning-left samples).
  Pairing lag inside the program was small (median 5.5 ms, p95 12.3 ms), so most of
  the delay would be before frame receipt (exposure, USB, MJPEG decode). Not yet
  separated or independently measured.

## Changes for trial 02 (decided before running it)

1. Analysis uses `--max-box-width-fraction 0.4 --exclude-edge-clipped`; the five
   criteria are unchanged.
2. Each bearing now logs the head quaternion, so directions can be re-expressed
   exactly from the centred head.
3. Placement uses the live label: start the preview with the head already centred
   and move the bottle until it reads about −30°/0° with its box fully inside the image.
