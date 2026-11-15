/* Interactive figures for orientation-explorer.html.
   Simulation arithmetic lives in orientation-math.js (EdgeOrientation); measured
   values below are copied from committed results and labelled on the page. */
(function () {
  "use strict";
  const O = window.EdgeOrientation, Charts = window.EdgeCharts;
  const $ = (id) => document.getElementById(id);
  const NEUTRAL = "#c3c2b7", INK = "#e5edf6", MUTED = "#98a8bb", LINE = "#2b394a";
  const signed = (v, d = 2) => `${v >= 0 ? "+" : "−"}${Math.abs(v).toFixed(d)}`;

  // Section 1: simulation charts, created once and redrawn on every control change.
  const angleChart = Charts.lines($("angle-chart"), {
    title: "Head angle: truth versus gyro estimate",
    series: [], x: { min: 0, max: O.CAPTURE_S, label: "time (s)", step: 2 },
    y: { min: -25, max: 25, label: "pan angle (°)", step: 10 }, height: 250, endLabels: true,
  });
  const rateChart = Charts.lines($("rate-chart"), {
    title: "Zoom: what the samples catch (3.0–4.2 s)",
    note: "Line: true turning speed during servo bursts. Stems: the gyro reads the thread actually took.",
    series: [], x: { min: 3.0, max: 4.2, label: "time (s)", step: 0.2, format: (v) => v.toFixed(1) },
    y: { min: -80, max: 10, label: "turning speed (°/s)", step: 20 }, height: 200,
  });

  /**
   * Read the controls, rerun the simulation and redraw every simulation figure.
   * @returns {void}
   */
  function update() {
    const o = { sleepMs: Number($("sleep").value), stepMs: Number($("burst").value),
      phase: Number($("phase").value), biasDps: Number($("bias").value), noiseDps: $("noise").checked ? 0.3 : 0 };
    $("sleep-out").textContent = `${o.sleepMs} ms`;
    $("burst-out").textContent = `${o.stepMs} ms`;
    $("phase-out").textContent = o.phase.toFixed(2);
    $("bias-out").textContent = `${o.biasDps.toFixed(2)} °/s`;
    const sim = O.simulate(o), T = o.stepMs / 1000;

    const truth = [];
    for (let t = 0; t <= O.CAPTURE_S + 1e-9; t += 0.01) truth.push([t, O.trueAngle(t, T)]);
    angleChart.redraw({ series: [
      { name: "true angle", color: NEUTRAL, points: truth, width: 2 },
      { name: "gyro estimate", color: "var(--s1)", points: sim.estimate, width: 2 },
    ] });

    const rate = [];
    for (let t = 3.0; t <= 4.2; t += 0.001) rate.push([t, O.trueRate(t, T)]);
    const peak = 2 / T;
    rateChart.redraw({ y: { min: -Math.ceil((peak + 8) / 20) * 20, max: 20, label: "turning speed (°/s)", step: 20 },
      series: [
        { name: "true speed", color: NEUTRAL, points: rate, width: 1.5 },
        { name: "gyro reads", color: "var(--s2)", points: sim.samples.filter(([t]) => t >= 3.0 && t <= 4.2), stems: true },
      ] });

    $("sim-readout").textContent =
      `reads per second   ${sim.readsPerSecond.toFixed(1)}  (pause ${o.sleepMs} ms + ${O.READ_OVERHEAD_MS} ms per read)\n` +
      `reads in 21.5 s    ${sim.samples.length}\n` +
      `peak burst speed   ${peak.toFixed(0)} °/s for ${o.stepMs} ms\n` +
      `true final angle   ${signed(sim.finalTruth)}°  (head returned)\n` +
      `estimate ends at   ${signed(sim.finalEstimate)}°\n` +
      `end error          ${signed(sim.error)}°`;

    // Every start offset at the current settings: the same physics, different luck.
    const rows = [];
    for (let p = 0; p < 0.951; p += 0.1) {
      const e = O.simulate({ ...o, phase: p }).error;
      rows.push({ label: `offset ${p.toFixed(1)}`, values: [Math.abs(e)], kind: Math.abs(p - o.phase) < 0.051 ? 1 : 0 });
    }
    Charts.bars($("phase-chart"), {
      title: "End error for ten start offsets",
      note: "Same motion and settings; only where the reads happen to fall changes.",
      series: [{ name: "other offsets", color: "var(--s1)" }, { name: "nearest to the slider", color: "var(--s2)" }],
      rows, unit: "°", digits: 2, labelWidth: 90, rowHeight: 22, rowPad: 10,
    });
  }
  ["sleep", "burst", "phase", "bias"].forEach((id) => $(id).addEventListener("input", update));
  $("noise").addEventListener("change", update);
  update();

  // Section 2: measured replay and three-policy runs.
  Charts.bars($("replay-chart"), {
    title: "Same recording, fewer samples",
    note: "Final gyro-only error after the head physically returned.",
    series: [{ name: "every read (≈80/s)", color: "var(--s3)" }, { name: "every 4th read (≈20/s)", color: "var(--s1)" }],
    rows: [
      { label: "all reads", values: [1.77], kind: 0 },
      { label: "every 4th, offset 1", values: [7.13], kind: 1 },
      { label: "every 4th, offset 2", values: [3.44], kind: 1 },
      { label: "every 4th, offset 3", values: [13.10], kind: 1 },
      { label: "every 4th, offset 4", values: [3.24], kind: 1 },
    ], unit: "°", digits: 2, labelWidth: 140,
  });
  Charts.scatter($("policy-chart"), {
    title: "Return error versus recorder CPU (6 runs)",
    note: "Lower-left is better. CPU is the recorder process, % of one core.",
    series: [{ name: "10 ms pause", color: "var(--s1)" }, { name: "50 ms pause", color: "var(--s2)" }, { name: "adaptive", color: "var(--s3)" }],
    points: [
      { x: 1.911, y: 2.678, series: 1, label: "", note: "imu-policy-50ms-01 · 18.95 reads/s" },
      { x: 4.152, y: 1.037, series: 0, label: "", note: "imu-policy-10ms-01 · 77.34 reads/s" },
      { x: 4.012, y: 0.739, series: 2, label: "", note: "imu-policy-adaptive-01 · 70.34 reads/s" },
      { x: 4.057, y: 0.553, series: 2, label: "", note: "imu-policy-adaptive-02 · 70.24 reads/s" },
      { x: 3.919, y: 1.085, series: 0, label: "", note: "imu-policy-10ms-02 · 77.48 reads/s" },
      { x: 2.004, y: 9.847, series: 1, label: "", note: "imu-policy-50ms-02 · 18.94 reads/s" },
    ],
    x: { label: "recorder CPU (% of one core)", max: 5 }, y: { label: "return error (°)", max: 10 }, height: 260,
  });

  // Section 4: IMU axes and fitted camera axes from one origin.
  const M = [[-0.05508889386133572, 0.04336969080146373, 0.9975391138661782],
    [0.18820433128499112, 0.9815991693448528, -0.03228312913991416],
    [-0.9805836748889428, 0.18596273998110616, -0.06223757610974021]];
  $("tilt-deg").textContent = `${(Math.asin(M[1][0]) * 180 / Math.PI).toFixed(0)}°`;

  /**
   * Isometric screen position for an IMU-frame vector.
   * @param {number[]} v IMU [x, y, z].
   * @param {number} s Scale in SVG units.
   * @returns {number[]} SVG [x, y] around the origin (230, 165).
   */
  function iso(v, s) {
    const c = Math.cos(Math.PI / 6), n = Math.sin(Math.PI / 6);
    return [230 + s * (-v[0] + v[1]) * c, 165 + s * ((v[0] + v[1]) * n - v[2])];
  }

  /**
   * Text element placed a fixed distance beyond an arrow tip, along the arrow,
   * anchored on the side the arrow points to, so labels never sit on the line.
   * @param {number} ox Arrow origin x.
   * @param {number} oy Arrow origin y.
   * @param {number} x Tip x.
   * @param {number} y Tip y.
   * @param {string} text Label.
   * @param {string} fill Text colour.
   * @param {boolean} [leftOfVertical] Put labels of near-vertical arrows left of the tip.
   * @returns {string} SVG markup.
   */
  function tipLabel(ox, oy, x, y, text, fill, leftOfVertical = false) {
    const len = Math.hypot(x - ox, y - oy) || 1, dx = (x - ox) / len, dy = (y - oy) / len;
    let anchor = dx > 0.35 ? "start" : dx < -0.35 ? "end" : "middle", nudge = 0;
    if (anchor === "middle" && leftOfVertical) { anchor = "end"; nudge = -10; }
    return `<text x="${x + 14 * dx + nudge}" y="${y + 14 * dy + 4 + (dy > 0.5 ? 6 : 0)}" fill="${fill}" font-size="12" text-anchor="${anchor}">${text}</text>`;
  }

  /**
   * SVG arrow from the origin along a vector, labelled beyond its tip.
   * @param {number[]} v Vector in IMU coordinates.
   * @param {string} color Stroke colour.
   * @param {string} label Text near the tip.
   * @param {number} width Stroke width.
   * @param {number} s Scale (camera axes are drawn longer so their labels clear the IMU labels).
   * @returns {string} SVG markup.
   */
  function axisArrow(v, color, label, width, s) {
    const [x, y] = iso(v, s);
    return `<line x1="230" y1="165" x2="${x}" y2="${y}" stroke="${color}" stroke-width="${width}" marker-end="url(#tip-${color.replace(/[^a-z0-9]/gi, "")})"/>` +
      tipLabel(230, 165, x, y, label, color === MUTED ? MUTED : INK, color === MUTED);
  }
  const colors = { right: "#3987e5", down: "#199e70", forward: "#65d8bb" };
  const markers = [MUTED, ...Object.values(colors)].map((c) =>
    `<marker id="tip-${c.replace(/[^a-z0-9]/gi, "")}" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="${c}"/></marker>`).join("");
  $("axes-svg").innerHTML = `<defs>${markers}</defs>` +
    axisArrow([1, 0, 0], MUTED, "IMU x", 1.5, 92) + axisArrow([0, 1, 0], MUTED, "IMU y", 1.5, 92) + axisArrow([0, 0, 1], MUTED, "IMU z", 1.5, 92) +
    axisArrow(M[0], colors.right, "camera right", 3, 128) + axisArrow(M[1], colors.down, "camera down", 3, 128) + axisArrow(M[2], colors.forward, "camera forward", 3.5, 128) +
    `<circle cx="230" cy="165" r="4" fill="${INK}"/>`;

  // Section 5: two orders of the same 90° turns, composed in the camera (body) frame.
  const yawRight = O.fromRotationVector([0, 90, 0]);   // about the camera's down axis
  const tiltUp = O.fromRotationVector([90, 0, 0]);     // about the camera's right axis

  /**
   * Oblique drawing position: right → screen right, up → screen up, forward → up-right.
   * @param {number[]} v Camera-start coordinates [x right, y down, z forward].
   * @returns {number[]} SVG [x, y].
   */
  function oblique(v) { return [150 + 78 * (v[0] + 0.55 * v[2]), 140 - 78 * (-v[1] + 0.38 * v[2])]; }

  /**
   * Draw the start frame faintly and the final camera axes for one turn order.
   * @param {string} id SVG element id.
   * @param {number[]} q Final orientation quaternion.
   * @returns {string} Name of where the camera ends up looking.
   */
  function drawOrder(id, q) {
    const ref = [[[1, 0, 0], "start right"], [[0, -1, 0], "start up"], [[0, 0, 1], "start forward"]];
    let svg = "";
    // Start-frame labels sit beyond and above each dashed tip; final-axis labels sit right of their tips.
    for (const [v, name] of ref) {
      const [x, y] = oblique(v), [lx, ly] = oblique(v.map((c) => c * 1.3));
      svg += `<line x1="150" y1="140" x2="${x}" y2="${y}" stroke="${LINE}" stroke-width="2" stroke-dasharray="5 5"/><text x="${lx}" y="${ly - 12}" fill="${MUTED}" font-size="11" text-anchor="middle">${name}</text>`;
    }
    const axes = [[[0, 0, 1], colors.forward, "camera looks", 4], [[1, 0, 0], colors.right, "camera right", 2.5], [[0, -1, 0], "#efb77b", "camera top", 2.5]];
    for (const [v, color, name, w] of axes) {
      const r = O.rotate(q, v), [x, y] = oblique(r.map((c) => c * 0.9));
      svg += `<line x1="150" y1="140" x2="${x}" y2="${y}" stroke="${color}" stroke-width="${w}" stroke-linecap="round"/><circle cx="${x}" cy="${y}" r="${w + 1}" fill="${color}"/>` + tipLabel(150, 140, x, y, name, INK);
    }
    $(id).innerHTML = svg + `<circle cx="150" cy="140" r="4" fill="${INK}"/>`;
    const f = O.rotate(q, [0, 0, 1]).map((c) => Math.round(c * 1000) / 1000);
    if (f[1] < -0.9) return "straight up";
    if (f[0] > 0.9) return "to the right, lying on its side";
    return `(${f.join(", ")})`;
  }
  const a = drawOrder("order-a", O.multiply(yawRight, tiltUp));
  const b = drawOrder("order-b", O.multiply(tiltUp, yawRight));
  $("order-a-cap").innerHTML = `<strong>Turn right 90°, then tilt up 90°</strong> about the camera’s own right axis → the camera looks <strong>${a}</strong>.`;
  $("order-b-cap").innerHTML = `<strong>Tilt up 90°, then turn 90°</strong> about the camera’s own down axis (which now points forward) → the camera looks <strong>${b}</strong>.`;

  // Worked update computed by the same function the page simulation uses.
  const q1 = O.step([1, 0, 0, 0], [0, 30, 0], [0, 30, 0], 0.0129);
  $("quat-math").textContent =
    `per gyro read (≈12.9 ms apart with a 10 ms pause):\n` +
    `  average rate   ω = (previous + current) / 2      e.g. (0, 30, 0) °/s about the camera's down axis\n` +
    `  small turn     θ = |ω| × dt = 30 °/s × 0.0129 s  = 0.387°\n` +
    `  increment      Δq = (cos θ/2, axis × sin θ/2)    = (${q1.map((v) => v.toFixed(7)).join(", ")})\n` +
    `  compose        q ← normalize(q ⊗ Δq)             turn applied in the camera's own frame`;
})();
