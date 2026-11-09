# Experimental person exclusion for scene recognition

**Current 2026-11-10 implementation:** use the
[paired-source partial-background guide](SCENE_OCCLUSION_RETEST.md). It adds
exact detector/image/context pairing, 8-second enrollment waiting, clear-reference
enrollment, partial-support gates and source-matched visual evidence. The v1
description/commands below are historical, retained for interpreting older runs.

Implemented opt-in; [first Pi trial reviewed](SPATIAL_FOREGROUND_RESULTS_01.md),
but recognition benefit and incremental AP cost **not validated**. No recognition
threshold changes. This is a bounded spatial-workload integration, not object
identity recovery, 3D mapping, a segmentation model or a proven improvement.

## Behavior and source map

`vision.live_detector.DetectionState.scene_evidence` copies the latest result
under its lock. `spatial.foreground.person_mask` compares detector source host
receipt with scene source host receipt. Accept lag 0–0.5 s, reject future/stale,
missing or failed detector results. Latest-only evidence may miss an older
eligible result: no unbounded history or waiting for inference.

For VOC person class 15, scale 1280×720 boxes to canonical 640×360, round outwards,
clip and exclude those pixels from ORB keypoint extraction. A conservative
scale-dependent keypoint neighborhood check also rejects descriptors that
overlap the excluded region. Original image pixels/recorded PNGs are unchanged.
`SceneMemory.process` applies this for enrollment and queries; geometric and
ambiguity gates remain identical. Too few/spatially concentrated features return
unknown. Missing usable detector evidence returns unknown and leaves enrollment
pending. Weak masked images consume the enrollment attempt without creating a
view; inspect the reason and click Remember again with adequate background.
The preview now retains the last 12 request outcomes as PENDING, STORED or
NOT STORED, and recordings retain `enrollment_status`. Follow the
[confirmed-left retest](SCENE_ENROLLMENT_RETEST.md) for the current run commands.

An empty fresh detector result permits ordinary recognition; it does not prove
no person is present. Boxes are coarse and may lag moving people/cameras even
within 0.5 s. No optical-flow warping, semantic furniture scores, gyro fusion or
learned motion classification is included yet. Those remain distinct steps.

Recorded `decision.foreground`: policy, source sequence/time, relative source
age, availability reason, person count, canonical boxes and excluded pixel fraction. `features`
is the usable feature count after exclusion. Metadata identifies opt-in policy.
Existing compute/thread CPU/queue/IMU fields remain; enabling detection creates
a different workload from the previous detector-off storage trial.

## Pi smoke trial (no servo commands)

Stop the old preview with Ctrl+C; keep camera/head still during IMU startup.
Use the already installed model and verified device path. Do not install new
dependencies. Output must be new; use a new suffix on retries.

```bash
cd ~/projects/edgexr
git pull --ff-only
PYTHONPATH=src python3 -m app.live_preview \
  --device /dev/video0 --port 8765 \
  --imu --imu-sleep-ms 10 \
  --camera-axis-basis configs/camera_axes_neutral.json \
  --relative-orientation --scene-memory --detect --scene-exclude-people \
  --scene-output recordings/spatial-foreground-01 \
  --scene-save-images --scene-seconds 180
```

Mac tunnel (reuse the existing one if already connected):

```bash
ssh -N -o ExitOnForwardFailure=yes \
  -L 127.0.0.1:8766:127.0.0.1:8765 pi@ai-fusion.local
```

Another Mac terminal:

```bash
open http://127.0.0.1:8766
```

Enroll center/left/right with no person covering important background. Revisit
center, then keep the camera fixed as a person briefly crosses it, leaves, and
returns. Include an unenrolled direction: it must not be forced to a known view.
Note the approximate event times. Unknown during heavy occlusion or unavailable
detector evidence is allowed; wrong confident recognition is not. This smoke
trial is not an A/B accuracy claim. A later paired comparison must keep --detect
enabled in both modes, changing only --scene-exclude-people; re-enroll each run.

After auto-stop, transfer from Mac:

```bash
scp -r pi@ai-fusion.local:/home/pi/projects/edgexr/recordings/spatial-foreground-01 \
  /Users/ryanchoi/Desktop/
```

## Bounded completion roadmap

Person exclusion → semantic labels attached to remembered views → quality-gated
motion/IMU context → recorded acceptance → freeze reference application. This
does not itself implement 3D reconstruction or general re-identification.
The user's later [roadmap extension](decisions/2026-11-08-reconstruction-before-fpga.md)
adds a proposed bounded reconstruction milestone before FPGA implementation.
AP/FPGA work uses the reference: measure one candidate computation, implement
it in hardware, include transfer/driver overhead in comparison. Real FPGA work
requires additional FPGA hardware; simulations can begin on the current Mac/Pi.
No purchase, tools installation or hardware change is authorized by this guide.
