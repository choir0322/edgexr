# EdgeXR Spatial Application v1

Status: **profile defined; existing components implemented and individually
exercised on Pi; final packaged acceptance run pending.** This is an application
milestone, not a claim of production reliability or a new algorithm release.

## Outcome and boundaries

On a Raspberry Pi 4 with the existing monochrome USB camera and rigidly mounted
SH3001 IMU, explicitly remember several room views, recognize revisits, and show
their estimated directions relative to the current camera. Keep the base fixed.
The map is session-local visual memory, not a floor plan. Restart clears it.

No position, distance, depth, geographic heading, SLAM, visual drift correction,
automatic motor control or cross-session localization is included. Gyro drift
can grow while status remains ready; recognition means visual overlap, not an
identical lens direction. Do not promise angular accuracy from these tests.

## 1. Frozen launch profile: `spatial-v1-evidence`

This documented command is the configuration; no new config loader is required.
Record the Git commit in the generated metadata. Use the existing mounting and
`configs/camera_axes_neutral.json`; a moved IMU invalidates that assumption.

| Component | Selected behavior |
| --- | --- |
| Camera | Request 1280×720 MJPEG, 30 fps; verified device path supplied by user |
| Motion/display | 320×180 grayscale; newest-frame processing |
| Scene | 640×360 grayscale ORB/geometric matching, target 1 Hz, existing thresholds |
| IMU | 10 ms pause after reads, **not** a guaranteed 100 Hz sample rate |
| Orientation | Per-run still bias, fitted camera axes, gyro-only quaternion |
| View map | At most 12 references, 132 directed label-change links; LRU eviction |
| OpenCV | Existing two-internal-thread setting |
| Detection/re-identification | Off; no model weights needed for this profile |
| Recording | JSONL plus selected scene PNGs; four waiting jobs and one active write |
| Demo duration | 180 seconds of server run time, plus startup/shutdown |

Image-backed evidence is intentional for this acceptance run. A JSON-only run
is a different workload and must not silently replace it in an AP comparison.
No new dependencies or hardware settings are introduced.

### Pi terminal

Stop any old preview with Ctrl+C. Verify the selected camera path using the
existing inventory; `/dev/video0` below is the previously used path, not a rule.
Remove the lens cap. Keep the head still during startup bias collection.

```bash
cd ~/projects/edgexr
git pull --ff-only
git rev-parse HEAD
v4l2-ctl --list-devices
PYTHONPATH=src python3 -m app.live_preview \
  --device /dev/video0 --port 8765 \
  --imu --imu-sleep-ms 10 \
  --camera-axis-basis configs/camera_axes_neutral.json \
  --relative-orientation --scene-memory \
  --scene-output recordings/spatial-v1-acceptance-01 \
  --scene-save-images --scene-seconds 180
```

The directory must be new. On a retry use `spatial-v1-acceptance-02` everywhere;
never delete or overwrite an earlier trial. Use the same already-working Pi
Python environment. If startup fails, retain the error; do not install packages
or rerun with elevated privileges as an unexplained workaround.

### Mac terminal: view the preview

Reuse an existing working tunnel, or start this and leave it running:

```bash
ssh -N -o ExitOnForwardFailure=yes \
  -L 127.0.0.1:8766:127.0.0.1:8765 pi@ai-fusion.local
```

In another Mac terminal:

```bash
open http://127.0.0.1:8766
```

Reload after restarting the Pi app. A port conflict means a local listener
already exists; reuse the correct tunnel or choose a different unused local
port and open that port. Do not stop an unidentified process.

## 2. Short repeatable demonstration

Use the previously proven safe view-changing method with the base fixed. This
launch does not command motors; do not force powered servo gears. Keep lighting
stable and avoid moving people dominating the views. Timing is approximate:
the sequence and holding each view matter more than exact seconds.

1. **0–20 s:** Wait for camera and orientation ready. At textured center, click
   **Remember current view** once. Wait for successful View-1 enrollment.
2. **20–50 s:** Aim left and enroll View-2, then right and enroll View-3. Hold
   until each succeeds. Pick distinct views, not three nearly identical crops.
3. **50–100 s:** Without clicking Remember, revisit center → left → right →
   center. Hold each roughly 8–10 seconds. Record the actual recognized labels.
4. **100–125 s:** Show a clearly different unenrolled view; note its outcome.
   Overlap can legitimately match a saved view. If necessary use a texture-poor
   wall to exercise visual unknown, recording that this was a low-texture case.
5. **125–150 s:** Return to center; expect View-1 again. Inspect three map nodes,
   recognition counts and directed links. Saved-left/right directions should
   have sensible signs; do not require separation exactly zero.
6. **150–180 s:** Hold center and let the timer stop. Allow up to five seconds
   for the recording queue to drain. Note errors or partial recording.

No deliberate cable disconnection, sensor interruption or storage blockage is
needed. Existing hardware-free tests exercise those failure policies safely.

## 3. Timestamp, unknown and stale contracts

| Situation | Contract and source |
| --- | --- |
| Fresh visual query fails verification or has competing candidates | Explicit unknown; do not force the nearest label (`scene_memory.py`) |
| Source frame older than 0.5 s | Scene worker skips it; no stale frame inference (`live_scene.py`) |
| Scene result older than 2 s or camera analysis not live | Scene status stale; retain last result diagnostically, do not show old bearings as current |
| Frame orientation association | Latest preceding IMU snapshot within 200 ms, at most 256 historical snapshots; no future sample (`imu/live_reader.py`) |
| Missing/invalid orientation or reference epoch mismatch | Angular context unknown; visual recognition may still succeed (`view_map.py`) |
| Non-increasing IMU time or gap over 200 ms | Integration becomes unknown until a new still-calibrated run (`live_orientation.py`) |
| Browser loses connection | Do not interpret last displayed values as fresh; reconnect/reload and check live status |

Frame receipt, IMU read midpoint and recording times use host clocks. They are
not exposure synchronization. The saved enrollment orientation is immutable;
recognition does not reset it or correct drift. A link counts observed changes
between labels, including intervening unknown counts; it is not a travel path.

## 4. Bounded background recording and evidence

Scene recognition publishes live results independently of disk writing. A full
queue drops **new query records**, with counters, not camera acquisition.
Enrollment waits for admission so its reference evidence is not silently lost.
Writer errors are separate from scene status. A shutdown timeout or missing
final record means incomplete evidence, even if the screen looked healthy.

After the app exits, on the Pi:

```bash
cat recordings/spatial-v1-acceptance-01/metadata.json
cat recordings/spatial-v1-acceptance-01/timing-final.json
```

`metadata.json` identifies Git/runtime/settings; `updates.jsonl` contains scene
decisions, timestamped orientation contexts, view-map snapshots and timing.
Selected 640×360 PNGs provide image evidence, not continuous video.
`timing-final.json` contains final recording counters and errors.

On the Mac:

```bash
scp -r pi@ai-fusion.local:/home/pi/projects/edgexr/recordings/spatial-v1-acceptance-01 \
  /Users/ryanchoi/Desktop/
```

Keep private images and large logs out of Git. Commit only a small reviewed
result summary. Complete evidence requires recording status `complete`, zero
drops, zero accepted-not-written records and no writer/scene error. `partial`
is honest degraded recording, not a fully accepted evidence run. An explicit
error is correct failure reporting, not successful recording.

## 5. Acceptance checklist and current evidence

| Requirement | Existing evidence | Packaged-run check |
| --- | --- | --- |
| Reproducible configuration | Command above; metadata captures commit/settings | Confirm requested profile, actual camera mode and clean checkout |
| Three references and recognition | [Three-view trial](LIVE_SCENE_THREE_RESULTS.md), user map confirmation | Three enrollments; both center revisits and left/right revisits recognized during holds |
| Timestamped relative orientation | [Direction check](DIRECTION_CONSISTENCY_RESULTS.md); bounded, not angle ground truth | Ready context with timestamps; no unexplained continuity loss |
| Map and unknown handling | [View-map review](VIEW_MAP_RESULTS.md); freshness/epoch unit tests | Three nodes; counts/links advance; visual unknown then known return; no false position claim |
| Bounded recording | [Writer evidence](LIVE_SCHEDULING_RESULTS.md); queue/error/timeout unit tests | Final complete recording, zero drops/pending/errors, PNGs referenced by rows exist |
| Usable demonstration | Prior component demonstrations | Preview remains usable; actual sequence and exceptions recorded |

Freshness/fault contracts are covered by `test_live_scene.py`,
`test_live_orientation.py`, `test_view_map.py` and `test_scene_recorder.py` under
`tests/unit/`. A healthy live demo alone cannot prove those failure cases.
On 2026-11-05 all 191 unit tests passed on the Mac with OpenCV 4.11.0;
this is correctness evidence, not Pi performance or packaged live acceptance.
Do not adjust thresholds to make this acceptance run pass. Diagnose a failure
first; repeat only the affected check if justified. No general recognition
accuracy, exact-angle accuracy or frame-rate guarantee follows from this demo.

Copy this result template into the eventual small result summary:

```text
Profile: spatial-v1-evidence
Git commit / dirty status:
Pi / OS / Python / OpenCV:
Requested and negotiated camera mode:
Scene, lighting, base/mount unchanged:
Power / cooling (unknown if not recorded):
Actual view sequence and approximate times:
Enrollment and revisit outcomes:
Unknown case and recovery:
Orientation continuity / direction observations:
Map node/link/count behavior:
Final recording status / accepted / written / dropped / pending / error:
Unexpected behavior:
Verdict: accepted within stated scope / needs investigation
AP CPU/RSS/thermal/power baseline: not measured in this acceptance run
```

## 6. What follows acceptance

Freeze the accepted source revision and feature profile. Then define a sustained
AP baseline for this exact spatial workload, rather than reusing the older
detector baseline. Keep two distinct records:

- **Computer systems:** scheduling, bounded state/queues, synchronization,
  freshness, failure handling and graceful shutdown.
- **Application processor:** total/per-process CPU, RSS, memory traffic,
  rates/latency, skipped work, temperature and throttling; power only if measured.

No performance improvement is claimed by this packaging step. No persistence,
SLAM, re-identification tuning or new learning website is required to close v1.
Source overview: [pipeline](PIPELINE.md), [scene source guide](learning/SCENE_MEMORY.md),
[walkthrough](learning/program-flow-explorer.html).
