# Recorded scene memory: first A → B → A check

This implemented offline tool teaches the program a named view from one video
frame, then asks whether later frames match it. It returns a session-local
**scene** ID, separate from detector object IDs. It uses the Pi's existing
NumPy/OpenCV runtime. The live preview, IMU, and servo programs are not involved.
Live automatic enrollment and orientation association are the next steps.

## Run on the Pi

No camera preview or SSH tunnel is required; this reads a saved video. The
following example was exercised on the transferred `combined-motion-02` clip.
Its local SHA-256 is recorded in the small development result below; a different
clip at that path may need different selected times.

```bash
cd ~/projects/edgexr
git pull --ff-only
python3 -c "import cv2; print(cv2.__version__)"
PYTHONPATH=src python3 -m unittest discover -s tests/unit -p 'test_scene*.py' -v
PYTHONPATH=src python3 -m spatial.scene_revisit \
  recordings/combined-motion-02/camera.mkv \
  --reference A=2 --query 7 --query 13 \
  --output recordings/scene-revisit-01
cat recordings/scene-revisit-01/report.json
```

On the development recording, expected decisions were `enrolled A`, `unknown`,
then `known A`. Unknown at seven seconds is intentional: only A has been taught.
A new view is created only through an explicit `--reference LABEL=SECONDS`.
You can supply multiple references and queries; all events run in chronological
order, so a future reference cannot answer an earlier query. Labels are unique
within the input list. Use another output name for repeats; existing output is
never overwritten. Video times are seconds from the first decoded timestamp,
not seconds after a servo cue. Each event uses the first decoded frame at or
after its requested time. Requests that land on the same frame fail explicitly.

Copy the result to the Mac with:

```bash
scp -r pi@ai-fusion.local:/home/pi/projects/edgexr/recordings/scene-revisit-01 \
  /Users/ryanchoi/Desktop/
```

Each run saves `report.json` and one 640×360 PNG per selected event under ignored
`recordings/`. Open those images to confirm the view sequence. The report retains
requested/actual video times, source hash, source-code revision/dirty flag,
runtime versions, thresholds, event compute time and rejected candidate reasons.
`complete` means all requested frames were processed, not that all queries
matched. EOF/decoder errors yield a partial report and a nonzero exit status.
Frame selection relies on OpenCV decoder timestamps; missing/non-increasing
timestamps fail rather than pretending to know exposure or IMU alignment.

## Implemented rules

- Input is uint8 16:9 grayscale, resized to 640×360. At most 600 ORB features
  are extracted per view. Stored memory contains feature coordinates and
  descriptors, not the full images or an object model.
- A frame needs at least 60 features and distributed image coverage before
  enrollment/query matching. Weak frames return unknown without changing views.
- Descriptor matches pass a 0.75 nearest-neighbor ratio and Hamming distance
  ≤64, then mutual nearest-neighbor checks enforce unique correspondences.
- A candidate needs at least 24 matches. RANSAC fits a reference-to-query
  homography with a three-pixel threshold. At least 20 inliers and a 0.55
  inlier fraction are required. These are experimental thresholds.
- Inliers must cover at least 12% of each image's area by convex hull and
  occupy at least four of nine spatial cells in both frames. This reduces the
  chance that one small foreground object establishes an entire scene match.
- The projected image footprint must be finite, convex, non-mirrored and
  between 0.25× and 4× the canonical image area. A homography does not provide
  a camera rotation angle or a 3D position here.
- If a second verified view has at least 85% of the best candidate's inlier
  count, return `unknown: ambiguous_views`. Counts are not probabilities.
- Up to 12 explicit views are kept by default (configurable up to 30).
  At capacity the least recently enrolled/successfully queried view is evicted.
  Queries never enroll automatically. Reset clears references/time but scene
  IDs are not reused within the same memory instance.

Source paths: [`scene_memory.py`](../src/spatial/scene_memory.py) owns feature
extraction, verification and bounded state. [`scene_revisit.py`](../src/spatial/scene_revisit.py)
owns local-video decoding and reports. [The source guide](learning/SCENE_MEMORY.md)
maps the named functions; [the active plan](exec-plans/active/visual-scene-memory.md)
tracks live and held-out work still needed.

## Evidence and limits

The Mac development replay of existing Pi footage recognized the return at
13.014 s with 324 geometric inliers spread across six cells in both images.
The turned-away frame at 7.029 s had only seven descriptor matches to A and
was rejected. The selected images were visually inspected. This is **one
development clip**, not held-out recognition accuracy or measured Pi performance.
The [small machine-readable record](../benchmarks/results/scene-revisit-development-2026-10-29.json)
contains the input hash and derived counts. No image/descriptor payload is in Git.

The [Pi reproduction](../benchmarks/results/scene-revisit-pi-2026-10-29.json)
used the identical source hash and returned the same three states. The return
had 320/388 geometric inliers across six cells, compared with 324 on the Mac;
the exact numeric results differ, but both pass the unchanged criteria.
Event compute was 90.87 ms to enroll, 56.60 ms to reject B, and 110.06 ms to
recognize A. These three observations exclude decoding and I/O, and establish
neither sustained live rate nor CPU cost. The Pi reported a dirty working tree.
Next, test a separate recording without tuning thresholds to this clip, then
integrate a bounded live scene worker with timestamped orientation context.

A second replay enrolled both A at 2 s and B at 7 s. A query at 7.529 s still
overlapped B visually, but contained only 62 features and 11 usable matches to
B as the viewpoint changed; it returned unknown. The final query again retrieved
A. This preserves a real coverage limitation rather than lowering thresholds
to force recognition. It reinforces the need for multiple representative views
and held-out testing before a dependable live scene-memory claim.

Synthetic tests also cover transformed returns, unrelated views, blank frames,
small shared foregrounds, ambiguous duplicate references, bounded eviction,
reset, invalid timestamps, chronological replay and partial output. Large moving
foregrounds or repeated patterns can still fool geometric matching; parallax,
blur and lighting changes can cause missed returns. Scene IDs describe visual
overlap with references and do not partition a room into metric areas.
No visual correction of the gyro, depth, world heading or translation estimate
is implemented. Dedicated AP cost measurement remains deferred.

The implementation follows OpenCV's documented
[ORB descriptor matching convention](https://docs.opencv.org/4.x/d1/d89/tutorial_py_orb.html)
and [RANSAC homography verification](https://docs.opencv.org/4.x/d1/de0/tutorial_py_feature_homography.html).
All project thresholds and acceptance rules above are our experimental choices.
