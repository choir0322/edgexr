/* The scene renderer uses explicit visual metaphors and small teaching tensors.
 * Exact graph dimensions and saved Pi detections are separate from toy weights.
 */
(() => {
  "use strict";
  const M = window.DetectionMath,
    D = window.DETECTION_LESSON_DATA;
  const $ = (id) => document.getElementById(id);
  const C = {
    ink: "#edf5fc",
    muted: "#a9bdd1",
    teal: "#61dfc2",
    amber: "#ffc47a",
    purple: "#c5a3ff",
    red: "#ff9b9b",
    blue: "#82bcff",
    line: "#354c63",
  };
  const COLORS = [C.blue, C.teal, C.red];
  const titles = [
    "Split the image",
    "Standard convolution",
    "Depthwise convolution",
    "Pointwise convolution",
    "Compare both paths",
    "MobileNet → SSD",
    "Default boxes",
    "Box & class predictions",
    "Remove duplicate boxes",
    "One stage vs two",
    "Your EdgeXR result",
  ];
  const chapters = ["INPUT & CONVOLUTION", "MOBILENET", "SSD & THE RESULT"];
  const source = new Image();
  let scene = 0,
    overview = true,
    timer = null,
    phase = 0,
    pos = 0,
    split = false;
  let filter = 0,
    stride = 1,
    padding = 0,
    bias = 0,
    diverse = false;
  let channels = 3,
    selectedChannel = 0,
    pointFilter = 0;
  let head = 0,
    cellX = 3,
    cellY = 11,
    priorIndex = 0,
    centers = false;
  let offsets = [0, 0, 0, 0],
    classId = 9,
    logit = 4,
    nmsPhase = 0;
  let nmsThreshold = 0.45,
    appThreshold = 0.5,
    selectedCandidate = 1;
  const customWeights = new Map();
  const kernels = [
    [
      [-1, 0, 1, -1, 0, 1, -1, 0, 1],
      [0, 1, 0, 1, 1, 1, 0, 1, 0],
      [1, 0, -1, 0, 1, 0, -1, 0, 1],
    ],
    [
      [0, -1, 0, -1, 4, -1, 0, -1, 0],
      [1, 1, 1, 0, 0, 0, -1, -1, -1],
      [0, 0, 0, 0, 1, 0, 0, 0, 0],
    ],
    [
      [1, 0, 0, 0, 1, 0, 0, 0, 1],
      [1, 0, -1, 1, 0, -1, 1, 0, -1],
      [0, 1, 0, 1, -2, 1, 0, 1, 0],
    ],
  ];
  const candidates = [
    { id: "A", label: "chair", score: 0.94, box: [0.002, 0.446, 0.276, 0.743] },
    { id: "B", label: "chair", score: 0.82, box: [0.02, 0.45, 0.29, 0.75] },
    { id: "C", label: "chair", score: 0.45, box: [0, 0.4, 0.3, 0.76] },
    { id: "D", label: "diningtable", score: 0.99, box: [0, 0.72, 0.992, 1] },
    { id: "E", label: "chair", score: 0.35, box: [0.55, 0.45, 0.86, 0.77] },
    { id: "F", label: "tvmonitor", score: 0.18, box: [0.03, 0.46, 0.28, 0.74] },
    { id: "G", label: "person", score: 0.65, box: [0.025, 0.45, 0.285, 0.75] },
  ];

  /** Format one arithmetic value without distracting trailing zeros. @param {number} n @returns {string} */
  function f(n) {
    return Number(n.toFixed(2)).toString();
  }

  /** Write a short explanation, a visible result, and source details. @param {string} title @param {string} intro @param {string} kind @param {string} details @returns {void} */
  function heading(title, intro, kind, details) {
    $("scene-title").textContent = title;
    $("scene-intro").textContent = intro;
    $("scene-kind").textContent = kind;
    $("scene-kicker").textContent =
      `Scene ${scene + 1} of ${titles.length} · ${scene < 2 ? "Convolution" : scene < 6 ? "MobileNet" : "SSD"}`;
    $("detail-content").innerHTML = details;
  }

  /** Create a local control whose changes immediately recompute the scene. @param {string} id @param {string} label @param {number} min @param {number} max @param {number} step @param {number} value @returns {string} */
  function range(id, label, min, max, step, value) {
    return `<label for="${id}">${label} <output id="${id}-value">${value}</output><input id="${id}" type="range" min="${min}" max="${max}" step="${step}" value="${value}"></label>`;
  }

  /** Attach a numeric slider and keep its label current. @param {string} id @param {function(number):void} change @returns {void} */
  function slider(id, change) {
    $(id).addEventListener("input", () => {
      $(id + "-value").textContent = $(id).value;
      change(Number($(id).value));
      render();
    });
  }

  /** Set a button's click behavior. @param {string} id @param {function():void} action @returns {void} */
  function click(id, action) {
    $(id).addEventListener("click", () => {
      action();
      render();
    });
  }

  /** Prepare a fixed coordinate system while CSS scales or scrolls the drawing. @param {number} height @param {boolean} numeric @returns {void} */
  function makeCanvas(height = 480, numeric = true) {
    $("visual").className = `visual${numeric ? " numeric" : ""}`;
    $("visual").innerHTML =
      `<canvas id="diagram" width="1000" height="${height}" role="img" aria-label="${titles[scene]} interactive diagram">Use the explanation and arithmetic readout below.</canvas>`;
  }

  /** Clear and return the current scene's 2D drawing context. @returns {CanvasRenderingContext2D} */
  function canvas() {
    const ctx = $("diagram").getContext("2d");
    ctx.clearRect(0, 0, 1000, $("diagram").height);
    ctx.fillStyle = "#0e1a28";
    ctx.fillRect(0, 0, 1000, $("diagram").height);
    return ctx;
  }

  /** Draw a legible canvas label. @param {CanvasRenderingContext2D} ctx @param {string} value @param {number} x @param {number} y @param {string} color @param {number} size @param {string} align @returns {void} */
  function text(ctx, value, x, y, color = C.ink, size = 15, align = "left") {
    ctx.fillStyle = color;
    ctx.font = `${size}px system-ui`;
    ctx.textAlign = align;
    ctx.fillText(value, x, y);
    ctx.textAlign = "left";
  }

  /** Draw a directional dependency, with an optional highlighted traveling dot. @param {CanvasRenderingContext2D} ctx @param {number} x @param {number} y @param {number} endX @param {number} endY @param {string} color @param {boolean} active @returns {void} */
  function arrow(ctx, x, y, endX, endY, color = C.line, active = false) {
    ctx.beginPath();
    ctx.moveTo(x, y);
    ctx.lineTo(endX, endY);
    ctx.strokeStyle = color;
    ctx.lineWidth = active ? 3 : 1.5;
    ctx.stroke();
    const a = Math.atan2(endY - y, endX - x);
    ctx.beginPath();
    ctx.moveTo(endX, endY);
    ctx.lineTo(endX - 9 * Math.cos(a - 0.4), endY - 9 * Math.sin(a - 0.4));
    ctx.lineTo(endX - 9 * Math.cos(a + 0.4), endY - 9 * Math.sin(a + 0.4));
    ctx.closePath();
    ctx.fillStyle = color;
    ctx.fill();
    if (active) {
      const t = (phase % 10) / 10;
      ctx.beginPath();
      ctx.arc(x + (endX - x) * t, y + (endY - y) * t, 5, 0, Math.PI * 2);
      ctx.fillStyle = color;
      ctx.fill();
    }
  }

  /** Draw a rectangular tensor or graph node. @param {CanvasRenderingContext2D} ctx @param {number} x @param {number} y @param {number} w @param {number} h @param {string} color @param {string} title @param {string} subtitle @returns {void} */
  function card(ctx, x, y, w, h, color, title, subtitle = "") {
    ctx.fillStyle = "#192c40";
    ctx.fillRect(x, y, w, h);
    ctx.strokeStyle = color;
    ctx.lineWidth = 2;
    ctx.strokeRect(x, y, w, h);
    text(ctx, title, x + w / 2, y + 25, color, 15, "center");
    if (subtitle) text(ctx, subtitle, x + w / 2, y + 47, C.muted, 12, "center");
  }

  /** Draw numeric image entries, a sliding footprint and a selected multiplication. @param {CanvasRenderingContext2D} ctx @param {number[]} values @param {number} side @param {number} x @param {number} y @param {number} cell @param {?number[]} footprint @param {?number} selected @param {string} color @returns {void} */
  function matrix(
    ctx,
    values,
    side,
    x,
    y,
    cell = 25,
    footprint = null,
    selected = null,
    color = C.teal,
  ) {
    for (let r = 0; r < side; r += 1)
      for (let c = 0; c < side; c += 1) {
        const i = r * side + c,
          v = values[i];
        ctx.fillStyle =
          selected === i ? "#49604d" : v === null ? "#122233" : "#22364b";
        ctx.fillRect(x + c * cell, y + r * cell, cell - 1, cell - 1);
        if (v !== null)
          text(
            ctx,
            f(v),
            x + (c + 0.5) * cell,
            y + (r + 0.67) * cell,
            selected === i ? C.amber : C.ink,
            Math.min(13, cell * 0.48),
            "center",
          );
      }
    if (footprint) {
      ctx.strokeStyle = color;
      ctx.lineWidth = 3;
      ctx.strokeRect(
        x + footprint[0] * cell,
        y + footprint[1] * cell,
        3 * cell,
        3 * cell,
      );
    }
  }

  /** Build the small input stack; equal planes mimic this project's gray input. @returns {number[][]} */
  function inputs() {
    const base = D.sample.map((v) => Math.round(v / 28.333));
    return [
      base,
      base.map((v, i) => (diverse ? (v + (i % 4)) % 10 : v)),
      base.map((v, i) => (diverse ? (9 - v + Math.floor(i / 6)) % 10 : v)),
    ];
  }

  /** Compute the three depthwise teaching maps for subsequent pointwise mixing. @returns {number[][]} */
  function depthMaps() {
    return inputs().map((map, c) =>
      Array.from(
        { length: 16 },
        (_, i) =>
          M.convolution([map], [kernels[0][c]], 6, i % 4, Math.floor(i / 4))
            .total,
      ),
    );
  }

  /** Select an editable illustrative pointwise weight, not a pretrained value. @param {number} output @param {number} input @returns {number} */
  function weight(output, input) {
    return (
      customWeights.get(`${channels}:${output}:${input}`) ??
      (((output * 3 + input * 2) % 9) - 4) / 4
    );
  }

  /** Explain grayscale replication with a clickable split-plane animation. @returns {void} */
  function setupInput() {
    heading(
      "Click the image. Reveal its three input planes.",
      "The colored borders identify channel slots. Your camera is monochrome, so all three planes contain the same gray intensities.",
      "Real image · visual metaphor",
      '<p><code>infer_once()</code> calls <code>cv.cvtColor(gray, cv.COLOR_GRAY2BGR)</code>, then <code>blobFromImage(..., size=(300,300), crop=False)</code>. The square resize stretches the image. BGR is OpenCV’s order; each slot has identical values here.</p><p>The sample selector inspects a coarse 6×6 chair-region sample. It is used for teaching, not as the network’s actual input tensor. Normalization is continuous: <code>(pixel − 127.5) × 0.007843</code>.</p><p><a href="../../src/vision/detect_image.py">Code: infer_once()</a></p>',
    );
    $("scene-controls").innerHTML =
      '<button id="split-button" type="button" class="primary">Split into B / G / R</button>' +
      range("sample-index", "Inspect sample cell", 0, 35, 1, pos);
    $("visual").className = "visual";
    $("visual").innerHTML =
      '<div class="split-scene"><button id="split-source" class="split-source" type="button" aria-label="Click the actual image to resize and separate channels"><img src="' +
      D.image +
      '" alt="Your recorded Pi camera image"></button><span class="big-arrow">→</span><div id="channel-stack" class="channel-stack">' +
      ["B slot", "G slot", "R slot"]
        .map(
          (label) =>
            '<div class="channel-plane"><img src="' +
            D.image +
            '" alt="Identical grayscale channel"><span>' +
            label +
            " · 300 × 300</span></div>",
        )
        .join("") +
      "</div></div>";
    click("split-button", () => {
      split = !split;
    });
    click("split-source", () => {
      split = !split;
    });
    slider("sample-index", (v) => {
      pos = v;
    });
  }

  /** Update the input-plane metaphor and the exact normalization arithmetic. @returns {void} */
  function renderInput() {
    $("channel-stack").classList.toggle("expanded", split);
    $("split-source").classList.toggle("squared", split);
    $("split-button").textContent = split
      ? "Recombine the planes"
      : "Split into B / G / R";
    const value = D.sample[pos % 36],
      normalized = (value - 127.5) * 0.007843;
    $("readout").innerHTML =
      `Sample intensity <strong>${value}</strong> → B=${value}, G=${value}, R=${value} → <span class="equation">(${value} − 127.5) × 0.007843 = ${normalized.toFixed(4)}</span> in each input channel.`;
    $("extra").innerHTML =
      '<div class="stats"><div class="stat">Camera source<strong>1280 × 720 × 1</strong>one monochrome image</div><div class="stat">Prepared network input<strong>1 × 3 × 300 × 300</strong>batch × channels × height × width</div><div class="stat">After actual conv0<strong>150 × 150 × 32</strong>32 learned feature channels</div></div>';
  }

  /** Create the standard/depthwise spatial controls and diagram. @param {boolean} depthwise @returns {void} */
  function setupSpatial(depthwise) {
    heading(
      depthwise
        ? "Depthwise: filter each channel in its own lane."
        : "Standard: one filter spans every input channel.",
      depthwise
        ? "Every lane keeps its own result. No sum crosses from one channel to another here."
        : "Watch the 27 products combine into one output number. A different complete filter produces a different output map.",
      "Small arithmetic example",
      '<p>The sliding outline is a metaphor for selecting tensor entries. Each kernel element multiplies the corresponding input value, then products are added. Filters reuse the same learned weights at every location.</p><p>These 6×6 inputs are coarse samples of your image, quantized to 0–9. Kernels are deliberately small teaching weights. The actual first layer uses a 3×3×3 filter for each of 32 outputs. The next depthwise layer uses 32 separate 3×3 kernels.</p><p><code>output = floor((input + 2×padding − kernel) / stride) + 1</code>. A bias, when enabled, belongs to an output channel and is reused at every position. This model’s backbone convolution bias is disabled; BatchNorm/Scale and ReLU follow its convolutions.</p><p><a href="../../src/vision/detect_image.py">Code: net.forward() executes these graph layers</a></p>',
    );
    $("scene-controls").innerHTML =
      (depthwise
        ? ""
        : range("filter", "Output filter", 0, 2, 1, filter) +
          range("bias", "One output bias", -5, 5, 1, bias)) +
      '<label>Stride<select id="stride"><option value="1">1 pixel</option><option value="2">2 pixels</option></select></label><label>Padding<select id="padding"><option value="0">0</option><option value="1">1 pixel border</option></select></label><label>Input channels<select id="input-kind"><option value="gray">Same gray values</option><option value="different">Different values (teaching)</option></select></label><button id="finish-cell" type="button">Finish this cell</button><button id="slide-window" type="button">Slide window →</button>';
    $("stride").value = String(stride);
    $("padding").value = String(padding);
    $("input-kind").value = diverse ? "different" : "gray";
    ["stride", "padding"].forEach((id) =>
      $(id).addEventListener("change", () => {
        if (id === "stride") stride = Number($(id).value);
        else padding = Number($(id).value);
        pos = 0;
        phase = 0;
        render();
      }),
    );
    $("input-kind").addEventListener("change", () => {
      diverse = $("input-kind").value === "different";
      render();
    });
    if (!depthwise) {
      slider("filter", (v) => {
        filter = v;
      });
      slider("bias", (v) => {
        bias = v;
      });
    }
    click("finish-cell", () => {
      phase = depthwise ? 8 : 26;
    });
    click("slide-window", () => {
      pos += 1;
      phase = 0;
    });
    makeCanvas(depthwise ? 570 : 490);
  }

  /** Draw sliding windows, products, partial sums, and their output maps. @param {boolean} dw @returns {void} */
  function renderSpatial(dw) {
    const ctx = canvas(),
      maps = inputs(),
      out = M.outputSize(6, 3, stride, padding);
    pos %= out * out;
    const ox = pos % out,
      oy = Math.floor(pos / out),
      ks = dw ? kernels[0] : kernels[filter];
    const calculation = M.convolution(maps, ks, 6, ox, oy, stride, padding),
      current = phase % (dw ? 9 : 27),
      term = calculation.terms[dw ? current : current];
    const positions = dw ? [65, 385, 705] : [40, 265, 490];
    maps.forEach((map, c) => {
      const x = positions[c],
        active = dw || Math.floor(current / 9) === c;
      text(ctx, `Input channel ${c + 1}`, x, 32, COLORS[c], 16);
      const footprint = [ox * stride - padding, oy * stride - padding],
        chosen = dw ? calculation.terms[c * 9 + current] : term;
      matrix(
        ctx,
        map,
        6,
        x,
        65,
        26,
        footprint,
        active && chosen.x >= 0 && chosen.x < 6 && chosen.y >= 0 && chosen.y < 6
          ? chosen.y * 6 + chosen.x
          : null,
        COLORS[c],
      );
      text(
        ctx,
        dw ? `Own 3×3 kernel` : `Slice ${c + 1} of filter ${filter + 1}`,
        x,
        260,
        C.muted,
        13,
      );
      matrix(
        ctx,
        ks[c],
        3,
        x + 35,
        278,
        27,
        null,
        active ? current % 9 : null,
        COLORS[c],
      );
      const partial = calculation.terms
        .filter((t, i) => t.c === c && (dw ? i % 9 <= current : i <= current))
        .reduce((sum, t) => sum + t.product, 0);
      text(ctx, `Sum = ${f(partial)}`, x + 80, 390, COLORS[c], 20, "center");
      if (dw) {
        arrow(ctx, x + 80, 400, x + 80, 430, COLORS[c], true);
        const values = Array.from({ length: out * out }, (_, i) =>
          i < pos || (i === pos && current === 8)
            ? M.convolution(
                [map],
                [ks[c]],
                6,
                i % out,
                Math.floor(i / out),
                stride,
                padding,
              ).total
            : null,
        );
        matrix(
          ctx,
          values,
          out,
          x + 20,
          440,
          Math.min(25, 130 / out),
          null,
          pos,
          COLORS[c],
        );
      } else arrow(ctx, x + 100, 397, 803, 290, COLORS[c], active);
    });
    if (!dw) {
      text(ctx, "ONE output map", 785, 32, C.amber, 18);
      text(ctx, `${out}×${out} · filter ${filter + 1}`, 785, 57, C.muted, 13);
      const values = Array.from({ length: out * out }, (_, i) =>
        i < pos || (i === pos && current === 26)
          ? M.convolution(
              maps,
              ks,
              6,
              i % out,
              Math.floor(i / out),
              stride,
              padding,
            ).total + bias
          : null,
      );
      matrix(
        ctx,
        values,
        out,
        790,
        85,
        Math.min(32, 185 / out),
        null,
        pos,
        C.amber,
      );
      text(ctx, "Add across channels", 790, 320, C.amber, 15);
      text(ctx, `+ one bias (${bias})`, 790, 345, C.muted, 13);
      const partial = calculation.terms
        .slice(0, current + 1)
        .reduce((sum, t) => sum + t.product, 0);
      text(ctx, `${f(partial + bias)}`, 830, 390, C.amber, 34, "center");
    }
    const selected = calculation.terms[current];
    $("readout").innerHTML = dw
      ? `The same spatial location yields <strong>three separate outputs: ${calculation.sums.join(", ")}</strong>. Each is a sum within its own channel. These values are not added together at this stage.`
      : `<span class="equation">Channel ${selected.c + 1}: ${selected.value} × ${selected.weight} = ${selected.product}</span> · product ${current + 1}/27. Completed cell: <strong>${calculation.sums.join(" + ")} + bias ${bias} = ${calculation.total + bias}</strong>.`;
    $("extra").innerHTML =
      `<p class="small">Window origin (${ox * stride - padding}, ${oy * stride - padding}); output cell (${ox}, ${oy}). ${padding ? "Parts outside the input are zero-padding. " : ""}6×6 input → ${out}×${out} output. ${dw ? "In the real conv1/dw block, there are 32 independent lanes." : "The 3 kernel slices together form ONE 3×3×3 filter, containing 27 weights."}</p>`;
  }

  /** Create the cross-channel dot-product inspector. @returns {void} */
  function setupPointwise() {
    heading(
      "Pointwise: gather one value from every channel.",
      "A 1×1 footprint is one spatial location. Its filter still extends through the full channel depth.",
      "Editable feature/weight example",
      "<p>At a fixed (x,y), a pointwise output is <code>Σ input[channel] × weight[output,channel]</code>. Each output filter owns a different weight vector. Reusing that vector at all positions builds a complete output map.</p><p>The 3-channel view uses the preceding toy depthwise maps. The expanded 32-channel view uses illustrative values with the actual conv1 dimensions: 32 input channels and 64 output filters. These are not captured trained activations. Architecture chooses 64; training learns the weights.</p><p>The first real block is <code>conv0 → conv1/dw → conv1</code>, with BatchNorm/Scale and ReLU after the convolutions. The depthwise output entering pointwise has shape 150×150×32; pointwise produces 150×150×64.</p>",
    );
    $("scene-controls").innerHTML =
      '<label>Channel view<select id="channel-count"><option value="3">3 lanes: see every product</option><option value="32">32 lanes: actual block dimensions</option></select></label>' +
      range(
        "point-output",
        "Output filter",
        0,
        channels === 3 ? 3 : 63,
        1,
        pointFilter,
      ) +
      range(
        "point-position",
        "Spatial position (toy 4×4)",
        0,
        15,
        1,
        pos % 16,
      ) +
      range(
        "point-channel",
        "Inspect input channel",
        0,
        channels - 1,
        1,
        selectedChannel,
      ) +
      range(
        "point-weight",
        "Edit its weight",
        -2,
        2,
        0.25,
        weight(pointFilter, selectedChannel),
      );
    $("channel-count").value = String(channels);
    $("channel-count").addEventListener("change", () => {
      channels = Number($("channel-count").value);
      pointFilter = 0;
      selectedChannel = 0;
      setupPointwise();
      render();
    });
    slider("point-output", (v) => {
      pointFilter = v;
      syncWeight();
    });
    slider("point-position", (v) => {
      pos = v;
    });
    slider("point-channel", (v) => {
      selectedChannel = v;
      syncWeight();
    });
    slider("point-weight", (v) => {
      customWeights.set(`${channels}:${pointFilter}:${selectedChannel}`, v);
    });
    makeCanvas(440);
  }

  /** Keep the editable weight control matched to the selected filter and channel. @returns {void} */
  function syncWeight() {
    $("point-weight").value = String(weight(pointFilter, selectedChannel));
    $("point-weight-value").textContent = f(
      weight(pointFilter, selectedChannel),
    );
  }

  /** Animate values at one coordinate combining into one of several output maps. @returns {void} */
  function renderPointwise() {
    const ctx = canvas(),
      maps = depthMaps(),
      values = Array.from({ length: channels }, (_, c) =>
        channels === 3
          ? maps[c][pos % 16]
          : Math.round(maps[c % 3][pos % 16] / (1 + Math.floor(c / 3))),
      );
    const weights = values.map((_, c) => weight(pointFilter, c)),
      total = M.pointwise(values, weights);
    text(
      ctx,
      `One spatial position (${pos % 4}, ${Math.floor((pos % 16) / 4)})`,
      30,
      32,
      C.ink,
      18,
    );
    text(
      ctx,
      `${channels} input channels → ${channels === 3 ? 4 : 64} output filters`,
      30,
      58,
      C.muted,
      14,
    );
    const count = channels === 3 ? 3 : 8;
    for (let j = 0; j < count; j += 1) {
      const c = channels === 3 ? j : Math.floor(selectedChannel / 8) * 8 + j,
        y = 105 + j * (channels === 3 ? 90 : 36),
        active = c === selectedChannel;
      if (channels === 3)
        matrix(ctx, maps[c], 4, 35, y - 15, 17, null, pos % 16, COLORS[c]);
      text(
        ctx,
        `ch ${c + 1}: ${values[c]}`,
        channels === 3 ? 125 : 50,
        y + 13,
        active ? C.amber : C.ink,
        16,
      );
      card(
        ctx,
        275,
        y - 13,
        105,
        43,
        active ? C.amber : C.line,
        `× ${f(weights[c])}`,
      );
      text(
        ctx,
        `= ${f(values[c] * weights[c])}`,
        420,
        y + 13,
        active ? C.amber : C.muted,
        16,
      );
      arrow(ctx, 535, y, 640, 230, active ? C.amber : C.line, active);
    }
    card(ctx, 645, 183, 135, 95, C.teal, "SUM", f(total));
    arrow(ctx, 785, 230, 845, 230, C.teal, true);
    card(
      ctx,
      855,
      193,
      115,
      75,
      C.purple,
      `Output ${pointFilter + 1}`,
      f(total),
    );
    text(ctx, "Same location, new feature channel", 640, 316, C.muted, 14);
    text(
      ctx,
      channels === 32
        ? "Showing 8 of 32 products; the sum includes all 32."
        : "Move spatial position to fill another output cell.",
      30,
      415,
      C.muted,
      14,
    );
    $("readout").innerHTML =
      `One filter has shape <strong>1 × 1 × ${channels}</strong>, so it owns <strong>${channels} weights</strong>. At this position, output ${pointFilter + 1} = <strong>${f(total)}</strong>. Select another output filter: its weights change, while the inputs stay the same.`;
    $("extra").innerHTML =
      '<div class="vector-list">' +
      values
        .map(
          (v, c) =>
            `<button type="button" data-channel="${c}" aria-pressed="${c === selectedChannel}">ch ${c + 1}<br>${v} × ${f(weights[c])}</button>`,
        )
        .join("") +
      "</div>";
    document.querySelectorAll("[data-channel]").forEach((button) =>
      button.addEventListener("click", () => {
        selectedChannel = Number(button.dataset.channel);
        $("point-channel").value = String(selectedChannel);
        $("point-channel-value").textContent = String(selectedChannel);
        syncWeight();
        render();
      }),
    );
  }

  /** Configure the side-by-side spatial/channel comparison. @returns {void} */
  function setupCompare() {
    heading(
      "Same job shape. Different connections and weight sharing.",
      "Follow the colored paths. Standard convolution mixes channels while filtering space; depthwise separates spatial filtering from pointwise channel mixing.",
      "Connection metaphor · exact counts",
      "<p>Standard: each output has a separate spatial kernel for each input channel. Depthwise: one spatial kernel per input channel; its result can feed every pointwise output. Pointwise: one mixing weight per input/output channel pair.</p><p>Kernel weights: <code>9×C_in×C_out</code> versus <code>9×C_in + C_in×C_out</code>. Multiply by the output spatial positions for these convolution MAC counts. This excludes BatchNorm/Scale, biases and activations. One MAC contains a multiplication and accumulation.</p><p>The factorization changes what functions the layer/block can represent; it is not a guarantee of identical output. Actual MobileNet also has nonlinearities between operations. Fewer MACs do not directly predict measured Pi latency.</p>",
    );
    $("scene-controls").innerHTML =
      range("cost-in", "Input channels", 1, 64, 1, 32) +
      range("cost-out", "Output channels", 1, 128, 1, 64) +
      range("cost-side", "Output map side", 1, 150, 1, 150) +
      '<button id="comparison-spatial" type="button">Highlight spatial filtering</button><button id="comparison-mixing" type="button">Highlight channel mixing</button>';
    ["cost-in", "cost-out", "cost-side"].forEach((id) => slider(id, () => {}));
    click("comparison-spatial", () => {
      phase = 0;
    });
    click("comparison-mixing", () => {
      phase = 5;
    });
    makeCanvas(420);
  }

  /** Compare where weights live and count their reuse across output locations. @returns {void} */
  function renderCompare() {
    const ctx = canvas(),
      mixing = phase % 10 >= 5;
    text(ctx, "STANDARD CONVOLUTION", 30, 35, C.purple, 19);
    text(ctx, "DEPTHWISE → POINTWISE", 530, 35, C.teal, 19);
    for (let c = 0; c < 3; c += 1) {
      const y = 110 + c * 95;
      card(ctx, 25, y, 90, 55, COLORS[c], `input ${c + 1}`);
      card(ctx, 520, y, 80, 55, COLORS[c], `input ${c + 1}`);
      card(ctx, 645, y, 95, 55, COLORS[c], "own 3×3");
      arrow(ctx, 603, y + 27, 642, y + 27, COLORS[c], !mixing);
      arrow(ctx, 740, y + 27, 805, 175, COLORS[c], mixing);
      arrow(ctx, 740, y + 27, 805, 290, COLORS[c], mixing);
      for (let o = 0; o < 2; o += 1) {
        const oy = 140 + o * 125;
        arrow(ctx, 118, y + 27, 330, oy, COLORS[c], true);
        text(ctx, `3×3`, 190 + o * 35, y + 14 + o * 19, COLORS[c], 12);
      }
    }
    card(ctx, 335, 110, 130, 60, C.purple, "output 1", "spatial + mixing");
    card(ctx, 335, 235, 130, 60, C.purple, "output 2", "different kernels");
    card(
      ctx,
      810,
      145,
      160,
      60,
      C.teal,
      "1×1 vector → out 1",
      "mix the filtered lanes",
    );
    card(
      ctx,
      810,
      260,
      160,
      60,
      C.teal,
      "1×1 vector → out 2",
      "another weight vector",
    );
    text(
      ctx,
      "6 spatial kernels in this 3-input / 2-output drawing",
      25,
      405,
      C.muted,
      13,
    );
    text(
      ctx,
      "3 spatial kernels + 6 pointwise mixing weights",
      520,
      405,
      C.muted,
      13,
    );
    const ci = Number($("cost-in").value),
      co = Number($("cost-out").value),
      side = Number($("cost-side").value);
    const standard = 9 * ci * co,
      depth = 9 * ci,
      point = ci * co,
      separable = depth + point;
    $("readout").innerHTML =
      `${ci} inputs → ${co} outputs: standard <strong>${standard.toLocaleString()} kernel weights</strong>; depthwise ${depth.toLocaleString()} + pointwise ${point.toLocaleString()} = <strong>${separable.toLocaleString()}</strong>. The drawing shows only 3 lanes and 2 outputs so you can see the connections.`;
    $("extra").innerHTML =
      `<div class="stats"><div class="stat">Standard kernel weights<strong>${standard.toLocaleString()}</strong><div class="bar-track"><i style="width:100%;background:var(--purple)"></i></div></div><div class="stat">Depthwise + pointwise weights<strong>${separable.toLocaleString()}</strong><div class="bar-track"><i style="width:${Math.min(100, (100 * separable) / standard)}%"></i></div></div><div class="stat">Across ${side}×${side} output positions<strong>${((standard * side * side) / 1e6).toFixed(2)}M / ${((separable * side * side) / 1e6).toFixed(2)}M</strong>standard / separable MACs; weights are reused</div></div>`;
  }

  // Remaining scenes follow the graph's feature-map handoff and SSD decisions.

  /** Build the actual feature-map-to-head architecture selector. @returns {void} */
  function setupBridge() {
    heading(
      "The handoff is a tensor of learned features—not a list of objects.",
      "MobileNet computes feature maps. SSD taps two of them, adds four coarser maps, and attaches box and class predictors at every chosen scale.",
      "Actual graph · schematic tensors",
      '<p>MobileNet’s <code>conv11</code> (19×19×512) and <code>conv13</code> (10×10×1024) feed prediction heads. The latter also feeds SSD’s extra layers to produce 5×5, 3×3, 2×2 and 1×1 maps. There is no one flattened handoff vector.</p><p>A feature map is an array of learned numerical responses indexed by row, column and channel. Its channels can encode useful patterns, but we have not measured or named individual trained channels here. The schematic tiles below are not captured activations.</p><p>At each location, the localization head predicts 4 values per default box; the confidence head predicts 21 scores per box. These heads are 1×1 convolutions in this graph. All this happens inside one <code>net.forward()</code>; Python does not call separate MobileNet and SSD functions.</p><p><a href="../../src/vision/detect_image.py">infer_once()</a> · <a href="https://github.com/chuanqi305/MobileNet-SSD/blob/bb17b6c3eef36d80be441ae8e5339be66e8e3b7a/deploy.prototxt">Exact graph and layer names</a></p>',
    );
    $("scene-controls").innerHTML =
      range("bridge-head", "Inspect prediction scale", 0, 5, 1, head) +
      '<button id="trace-features" type="button">Trace the selected feature map</button>';
    slider("bridge-head", (v) => {
      head = v;
      phase = 0;
    });
    click("trace-features", () => {
      phase = (phase + 1) % 4;
    });
    makeCanvas(540);
  }

  /** Draw the two MobileNet taps, extra SSD scales, and parallel prediction heads. @returns {void} */
  function renderBridge() {
    const ctx = canvas(),
      h = M.HEADS[head],
      count = M.priors(head, 0, 0).length;
    ctx.fillStyle = "#113c37";
    ctx.fillRect(18, 20, 365, 205);
    ctx.fillStyle = "#3b3021";
    ctx.fillRect(395, 20, 588, 490);
    text(ctx, "MOBILENET · feature extraction", 35, 47, C.teal, 18);
    text(ctx, "SSD · extra scales and object prediction", 410, 47, C.amber, 18);
    ctx.drawImage(source, 30, 76, 100, 85);
    text(ctx, "300×300×3", 30, 181, C.muted, 12);
    card(ctx, 150, 80, 100, 65, C.teal, "conv11", "19×19×512");
    card(ctx, 270, 80, 100, 65, C.teal, "conv13", "10×10×1024");
    arrow(ctx, 133, 112, 147, 112, C.teal, true);
    arrow(ctx, 253, 112, 267, 112, C.teal, true);
    const extraXs = [410, 550, 690, 830];
    for (let i = 2; i < 6; i += 1) {
      const node = M.HEADS[i],
        x = extraXs[i - 2];
      card(
        ctx,
        x,
        80,
        130,
        65,
        head === i ? C.amber : C.line,
        node.name,
        `${node.grid}×${node.grid}×${node.channels}`,
      );
      arrow(ctx, i === 2 ? 373 : x - 7, 112, x - 3, 112, C.amber, head >= i);
    }
    text(
      ctx,
      "Intervening MobileNet layers are collapsed into these arrows.",
      30,
      208,
      C.muted,
      12,
    );
    const selectedX =
      head === 0 ? 200 : head === 1 ? 320 : extraXs[head - 2] + 65;
    arrow(
      ctx,
      selectedX,
      148,
      selectedX,
      260,
      head < 2 ? C.teal : C.amber,
      true,
    );
    arrow(ctx, selectedX, 260, 560, 290, C.amber, true);
    card(
      ctx,
      425,
      295,
      270,
      85,
      C.amber,
      `${h.grid} × ${h.grid} × ${h.channels}`,
      `Feature tensor from ${h.name}`,
    );
    arrow(ctx, 695, 315, 755, 285, C.purple, phase % 4 >= 1);
    arrow(ctx, 695, 355, 755, 405, C.blue, phase % 4 >= 1);
    card(
      ctx,
      760,
      245,
      200,
      90,
      C.purple,
      "BOX OFFSETS",
      `${h.grid}×${h.grid}×${count * 4}`,
    );
    card(
      ctx,
      760,
      365,
      200,
      90,
      C.blue,
      "CLASS SCORES",
      `${h.grid}×${h.grid}×${count * 21}`,
    );
    text(ctx, `${count} boxes × 4 values`, 860, 318, C.muted, 12, "center");
    text(ctx, `${count} boxes × 21 scores`, 860, 438, C.muted, 12, "center");
    text(ctx, "Feature-map stack", 35, 285, C.ink, 16);
    const tile = 130 / h.grid;
    for (let layer = 2; layer >= 0; layer -= 1) {
      const left = 35 + layer * 8,
        top = 310 - layer * 8;
      ctx.fillStyle = "#14372f";
      ctx.fillRect(left, top, 130, 130);
      ctx.strokeStyle = C.teal;
      ctx.strokeRect(left, top, 130, 130);
      if (layer === 0) {
        for (let y = 0; y < h.grid; y += 1) {
          for (let x = 0; x < h.grid; x += 1) {
            ctx.fillStyle = (x + y * 3) % 5 === 0 ? "#356e60" : "#214b42";
            ctx.fillRect(
              left + x * tile,
              top + y * tile,
              tile - 0.5,
              tile - 0.5,
            );
          }
        }
        ctx.strokeStyle = C.amber;
        ctx.lineWidth = 2;
        ctx.strokeRect(
          left + (phase % h.grid) * tile,
          top + Math.floor(h.grid / 2) * tile,
          tile,
          tile,
        );
      }
    }
    arrow(ctx, 184, 365, 230, 365, C.amber, true);
    for (let i = 0; i < 6; i += 1) {
      ctx.fillStyle = i === phase % 6 ? C.teal : "#2c5954";
      ctx.fillRect(238, 302 + i * 24, 48, 22);
      text(ctx, `f${i}`, 262, 318 + i * 24, C.ink, 12, "center");
    }
    text(ctx, `… ${h.channels} channels`, 205, 467, C.teal, 13);
    text(
      ctx,
      "Schematic tiles; not measured activations.",
      35,
      497,
      C.muted,
      12,
    );
    arrow(ctx, 290, 365, 420, 337, C.amber, true);
    $("readout").innerHTML =
      `<strong>MobileNet’s role:</strong> represent visual patterns across space and channels. <strong>SSD’s role:</strong> convert those features into ${count} candidate boxes and their class scores at each location of the selected ${h.grid}×${h.grid} grid.`;
    $("extra").innerHTML =
      `<div class="stats"><div class="stat">Selected feature-map values<strong>${(h.grid * h.grid * h.channels).toLocaleString()}</strong>${h.grid} rows × ${h.grid} columns × ${h.channels} channels</div><div class="stat">Default boxes on this map<strong>${h.grid * h.grid * count}</strong>${count} reference shapes per location</div><div class="stat">Predictions per location<strong>${count * 4} + ${count * 21}</strong>offset values + class scores</div></div>`;
  }

  /** Resolve the currently selected real default-box geometry. @returns {object} */
  function currentPrior() {
    const h = M.HEADS[head];
    cellX = Math.min(cellX, h.grid - 1);
    cellY = Math.min(cellY, h.grid - 1);
    const choices = M.priors(head, cellX, cellY);
    priorIndex %= choices.length;
    return choices[priorIndex];
  }

  /** Draw a box in normalized image coordinates, allowing out-of-image edges. @param {CanvasRenderingContext2D} ctx @param {number[]} box @param {number[]} area [x,y,w,h]. @param {string} color @param {string} label @param {boolean} dashed @returns {void} */
  function drawBox(ctx, box, area, color, label = "", dashed = false) {
    const [x, y, w, h] = area;
    ctx.strokeStyle = color;
    ctx.lineWidth = 2.5;
    ctx.setLineDash(dashed ? [7, 5] : []);
    ctx.strokeRect(
      x + box[0] * w,
      y + box[1] * h,
      (box[2] - box[0]) * w,
      (box[3] - box[1]) * h,
    );
    ctx.setLineDash([]);
    if (label) {
      const tx = x + box[0] * w,
        ty = y + box[1] * h;
      ctx.fillStyle = "#0c1420";
      ctx.fillRect(tx, ty - 22, Math.max(70, label.length * 7.4), 22);
      text(ctx, label, tx + 4, ty - 6, color, 12);
    }
  }

  /** Configure the grid/cell/shape explorer for the pinned SSD priors. @returns {void} */
  function setupAnchors() {
    heading(
      "Default boxes are reference shapes at grid locations.",
      "Select a scale, then click the image to choose a grid cell. Reveal its alternative box shapes. All six scales predict during the same forward pass.",
      "Actual prior geometry",
      "<p>Default boxes are not extracted camera frames or separate image crops. Each cell is associated with reference centers, sizes and aspect ratios. The learned predictor adjusts these references to fit objects.</p><p>This graph uses 19²×3 + 10²×6 + 5²×6 + 3²×6 + 2²×6 + 1²×6 = <strong>1,917 priors</strong>. Minimum square sides are 60, 105, 150, 195, 240 and 285 on the 300-pixel input. Sizes overlap; grids are not hard small/medium/large class assignments.</p><p>Center: <code>((column+0.5)/grid, (row+0.5)/grid)</code>. For aspect ratio r: <code>w=s√r, h=s/√r</code>. The extra square uses <code>√(min_size×max_size)</code>. The first map has no extra square. <code>clip:false</code> permits reference boxes outside the image.</p>",
    );
    currentPrior();
    $("scene-controls").innerHTML =
      range("anchor-head", "Smaller → larger reference scale", 0, 5, 1, head) +
      range(
        "anchor-shape",
        "Shape at selected cell",
        0,
        M.priors(head, 0, 0).length - 1,
        1,
        priorIndex,
      ) +
      '<button id="all-centers" type="button">Show / hide all grid centers</button>';
    slider("anchor-head", (v) => {
      head = v;
      cellX = Math.floor(M.HEADS[head].grid / 2);
      cellY = cellX;
      priorIndex = 0;
      $("anchor-shape").max = String(M.priors(head, 0, 0).length - 1);
      $("anchor-shape").value = "0";
      $("anchor-shape-value").textContent = "0";
    });
    slider("anchor-shape", (v) => {
      priorIndex = v;
    });
    click("all-centers", () => {
      centers = !centers;
    });
    makeCanvas(570);
    $("diagram").addEventListener("click", (event) => {
      const rect = event.currentTarget.getBoundingClientRect(),
        x = ((event.clientX - rect.left) * 1000) / rect.width,
        y = ((event.clientY - rect.top) * 570) / rect.height;
      if (x >= 130 && x <= 550 && y >= 80 && y <= 500) {
        const n = M.HEADS[head].grid;
        cellX = Math.min(n - 1, Math.floor(((x - 130) / 420) * n));
        cellY = Math.min(n - 1, Math.floor(((y - 80) / 420) * n));
        render();
      }
    });
  }

  /** Draw one cell's default boxes over the actual image with scale readouts. @returns {void} */
  function renderAnchors() {
    const ctx = canvas(),
      h = M.HEADS[head],
      prior = currentPrior(),
      boxes = M.priors(head, cellX, cellY),
      area = [130, 80, 420, 420];
    ctx.drawImage(source, ...area);
    text(ctx, `${h.name} · ${h.grid}×${h.grid} grid`, 130, 38, C.teal, 20);
    text(ctx, "Square 300×300 detector view", 130, 61, C.muted, 13);
    ctx.strokeStyle = "#79b8c977";
    ctx.lineWidth = 1;
    for (let i = 0; i <= h.grid; i += 1) {
      const t = i / h.grid;
      ctx.beginPath();
      ctx.moveTo(130 + t * 420, 80);
      ctx.lineTo(130 + t * 420, 500);
      ctx.moveTo(130, 80 + t * 420);
      ctx.lineTo(550, 80 + t * 420);
      ctx.stroke();
    }
    if (centers)
      for (let y = 0; y < h.grid; y += 1)
        for (let x = 0; x < h.grid; x += 1) {
          ctx.fillStyle = C.teal;
          ctx.beginPath();
          ctx.arc(
            130 + ((x + 0.5) / h.grid) * 420,
            80 + ((y + 0.5) / h.grid) * 420,
            2,
            0,
            Math.PI * 2,
          );
          ctx.fill();
        }
    ctx.save();
    ctx.beginPath();
    ctx.rect(0, 65, 630, 490);
    ctx.clip();
    boxes.forEach((box, i) =>
      drawBox(
        ctx,
        M.corners(box),
        area,
        i === priorIndex ? C.amber : "#b7d2e066",
        "",
        i !== priorIndex,
      ),
    );
    ctx.restore();
    ctx.fillStyle = C.amber;
    ctx.beginPath();
    ctx.arc(130 + prior.cx * 420, 80 + prior.cy * 420, 5, 0, Math.PI * 2);
    ctx.fill();
    card(
      ctx,
      665,
      90,
      290,
      75,
      C.amber,
      `Cell (${cellX}, ${cellY})`,
      `${boxes.length} boxes share this center`,
    );
    text(ctx, prior.label, 665, 205, C.amber, 25);
    text(ctx, `Width ${f(prior.w * 300)} px`, 665, 247, C.ink, 20);
    text(ctx, `Height ${f(prior.h * 300)} px`, 665, 279, C.ink, 20);
    text(
      ctx,
      `Center (${f(prior.cx * 300)}, ${f(prior.cy * 300)})`,
      665,
      321,
      C.muted,
      15,
    );
    text(
      ctx,
      `${h.grid * h.grid * boxes.length} priors on this map`,
      665,
      376,
      C.teal,
      18,
    );
    text(ctx, "1,917 across all six maps", 665, 406, C.muted, 15);
    text(ctx, "The border of the image is not a", 665, 461, C.muted, 13);
    text(ctx, "constraint on a default box’s extent.", 665, 482, C.muted, 13);
    $("readout").innerHTML =
      `The selected <strong>${prior.label}</strong> is a predefined starting geometry. Its presence does not mean an object was found. A larger grid has more locations; a larger box covers more of the input. Those are different properties.`;
    $("extra").innerHTML =
      '<p class="small">Switching grids changes the feature-map head and reference boxes, not the camera frame. Very wide boxes can extend beyond the drawing viewport; the numerical prior remains unclipped.</p>';
  }

  /** Create the exact center/size decoding controls plus illustrative class logits. @returns {void} */
  function setupDecode() {
    heading(
      "SSD predicts two things for every default box.",
      "Four offsets adjust the box. A separate set of scores describes its possible class. Move either set of controls and watch the corresponding output change.",
      "Actual formula · illustrative predictions",
      "<p>Box decoding in this graph uses <code>cx=prior_cx+0.1×tx×prior_w</code>, <code>cy=prior_cy+0.1×ty×prior_h</code>, <code>w=prior_w×exp(0.2×tw)</code>, and <code>h=prior_h×exp(0.2×th)</code>. Width/height remain positive.</p><p>Confidence heads produce 21 logits per prior; softmax converts them to class scores. Here you edit one logit to see that conversion. A high score is not measured detection accuracy. Offsets and logits on this screen are invented teaching values; the saved real result appears at the end.</p><p>The chosen default box carries over from the previous scene. The heads read features at the selected grid cell; they do not run the full network independently on each drawn rectangle.</p>",
    );
    $("scene-controls").innerHTML =
      offsets
        .map((v, i) =>
          range(
            "offset-" + i,
            ["Center X: tx", "Center Y: ty", "Width: tw", "Height: th"][i],
            -4,
            4,
            0.1,
            v,
          ),
        )
        .join("") +
      '<label>Class to adjust<select id="class-id">' +
      M.LABELS.map((name, i) => `<option value="${i}">${name}</option>`).join(
        "",
      ) +
      "</select></label>" +
      range("class-logit", "Class logit", -3, 8, 0.1, logit);
    offsets.forEach((_, i) =>
      slider("offset-" + i, (v) => {
        offsets[i] = v;
      }),
    );
    $("class-id").value = String(classId);
    $("class-id").addEventListener("change", () => {
      classId = Number($("class-id").value);
      render();
    });
    slider("class-logit", (v) => {
      logit = v;
    });
    makeCanvas(500);
  }

  /** Draw the selected prior and decoded prediction while exposing independent scores. @returns {void} */
  function renderDecode() {
    const ctx = canvas(),
      prior = currentPrior(),
      box = M.decode(prior, offsets),
      area = [120, 65, 380, 380];
    ctx.drawImage(source, ...area);
    ctx.save();
    ctx.beginPath();
    ctx.rect(0, 0, 600, 500);
    ctx.clip();
    drawBox(ctx, M.corners(prior), area, C.amber, "default box", true);
    drawBox(ctx, M.corners(box), area, C.teal, "adjusted box");
    ctx.restore();
    const logits = M.LABELS.map((_, i) =>
        i === classId ? logit : i === 0 ? 1 : -1,
      ),
      scores = M.softmax(logits),
      top = scores.indexOf(Math.max(...scores));
    card(
      ctx,
      630,
      60,
      320,
      78,
      C.teal,
      "LOCALIZATION",
      `cx=${f(box.cx)}  cy=${f(box.cy)}`,
    );
    text(
      ctx,
      `w=${f(box.w)}  h=${f(box.h)} (normalized)`,
      645,
      168,
      C.muted,
      15,
    );
    card(
      ctx,
      630,
      225,
      320,
      90,
      C.blue,
      "CLASSIFICATION",
      `${M.LABELS[top]} · ${scores[top].toFixed(3)}`,
    );
    text(ctx, "21 scores for this same candidate box", 640, 355, C.muted, 14);
    text(ctx, "20 object classes + background", 640, 382, C.muted, 14);
    $("readout").innerHTML =
      `<strong>Geometry and category are parallel predictions.</strong> The box offsets change location/size; the class logit changes the score distribution. Current top class: <strong>${M.LABELS[top]}</strong>.`;
    $("extra").innerHTML =
      '<div class="score-grid">' +
      scores
        .map(
          (value, i) =>
            `<div class="score-row"><span>${M.LABELS[i]}</span><div><i style="width:${Math.max(0.5, value * 100)}%"></i></div><span>${value.toFixed(3)}</span></div>`,
        )
        .join("") +
      "</div>";
  }

  /** Set up duplicate removal with independent overlap and score controls. @returns {void} */
  function setupNms() {
    heading(
      "Many boxes can describe the same object.",
      "Step through graph score filtering, same-class overlap suppression, then EdgeXR’s score threshold. The candidates here are an artificial example over your image.",
      "Teaching candidates · actual policy",
      "<p>IoU = intersection area / union area. NMS sorts candidates by score and suppresses lower-scored same-class boxes that overlap a retained box above the IoU threshold. It does not simply merge every touching box.</p><p>Baseline graph settings: confidence threshold 0.25, NMS IoU threshold 0.45, top_k=100, keep_top_k=100. EdgeXR’s <code>parse_detections()</code> subsequently accepts scores ≥0.5. The small example never reaches the top-k limits. NMS is inside the loaded graph, not reimplemented by EdgeXR’s Python parser.</p><p>Notice G: it overlaps a chair but has a different hypothetical class. Class-wise NMS alone does not remove it. The actual saved model output is shown on the final screen.</p>",
    );
    $("scene-controls").innerHTML =
      range("nms-stage", "Filtering step", 0, 3, 1, nmsPhase) +
      range("nms-iou", "NMS IoU threshold", 0, 1, 0.05, nmsThreshold) +
      range("app-score", "EdgeXR score cutoff", 0, 1, 0.05, appThreshold) +
      range("candidate", "Inspect overlap with A", 1, 6, 1, selectedCandidate);
    slider("nms-stage", (v) => {
      nmsPhase = v;
    });
    slider("nms-iou", (v) => {
      nmsThreshold = v;
    });
    slider("app-score", (v) => {
      appThreshold = v;
    });
    slider("candidate", (v) => {
      selectedCandidate = v;
    });
    makeCanvas(460);
  }

  /** Show score gates, overlap area and class-wise NMS decisions. @returns {void} */
  function renderNms() {
    const ctx = canvas(),
      area = [25, 80, 650, 365],
      decisions = M.suppress(candidates, nmsThreshold, appThreshold),
      chosen = candidates[selectedCandidate],
      a = candidates[0];
    ctx.drawImage(source, ...area);
    text(
      ctx,
      [
        "0 · all teaching candidates",
        "1 · graph score > 0.25",
        "2 · same-class NMS",
        "3 · EdgeXR score cutoff",
      ][nmsPhase],
      25,
      35,
      C.amber,
      21,
    );
    const intersection = [
      Math.max(a.box[0], chosen.box[0]),
      Math.max(a.box[1], chosen.box[1]),
      Math.min(a.box[2], chosen.box[2]),
      Math.min(a.box[3], chosen.box[3]),
    ];
    if (
      intersection[2] > intersection[0] &&
      intersection[3] > intersection[1]
    ) {
      ctx.fillStyle = "#c5a3ff77";
      ctx.fillRect(
        area[0] + intersection[0] * area[2],
        area[1] + intersection[1] * area[3],
        (intersection[2] - intersection[0]) * area[2],
        (intersection[3] - intersection[1]) * area[3],
      );
    }
    decisions.forEach((box) => {
      const suppressed =
        (nmsPhase >= 1 && box.reason.startsWith("graph")) ||
        (nmsPhase >= 2 && box.reason.startsWith("overlaps")) ||
        (nmsPhase >= 3 && box.reason.startsWith("app"));
      ctx.globalAlpha = suppressed ? 0.2 : 1;
      drawBox(
        ctx,
        box.box,
        area,
        box.id === chosen.id
          ? C.purple
          : suppressed
            ? C.amber
            : nmsPhase >= 2
              ? C.teal
              : C.blue,
        `${box.id} ${box.label} ${box.score}`,
        suppressed,
      );
      ctx.globalAlpha = 1;
    });
    text(ctx, `A ∩ ${chosen.id}`, 735, 125, C.purple, 23);
    text(
      ctx,
      `IoU = ${M.iou(a.box, chosen.box).toFixed(3)}`,
      735,
      169,
      C.ink,
      22,
    );
    text(ctx, `${a.label} / ${chosen.label}`, 735, 206, C.muted, 14);
    text(ctx, "Purple tint = intersection", 705, 260, C.purple, 14);
    text(ctx, "Faded = rejected by this step", 705, 292, C.muted, 14);
    text(ctx, "Dashed = rejected outline", 705, 320, C.muted, 14);
    $("readout").innerHTML =
      `Compare A and ${chosen.id}: IoU <strong>${M.iou(a.box, chosen.box).toFixed(3)}</strong>, threshold ${nmsThreshold.toFixed(2)}. ${chosen.label === a.label ? "They share a class, so sufficient overlap can suppress the lower score." : "They have different classes; this class-wise NMS does not compare them for suppression."}`;
    $("extra").innerHTML =
      '<div class="vote-list">' +
      decisions
        .map((box) => {
          let reason =
            nmsPhase === 0
              ? "waiting"
              : box.reason.startsWith("graph")
                ? box.reason
                : nmsPhase === 1
                  ? "passed graph score gate"
                  : box.reason.startsWith("overlaps")
                    ? box.reason
                    : nmsPhase === 2
                      ? "retained by NMS"
                      : box.reason;
          return `<div class="vote ${reason === "keep" ? "keep" : reason.startsWith("overlaps") || reason.startsWith("graph") || reason.startsWith("app") ? "reject" : ""}">${box.id} · ${box.label} · ${box.score.toFixed(2)} → ${reason}</div>`;
        })
        .join("") +
      "</div>";
  }

  /** Configure a semantic-stage comparison rather than a latency race. @returns {void} */
  function setupStages() {
    heading(
      "“Two stages” means proposals, then regional prediction.",
      "Both architectures share feature computation. The difference is how candidate regions enter the object-prediction process.",
      "Architecture metaphor",
      '<p>SSD predicts default-box offsets and class scores densely from multiple feature maps, without first selecting region proposals for a second region-specific predictor. Faster R-CNN uses a region proposal network, selects proposals, then performs region-based classification and box refinement using shared features.</p><p>Faster R-CNN’s proposal network can also use anchors. Anchors by themselves do not define one-stage versus two-stage detection. These diagrams omit implementation details, and their moving packets are a teaching sequence—not measured timing or a claim that every two-stage model is identical.</p><p><a href="https://arxiv.org/abs/1506.01497">Faster R-CNN paper</a> · <a href="https://arxiv.org/abs/1512.02325">SSD paper</a></p>',
    );
    $("scene-controls").innerHTML = range(
      "architecture-step",
      "Follow the information",
      0,
      4,
      1,
      phase % 5,
    );
    slider("architecture-step", (v) => {
      phase = v;
    });
    makeCanvas(400);
  }

  /** Animate the extra proposal selection and region-specific prediction stage. @returns {void} */
  function renderStages() {
    const ctx = canvas(),
      step = phase % 5;
    text(ctx, "YOUR SSD PATH", 25, 40, C.teal, 19);
    text(ctx, "TWO-STAGE EXAMPLE · FASTER R-CNN", 25, 222, C.amber, 19);
    const xs = [25, 215, 415, 615, 815],
      top = [
        "Image",
        "Shared features",
        "Dense box + class",
        "Filter / NMS",
        "Objects",
      ],
      bottom = [
        "Image",
        "Shared features",
        "Propose regions",
        "Classify + refine",
        "Objects",
      ];
    for (let i = 0; i < 5; i += 1) {
      card(
        ctx,
        xs[i],
        70,
        160,
        75,
        i === step ? C.teal : C.line,
        top[i],
        i === 2 ? "all default-box heads" : "",
      );
      card(
        ctx,
        xs[i],
        255,
        160,
        75,
        i === step ? C.amber : C.line,
        bottom[i],
        i === 3 ? "selected regions" : "",
      );
      if (i < 4) {
        arrow(ctx, xs[i] + 163, 107, xs[i + 1] - 4, 107, C.teal, i === step);
        arrow(ctx, xs[i] + 163, 292, xs[i + 1] - 4, 292, C.amber, i === step);
      }
    }
    arrow(ctx, 295, 335, 695, 350, C.blue, step >= 3);
    text(
      ctx,
      "Shared feature values also feed the regional predictor",
      335,
      380,
      C.blue,
      13,
    );
    $("readout").innerHTML = [
      "Both start with an image.",
      "Both compute reusable image features.",
      "SSD predicts boxes and classes densely. The proposal stage instead selects likely regions.",
      "The two-stage regional head now classifies and refines selected regions. SSD is already filtering its dense predictions.",
      "Both can output labelled boxes. “One-stage” does not mean one neural-network layer.",
    ][step];
    $("extra").innerHTML = "";
  }

  /** Connect observed saved predictions to the project source functions. @returns {void} */
  function setupSaved() {
    heading(
      "Back in EdgeXR: the observed boxes on your Pi image.",
      "These two detections are from your saved report. The intermediate animations explain how the architecture works; these are the actual recorded final predictions.",
      "Saved Pi result",
      '<p><code>infer_once()</code> creates the 1×3×300×300 blob and calls <code>net.forward()</code>. The Caffe graph contains MobileNet, SSD heads, decoding and NMS. <code>parse_detections()</code> filters scores and maps normalized boxes to original image pixels.</p><p>In live mode, <code>detect_latest()</code> chooses the newest frame at a target of at most two starts per second. <code>DetectionState.publish()</code> records its source identity and age; the browser can show the older boxes over a newer preview frame. Two OpenCV threads and the 2Hz target are separate settings.</p><p><a href="../../src/vision/detect_image.py">infer_once / parse_detections</a> · <a href="../../src/vision/live_detector.py">CpuDetector / detect_latest / DetectionState</a> · <a href="../../src/app/preview.html">render</a> · <a href="OBJECT_DETECTION.md">Full code tour</a></p>',
    );
    $("scene-controls").innerHTML =
      '<button id="saved-chair" type="button">Trace the saved chair box</button><button id="saved-table" type="button">Trace the saved table box</button>';
    filter = 0;
    click("saved-chair", () => {
      filter = 1;
    });
    click("saved-table", () => {
      filter = 0;
    });
    makeCanvas(470);
  }

  /** Display only measured predictions and their independent x/y coordinate mapping. @returns {void} */
  function renderSaved() {
    const ctx = canvas(),
      area = [25, 45, 710, 399],
      selected = D.detections[filter];
    ctx.drawImage(source, ...area);
    D.detections.forEach((d, i) => {
      const box = d.box_xyxy.map((v, j) => v / (j % 2 ? 720 : 1280));
      drawBox(
        ctx,
        box,
        area,
        i === filter ? C.teal : C.amber,
        `${d.label} ${d.confidence.toFixed(3)}`,
      );
    });
    text(ctx, "SAVED PI TRIAL", 760, 70, C.teal, 15);
    text(ctx, selected.label, 760, 112, C.ink, 23);
    text(ctx, `score ${selected.confidence.toFixed(3)}`, 760, 146, C.muted, 15);
    const [x1, y1, x2, y2] = selected.box_xyxy;
    text(ctx, `left ${x1} · top ${y1}`, 760, 205, C.ink, 15);
    text(ctx, `right ${x2} · bottom ${y2}`, 760, 235, C.ink, 15);
    text(ctx, "Coordinates in 1280×720", 760, 280, C.muted, 13);
    $("readout").innerHTML =
      `Recorded <strong>${selected.label}</strong> box: <span class="equation">[${selected.box_xyxy.join(", ")}]</span>. X scales with the original width; Y scales with the original height. MobileNet supplies features; SSD predicts the box/class; EdgeXR maps and displays the result.`;
    $("extra").innerHTML =
      '<div class="stats"><div class="stat">Feature computation<strong>MobileNet</strong>Learned responses across space and channels</div><div class="stat">Object prediction<strong>SSD</strong>Additional scales, offsets, classes, decoding and NMS</div><div class="stat">Application behavior<strong>EdgeXR</strong>Newest-frame selection, threshold, mapping and display</div></div>';
  }

  const setups = [
    setupInput,
    () => setupSpatial(false),
    () => setupSpatial(true),
    setupPointwise,
    setupCompare,
    setupBridge,
    setupAnchors,
    setupDecode,
    setupNms,
    setupStages,
    setupSaved,
  ];
  const renders = [
    renderInput,
    () => renderSpatial(false),
    () => renderSpatial(true),
    renderPointwise,
    renderCompare,
    renderBridge,
    renderAnchors,
    renderDecode,
    renderNms,
    renderStages,
    renderSaved,
  ];

  /** Render only the selected scene, keeping active controls mounted. @returns {void} */
  function render() {
    if (!overview) renders[scene]();
  }

  /** Stop timed animation before changing the learner's context. @returns {void} */
  function pause() {
    if (timer !== null) window.clearInterval(timer);
    timer = null;
    $("play").textContent = "Play this scene";
  }

  /** Keep both navigation surfaces and playback bounds in agreement. @returns {void} */
  function navigation() {
    $("overview").hidden = !overview;
    $("lesson").hidden = overview;
    document.querySelectorAll("[data-scene]").forEach((button) => {
      if (!overview && Number(button.dataset.scene) === scene)
        button.setAttribute("aria-current", "step");
      else button.removeAttribute("aria-current");
    });
    $("back").disabled = overview || scene === 0;
    $("next").disabled = !overview && scene === titles.length - 1;
    $("play").disabled = overview;
    $("step").disabled = overview;
    $("reset").disabled = overview;
    $("progress").textContent = overview
      ? "Architecture overview"
      : `${scene + 1} / ${titles.length}`;
  }

  /** Enter a scene with a fresh animation position while retaining useful selections. @param {number} index @returns {void} */
  function go(index) {
    pause();
    scene = index;
    overview = false;
    phase = 0;
    pos = 0;
    filter = 0;
    stride = 1;
    padding = 0;
    bias = 0;
    $("scene-controls").replaceChildren();
    $("extra").replaceChildren();
    $("details").open = false;
    setups[scene]();
    navigation();
    render();
  }

  /** Advance one meaningful operation in the active scene, not an automatic chapter jump. @returns {void} */
  function advance() {
    if (scene === 0) {
      split = !split;
    } else if (scene === 1 || scene === 2) {
      const limit = scene === 1 ? 26 : 8;
      if (phase >= limit) {
        pos += 1;
        phase = 0;
      } else phase += 1;
    } else if (scene === 3) {
      selectedChannel = (selectedChannel + 1) % channels;
      $("point-channel").value = String(selectedChannel);
      $("point-channel-value").textContent = String(selectedChannel);
      syncWeight();
    } else if (scene === 4 || scene === 5) {
      phase += 1;
    } else if (scene === 6) {
      priorIndex = (priorIndex + 1) % M.priors(head, 0, 0).length;
      $("anchor-shape").value = String(priorIndex);
      $("anchor-shape-value").textContent = String(priorIndex);
    } else if (scene === 7) {
      phase += 1;
      offsets[0] = Math.sin(phase * 0.3) * 2;
      offsets[2] = Math.sin(phase * 0.2);
      [0, 2].forEach((i) => {
        $("offset-" + i).value = String(offsets[i]);
        $("offset-" + i + "-value").textContent = f(offsets[i]);
      });
    } else if (scene === 8) {
      nmsPhase = (nmsPhase + 1) % 4;
      $("nms-stage").value = String(nmsPhase);
      $("nms-stage-value").textContent = String(nmsPhase);
    } else if (scene === 9) {
      phase = (phase + 1) % 5;
      $("architecture-step").value = String(phase);
      $("architecture-step-value").textContent = String(phase);
    } else if (scene === 10) {
      filter = 1 - filter;
    }
    render();
    // Arithmetic scenes pause when one complete output has been explained.
    if ((scene === 1 && phase === 26) || (scene === 2 && phase === 8)) pause();
  }

  /** Start a scene's controllable timer; speed represents teaching pace only. @returns {void} */
  function play() {
    if (timer !== null) {
      pause();
      return;
    }
    timer = window.setInterval(advance, Number($("speed").value));
    $("play").textContent = "Pause";
  }

  /** Bind global navigation after the real image has loaded successfully. @returns {void} */
  function initialize() {
    let markup = "";
    titles.forEach((title, i) => {
      if (i === 0 || i === 2 || i === 6)
        markup += `<p class="chapter-title">${chapters[i === 0 ? 0 : i === 2 ? 1 : 2]}</p>`;
      markup += `<button type="button" class="chapter-button" data-scene="${i}"><span class="number">${String(i + 1).padStart(2, "0")}</span>${title}</button>`;
    });
    $("chapters").innerHTML = markup;
    $("route").innerHTML = titles
      .map(
        (title, i) =>
          `<button type="button" data-scene="${i}">${i + 1} · ${title}</button>`,
      )
      .join("");
    document
      .querySelectorAll("[data-scene]")
      .forEach((button) =>
        button.addEventListener("click", () =>
          go(Number(button.dataset.scene)),
        ),
      );
    document
      .querySelectorAll("[data-go]")
      .forEach((button) =>
        button.addEventListener("click", () => go(Number(button.dataset.go))),
      );
    $("overview-button").addEventListener("click", () => {
      pause();
      overview = true;
      navigation();
    });
    $("back").addEventListener("click", () => go(Math.max(0, scene - 1)));
    $("next").addEventListener("click", () =>
      go(overview ? 0 : Math.min(titles.length - 1, scene + 1)),
    );
    $("play").addEventListener("click", play);
    $("step").addEventListener("click", () => {
      pause();
      advance();
    });
    $("reset").addEventListener("click", () => {
      split = false;
      channels = 3;
      selectedChannel = 0;
      pointFilter = 0;
      customWeights.clear();
      head = 0;
      cellX = 3;
      cellY = 11;
      priorIndex = 0;
      centers = false;
      offsets = [0, 0, 0, 0];
      classId = 9;
      logit = 4;
      nmsPhase = 0;
      nmsThreshold = 0.45;
      appThreshold = 0.5;
      selectedCandidate = 1;
      diverse = false;
      go(scene);
    });
    $("speed").addEventListener("change", () => {
      if (timer !== null) {
        pause();
        play();
      }
    });
    navigation();
    $("status").textContent =
      "Ready · works offline · click a stage or start the guided lesson.";
  }

  if (!M || !D) {
    $("status").textContent =
      "Lesson data is missing. Keep the HTML, JavaScript, CSS and images together.";
    return;
  }
  source.onload = initialize;
  source.onerror = () => {
    $("status").textContent =
      "The recorded image could not load. Check images/detection-lesson-scene.png.";
  };
  source.src = D.image;
})();
