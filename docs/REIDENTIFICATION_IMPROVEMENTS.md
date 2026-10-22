# Re-identification improvements — 2026-10-22

The first-return failure recorded as ID 8→9 now restores ID 8 in an offline
replay of all 117 exact detector updates. Existing successful returns remain
successful. This is development-set evidence, not a general accuracy estimate.

## Implemented

- `BasicTracker._learn_appearance` keeps up to four 64-value normalized
  brightness descriptors per ID. The first eligible view remains an anchor;
  additional distinct views rotate through three slots. Cosine ≥0.98 against
  a stored view prevents nearly identical samples filling the gallery.
- Enrollment requires detection confidence ≥0.50 and source-box area ≥60% of
  the largest accepted area for that track. Tiny/flat descriptors already fail
  extraction. A weak or shrunken detection can still be tracked/displayed at
  the existing live 0.30 cutoff; it simply does not teach memory a new view.
- `RetiredObjectMemory.take_match` uses the best gallery score for each ID,
  then compares different IDs for ambiguity. Two good views of one ID are not
  competing identities. Threshold 0.85, margin 0.05, class gating, one-time
  claims, 32 retired IDs and 10 seconds since last detection remain in effect.
- A restored ID carries its previous gallery back into active tracking, so
  repeated exits can still use earlier references.
- Tracker statistics report enrollment reasons and active gallery sizes;
  memory diagnostics include the best candidate's gallery size. These flow
  through existing snapshot/trial metadata; no raw descriptors enter that API.

The area test is a heuristic, not a body-completeness detector. It can reject
legitimate smaller views as an object recedes. Likewise, a high-confidence crop
may still contain background. The initial anchor can be poor. More candidate
views can increase false matches; same-class lookalike trials remain necessary.

## Replay evidence

Input: `reid-person-bottle-01`, recorded source `49145eb`, Raspberry Pi 4,
OV9281 1280×720 gray detector frames, fixed original detections and timestamps.
Replay runs on the Mac; it does not measure Pi performance or re-run inference.
Rows are zero-based detector-update rows. Times in the older report use the
recording start; the replay command reports seconds from the first input frame.

| Row | Recorded transition | New replay transition | Best score | Result |
|---|---|---|---|---|
| 21 | 4→6 | 4→6 | 0.440 | Still fails |
| 36 | 6→7 | 6→7 | 0.801 | Still fails |
| 50 | 7→8 | 7→8 | 0.582 | Still fails |
| 65 | 8→8 | 8→8 | 0.943 | Preserved |
| 80 | 8→9 | 8→8 | 0.903 | Recovered |
| 92 | 9→9 | 8→8 | 0.948 | Preserved; ID stays 8 |
| 106 | 9→9 | 8→8 | 0.932 | Preserved; ID stays 8 |

Four of seven returns preserve the preceding ID, versus three previously.
Across all classes: 41 stored views, 127 duplicate-view skips, four low-score
skips and four shrunken-crop skips. Scores for some remaining failures decline;
the selected gallery is bounded, not an oracle containing every earlier view.
The recording has one returning person and no detected bottle boxes, so it
cannot establish false-restoration rates or repair the bottle detector.

Reproduce with an existing Python environment containing NumPy and Pillow:

```bash
PYTHONPATH=src python3 scripts/replay_reidentification.py /path/to/reid-person-bottle-01
PYTHONPATH=src python3 -m unittest discover -s tests/unit -v
```

The replay prints JSON and leaves private images untouched. Pillow is an
offline replay dependency already present on the development Mac; the live Pi
path needs no new dependency. No model or dependency was downloaded.

## Other ways to improve

1. **Temporal retry:** a first partial re-entry can fail while a later full
   view succeeds. An opt-in two-second provisional-ID experiment is now
   implemented; live two-person testing remains pending. See
   [the next trial](REIDENTIFICATION_NEXT_TRIAL.md).
2. **Learned appearance:** a compact person re-ID embedding may cope better
   with pose/crop changes than our brightness grid. Deep SORT demonstrates
   learned appearance association, but its reported results do not establish
   accuracy or speed on this monochrome Pi workload.
   [Original paper](https://arxiv.org/abs/1703.07402).
3. **Weak-detection association:** ByteTrack uses weaker detections to continue
   existing tracks, reducing fragmentation. This may help flickering objects,
   but requires retaining and separately handling lower-score detector outputs.
   [Original paper](https://arxiv.org/abs/2110.06864).
4. **Better crop representation:** foreground masking or aligned body regions
   could reduce background and partial-body sensitivity. Test them on the
   unresolved returns plus negative examples before replacing the descriptor.
5. **Spatial context:** an opt-in reliable image-motion tie-break now predicts
   a broad return region. It cannot establish identity; coverage and false
   claims need a pan trial. IMU-to-camera calibration remains future work.

The next live check uses `--detect --reidentify` with neither new option, then
replays those exact inputs with retry enabled. Capture a second person and
retain failed and false restores as well as successes. Measure added matching
time on the Pi. See [the staged trial protocol](REIDENTIFICATION_NEXT_TRIAL.md).

## Verification

113 unit tests ran successfully (two optional runtime checks skipped in this
environment), including four new gallery regression tests. The program-flow
learning test and whitespace check passed. The repository-wide comment-contract
audit still reports pre-existing missing docstring sections and anonymous
callbacks in older modules; the new helper/replay/test functions follow the
required contract. No physical hardware run was performed in this change.
