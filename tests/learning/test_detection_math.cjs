/** Hand-calculated contracts for the interactive detector lesson. */
const assert = require("node:assert/strict");
const M = require("../../docs/learning/detection-math.js");

// One standard filter accumulates across all channels. Depthwise keeps each sum.
const plane = Array(16).fill(1),
  kernel = Array(9).fill(1);
const result = M.convolution(
  [plane, plane.map((v) => 2 * v), plane.map((v) => 3 * v)],
  [kernel, kernel, kernel],
  4,
  0,
  0,
);
assert.deepEqual(result.sums, [9, 18, 27]);
assert.equal(result.total, 54);
assert.equal(result.terms.length, 27);
assert.equal(M.pointwise([9, 18, 27], [0.5, -2, 4]), 76.5);
assert.equal(M.outputSize(300, 3, 2, 1), 150);
assert.equal(M.outputSize(6, 3, 1, 0), 4);
assert.equal(
  M.convolution([plane], [kernel], 4, 0, 0, 1, 1).total,
  4,
  "padded corner has four valid inputs",
);

// These counts differ from the original VGG SSD300 configuration.
assert.equal(
  M.HEADS.reduce(
    (sum, h, i) => sum + h.grid * h.grid * M.priors(i, 0, 0).length,
    0,
  ),
  1917,
);
assert.equal(M.priors(0, 0, 0).length, 3);
assert.equal(M.priors(1, 0, 0).length, 6);
const square = M.priors(0, 0, 0)[0];
assert.equal(square.cx, 0.5 / 19);
assert.equal(square.w, 0.2);
assert.ok(M.corners(square)[0] < 0, "the graph does not clip priors");
const extra = M.priors(1, 0, 0)[1];
assert.equal(extra.w, Math.sqrt(105 * 150) / 300);
assert.deepEqual(M.decode(square, [0, 0, 0, 0]), {
  cx: square.cx,
  cy: square.cy,
  w: 0.2,
  h: 0.2,
});
const changed = M.decode(square, [2, -1, 1, 0]);
assert.ok(Math.abs(changed.cx - (square.cx + 0.04)) < 1e-12);
assert.ok(Math.abs(changed.w - 0.2 * Math.exp(0.2)) < 1e-12);

// Overlapping different classes survive class-wise NMS; app filtering is separate.
assert.equal(M.iou([0, 0, 2, 2], [1, 0, 3, 2]), 1 / 3);
const boxes = [
  { id: "A", label: "chair", score: 0.9, box: [0, 0, 1, 1] },
  { id: "B", label: "chair", score: 0.8, box: [0, 0, 1, 1] },
  { id: "C", label: "person", score: 0.7, box: [0, 0, 1, 1] },
  { id: "D", label: "chair", score: 0.28, box: [2, 2, 3, 3] },
  { id: "E", label: "chair", score: 0.25, box: [4, 4, 5, 5] },
];
const decisions = M.suppress(boxes);
assert.equal(decisions[0].reason, "keep");
assert.match(decisions[1].reason, /overlaps A/);
assert.equal(decisions[2].reason, "keep");
assert.match(decisions[3].reason, /app score/);
assert.match(decisions[4].reason, /graph score/);
assert.equal(boxes[0].reason, undefined, "do not mutate teaching inputs");
const scores = M.softmax([1000, 1000]);
assert.deepEqual(scores, [0.5, 0.5]);
console.log(
  "PASS: convolution sums, pointwise products, shapes, 1,917 priors, decoding and class-wise NMS.",
);
