# Semantic spatial memory as an AP workload experiment

## Purpose / big picture

Use the existing MobileNet-SSD to attach object observations to remembered views
and test whether excluding potentially dynamic foreground improves revisits.
The primary question is the **quality gained per added processor and memory
cost**. The user approved the direction on 2026-11-05. This plan is presented
before multi-module implementation. Current v1 profiling remains first.

## Context and orientation

`vision/live_detector.py` produces category/confidence/xyxy boxes from selected
720p grayscale frames, converted to the model's three-channel 300×300 input.
`spatial/live_scene.py` independently selects frames for target-1Hz ORB matching;
`spatial/scene_memory.py` owns references; `spatial/view_map.py` records nodes.
Latest detector and scene results need not refer to the same frame. Depthwise
and 1×1 pointwise convolution reduce feature-extractor cost; they are not mapping
operations. The Pi 4 has no NPU. Reuse the model; no new download/training.

## Progress

- [x] 2026-11-05: Record AP-first priority and user-approved policy direction.
- [x] 2026-11-05: Define source alignment, bounds, fallback and comparison design.
- [ ] Investigate v1 IMU pause/recording backlog and establish baseline profile.
- [ ] Inspect exact detector result schema and define immutable observation types.
- [ ] Implement recorded-frame semantic annotations and hardware-free checks.
- [ ] Implement opt-in person-box feature masks and compare on identical inputs.
- [ ] Integrate bounded live association and record its AP costs on Pi.
- [ ] Review/update `docs/PIPELINE.md` and `docs/learning/SCENE_MEMORY.md` when
  implementation lands; current diagram reviewed, unchanged (planned only).

## Plan of work

### 1. Bounded semantic observations

Store class ID/label, score, normalized or explicitly dimensioned xyxy box,
detector source sequence/time and observation time with a verified scene node.
Preserve geometry as the scene decision; no label-only relocalization. Start
with a conservative explicit class list: person potentially dynamic; chair,
sofa, diningtable and tvmonitor candidates for persistent semantic observations.
Bottle remains an object observation; class alone does not establish stability.
Other classes remain unclassified by motion policy until explicitly configured.

Keep a bounded last-observation summary, not an unbounded list of objects or
an identity tracker. Initial proposed cap: 20 observations per each of the
existing maximum 12 nodes. It represents at most 20 selected detection records,
not 20 distinct persistent objects. Record observation counts/last-seen time;
separate single sightings from repeated support. Expiration and any repeated-
support threshold are named experimental settings to define before testing.
Missing detections mean no current evidence; do not infer removal immediately.
Unknown scenes do not invent nodes to hold detections; evict semantics with nodes.

### 2. Foreground feature exclusion

For person boxes, create an ORB feature-extraction mask in the canonical
640×360 image, for both enrollment and query processing. Apply exclusion to
feature selection, not by blacking pixels and detecting artificial box edges.
Clip finite boxes and transform coordinates explicitly. Masked fraction,
retained feature count and reasons are recorded. Large masks or inadequate
background yield explicit unknown, not relaxed geometric thresholds.

Class is a prior: people can be still and chairs can move. A person box includes
background; detection misses and box inaccuracies can hurt. Do not mask all
furniture. No current evidence justifies treating all bottle/chair features as
stationary. A future motion-consistency policy requires separate validation.

### 3. Alignment and fallback

First evaluate on recorded frames with detector and ORB using the **same source
image**. For live masking require the same source sequence; freshness alone is
insufficient during camera motion. Choose a bounded paired processing route
after measuring its latency, rather than attaching unrelated latest results.
Keep at most one pending paired frame/result; dropping or deferring work must
be counted. No unvalidated gyro warp or camera-angle conversion is introduced.
If no aligned detection is available, use the original visual-only path and
mark semantic/mask support unavailable. A missing detection is not an empty room.
Unknown orientation does not prevent semantic annotation of a visually verified
view; direction fields retain unknown rather than inventing a bearing.

### 4. AP evaluation before broader deployment

Profiles, with matched recordings, thresholds and software revision:

| Profile | Purpose |
| --- | --- |
| S0 spatial only | Existing detector-off baseline |
| S1 spatial + detector, integration off | Measure inference/contention cost |
| S2 S1 + semantic bookkeeping | Isolate metadata association/storage overhead |
| S3 S2 + person masks | Measure additional cost and recognition effect |

Record whether S1–S3 use a paired scheduler; keep it identical across those
profiles so semantic overhead is not confused with different frame scheduling.
An independent-scheduler detector comparison, if used, is separately labelled.
Keep recording mode, camera mode, cooling and duration identical within each
live comparison. Separate startup/model-load cost from steady-state results.

Quality: labelled revisit correctness, false knowns, unknowns/recovery, moving-
person occlusion, repeated furniture, moved chair and empty/weak scenes. AP:
total and per-process CPU, worker rates, source age/p95 latency, RSS, buffers/
copies, skipped/dropped jobs, temperature/throttling and IMU continuity. Check
hardware counters where supported; energy only with electrical measurement.
Track a profile that costs more without improving quality as a negative result.

## Concrete steps

Current action remains v1 stall profiling; do not enable semantic flags that
do not yet exist. Existing run commands are in `docs/SPATIAL_APPLICATION_V1.md`.
Before future live tests, document exact Pi and Mac tunnel/browser/SCP commands.
Use existing public model files and private local recordings; no motor control.

## Validation and acceptance

Tests must cover coordinate scaling, nonfinite boxes, same-source association,
missing results, node eviction/reset, caps and unknown behavior. Recorded tests
compare paired frames under unchanged scene thresholds. Labels are observations,
not identity, depth or position. Live acceptance requires useful quality and
resource evidence, without IMU continuity regression or hidden queue growth.
Record failed hypotheses as well as improvements. Pipeline/source guides must
match actual shapes, units, timing, policies and current/planned boundaries.

## Surprises and discoveries

The existing v1 run loses orientation after a gap with detector off; enabling
SSD is not a remedy and could increase contention. Boxes cannot supply pixel-
accurate segmentation. Broad classes are ambiguous location cues.

## Decision log

- 2026-11-05: AP learning drives experiment selection; retain S0 and isolate
  inference, bookkeeping and masking costs rather than add everything at once.
- 2026-11-05: Use person as potentially dynamic and furniture as a semantic
  prior; do not assert constant motion or permanent stationarity from class.
- 2026-11-05: Require paired source images for initial masking; stale latest
  boxes are not reliable masks during pans. Explicit fallback retains usability.

## Outcomes and retrospective

Direction and design recorded; implementation and AP results pending. No new
runtime policy, dependency, default or measured performance claim in this plan.
