# Scene memory: current source map

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
   No result is currently published to the browser or used by the live IMU.

The next implementation will attach valid relative-direction context and a
bounded live observation policy. Those paths are not present in this version.
