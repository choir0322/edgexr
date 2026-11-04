# Scene memory: current source map

AP diagnostic: [stall profiler](../SPATIAL_STALL_PROFILING.md) correlates
`scene-worker`/`scene-recorder` native TIDs with kernel task counters. Their
recognition/recording policies are unchanged. HTTP telemetry adds Python thread
name/native-ID pairs, and the external observer samples procfs; this is sampled
accounting, not a full scheduler trace or automatic stall diagnosis.

The [v1 application guide](../SPATIAL_APPLICATION_V1.md) defines the exact live
profile, unknown/stale contracts and acceptance procedure. Source map reviewed
2026-11-05; functions, units and data flow unchanged. No new learning UI added.

Display review (2026-11-04): `preview.html` renders the scene/map/enrollment panel
before the camera and metric cards. `render` uses the unchanged map snapshot;
stale/disconnected scene state hides current bearings. `make_handler` loads HTML
at startup, so restart the Pi preview after pulling UI updates. Data-flow diagram
reviewed; no inference, orientation or recorder change. See
[image/orientation evidence](../VIEW_MAP_RESULTS.md) before interpreting angles.

This concise map records the new offline path; a detailed learning page is
deferred until the application and AP phases are complete. Follow the
[run guide](../SCENE_MEMORY.md) for commands and numeric rules.

1. `spatial.scene_revisit.parse_events` combines labelled reference times and
   query times into one sorted list. Each event has a requested video time;
   future references are not visible to earlier queries.
2. `scene_revisit.run` decodes the existing video sequentially with OpenCV and
   chooses the first frame at/after each event. It converts BGR to grayscale.
   The video clock is not a camera/IMU exposure clock.
3. `SceneMemory.process` validates a strictly increasing video time and sends
   the grayscale image to `prepare_gray` (640×360), then ORB's
   `detectAndCompute`. ORB supplies keypoint XY coordinates and 32-byte binary
   descriptions of local image patterns. There is no detector object label.
4. Explicit enrollment stores a `View` containing scene ID, label, observation
   time, recency, coordinates and descriptors. Capacity is bounded; no full
   image remains inside `SceneMemory`. An unknown query never writes a new view.
5. Query comparisons call `verify_view` against each stored view. Hamming
   descriptor matches are filtered for ambiguity and one-to-one correspondence.
   RANSAC checks whether a consistent homography supports enough matches.
   `spatial_support` checks coverage in both images; footprint checks reject
   extreme or folded transforms. This validates image agreement, not pose.
6. `process` selects a clearly stronger verified candidate or reports unknown.
   A known view refreshes recency; an ambiguous observation refreshes neither.
   The decision contains reasons and candidate counts, not a calibrated score.
7. `run` stores decisions and selected PNGs in a new ignored output folder,
   retaining actual/requested video times, thresholds and runtime provenance.
   This offline route remains independent of the live route below.

## Live source route

`spatial.view_map.ViewMap.update` now consumes each scene decision and its
associated orientation. It never changes the visual decision. Enrollment saves
the orientation once; later queries update observation counts, not the saved
orientation. It mirrors LRU eviction and records directed changes between known
labels, with intervening unknown counts. `orientation_context` validates finite
near-unit quaternions, preceding samples within 200 ms and the reference epoch.
`direction_to_view` computes `inverse(q_current) * q_enrolled`, then rotates the
saved forward `(0,0,1)` ray into current camera axes. It derives right/up angles
from that ray; absolute scalar quaternion component gives the shortest full
rotation difference, including roll. q and -q represent the same rotation.
There is no positional component. Map snapshots are copied into live/recorded
rows, independently of recording queue ownership. See [scope/protocol](../VIEW_MAP.md).

`State.publish_frame` in `app/live_preview.py` retains full gray bytes, frame
sequence, host receipt time and `LiveImu.orientation_at` context in one latest
slot. The IMU helper searches a bounded history for a preceding sample within
200 ms; it never guesses exposure pose. `spatial.live_scene.scene_latest`
owns `SceneMemory`, targets 1 Hz and invokes the same `process` rules as replay.
`LiveScene.enroll` queues at most one browser request; `take_request` consumes
it only on a newer frame. References retain their enrollment orientation.
`LiveScene.snapshot` independently ages the result. `State.snapshot` includes
it under `scene` for the browser and telemetry endpoint. Optional JSONL stores
accepted recording jobs; no visual result changes IMU integration or corrects drift.
Opt-in timed `--scene-save-images` diagnostics save the selected canonical image
and reference-image links with each row, enabling inspection of unknown decisions.
`poll_imu` brackets driver reads and publication; `LiveImu.record_poll_timing`
keeps cumulative maxima and 64 slow events. `scene_latest` snapshots these
without changing orientation validity, alongside its CPU/wall and image/log
write intervals. See [timing protocol](../LIVE_SCHEDULING_DIAGNOSTICS.md).
See [live commands and limits](../LIVE_SCENE_MEMORY.md).

### Bounded recorder (timing schema 2)

`spatial.scene_recorder.SceneRecorder.submit` copies a result dictionary and
retains immutable source bytes for opt-in images. It does not wait for a file
write. `SceneRecorder._run` owns the file stream; `_write` resizes/encodes the
selected source and flushes JSON in FIFO order. Four waiting jobs plus one active
write bound retained image payloads; query recording can drop without dropping
the live scene result. `can_enroll` is checked before `take_request`, so a full
queue leaves an explicit enrollment pending rather than discarding its evidence.
There is one producer, and the consumer only removes jobs. References therefore
enter the queue before queries that link to them. This protects against queue
overflow, not disk failure or process termination.

`LiveScene.snapshot` includes independent `recording` health/counters. Writer
errors stop further recording admission, not recognition. `close` requests a
FIFO drain and waits up to five seconds; timeout marks incomplete evidence.
Missing `timing-final.json` also means incomplete. The final file stores counts,
the last write interval and final producer IMU counters. Recorded rows include
queue wait and previous *recorded* JSON write, not necessarily the preceding
scene observation after a drop. IMU snapshots are now taken before enqueue,
not after PNG saving. Thread/process CPU fields still measure scene computation
only, and do not isolate recorder cost. A separate thread cannot guarantee no
CPU, GIL or storage contention; the Pi check remains required.
