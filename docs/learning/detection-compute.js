/* "Where the compute goes" section of detection-architecture.html.
   Layer sizes follow the pinned MobileNet-SSD graph (300×300 input, width 1.0;
   feature-map sizes match detection-math.js). Multiply-accumulates (MACs) per
   layer = output height × width × kernel area × input channels × output channels
   (depthwise: × channels once). Calculated, not timed per layer. Prediction heads,
   BatchNorm/ReLU and box decoding are excluded. */
(function () {
  "use strict";
  // [name, kind (0 standard, 1 depthwise, 2 pointwise), output shape, MACs, weights]
  const LAYERS = [
    ["conv0", 0, "150×150×32", 19440000, 864], ["conv1/dw", 1, "150×150×32", 6480000, 288], ["conv1", 2, "150×150×64", 46080000, 2048],
    ["conv2/dw", 1, "75×75×64", 3240000, 576], ["conv2", 2, "75×75×128", 46080000, 8192], ["conv3/dw", 1, "75×75×128", 6480000, 1152],
    ["conv3", 2, "75×75×128", 92160000, 16384], ["conv4/dw", 1, "38×38×128", 1663488, 1152], ["conv4", 2, "38×38×256", 47316992, 32768],
    ["conv5/dw", 1, "38×38×256", 3326976, 2304], ["conv5", 2, "38×38×256", 94633984, 65536], ["conv6/dw", 1, "19×19×256", 831744, 2304],
    ["conv6", 2, "19×19×512", 47316992, 131072], ["conv7/dw", 1, "19×19×512", 1663488, 4608], ["conv7", 2, "19×19×512", 94633984, 262144],
    ["conv8/dw", 1, "19×19×512", 1663488, 4608], ["conv8", 2, "19×19×512", 94633984, 262144], ["conv9/dw", 1, "19×19×512", 1663488, 4608],
    ["conv9", 2, "19×19×512", 94633984, 262144], ["conv10/dw", 1, "19×19×512", 1663488, 4608], ["conv10", 2, "19×19×512", 94633984, 262144],
    ["conv11/dw", 1, "19×19×512", 1663488, 4608], ["conv11", 2, "19×19×512", 94633984, 262144], ["conv12/dw", 1, "10×10×512", 460800, 4608],
    ["conv12", 2, "10×10×1024", 52428800, 524288], ["conv13/dw", 1, "10×10×1024", 921600, 9216], ["conv13", 2, "10×10×1024", 104857600, 1048576],
    ["conv14_1", 2, "10×10×256", 26214400, 262144], ["conv14_2", 0, "5×5×512", 29491200, 1179648], ["conv15_1", 2, "5×5×128", 1638400, 65536],
    ["conv15_2", 0, "3×3×256", 2654208, 294912], ["conv16_1", 2, "3×3×128", 294912, 32768], ["conv16_2", 0, "2×2×256", 1179648, 294912],
    ["conv17_1", 2, "2×2×64", 65536, 16384], ["conv17_2", 0, "1×1×128", 73728, 73728],
  ];
  const total = LAYERS.reduce((s, l) => s + l[3], 0);
  const byKind = [0, 1, 2].map((k) => LAYERS.filter((l) => l[1] === k).reduce((s, l) => s + l[3], 0));
  const weights = LAYERS.reduce((s, l) => s + l[4], 0);
  // Same backbone blocks (conv1–conv13) done as standard 3×3 convolutions instead.
  let standardEquivalent = 0, separable = 0;
  for (let i = 1; i < LAYERS.length; i++) {
    const [name, kind, shape, macs] = LAYERS[i];
    if (kind !== 1 || !/^conv\d+\/dw$/.test(name)) continue;
    const pw = LAYERS[i + 1], dims = shape.split("×").map(Number), out = pw[2].split("×").map(Number);
    separable += macs + pw[3];
    standardEquivalent += dims[0] * dims[1] * 9 * dims[2] * out[2];
  }
  const measuredMs = 226.39;   // AP baseline median detector compute (whole detector call)

  document.getElementById("compute-stats").innerHTML = [
    [`${(total / 1e9).toFixed(2)} billion`, "multiply-accumulates per detection"],
    [`${(100 * byKind[2] / total).toFixed(0)}%`, "of them in 1×1 pointwise layers"],
    [`${(standardEquivalent / separable).toFixed(1)}×`, "fewer than standard 3×3 convolutions would need for the same 13 backbone blocks"],
    [`${(weights / 1e6).toFixed(1)} million`, `convolution weights (≈${(weights * 4 / 1e6).toFixed(1)} MB as 32-bit floats)`],
    [`≈${(total / (measuredMs / 1000) / 1e9).toFixed(1)} billion/s`, "achieved on the Pi with two threads (lower bound: 226 ms includes pre/post-processing)"],
  ].map(([v, s]) => `<div><strong>${v}</strong><span>${s}</span></div>`).join("");

  window.EdgeCharts.bars(document.getElementById("compute-chart"), {
    title: "Multiply-accumulates per layer, in execution order",
    note: "Hover a bar for the layer’s output size and weight count. Prediction heads excluded.",
    series: [{ name: "standard convolution", color: "var(--s2)" }, { name: "depthwise (3×3, one kernel per channel)", color: "var(--s3)" }, { name: "pointwise (1×1, mixes channels)", color: "var(--s1)" }],
    rows: LAYERS.map(([name, kind, shape, macs, w]) => ({ label: name, values: [macs / 1e6], kind, note: `output ${shape} · ${w.toLocaleString("en-US")} weights` })),
    unit: "million MACs", digits: 1, labelWidth: 96, rowHeight: 17, rowPad: 6, barHeight: 10, valueLabels: false, max: 110,
  });
})();
