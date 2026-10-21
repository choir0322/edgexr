# EdgeXR whole-program flow explorer

## Purpose / big picture

Create one local learning HTML entry point that explains the running EdgeXR
program from camera and IMU inputs to the Mac browser. The first view is a
minimal graphical program map, not a wall of descriptions or four embedded
websites. Selecting a processing node expands its internal flow; selecting a
mathematical concept opens a focused visual explanation while preserving the
reader's place. Detail is available on demand without requiring source reading.

The user reviewed this design and approved implementation. The entry point is
`docs/learning/program-flow-explorer.html`. It runs offline using local assets;
there is no hosting, account or hardware control.

## Context and orientation

Source reviewed on 2026-10-21 after commit `8ff2945`:

- `docs/learning/edgexr-worker-rates.html`: overview graph, independent clocks,
  latest-frame slots, static/dynamic views and snapshot packaging.
- `docs/learning/basic-tracker.html` and its JS: minimal dark graph, a detector
  worker with an expanded ID-matching branch and per-node details.
- `docs/learning/detection-architecture.html` and its JS/CSS: standard versus
  depthwise/pointwise convolution, channels, weights/biases, SSD stages.
- `docs/learning/hann-fft-explorer.html` and its JS/CSS: real recorded Pi images,
  patch selection, Hann, spectra, correlation, refinement and consensus.
- `docs/PIPELINE.md`: current architecture and optional branches. Source code
  remains the authority when an older lesson differs.

FFmpeg is an external child process, not an FPGA or a Python reimplementation.
The camera provides compressed MJPEG; FFmpeg decodes it into grayscale pixels.
Capture, motion, detector and IMU workers are Python threads. OpenCV's internal
thread setting is a separate concept and does not reserve two CPU cores.

This program is a graph with multiple inputs, concurrent branches, state and
feedback—not a single object passing through every worker sequentially.
In particular, IMU samples never pass through the image-processing branch.

## Progress

- [x] 2026-10-21: Inspect existing page structures and current live source.
- [x] 2026-10-21: Draft architecture, learning interactions and acceptance checks.
- [x] 2026-10-21: User reviewed and approved the implementation scope.
- [x] 2026-10-21: Build the static overview and expandable motion branch.
- [x] 2026-10-21: Add detector, tracking, optional memory, IMU and browser branches.
- [x] 2026-10-21: Add deterministic execution walkthrough and concept visualizations.
- [x] 2026-10-21: Review `docs/PIPELINE.md`, update the learning index and correct the reused lesson's live confidence cutoff to 0.30.
- [x] 2026-10-22: Replace attached subgraphs with measured nodes that expand, reflow and collapse in their original graph position.
- [x] 2026-10-22: Validate offline behavior, source accuracy, keyboard controls and layout.

## Plan of work

### 1. Establish the clean overview

Use a horizontally flowing SVG graph with three visible spatial boundaries:
hardware inputs on the left, Raspberry Pi execution in the middle, Mac browser
on the right. Inside the Pi distinguish the FFmpeg child process from Python.

The camera lane begins with USB camera → FFmpeg → capture/latest slots. It
branches to motion analysis above and detection + tracking below. A separate
IMU lane runs directly from I2C reader to its latest result. All three result
branches converge at snapshot packaging → HTTP response → SSH tunnel → Mac UI.
Show the browser request as a subtle return/control arrow, not a second image
pipeline. Snapshot is requested, not a barrier that waits for all workers.

Collapsed nodes show only a short action label, a small shape/rate badge and an
expand cue. No paragraphs inside nodes. Color follows data type: image/motion,
detection/IDs, IMU, and transport; text and line styles also distinguish them.
Use the dark, restrained visual language of the tracker page, generous spacing,
and one clear reading direction. Reuse the worker-rates structure, not all its
simultaneously visible explanatory cards.

Default configuration: detection and IMU enabled, basic tracking. An optional
Modes panel reveals motion-aware tracking, appearance memory and recording.
Disabled branches remain absent or faintly marked, never animated as active.
Demonstrate detection-off resizing when that mode is selected.

Check: a reader can identify the independent inputs and explain why a detector
result need not belong to the image currently displayed.

### 2. Expand computation without losing context

Click a node to replace/expand it into a local subgraph with explicit input and
output ports. Keep the parent visible as a breadcrumb and compact context strip.
Allow one focused expansion at a time to prevent a giant unreadable graph.
Collapse restores the overview without resetting the selected frame or step.
Subgraphs return to the correct downstream node, not an invented execution loop.

Each selected node has a compact inspector with:

1. Input: where it came from, shape/type, units and source timestamp/sequence.
2. Operation: one sentence plus an actual visual transformation.
3. Output: what changes, where it is stored, and which consumer reads it.
4. Policy: eligibility, rejection, freshness, empty result or error behavior.
5. Source: repository-relative file link and exact function/class name.

Inputs and outputs should be visual chips, image thumbnails, arrays or boxes,
not just prose. Keep equations and code references behind secondary disclosure.
Hover provides a brief hint only; clicking/keyboard activation gives persistent
detail. Important information must not depend on hover.

### 3. Map each branch to the real implementation

| Branch | Expanded stages | Source anchors |
|---|---|---|
| Camera/capture | Request MJPEG → decode gray → assemble complete bytes → stamp receipt → resize when needed → replace latest slots | `app/live_preview.py`: `camera_command`, `start_workers`/`capture`, `read_frame`, `State.publish_frame` |
| Motion | Previous processed + latest image → nine sampled regions → per-patch computation → consensus → publish | `app/live_preview.py`: `analyze_latest`, `State.publish_result`; `recording/visual_motion.py`: `image_shift`, `patch_shift` |
| Detection | Select newest eligible source → gray replicated into three channels → 300×300 normalization → features → SSD boxes/scores → parse | `vision/live_detector.py`: `detect_latest`, `CpuDetector`; `vision/detect_image.py`: `infer_once`, `parse_detections` |
| Tracking | Validate boxes → same-class comparisons → IoU/ranking → one-to-one claims → age old tracks → IDs → publish | `vision/basic_tracker.py`: `BasicTracker.update`, `box_iou`; `vision/live_detector.py`: `DetectionState.publish` |
| Appearance memory, optional | Crop descriptor → retire old track → bounded memory → eligible unmatched return → score/margin → tentative restore or new ID | `vision/object_memory.py`: `grayscale_grid_descriptor`, `RetiredObjectMemory`; `BasicTracker.update` |
| IMU | Read raw sensor → midpoint timestamp → stationary startup offset → corrected gyro → publish/rate/freshness | `imu/live_reader.py`: `poll_imu`, `LiveImu` |
| Display | Independently protected latest results → freshness checks → JSON/base64 pixels → HTTP/SSH → render image/arrow/boxes/cards → wait/poll | `State.snapshot`, `make_handler`; `app/preview.html` |

The motion branch must show two images, not imply that one image determines
displacement. Nine regions are sampled patches, not a full equal 3×3 tiling.
Expose shape/finite checks, conversion, texture rejection, mean subtraction,
Hann weighting, FFTs, normalized cross-power, inverse FFT, peak quality,
subpixel refinement, signed displacement and consensus/rejection.

The detector branch must distinguish MobileNet feature extraction from SSD's
multi-scale default boxes, class/offset predictions, decoding and suppression.
Standard convolution versus depthwise/pointwise is a conceptual comparison,
not two competing runtime branches that both execute. Label illustrative
weights/biases and schematic boxes separately from actual model parameters.

Optional motion history feeds tracking, not IMU-based pose estimation. Current
appearance memory is the single-template implementation analyzed in trial 01;
the proposed gallery is future work and must not appear as implemented. Show
the observed 8→9 crop-change failure as a diagnostic explanation, not as a
claimed fixed behavior. Retained memory is not long-term verified identity.

### 4. Build focused concept views

Open a concept panel within the same page, retaining a breadcrumb such as
Program → Motion → Patch shift → Hann window. A Back action restores the graph.

- Hann: real earlier/later patch, mean-centered values, window weights and
  weighted patch; tiled-edge demonstration explains artificial seams.
- FFT: image and magnitude/phase views; displacement depends on relative phase,
  not simply subtracting brightness or spectral magnitudes.
- Inverse FFT: normalized cross-power → candidate-displacement surface → peak;
  label axes as possible dx/dy, not image positions or object locations.
- Consensus: nine vectors, rejected/accepted patches and the final shift.
- Convolution: sliding-window teaching metaphor, channel mixing, kernels,
  parameters versus repeated operations, bias, depthwise then pointwise.
- SSD: feature grids and default boxes → learned offsets/classes → selected
  detections. Explain one-stage versus proposal-based two-stage architecture
  without claiming MobileNet-SSD is universally best for the Pi.
- IoU/IDs: previous/current box overlap, competing assignments, missing tracks,
  retirement and optional appearance comparison.

Reuse existing local Pi imagery and computed Hann/FFT arrays with provenance.
Do not silently include new personal trial images in Git. Precomputed spectra
are labeled recorded calculations; illustrative timelines are labeled simulations.
No requirement to implement a browser CNN or FFT engine merely for animation.

### 5. Add a synchronized teaching simulation, not fake synchronization

Two views share the same graph: Structure (default, still) and Execution
(deterministic walkthrough). Minimal controls: Play/Pause, Next event, Reset.
No independent sliders in every branch. A small set of named scenarios covers
normal execution, motion falling behind, invalid shift, stale detector/IMU, and
an optional failed identity return.

Frames carry identifiers F1, F2, etc.; motion results carry a pair (F1→F3);
detections carry their source frame (F2); IMU samples carry independent IDs
and times (I1, I2). Latest slots visibly replace waiting frames while workers
retain their in-progress inputs. No token travels through every branch.
When the browser polls, highlight the independently aged records actually
selected for that illustrative snapshot. The display may combine motion image
F15, detections from F10 and IMU sample I9; that is explicitly not sensor fusion.

| Stage | Policy to depict |
|---|---|
| Camera | Requested 30 fps, approximately 33.3 ms between frames; not a downstream guarantee |
| Motion | Newest eligible frame when ready; no fixed 30 Hz target; skipped sequences counted separately from rejected estimates |
| Detector | Starts at least 0.5 s apart; target 2 Hz to bound expensive CPU work, not proven optimum; no backlog |
| IMU | Read then wait 50 ms; achieved rate includes read/scheduling time, independent of camera frames |
| Browser | Fetch/render then wait 200 ms; requests latest snapshot, does not display every input frame |

Show 0.30 live detection confidence separately from 0.30 IoU and 0.85 appearance
similarity. Freshness gates, motion reference reset and missing inputs are
distinct from low-confidence or low-quality rejection. Explain zero detections
as a valid detector update that still ages tracks.

### 6. Include auxiliary paths without clutter

A collapsed Supporting paths group covers model graph/weights and CLI options,
host clocks, FFmpeg stderr/error handling, shutdown, optional trial recording,
metrics-only HTTP collectors and AP profiling. Recording is a side output, not
an input to live tracking. Offline video/IMU analysis and servo experiments are
separate entry points linked from this group, not fabricated live workers.
Expand to module/function milestones rather than depicting every helper as a
top-level node. The ultimate distinction remains: current image displacement,
category detection, provisional IDs and gyro rates versus future calibrated
pose, persistent identity and spatial mapping.

## Concrete steps

1. Review this document with the user; do not modify existing learning pages yet.
2. Implement `program-flow-explorer.html`, `.css`, and `.js` in `docs/learning/`.
   One HTML entry point need not mean an unmaintainable inline script. Use
   buildless SVG/Canvas/HTML and existing local assets, no new dependencies.
3. Keep node contracts and source anchors in a declarative JS data structure;
   keep simulation timing separate from graph rendering and concept views.
4. First review milestone: overview → motion expansion → Hann concept → return.
   This checks the interaction before filling in every branch.
5. Complete the remaining branches and execution scenarios after that review.
6. Update `docs/learning/README.md` with the entry link and reconcile stale
   reused lesson labels. Preserve standalone lessons as deeper references.
7. Open the HTML locally, test offline and run relevant repository tests plus
   `git diff --check`. Inspect the diff for footage/personal images before any
   user-authorized commit/push. No camera, servo or network access is needed.

## Validation and acceptance

- First screen is a readable graph at a typical MacBook viewport, not a dashboard
  of paragraphs. Expanded views may scroll, but parent context remains visible.
- Every overview node either expands a computation or opens an explanation;
  each has input, output, policy and verified source-symbol references.
- End-to-end routes exist for camera→motion→browser, camera→detector→tracker→
  browser and IMU→browser. Optional branches respect mode prerequisites.
- Detection-off mode correctly moves the small resize to FFmpeg; detection-on
  mode correctly uses OpenCV for the 320×180 motion copy and 300×300 model input.
- Frame pairing, independent timestamps, source ages, skips, invalid estimates,
  retirement and stale display hiding are visibly distinct.
- All animation controls change visible state; pause stops progression; reset
  is deterministic; keyboard activation and reduced-motion mode work.
- Concept views retain recorded Pi images and accurate computations. No claim
  that a phase-correlation peak directly gives camera degrees or 3D pose.
- Source-link targets exist. The source audit covers shapes, rates, thresholds,
  clocks, ownership and current-versus-proposed behavior, including re-ID limits.
- `docs/PIPELINE.md` and study guides are updated or explicitly reviewed as
  unchanged with a reason. Unit tests remain passing; browser QA limits, if any,
  are reported rather than claiming unperformed checks.

## Surprises and discoveries

- The worker-rates and SSD lesson originally said confidence ≥0.5, whereas live
  detection now uses 0.30. They were corrected during the source audit. The
  standalone saved-frame detector still defaults to 0.50, which is a separate
  command-line policy.
- `docs/PIPELINE.md` includes re-identification/recording but its introductory
  update date predates them. Refresh provenance during implementation review.
- The existing Hann page already distinguishes precomputed numerical arrays
  from live computation; preserve that honesty in the unified explorer.

## Decision log

- 2026-10-21: Use an expandable graph plus focused concept panels, not iframes
  of four full websites. This preserves context and avoids duplicated controls.
- 2026-10-21: Show independent data tokens and latest slots instead of one token
  traversing every worker; the latter would teach a false sequential pipeline.
- 2026-10-21: Preserve local/offline operation and existing standalone lessons.
  This is a repository learning artifact, not a hosted or live-control website.
- 2026-10-21: Stage the visual work for user review before full implementation.
- 2026-10-21: Keep the existing standalone learning pages as deep references;
  the unified page links to them rather than duplicating every interaction.
- 2026-10-22: Expansion is spatial, not page-like. Keep the overview and every
  ancestor branch visible. The selected node itself becomes a larger group that
  contains its children; neighboring columns and edges move to make room. A
  second click collapses that group to its original node size. No child graph is
  appended below the overview.

## Outcomes and retrospective

Implementation and validation are complete. The page uses a declarative 49-node
map, recorded Pi motion imagery, focused calculation views and a deterministic
six-event concurrency walkthrough. Node activation now changes the selected
node from a compact box into a measured group in the same graph. Its internal
nodes live inside that group; root columns, canvas size and connecting curves
are recalculated around it. A nested Detection → MobileNet/SSD expansion and
its reverse collapse were exercised automatically and rendered in headless
Chrome. The structural lesson audit and repository tests passed. Source links,
thresholds, recorded assets, in-place nesting and restoration of the compact
graph width have automated checks. No runtime behavior or hardware setting
changed. The Sites design guidance informed progressive disclosure and
restrained interactions; registration/publication remain out of scope.
