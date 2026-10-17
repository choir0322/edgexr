# Interactive standard convolution, MobileNet and SSD lesson

## Purpose / big picture

Help the learner follow their own recorded Pi image from pixels, through
convolution and learned feature channels, into SSD default-box predictions and
EdgeXR's displayed detections. The interface must show calculations changing
in response to controls, with one understandable operation visible at a time.

The user approved the design and requested additional visual metaphors:
click-to-separate channel planes, sliding filters, a prominent synchronized
convolution comparison, and an explicit MobileNet-to-SSD feature-map bridge.

## Context and orientation

Source code: `src/vision/detect_image.py::infer_once/parse_detections`,
`src/vision/live_detector.py::CpuDetector/detect_latest/DetectionState`,
`src/app/live_preview.py::State.snapshot`, and `src/app/preview.html::render`.
The existing guide is `docs/learning/OBJECT_DETECTION.md`.

Use the user's local `Desktop/detection-input-01.png` as the visual anchor.
The matching `Desktop/edgexr-detection-01/report.json` records a diningtable
and chair prediction. Small derived teaching images can accompany the site;
the full model weights and raw video remain outside Git.

The upstream graph pinned by EdgeXR is:
https://github.com/chuanqi305/MobileNet-SSD/blob/bb17b6c3eef36d80be441ae8e5339be66e8e3b7a/deploy.prototxt

Its SHA-256 matches the user's Pi report exactly:
`2d180f723b3109e21f8287f6b3c691390d07b60eed998327cd3259ffa0e50608`.

Verified architecture facts, written as height × width × channels:

- Input: 300×300×3; EdgeXR duplicates gray into BGR and normalizes continuously
  with `(pixel - 127.5) * 0.007843`.
- `conv0`: standard 3×3, stride 2, padding 1; 150×150×32 output.
- `conv1/dw`: 32 separate 3×3 spatial kernels; 150×150×32 output.
- `conv1`: 64 pointwise filters of shape 1×1×32; 150×150×64 output.
- These convolutions have bias disabled and are followed by BatchNorm, Scale
  and ReLU operations. Kernel-only parameter comparisons must say so.

| SSD source layer | Grid | Channels | Priors/cell | Minimum size on 300px input | Maximum-size setting |
|---|---:|---:|---:|---:|---:|
| conv11 | 19×19 | 512 | 3 | 60 | absent |
| conv13 | 10×10 | 1024 | 6 | 105 | 150 |
| conv14_2 | 5×5 | 512 | 6 | 150 | 195 |
| conv15_2 | 3×3 | 256 | 6 | 195 | 240 |
| conv16_2 | 2×2 | 256 | 6 | 240 | 285 |
| conv17_2 | 1×1 | 128 | 6 | 285 | 300 |

Total priors: 1,917. The first head has square, wide and tall shapes. Other
heads also use aspect ratio 3 and its reciprocal, plus the extra square
whose side is sqrt(min_size × max_size). Maximum size is not the side of
that extra square. Priors can extend outside the image (`clip:false`).

Each prior receives four localization values and 21 class scores, including
background. The graph decodes CENTER_SIZE offsets, uses class-score filtering
at 0.25 and NMS IoU threshold 0.45, then EdgeXR filters output scores at 0.5.
The site must distinguish these controls and their locations.

Primary concept references:
- MobileNet v1: https://arxiv.org/abs/1704.04861
- SSD: https://arxiv.org/abs/1512.02325
- Faster R-CNN comparison: https://arxiv.org/abs/1506.01497

## Progress

- [x] 2026-10-16: inspect project preprocessing, prediction parsing and saved result.
- [x] Verify the pinned graph hash, first layers, SSD heads and default-box settings.
- [x] Prepare the proposed visual interactions and accuracy constraints.
- [x] User approved the design with visual-metaphor and feature-map-bridge additions.
- [x] Build the offline HTML lesson with linked JavaScript and derived image assets.
- [x] Verify arithmetic, shapes, anchor generation, decoding and filtering controls.
- [x] Review/update `docs/PIPELINE.md` and `docs/learning/OBJECT_DETECTION.md`.
- [ ] Browser interaction/layout review: computer-use permissions remain pending.
  Direct event tests pass; visual rendering has not been verified in a browser.

## Plan of work

### Interface and learning order

Use a horizontal overview connecting Input → Standard convolution → Depthwise
→ Pointwise → MobileNet feature maps → SSD boxes → Predictions → EdgeXR display.
Three chapter tabs group these into Convolution, MobileNet and SSD. An
Overview/Walk through toggle, Back/Next, Play/Pause, speed and Reset keep the
learner in control. Autoplay pauses at arithmetic steps; it must not race past
the idea being taught. Shapes and units stay visible. Use color consistently
for channels, filters, feature maps, default boxes and final predictions.

Each scene answers one question visually. A short explanation appears below;
an expandable "Numbers and code" area shows exact formulas, values, layer
names and links. Avoid paragraphs of tutorial text replacing the demonstration.
Controls must visibly modify the relevant canvas/SVG and numerical readout.

### 1. The real input and what a channel is

Show the 1280×720 recorded image resizing to 300×300. Split it into three
identical gray channel planes. Clicking a pixel highlights its three equal
values and animates subtraction/scaling into the model's numeric range.
Explicitly show that three input channels are a model input convention here;
they do not recover color from the monochrome sensor.

### 2. Standard convolution, one output number at a time

Zoom into a real crop and offer a small editable numeric example. Draw one
filter as a stack spanning all input channels. Move its 3×3 footprint across
the image. At each location, highlight elementwise products, per-channel sums,
then the sum across channels producing one output value. It is a dot product,
not ordinary matrix multiplication between two image tiles.

Switch output-filter identity to reveal another complete 3D filter and another
output feature map. A channel-stack view makes "one filter → one output map"
visible. Stride/padding controls show skipped centers, padded borders and the
resulting output dimensions. A bias teaching toggle explains one bias per
output channel, while identifying that this model's backbone convolutions
disable that bias. Include ReLU and the role of fixed inference-time BatchNorm
in an optional detail view so the diagram does not imply all layers are linear.

### 3. Depthwise convolution

Keep the same input stack and spatial footprint, but animate separate kernels
moving along separate channel lanes. No lines connect different input channels.
Each channel produces its own spatially filtered map. For the actual first
MobileNet block, label 32 input maps → 32 depthwise maps; allow inspecting one
lane at a time. This follows the 32 learned outputs of conv0, not RGB planes.

### 4. Pointwise convolution

Freeze one spatial coordinate and lift the values at that coordinate into a
vertical vector. Show one 1×1 filter extending through all 32 channels, with
32 weights. Animate value × weight and their sum into one output channel.
Changing output-filter identity changes the weight vector and fills another
output channel. Repeating at all positions produces 64 complete feature maps.

Use a three-channel teaching view first, then expand it into the actual
32→64 dimensions. Label reduced illustrations and editable weights as teaching
examples; they are not pretrained activations or weights from the saved model.
Channel count is an architectural choice; training learns the weights.

### 5. Why MobileNet changes the cost

Compare a standard 3×3, 32→64 convolution with the first depthwise+pointwise
block on equal-sized inputs/outputs. Animate weight tiles and show separate
counters for stored kernel weights and multiply-accumulates over positions:
18,432 versus 288+2,048=2,336 kernel weights. Explain that factorization changes
the layer's form and capacity; it does not reproduce every possible standard
convolution exactly. Exclude BN/Scale and other parameters explicitly from this
comparison. MAC estimates are not measured Pi timing.

### 6. SSD's multiple prediction grids

Show the actual six feature-map grids next to the recorded image. Selecting a
grid and then a cell draws only that cell's default boxes on the 300×300 input.
Allow a small-to-large box slider and square/wide/tall choice, keeping the
actual sizes and ratios visible. A toggle can reveal neighboring cells and
then all centers; do not begin by covering the image in 1,917 rectangles.

Explain that these are spatial reference boxes, not camera frames, independent
crops or hard categories of small/medium/large objects. Finer grids give denser
locations; associated scales overlap. The learned feature map is not simply
a tiny photographic copy of the input. Label schematic feature tiles as such.
The same input supplies all heads during one forward pass.

### 7. From a default box to a predicted object

Select a default box. Four sliders expose predicted center/size offsets and
animate the decoded box moving and expanding. Show the actual variance factors
(0.1 for centers; 0.2 for sizes) in the detailed formula. In parallel, show a
21-entry score view: 20 classes plus background. Clearly label the adjustable
scores/offsets as a mathematical demonstration, not actual hidden outputs.

Then show several overlapping predictions on the real image. Step through
score filtering and class-wise NMS; highlight intersection/union to explain IoU.
Use saved final detections as the actual observed endpoint, without inventing
the model's unseen pre-NMS proposals. Finish by mapping normalized coordinates
back to 1280×720 and the preview overlay, with source-frame age and 2Hz scheduling
as an optional application context panel.

### 8. Compare one-stage SSD with a two-stage detector

Use a synchronized side-by-side flow: SSD's shared features → dense box/class
predictions versus Faster R-CNN's shared features → region proposals → regional
classification/refinement. Animate feature reuse and proposal selection.
State explicitly that these are stages with many layers, not two literal
network layers. Faster R-CNN can also use anchors; predefined boxes alone do
not distinguish it from SSD. This comparison is architecture, not a Pi speed
benchmark or a claim that every two-stage implementation works identically.

## Concrete steps

Planned files after design review:
- `docs/learning/detection-architecture.html`: local website entry point.
- `docs/learning/detection-architecture.js`: numerical interactions and playback.
- Small derived image/model-metadata assets under `docs/learning/`.
- Relevant learning-guide/index updates and focused numerical checks.

Open the entry HTML directly on the Mac. Keep assets local and avoid a server
or dependency installation unless a concrete requirement arises. No browser
inference engine or model download is needed for the proposed first version.

## Validation and acceptance

Verify a hand-computable convolution, channel summation, pointwise dot product,
stride/padding dimensions and parameter/MAC accounting. Verify anchor count
1,917, selected centers/shapes, CENTER_SIZE decoding and a clear NMS example.
Use the pinned graph as the architecture reference. Confirm real-vs-teaching
data labels remain visible and that arbitrary controls never masquerade as
actual trained predictions. Validate saved final boxes against report.json.

In browser QA, exercise every slider, filter/anchor selection, chapter,
play/pause/reset and narrow layout. Check that a real image stays visually
connected to the current calculation. Confirm source links and pipeline
shape/rate/freshness statements remain accurate. Changes are instructional;
if the runtime diagram needs no edits, record "diagram reviewed; unchanged"
and the reason.

## Surprises and discoveries

The 32→64 example discussed earlier is actually present in this pinned model's
first separable block. This SSD variant uses 1,917 default boxes, not the 8,732
often quoted for the original VGG SSD300 configuration. The first prior-box
head omits max_size and therefore has three priors per cell, not six.

## Decision log

- 2026-10-16: use artificial sliding windows, traveling numbers and separated
  planes as explicitly labeled visual metaphors. They illustrate tensor indexing
  and arithmetic; they do not claim OpenCV physically slides rendered objects.
- 2026-10-16: make the two convolution paths and the MobileNet/SSD division of
  responsibility separate interactive scenes, rather than hiding them in notes.

- 2026-10-16: separate exact project architecture and observed detections from
  small editable arithmetic examples. This makes the math inspectable without
  fabricating trained feature values.
- 2026-10-16: retain the recorded image as the visual anchor across chapters.
- 2026-10-16: stop at the requested design check-in before building the HTML.

## Outcomes and retrospective

Implemented eleven scenes with click-to-split planes, spatial-filter arithmetic,
depthwise lanes, editable pointwise weights, a side-by-side connection comparison,
an explicit multi-tensor MobileNet/SSD bridge, prior geometry, prediction decoding,
class-wise NMS, one/two-stage comparison and actual saved Pi detections.

Validation:
- `node tests/learning/test_detection_math.cjs`: hand-computable convolution,
  depthwise sums, pointwise mixing, padding/stride, 1,917-prior geometry,
  CENTER_SIZE offsets, softmax and class-wise NMS pass.
- `node tests/learning/test_detection_ui.cjs`: all eleven scenes and playback
  handlers execute against DOM/canvas doubles, including expanded 32-channel
  controls and extreme SSD slider values. This checks event code, not layout.
- JavaScript syntax, HTML validation (retaining intentional empty decorative
  elements), and `git diff --check` pass. The new generator's function contract
  passes the repository's annotation/docstring audit.
- Generator verified the source-image hash against the saved Pi report before
  deriving the display PNG and coarse numerical sample. No new dependency was
  installed. Website runtime is local HTML/CSS/JavaScript.
- Diagram reviewed; unchanged: no live data flow, shape, scheduling, source-age,
  model, or worker behavior changed. The object-detection guide and learning
  index now link the lesson and explain the exact feature-map handoff.

Browser control reported Accessibility/Screen Recording permissions still
pending on repeated checks. No screenshot or actual browser-layout pass is
claimed. Keep this plan active for that remaining review. The repository changes
have not been committed or pushed in this task.
