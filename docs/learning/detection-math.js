/* Pure lesson arithmetic. Small examples are not pretrained model inference. */
(function (root) {
  "use strict";
  const HEADS = [
    { name: "conv11", grid: 19, channels: 512, min: 60, max: null },
    { name: "conv13", grid: 10, channels: 1024, min: 105, max: 150 },
    { name: "conv14_2", grid: 5, channels: 512, min: 150, max: 195 },
    { name: "conv15_2", grid: 3, channels: 256, min: 195, max: 240 },
    { name: "conv16_2", grid: 2, channels: 256, min: 240, max: 285 },
    { name: "conv17_2", grid: 1, channels: 128, min: 285, max: 300 },
  ];
  const LABELS = [
    "background",
    "aeroplane",
    "bicycle",
    "bird",
    "boat",
    "bottle",
    "bus",
    "car",
    "cat",
    "chair",
    "cow",
    "diningtable",
    "dog",
    "horse",
    "motorbike",
    "person",
    "pottedplant",
    "sheep",
    "sofa",
    "train",
    "tvmonitor",
  ];

  /** Output length for a dilatation-one spatial convolution. @param {number} n @param {number} kernel @param {number} stride @param {number} padding @returns {number} */
  function outputSize(n, kernel, stride, padding) {
    return Math.floor((n + 2 * padding - kernel) / stride) + 1;
  }

  /** Return every multiplication for one standard convolution output. @param {number[][]} channels Flattened square maps. @param {number[][]} kernels One 3×3 kernel per channel. @param {number} side @param {number} ox @param {number} oy @param {number} stride @param {number} padding @returns {{terms:object[],sums:number[],total:number}} */
  function convolution(
    channels,
    kernels,
    side,
    ox,
    oy,
    stride = 1,
    padding = 0,
  ) {
    const terms = [],
      sums = [];
    channels.forEach((map, c) => {
      let sum = 0;
      for (let ky = 0; ky < 3; ky += 1)
        for (let kx = 0; kx < 3; kx += 1) {
          const x = ox * stride + kx - padding,
            y = oy * stride + ky - padding;
          const value =
            x >= 0 && x < side && y >= 0 && y < side ? map[y * side + x] : 0;
          const weight = kernels[c][ky * 3 + kx],
            product = value * weight;
          terms.push({ c, x, y, kx, ky, value, weight, product });
          sum += product;
        }
      sums.push(sum);
    });
    return { terms, sums, total: sums.reduce((a, b) => a + b, 0) };
  }

  /** A 1×1 filter is a dot product across channels at one position. @param {number[]} values @param {number[]} weights @returns {number} */
  function pointwise(values, weights) {
    return values.reduce((sum, value, i) => sum + value * weights[i], 0);
  }

  /** Generate the actual prior shapes at one feature-map location, unclipped. @param {number} headIndex @param {number} column @param {number} row @returns {object[]} */
  function priors(headIndex, column, row) {
    const h = HEADS[headIndex],
      s = h.min / 300;
    const shapes = [{ w: s, h: s, label: "square" }];
    if (h.max !== null)
      shapes.push({
        w: Math.sqrt(h.min * h.max) / 300,
        h: Math.sqrt(h.min * h.max) / 300,
        label: "extra square",
      });
    for (const ratio of h.max === null ? [2] : [2, 3]) {
      shapes.push({
        w: s * Math.sqrt(ratio),
        h: s / Math.sqrt(ratio),
        label: `wide ${ratio}:1`,
      });
      shapes.push({
        w: s / Math.sqrt(ratio),
        h: s * Math.sqrt(ratio),
        label: `tall 1:${ratio}`,
      });
    }
    return shapes.map((shape) => ({
      ...shape,
      cx: (column + 0.5) / h.grid,
      cy: (row + 0.5) / h.grid,
    }));
  }

  /** Decode the graph's CENTER_SIZE offsets with its prior variances. @param {object} prior @param {number[]} offsets [tx,ty,tw,th]. @returns {object} */
  function decode(prior, offsets) {
    return {
      cx: prior.cx + 0.1 * offsets[0] * prior.w,
      cy: prior.cy + 0.1 * offsets[1] * prior.h,
      w: prior.w * Math.exp(0.2 * offsets[2]),
      h: prior.h * Math.exp(0.2 * offsets[3]),
    };
  }

  /** Convert center/size coordinates to corners. @param {object} box @returns {number[]} */
  function corners(box) {
    return [
      box.cx - box.w / 2,
      box.cy - box.h / 2,
      box.cx + box.w / 2,
      box.cy + box.h / 2,
    ];
  }

  /** Intersection over union of two corner-coordinate boxes. @param {number[]} a @param {number[]} b @returns {number} */
  function iou(a, b) {
    const area =
      Math.max(0, Math.min(a[2], b[2]) - Math.max(a[0], b[0])) *
      Math.max(0, Math.min(a[3], b[3]) - Math.max(a[1], b[1]));
    const union =
      (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - area;
    return union > 0 ? area / union : 0;
  }

  /** Class-wise greedy NMS, then the app's inclusive score cutoff. @param {object[]} boxes @param {number} threshold @param {number} appThreshold @returns {object[]} */
  function suppress(boxes, threshold = 0.45, appThreshold = 0.5) {
    const decisions = boxes.map((box) => ({
      ...box,
      reason: box.score > 0.25 ? "pending" : "graph score ≤ 0.25",
    }));
    const kept = [];
    decisions
      .filter((box) => box.reason === "pending")
      .sort((a, b) => b.score - a.score)
      .forEach((box) => {
        const duplicate = kept.find(
          (other) =>
            other.label === box.label && iou(box.box, other.box) > threshold,
        );
        if (duplicate) box.reason = `overlaps ${duplicate.id} (same class)`;
        else {
          kept.push(box);
          box.reason =
            box.score >= appThreshold
              ? "keep"
              : `app score < ${appThreshold.toFixed(2)}`;
        }
      });
    return decisions;
  }

  /** Stable class-score normalization for the editable teaching logits. @param {number[]} logits @returns {number[]} */
  function softmax(logits) {
    const max = Math.max(...logits),
      values = logits.map((value) => Math.exp(value - max));
    const sum = values.reduce((a, b) => a + b, 0);
    return values.map((value) => value / sum);
  }

  const api = {
    HEADS,
    LABELS,
    outputSize,
    convolution,
    pointwise,
    priors,
    decode,
    corners,
    iou,
    suppress,
    softmax,
  };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.DetectionMath = api;
})(typeof window !== "undefined" ? window : globalThis);
