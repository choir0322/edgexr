# Direction-consistency result — 2026-11-04

Source: transferred `direction-consistency-01`; user confirmed visible returns.
All four PGM images were independently viewed (lossless PNG conversion for display).
Metadata reports complete, 55.29 seconds, 994/994 ready orientation polls, zero
telemetry errors and settled final observation. All 162 commands, including two
initial centers, are logged; both axes finish at commanded zero. The four local
quaternion comparisons recompute exactly from `checkpoints.jsonl` using
`checkpoint_summary`. No raw images or logs committed.

| Comparison | Pointing change | Full rotation change | Estimated image shift dx, dy (320×180 px) |
|---|---:|---:|---:|
| Still for 30 seconds | 1.12° | 1.55° | −0.00, −0.01 |
| Pan return | 0.15° | 0.20° | −0.81, −0.03 |
| Tilt return relative to after-pan | 1.10° | 1.41° | −0.03, −8.96 |
| Combined return | 1.04° | 1.28° | −0.51, −9.04 |

Image shifts were calculated on the Mac with the unchanged
`recording.visual_motion.image_shift` applied directly to each pair of saved PGM
images. Respectively 9, 9, 8 and 7 patches agreed. They estimate image-content
translation, not physical rotation. No pixel-to-degree conversion is justified
without camera calibration. Visually, the same cabinet/books/bottles remain,
but the final tilt image is noticeably displaced vertically (about 5% of height).

## Decision: close this bounded check, with limits

All reported angular changes are below the provisional 5° criterion, and the
stationary/pan imagery supports close returns. This supports short-run consistency
for coarse experimental direction context. **It does not validate exact tilt
return or angle accuracy**: the tilt checkpoint is not image-aligned, so its
1.10° change cannot all be labeled gyro error. Mechanical return, viewpoint and
estimator effects have not been separated. No repeat requested; retain this
limitation rather than prolong the check or claim an exact pass.

The approximately 21° final angle in metadata is relative to the older startup
reference. The pre-sweep checkpoint was already about 21.6° from that reference;
use local quaternion comparisons, not the final startup-relative angle, for
this return test. The earlier 16.53° long-session discrepancy is not resolved by
this short run. No correction, threshold tuning or automatic pose reset was made.

## AP and provenance

[Structured result](../benchmarks/results/direction-consistency-2026-11-04.json)
retains the context and limitations. Polled medians: capture 30.09 fps, motion
27.88 fps, latest motion compute 33.72 ms, IMU 77.64 Hz. Skipped motion-analysis
frames increased by 132; these are not camera sensor losses. Polls can repeat
the same rate/compute estimates; they are not distinct-event benchmarks.
CPU, memory, temperature and power were not measured. Actual commit/software
versions, negotiated camera mode, power and cooling were not saved by this
diagnostic and must not be inferred from the developer checkout. Requested
mode per instructions was 720p MJPEG30, detector off, scene memory on, IMU sleep
10 ms. Diagram/source guide reviewed; no implementation/data-flow changes.
