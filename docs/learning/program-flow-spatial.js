/* Spatial additions to the existing expandable learning graph, reviewed 2026-11-04.
 * These contracts describe runtime code; the page never connects to hardware.
 */
(() => {
  'use strict';
  const nodes = window.EDGEXR_FLOW;
  /** Register a spatial milestone in the shared graph.
   * @param {string} id Node key. @param {string} title Display title.
   * @param {string} badge Compact constraint. @param {string} input Source data.
   * @param {string} output Result data. @param {string} explanation Operation.
   * @param {string} policy Limits. @param {string} source Repository source path.
   * @param {string} symbol Source function. @param {string[]} children Deeper nodes.
   * @param {string} visual Illustration key. @returns {void}
   */
  function add(id,title,badge,input,output,explanation,policy,source,symbol,children=[],visual='') {
    nodes[id]={id,title,badge,input,output,explanation,policy,source,symbol,children,visual,lane:'imu'};
  }
  nodes.root.children.splice(4,0,'scene');
  nodes.root.policy='Optional --detect, --imu, --relative-orientation and --scene-memory branches are shown together; they need not all run. Offline teaching page, not a sensor connection.';
  nodes.root.output='Mac image, motion, boxes/IDs, relative orientation, recognized views, session map and independent status/ages';
  nodes.capture.output='Latest 320×180 motion slot and shared full-resolution input for enabled detector/scene consumers';
  nodes.decode.output='1280×720 gray when detection OR scene memory is enabled; otherwise 320×180 gray';
  nodes.decode.policy='FFmpeg scales before the pipe only when neither full-resolution consumer is enabled.';
  nodes.resize.policy='With neither detection nor scene memory, FFmpeg already outputs small pixels. Scene ORB uses 640×360; detector uses its separate 300×300 tensor.';
  nodes.slots.output='Latest motion, detection and scene inputs with shared sequence/time; scene input also carries preceding orientation context';
  nodes.slots.explanation='State.publish_frame replaces waiting slots. Scene capture attaches a preceding valid orientation from bounded IMU history; each worker independently selects its newest input.';
  nodes.imu.badge='Read + configurable pause';
  nodes.imu.output='Corrected angular rates; optional camera-axis rates, quaternion and bounded timestamp history';
  nodes.imu.policy='50 ms default pause; recent spatial trials use 10 ms. Actual rate includes read/scheduling time. Optional integration is gyro-only, not visual fusion or position.';
  nodes.imu.children=['readImu','bias','axes','orientation','imuPublish','association'];
  nodes.readImu.explanation='Timestamp the host read midpoint, then wait the configured pause (50 ms default; 10 ms used in recent spatial trials). Achieved rate includes I2C and scheduling overhead.';
  nodes.resultStores.input='State + DetectionState + LiveImu + LiveScene';
  nodes.resultStores.explanation='Separate stores own motion, detections, gyro/orientation and scene/map results. Locks protect local updates, not a globally synchronized sensor bundle.';
  nodes.imuPublish.output='Latest rate/orientation status, ages and bounded orientation history; unknown on invalid continuity';
  nodes.snapshot.input='Independent motion, detection, IMU and scene/map result stores';
  nodes.browser.output='Existing image/metrics plus a prominent Session View Map, enrollment button and recorder health';
  nodes.support.children.push('sceneRecorder','directionCheck');
  add('axes','Camera-axis conversion','One conversion/sample','Bias-corrected IMU angular rate + fitted orthonormal basis','Camera X/Y/Z rates in degrees/s',
    'Take three dot products: camera_rate[i] = dot(camera_axis[i], imu_rate). This changes coordinates, not the physical motion.',
    'Camera X right, Y down, Z forward. Neutral-head fit has independent tilt-direction evidence, not measured shaft-angle accuracy. About 28 µs/call in isolated Pi trials; live A/B showed no clear throughput penalty.',
    'spatial/camera_axes.py','camera_components()',[],'axisMath');
  add('orientation','Integrate orientation','Optional gyro quaternion','Adjacent corrected camera-axis rates + host midpoint dt','Unit quaternion mapping camera axes into startup reference',
    'Average adjacent rates, multiply by dt to form an incremental rotation, compose with the previous quaternion and normalize. w is cos(angle/2), not time or speed; xyz = axis × sin(angle/2).',
    'No accelerometer/vision drift correction. Non-increasing timestamps or >200 ms gaps invalidate continuity; stale samples are not silently integrated. This is rotation, not XYZ position.',
    'spatial/live_orientation.py','LiveOrientation.add()',[],'quaternionMath');
  add('association','Attach timed context','256-sample history','Frame host receipt + preceding orientation history','Ready context within 200 ms, or unknown',
    'Choose a preceding orientation from a bounded history. Recognition can continue if orientation is unknown; it must not invent a current angle.',
    'Host receipt/read midpoint is not camera exposure synchronization. A shared JSON response does not make different workers simultaneous.',
    'imu/live_reader.py','LiveImu.orientation_at()',[],'contextMath');
  add('scene','Scene memory + map','Optional · target 1 Hz','Newest full gray frame + timestamped orientation + explicit Remember request','Known/enrolled/unknown scene, bounded map, optional queued evidence',
    'Separate scene worker, independent of object detection. ORB compares scene structure; it does not assign person IDs. Open this node to follow the recognition and map path.',
    'At most 12 views. Newest input only, source age ≤0.5 s; scene result becomes stale after 2 s. No automatic enrollment, physical position or metric distance.',
    'spatial/live_scene.py','scene_latest()',['sceneSelect','orb','geometry','sceneDecision','viewMap','sceneOutput'],'sceneFlow');
  add('sceneSelect','Select + resize','1280×720 → 640×360','Latest scene slot; optional user enrollment request','Canonical gray image and original host-time context',
    'The worker processes at target 1 Hz rather than every camera frame. A full recording queue defers enrollment so its reference evidence is not dropped.',
    'Image downsampling and source-time association are separate operations. Selecting a new image does not create a new physical location.',
    'spatial/live_scene.py','scene_latest()',[],'sceneFlow');
  add('orb','Describe image points','≤600 ORB features','640×360 grayscale image','Keypoint coordinates and binary descriptors',
    'ORB finds distinctive local patterns and encodes brightness comparisons into binary descriptors. Hamming distance counts differing bits; no neural model is used.',
    'Blank walls, repeated patterns, blur or foreground motion may provide insufficient or misleading features. Descriptors are not 3D coordinates.',
    'spatial/scene_memory.py','SceneMemory.process()',[],'orbMath');
  add('geometry','Verify overlap','Descriptor + geometry gates','Reference/query ORB matches','Geometrically supported candidate or rejection',
    'Keep mutual nearest matches with ratio <0.75 and Hamming ≤64. Require ≥24 matches; RANSAC homography tests consistent image geometry, ≥20 inliers and ≥0.55 inlier ratio.',
    'Support must cover ≥0.12 of each image and ≥4 cells; footprint ratio 0.25–4. Homography overlap is not identical camera pose. No calibrated rotation is extracted.',
    'spatial/scene_memory.py','verify_view()',[],'geometryMath');
  add('sceneDecision','Choose or abstain','12-view LRU bound','Verified candidates or explicit enrollment','known / unknown / enrolled + scene ID',
    'Explicit Remember creates a bounded reference. Ambiguous or unsupported candidates return unknown. Least-recently-used eviction bounds memory.',
    'Overlapping references can compete; label transitions can flicker. Unknown is a valid result, not a fabricated pose. All memory resets at restart.',
    'spatial/scene_memory.py','SceneMemory.process()',[],'sceneFlow');
  add('viewMap','Session View Map','Directions, not positions','Scene decision + valid same-epoch gyro context','Nodes, directed label history, saved-ray right/up/separation',
    'Keep enrollment orientation immutable. Express each saved forward ray in the current camera frame, and count observed changes in scene labels.',
    'Turning left makes a fixed remembered direction lie right. Turning up makes it lie below. A link A→B means recognized A then B, not traveled along a physical path.',
    'spatial/view_map.py','ViewMap.update()',['bearing','links','mapLimits'],'bearingMath');
  add('bearing','Calculate saved ray','Quaternion relative rotation','q_current and q_saved with same reference epoch','Right/up angles and unsigned pointing separation',
    'q_relative = conjugate(q_current) × q_saved. Rotate forward (0,0,1) by it. right = atan2(x,z); up = atan2(−y,hypot(x,z)); separation = acos(z).',
    'All angles in degrees, unit ray required. Pure roll changes full orientation difference but not forward-ray separation. Horizontal angle is undefined for a vertical ray.',
    'spatial/view_map.py','direction_to_view()',[],'bearingMath');
  add('links','Count label changes','≤12 nodes / 132 links','Current known/enrolled ID and previous non-unknown ID','Directed counts with intervening unknown observations',
    'A→B and B→A are different connections. Repeated A→B increments the existing connection. Unknown frames do not invent nodes or erase their interval from history.',
    'No route, speed, translation or distance is measured. Evicting a scene removes its node and connected links.',
    'spatial/view_map.py','ViewMap.update()',[],'linkMath');
  add('mapLimits','Retain uncertainty','Ready ≠ accurate','Visual overlap and drifting gyro context','Independent visual and angular status',
    'The first live map recorded 180 snapshots and 3 views. Its final center match had 16.53° gyro pointing separation despite close imagery. The later short trial does not erase that evidence.',
    'Short trial: still 1.12°, pan return 0.15°, combined return 1.04°. Tilt imagery shifted about 9 pixels; exact tilt return and angular accuracy remain unvalidated. No automatic angle reset.',
    'spatial/view_map.py','orientation_context()',[],'evidenceMath');
  add('sceneOutput','Publish + enqueue','No disk wait in recognizer','Decision/map row and optional canonical pixels','LiveScene result; bounded recorder admission',
    'Submit evidence without blocking on disk, then publish the live result. The dedicated writer handles optional PNGs and JSONL. Rendering does not wait for file completion.',
    'Four waiting jobs plus one active. Full queue drops new query evidence, not live recognition; reference enrollment is deferred. Recorder failure is distinct from recognition failure.',
    'spatial/live_scene.py','scene_latest()',[],'queueMath');
  add('sceneRecorder','Bounded recorder','Optional background worker','FIFO reference/query jobs','PNG + JSONL + final counters, or explicit incomplete/error',
    'The scene worker owns recognition; the writer owns evidence I/O. FIFO keeps reference evidence before dependent queries. Shutdown requests a bounded five-second drain.',
    'Pi trial: recognition completed while a PNG write took 1.335 s; zero drops in 120 records. This demonstrates decoupling, not zero CPU/GIL/storage contention.',
    'spatial/scene_recorder.py','SceneRecorder.submit() / close()',[],'queueMath');
  add('directionCheck','Check short returns','Separate attended motor test','30 s still + ±20° pan/tilt sweeps; HTTP snapshots','Four images, commands, telemetry and local quaternion differences',
    'Reuse a saved settled checkpoint as reference. Compare local rotations rather than subtracting startup angle magnitudes. Review images before calling a change drift.',
    'One ~55 s trial, 994 ready polls, no errors. Commanded servo angles are not ground truth. No repeat series or live correction was added.',
    'spatial/servo_orientation_demo.py','checkpoint_summary()',[],'evidenceMath');
})();
