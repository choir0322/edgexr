/* A learning hierarchy, not a second implementation of the Pi runtime.
 * Each record names a source operation, its contract and deeper milestones.
 * Optional paths are explicitly labeled; timings and numerical examples are
 * not evidence that browser animation is a real hardware trace.
 */
(() => {
  'use strict';
  const nodes = {};
  /** Register one operation. All arguments are strings except children (string[]).
   * @returns {void} Stores a declarative contract used by the graph renderer.
   */
  function node(id, title, badge, input, output, explanation, policy, source, symbol, children = [], visual = '', lane = '') {
    nodes[id] = {id, title, badge, input, output, explanation, policy, source, symbol, children, visual, lane};
  }

  // Overview: physical inputs remain independent until latest-result packaging.
  node('root','The whole program','Two inputs · independent workers',
    'USB camera video + I2C IMU readings','Mac browser: image, shift arrow, boxes / IDs, gyro and timing cards',
    'The Pi continuously updates several independent results. A browser request collects the newest available values; it does not wait for a synchronized camera–IMU–detector bundle.',
    'This view assumes --detect --imu. Optional paths are identified inside their branches. The page is a teaching map, not a live camera connection.',
    'app/live_preview.py','main()',['capture','motion','detection','imu','snapshot','transport','browser','support'],'overview');
  node('capture','Camera → frames','MJPEG → gray bytes',
    'USB camera: requested 1280×720 MJPEG at 30 fps','Two latest slots: 320×180 motion bytes + 1280×720 detector bytes',
    'FFmpeg decodes the compressed stream. The capture thread assembles each complete gray frame, timestamps it and creates the small motion copy before publishing both slots.',
    '30 fps is a request, not a guarantee. This is FFmpeg, not an FPGA. The detector and motion consumers do not receive a queue of every frame.',
    'app/live_preview.py','camera_command() / start_workers()',['decode','assemble','resize','slots'],'','motion');
  node('motion','Motion analysis','Newest pair · no fixed rate',
    'Previous processed image + newest 320×180 image','Image-content dx/dy in pixels per pair, or unreliable',
    'The motion worker estimates how image patterns shifted. It does not directly estimate camera rotation in degrees. Selecting this node opens the actual layers of computation.',
    'A new sequence wakes the worker. The 0.5 s wait timeout is not a 2 Hz limit. Pair gaps above 0.5 s reset the reference.',
    'app/live_preview.py','analyze_latest()',['pair','imageShift','publishMotion'],'','motion');
  node('detection','Detect + track','Target 2 updates/s',
    'Latest full 1280×720 grayscale frame + local model files','Class, confidence, source-pixel box, session ID and source time',
    'One detector worker loads the model and tracker once. It performs inference, then ID matching, then publishes a complete result. Tracking is not another independent worker.',
    'Starts are at least 0.5 s apart to limit CPU work. Two updates/s and two OpenCV internal threads are different settings; neither reserves CPU cores.',
    'vision/live_detector.py','detect_latest()',['selectDetection','preprocess','network','parse','tracking','publishDetection'],'','detector');
  node('imu','Read IMU','Read + 50 ms wait',
    'Camera-mounted SH3001 gyro over I2C','Latest bias-corrected XYZ angular rates + achieved sample rate',
    'The IMU measures physical angular rate independently of image frames. It publishes to LiveImu, not to an individual camera frame.',
    'No live pose integration or gyro-driven identity restoration. IMU Hz is samples/s; gyro °/s is rotation rate; read milliseconds are duration, not sample rate.',
    'imu/live_reader.py','poll_imu() / LiveImu',['readImu','bias','imuPublish'],'','imu');
  node('snapshot','Latest snapshot','On browser request',
    'Latest motion image, detector result and IMU state','JSON: independently timed values, status, ages and pixels',
    'State.snapshot reads the protected result stores. One screen may show a newer image with older detection boxes and a separately timed gyro sample.',
    'The whole snapshot is not an atomic cross-sensor measurement. Motion >2 s becomes stale; boxes >1.5 s or camera not live are hidden; IMU >300 ms is stale. Source ages exclude SSH/browser delay.',
    'app/live_preview.py','State.snapshot()',['resultStores','freshness'],'snapshot','display');
  node('transport','HTTP → SSH','Pi loopback → Mac',
    'Browser GET /api/frame through SSH tunnel','HTTP JSON response containing base64 grayscale pixels and metadata',
    'The Pi HTTP server answers requests. SSH forwards a Mac local port to the Pi local port. The tunnel carries bytes; it does not run image analysis.',
    'The browser initiates each fetch. /api/telemetry omits image bytes. A local port conflict can be avoided by selecting a different Mac port without changing the Pi port.',
    'app/live_preview.py','make_handler() / make_server()',[],'transport','display');
  node('browser','Mac screen','Render → wait 200 ms',
    'HTTP snapshot with image bytes and latest available metadata','Canvas image, exaggerated shift arrow, scaled boxes / IDs and metric cards',
    'The browser draws what the Pi already computed. It neither runs MobileNet nor computes FFTs. The arrow represents image-content displacement, not a compass direction.',
    'Fetch/render then wait 200 ms means less than 5 refreshes/s with overhead. Old boxes can lag the newer displayed image. ↺ marks a tentative appearance restore, not verified identity.',
    'app/preview.html','poll() / render()',[],'browser','display');
  node('support','Supporting paths','Optional inputs / outputs',
    'CLI options, model files, host clocks and optional recorders','Configuration, diagnostics, local recordings or measurement reports',
    'These paths support the live program; they are not additional image-analysis workers. Open the separate steps to see what is optional.',
    'Live preview does not command servos. Offline replay and servo trials are separate programs. Raw recordings remain outside Git.',
    'app/live_preview.py','main()',['config','recording','profiling','lifecycle'],'','');

  // Acquisition: source sizes and ownership change at explicit boundaries.
  node('decode','Decode MJPEG','FFmpeg child process','Compressed USB MJPEG packets','1280×720 uint8 grayscale pixels when detection is on',
    'Compression reduces USB traffic. FFmpeg decodes each packet into pixels and converts its output to one gray channel. Python reads this child process’s stdout pipe.',
    'The camera is not sending an uncompressed Python array. With detection off, FFmpeg also scales to 320×180 before the pipe.',
    'app/live_preview.py','camera_command()',[],'sizes');
  node('assemble','Assemble + stamp','Complete frame only','Chunks of bytes from the FFmpeg pipe','One full frame + increasing sequence + monotonic host receipt time',
    'read_frame keeps reading until one frame is complete. Receipt time is recorded after assembly, before resize; it is not an exposure timestamp.',
    'Full source frame = 1280×720×1 = 921,600 bytes. A partial frame at EOF is an error; an empty clean EOF ends the stream.',
    'app/live_preview.py','read_frame() / capture()',[],'sizes');
  node('resize','Make motion copy','OpenCV INTER_AREA','Full 1280×720 gray image','Small 320×180 gray image; full image remains available',
    'OpenCV reduces both dimensions by four. The detector still receives the original full-size image, not the small motion copy.',
    'With detection off, pixels are already small because FFmpeg did the resize. The 300×300 model tensor is a later, separate operation.',
    'app/live_preview.py','capture() / cv.resize()',[],'resize');
  node('slots','Replace latest slots','State.publish_frame','Small bytes, full bytes, sequence and receipt time','State.latest and State.detection_frame, sharing source identity',
    'Publishing replaces waiting data and wakes consumers. A busy worker keeps its current frame; when ready, it selects the newest waiting one.',
    'Frames bypassed by detection are intentional sampling, not a detector failure. The motion skipped counter measures its own bypassed sequences. Drivers and pipes may still buffer bytes.',
    'app/live_preview.py','State.publish_frame()',[],'slots');
  node('pair','Select an image pair','Two processed sources','Previous processed frame A + latest frame B','Two float-compatible 180×320 arrays for comparison',
    'The worker may compare F1 with F3 if F2 arrived while it was busy. A single image cannot reveal temporal displacement.',
    'First frame establishes a reference. Pair gap >0.5 s yields no estimate and resets the reference. The source frame is still published.',
    'app/live_preview.py','analyze_latest()',[],'pair');
  node('imageShift','Estimate scene shift','image_shift()','Two 320×180 gray images','Robust dx/dy + agreement count + median quality, or None',
    'Nine local measurements vote on a common image translation. Agreement reduces the influence of an independently moving object or a bad patch.',
    'This assumes enough scene regions share a translation. Parallax, rotation, blur or a large moving foreground can defeat that assumption.',
    'recording/visual_motion.py','image_shift()',['patches','patchShift','consensus'],'patches','motion');
  node('patches','Sample nine regions','9 × 80×56','Same fixed positions in both 320×180 images','Nine pairs of small patches',
    'The code samples x = 5,117,229 and y = 5,62,119. These are nine regions with gaps, not a complete equal 3×3 split of the image.',
    'All nine pairs are evaluated. The highlighted patch is only the teaching example; the program does not rely on it alone.',
    'recording/visual_motion.py','PATCH_ORIGINS / image_shift()',[],'patches');
  node('patchShift','Estimate each patch','patch_shift()','Earlier/later 80×56 patches','A local signed dx/dy and quality, or rejection',
    'Follow the numerical transformations. The same operations are repeated for each patch pair; only the input pixels change.',
    'Fourier calculations come from NumPy, not MobileNet. A clear local peak is necessary but does not guarantee whole-scene agreement.',
    'recording/visual_motion.py','patch_shift()',['texture','hann','fft','cross','inverse','peak'],'pair','motion');
  node('texture','Check usable texture','stddev ≥ 3','Matching finite 2D patches, each dimension ≥16','Floating-point patches with enough variation',
    'Standard deviation measures variation around the average brightness. An almost uniform wall gives little evidence of where a pattern moved.',
    'Invalid shapes/nonfinite values raise an error. Intensity stddev below 3 rejects the patch. This is not the later peak-quality score.',
    'recording/visual_motion.py','patch_shift() input checks',[],'texture');
  node('hann','Center + Hann','Weight the whole patch','Patch A/B with their respective means','(A − mean(A)) × window, and the same for B',
    'One smooth weight map spans each entire patch. Edge weights approach zero; central weights are high. This softens the artificial discontinuity where FFT’s periodic extension joins opposite edges—not the border of every individual pixel.',
    'Subtract the mean first. Signed zero is displayed as middle gray here. Hann is not blur, cropping, object attention or a detector preprocessing step.',
    'recording/visual_motion.py','patch_shift(): np.outer(np.hanning(...))',[],'hann');
  node('fft','Transform both patches','np.fft.fft2','Two mean-centered, windowed spatial arrays','Complex frequency arrays FA and FB: magnitude + phase',
    'Each frequency describes a repeating spatial pattern. Magnitude describes its strength; phase describes its alignment. Translation changes relative phase in a structured way.',
    'FFT does not physically tile the image in memory. The periodic interpretation explains seam artifacts. Magnitude alone does not tell which way a pattern shifted.',
    'recording/visual_motion.py','patch_shift(): np.fft.fft2',[],'fft');
  node('cross','Compare relative phase','FB × conjugate(FA)','Complex spectra of the two patches','Normalized cross-power spectrum',
    'Conjugation reverses A’s phase. Multiplication adds B’s phase to that reversed phase: a phase difference. Dividing by magnitude makes phase alignment dominate rather than strong brightness components.',
    'C = FB × conj(FA); R = C / max(|C|, 10⁻⁹). The floor prevents division by zero. This is not subtraction of two spectrum images.',
    'recording/visual_motion.py','patch_shift(): cross / magnitude',[],'cross');
  node('inverse','Find displacement peak','np.fft.ifft2','Normalized cross-power spectrum R','Real correlation surface with a score at every candidate shift',
    'Inverse FFT combines the relative phases. At the displacement that aligns the patterns, frequency contributions reinforce one another and create a peak.',
    'The output is not a reconstructed camera image because its input is a cross-spectrum, not one original image spectrum. Axis positions mean candidate displacements.',
    'recording/visual_motion.py','patch_shift(): ifft2 / argmax',[],'inverse');
  node('peak','Validate + refine peak','Quality ≥8','Correlation surface + strongest integer cell','Subpixel signed shift, or rejection',
    'Exclude the wrapped 5×5 peak neighborhood from background statistics. Compare peak prominence with background variation, fit neighboring scores, then unwrap periodic indices.',
    'Reject quality <8 or |dx|>20 or |dy|>14 for an 80×56 patch. Quality is not probability. Positive dx is image content moving right; positive dy means down.',
    'recording/visual_motion.py','patch_shift() / refine()',['quality','refine'],'inverse');
  node('quality','Measure peak quality','Peak-to-background ratio','Peak + surface excluding wrapped 5×5 neighborhood','Q = (peak − background mean) / max(background std, 10⁻⁹)',
    'A sharp peak is useful only relative to other candidate scores. Excluding 25 neighboring cells avoids treating the main peak’s own shoulders as competing evidence.',
    'The exclusion wraps across array edges. The sample’s 80×56 surface has 4,480 cells; 4,455 remain as background.',
    'recording/visual_motion.py','patch_shift(): mask / side / quality',[],'quality');
  node('refine','Refine below one pixel','Three-point parabola','Left, center and right scores through the peak','Signed integer shift + fractional offset clipped to ±0.5',
    'The best integer cell need not be the true peak center. A local parabolic fit estimates a fractional location along each axis.',
    'δ = 0.5(L−R)/(L−2C+R); nearly zero denominator gives δ=0. For length 80, index 76 unwraps to −4 before adding the fraction.',
    'recording/visual_motion.py','patch_shift.refine()',[],'refine');
  node('consensus','Combine agreement','At least four votes','Valid patch shifts and their quality values','Median shift of patches within 1.5 px of the initial median',
    'First require four valid patches. Calculate the componentwise median, then each vector’s Euclidean distance to it. Require four close votes and take their median again.',
    'A strong single-patch result cannot bypass scene consensus. If too few agree, return None rather than inventing a zero shift.',
    'recording/visual_motion.py','image_shift(): median / norm / good',[],'consensus');
  node('publishMotion','Publish image + shift','State.publish_result','Source frame, pair result and estimator duration','Latest analyzed image, reliable/unreliable status, timing and skip count',
    'The processed image and its motion result are stored together. The browser may display this image even if the shift is unreliable, but it should not draw a reliable arrow.',
    'Optional motion-aware tracking also retains up to 180 timestamped pair records. Unknown or >0.12 s history gaps are not zero motion; this differs from the motion worker’s 0.5 s pair reset.',
    'app/live_preview.py','State.publish_result()',['history'],'publish');
  node('history','Optional motion bridge','--motion-aware-tracking','Reliable analyzed-pair history over the old→new detector interval','Accumulated image displacement ×4 → predicted old box',
    'Require continuous interval coverage and prorate partial endpoint pairs. Scaling by four converts 320×180 shift pixels to the 1280×720 detector coordinate system.',
    'Compare raw and translated old boxes, using the stronger eligible IoU. Missing/implausible history falls back to raw IoU. IMU does not supply this correction.',
    'vision/live_detector.py','source_shift() / State.motion_between()',[],'history');

  // Detection and memory: math gates are distinct despite similar numbers.
  node('selectDetection','Select newest input','≥0.5 s between starts','Latest full frame with a new source sequence','One selected inference input, never a catch-up backlog',
    'The worker waits until due, then takes the newest available frame. Inference can overlap capture, motion and IMU work.',
    'Input older than 1.5 s is skipped. Slow inference lowers achieved Hz. Zero boxes is a valid completed result.',
    'vision/live_detector.py','detect_latest()',[],'slots');
  node('preprocess','Prepare model input','300×300×3','1280×720 gray source image','Blob shaped 1×3×300×300 with normalized float values',
    'Three identical grayscale channels satisfy the model’s three-channel input contract; they do not restore lost color. Resize to 300×300, then transform intensity values.',
    'Value = (pixel −127.5)×0.007843, approximately −1…+1, not just three discrete values. The separate motion image remains 320×180.',
    'vision/detect_image.py','infer_once()',[],'normalize');
  node('network','MobileNet → SSD','Features → boxes','Three-channel normalized model input','Predicted class scores and decoded object boxes',
    'MobileNet extracts learned feature maps. SSD uses maps at several scales to predict object classes and box adjustments in one network pass.',
    'CPU OpenCV DNN, two internal threads. Model graph and pretrained weights are local files; this page does not run inference or train a model.',
    'vision/detect_image.py','infer_once(): net.forward()',['features','ssd'],'network');
  node('features','Extract learned features','MobileNet backbone','RGB-compatible tensor (identical channels here)','Feature maps: spatial grids of learned responses',
    'After the first standard convolution, MobileNet uses depthwise spatial filtering followed by pointwise channel mixing. Deeper channels are learned features, not additional camera colors.',
    'Depthwise/pointwise stages are inside the model, not Python worker threads. See the linked lesson for exact model dimensions and sliding-filter visuals.',
    'vision/detect_image.py','infer_once() / local deploy.prototxt',[],'convolution');
  node('ssd','Predict object boxes','Single-shot detection','Feature maps at multiple resolutions','Class scores + adjusted default boxes, then filtered detections',
    'At each feature-map position, default boxes supply reference sizes/aspect ratios. Learned offsets adjust them; class scores identify candidates. Suppression removes highly overlapping duplicates.',
    'Default boxes are references, not hard crops that independently classify pixels. Two-stage proposal-based detectors instead select regions then classify/refine them. Efficiency on this Pi must be benchmarked, not assumed from the name.',
    'vision/detect_image.py','infer_once(): network DetectionOutput',[],'ssd');
  node('parse','Parse detections','Live confidence ≥0.30','Network class, confidence and normalized box coordinates','Clipped positive-area boxes in 1280×720 source pixels',
    'Multiply normalized x coordinates by source width and y coordinates by source height. Keep supported labels and scores meeting the live cutoff.',
    'xyxy = left, top, right, bottom. 0.30 detection confidence is not 0.30 IoU. Lowering confidence admits more candidate detections, including possible false positives.',
    'vision/detect_image.py','parse_detections()',[],'boxes');
  node('tracking','Assign session IDs','BasicTracker.update','Current boxes + previous active tracks','Current detections with one-to-one track IDs',
    'Matching uses same-class overlap first. Unmatched tracks age; unmatched detections receive a fresh ID unless optional appearance memory restores one.',
    'The tracker sees completed detector updates, not every camera frame. IDs are shared across classes, grow monotonically and are not verified physical identities.',
    'vision/basic_tracker.py','BasicTracker.update()',['iou','claim','age','memory'],'boxes');
  node('iou','Compare box overlap','IoU ≥0.30','Previous/current same-class source-pixel xyxy boxes','Intersection area ÷ union area',
    'Overlap is an inexpensive continuity clue. The same person can fail it after a large displacement or a sharply changed detector box.',
    'Intersection width=max(0,min(rights)−max(lefts)); similarly height. Union=areaA+areaB−intersection. Optional motion history translates the old box before comparison.',
    'vision/basic_tracker.py','box_iou()',[],'iou');
  node('claim','Claim one-to-one','Highest eligible overlap first','Ranked same-class matching candidates','At most one detection per old ID and one old ID per detection',
    'Once an old track or new detection is claimed, other candidates using it cannot inherit that match. This prevents two visible objects receiving one old ID.',
    'Greedy overlap matching is not proof of identity. Similar neighboring objects can still be confused.',
    'vision/basic_tracker.py','BasicTracker.update(): candidate assignments',[],'claim');
  node('age','Age missing tracks','Detector updates, not frames','Old IDs without a current match','Hidden after one miss; retired after two consecutive misses',
    'One missed detector result is tolerated internally. The missing box is not displayed. A second consecutive miss removes the active track.',
    'Without appearance memory, a retired ID is not reused. A new detection gets the next global ID; camera frames intentionally skipped by detection do not count as misses.',
    'vision/basic_tracker.py','BasicTracker.update(): retirement',[],'age');
  node('memory','Optional appearance memory','--reidentify','Unmatched detection + retired same-class appearances','Tentative old ID (↺), or a fresh ID',
    'Describe each suitable crop by an 8×8 brightness grid, subtract its mean and normalize its vector length. Compare unit vectors with a dot product: cosine similarity.',
    'Current policy: up to 32 retired IDs; ≤10 s since last sighting; score ≥0.85 and margin ≥0.05 over runner-up. Multiple unmatched same-class returns abstain. Current code keeps one latest template, not the proposed gallery. IMU does not gate this decision.',
    'vision/object_memory.py','grayscale_grid_descriptor() / take_match()',[],'cosine');
  node('publishDetection','Publish boxes + IDs','DetectionState.publish','Completed detector result with original source receipt time','One latest detector result, compute time and tracking diagnostics',
    'The source identity survives inference and matching. Compute time measures inference, whereas box source age includes time since capture receipt.',
    'Snapshot may hide stale boxes. A fresh motion image does not make an old detector result fresh.',
    'vision/live_detector.py','DetectionState.publish() / snapshot()',[],'ageMath');

  // Independent sensor and transport math, often hidden by image-only lessons.
  node('readImu','Read + timestamp','I2C host observation','Driver read start/end times + raw gyro XYZ','Sample time = (start+end)/2; raw rate in °/s',
    'Midpoint timing approximates when the host read happened. The worker sleeps 50 ms after the read, so its achieved frequency includes read and scheduling costs.',
    'Acceleration and temperature from the combined read are not used by this live gyro display. Midpoint is not a sensor exposure timestamp.',
    'imu/live_reader.py','poll_imu()',[],'imuTime');
  node('bias','Remove stationary offset','First ~1 s must be still','At least 10 stationary gyro readings','Per-axis offset mean; corrected = raw − offset',
    'A stationary gyro can report a nonzero rate. Estimate that offset at startup and subtract it independently on X, Y and Z.',
    'Reject startup if per-axis standard deviation exceeds 0.5 °/s; restart while still. This is per-run correction, not saved calibration or an orientation estimate.',
    'imu/live_reader.py','stationary_offset() / LiveImu.publish()',[],'bias');
  node('imuPublish','Publish latest gyro','LiveImu snapshot','Latest raw sample, offset and recent timestamps','Corrected XYZ °/s, sample rate Hz, age and status',
    'Achieved rate uses (number of samples−1)/(last time−first time), within the recent history. It is not the inverse of the sensor read duration alone.',
    'No samples after 2 s is stale; a latest sample older than 300 ms is stale. Failed/calibrating/stale rates are unavailable, not zero.',
    'imu/live_reader.py','LiveImu.snapshot()',[],'rate');
  node('resultStores','Read separate stores','Locks protect updates','State + DetectionState + LiveImu','Latest independently timed records',
    'Each publisher owns its result type: publish_result for motion, DetectionState.publish for detections, and LiveImu.publish for raw samples/baseline state.',
    'Different publish names reflect different objects and responsibilities. They are not stages that mutate one universal frame object.',
    'app/live_preview.py','State.snapshot()',[],'snapshot');
  node('freshness','Check age / status','now − source time','Host monotonic timestamps and error state','Ready values or explicit stale/error/off status',
    'Age answers how old the source is now, not how long inference took. All live ages use the Pi host clock before network transport.',
    'Do not compare a camera PTS with a host monotonic timestamp without alignment. Current snapshots are approximate observations, not synchronized sensor fusion.',
    'app/live_preview.py','State.snapshot()',[],'ageMath');
  node('config','Load configuration','Options + model files','CLI flags, graph architecture and pretrained parameters','Requested camera mode and enabled workers',
    'Model files are loaded once. --detect and --imu select independent features. --demo replaces the camera source, not a simulated IMU.',
    'No GPU/NPU is configured in this baseline. CPU work competes with motion, capture and other processes.',
    'app/live_preview.py','main()',[],'config');
  node('recording','Optional trial output','--trial-output','Same camera input + selected detector frames/results','camera.mkv, exact selected PNGs, JSONL and metadata',
    'A second FFmpeg output packet-copies incoming MJPEG, while detector updates save their exact selected gray inputs and decisions. The camera is not opened a second time.',
    'Recording is disabled by default and changes workload. Saved footage is private and ignored by Git. Offline analysis is a separate command, not a live worker.',
    'app/live_preview.py','camera_command() / detect_latest(recorder=...)',[],'recording');
  node('profiling','Optional AP metrics','Separate collector process','Metrics-only HTTP + Pi /proc and thermal readings','CPU/RSS/temperature/rates summaries',
    'The AP collector polls observations. It does not change worker schedules or measure electrical power or exposure-to-display latency.',
    'Process CPU uses one logical core=100%; all-core busy uses total machine capacity=100%. Polling can miss detector updates.',
    'profiling/ap_baseline.py','main()',[],'profiling');
  node('lifecycle','Errors + shutdown','Control, not pixel data','FFmpeg stderr, worker errors, Ctrl+C','Status messages and orderly stop of threads/child process',
    'A diagnostic thread drains FFmpeg stderr. A shared stop event requests shutdown; status errors are not interpreted as valid zero-valued measurements.',
    'Servo commissioning and offline gyro/visual comparisons are distinct entry points. This explorer never issues a hardware command.',
    'app/live_preview.py','start_workers() / stop_workers()',[],'lifecycle');
  window.EDGEXR_FLOW = nodes;
})();
