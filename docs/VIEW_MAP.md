# Session-local view map

## What is implemented

With `--scene-memory`, the scene worker now maintains a map alongside the
unchanged ORB matcher. No new flag, dependency, sensor command or model is added.

- A node is an explicitly enrolled visual reference, retaining its enrollment
  timestamp and valid gyro orientation (or the reason it was unavailable).
- A recognized view updates its last-seen time and query count; it does not
  overwrite its enrollment orientation or correct gyro drift.
- A directed edge counts observed changes between enrolled/recognized labels.
  Intermediate unknown observations are counted. An edge is **not** a physical
  path, proof of travel, or a map of unseen intermediate space. Recognition
  flicker can produce edges; no new smoothing/matching threshold is introduced.
- At most 12 nodes and 132 non-self directed edges remain. Existing scene-memory
  LRU eviction removes the corresponding node and connected edges.
- Everything resets on application restart. Logs preserve map snapshots for
  inspection, not automatic reload or cross-session localization.

Each node reports the saved forward lens direction expressed in the current
camera frame: positive horizontal angle is right, positive elevation is up.
Negative values mean left/down. These are **gyro-derived viewing-ray estimates**,
not positions or bearings to reconstructed objects. Fixed base and rigid mounting
are assumptions; translation invalidates a physical-location interpretation.
Full orientation difference includes roll; pointing separation ignores pure roll.
Horizontal angle is undefined when the saved ray is directly up/down.
The browser shows all nodes and up to six recently observed directed links;
full bounded edge history remains in each recorded map snapshot.

Both orientations must be valid frame-associated contexts and have the same
reference epoch. No finite unit quaternion, an old/future IMU sample, unknown
integration, or different epochs yields unknown angular context. Visual
recognition can still succeed. Missing enrollment orientation is never backfilled
from a later matched frame: visual overlap does not imply identical orientation.
Drift remains possible even when status says ready. No exposure synchronization,
metric distance, geographic heading, automatic pan/tilt or pose correction.

## Pi verification: three distinct views

Stop the earlier preview. Keep the base fixed and use the same safe manual
view-changing method used for the prior three-view trial; do not force powered
servo gears. No motor-control command is included here.

On the Pi:

```bash
cd ~/projects/edgexr
git pull --ff-only
PYTHONPATH=src python3 -m app.live_preview \
  --device /dev/video0 --imu --imu-sleep-ms 10 \
  --camera-axis-basis configs/camera_axes_neutral.json \
  --relative-orientation --scene-memory \
  --scene-output recordings/live-view-map-01 \
  --scene-seconds 180 --scene-save-images
```

On the Mac, reuse the tunnel if it is already working; otherwise:

```bash
ssh -N -o ExitOnForwardFailure=yes \
  -L 127.0.0.1:8766:127.0.0.1:8765 pi@ai-fusion.local
```

In another Mac terminal:

```bash
open http://127.0.0.1:8766
```

Reload after startup. Remain still for initial IMU bias collection. Then:

1. Once orientation is ready, remember center (View-1), left (View-2), then right
   (View-3). Hold each textured view steady until enrollment succeeds. Keep the
   views distinct enough that identical-looking references do not compete.
2. Without clicking Remember again, revisit center → left → right → center.
   Hold each approximately five seconds; exact timing is not required.
3. Briefly show an unenrolled view, then return to center. Visual overlap can
   legitimately recognize a stored view; unknown is not guaranteed by a turn.
4. At center, check that the left/right saved directions have sensible signs.
   At a recognized view, separation may be nonzero due to overlap and drift;
   do not treat it as an accuracy test against measured physical angles.
5. Let the 180-second timer stop; inspect recording completion. Tell us the
   actual sequence and any unexpected orientation-unknown or recording errors.

On the Mac after completion:

```bash
scp -r pi@ai-fusion.local:/home/pi/projects/edgexr/recordings/live-view-map-01 \
  /Users/ryanchoi/Desktop/
```

## Evidence and AP scope

`updates.jsonl` includes `view_map` and `view_map_update_ms` on each saved row.
The latter brackets map update, angular comparisons and snapshot creation, not
ORB, JSON/PNG writing, total CPU or end-to-end latency. Existing scene compute
fields retain their old scope. Dropped recording jobs can skip snapshots; later
snapshots contain cumulative map state. Recorder bounds and diagnostics remain.

Local checks cover bearing signs, roll, quaternion sign equivalence, timing,
invalid references, unknown visual gaps, immutable snapshots and LRU pruning.
Offline replay of `live-scene-three-01` yields three nodes, five distinct links
and nine label changes; 94 ready/114 unknown orientation contexts. The final
bearings correctly stay unknown. This reuses recorded decisions, not new image
inference or ground-truth validation. Pi live verification and map cost pending.

2026-11-04 local validation: all 187 unit tests passed. A synthetic ten-second
CLI run saved ten map snapshots with complete recorder shutdown. Changed-file
function contracts, browser JavaScript syntax and whitespace checks passed.
These are development-computer correctness checks, not Pi performance claims.
