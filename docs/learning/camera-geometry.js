/* Interactive figures for camera-geometry.html.
   All arithmetic comes from camera-geometry-math.js (EdgeGeometry), which is
   checked against OpenCV; this file only draws and wires controls. */
(function () {
  "use strict";
  const G = window.EdgeGeometry, C = G.CAL;
  const $ = (id) => document.getElementById(id);
  const NS = "http://www.w3.org/2000/svg";
  const INK = "#e5edf6", MUTED = "#98a8bb", GREEN = "#65d8bb", BLUE = "#82bcff", ORANGE = "#efb77b", LINE = "#2b394a";
  const signed = (v, d = 1) => `${v >= 0 ? "+" : "−"}${Math.abs(v).toFixed(d)}`;
  const fov = G.fieldOfView();

  /**
   * Replace an SVG's children with markup.
   * @param {SVGSVGElement} svg Target.
   * @param {string} markup SVG child elements.
   * @returns {void}
   */
  function paint(svg, markup) { svg.innerHTML = markup; }

  // Headline numbers: fitted intrinsics and derived field of view.
  $("headline-stats").innerHTML = [
    [`${C.fx.toFixed(1)} px`, "focal length (fitted by calibration)"],
    [`(${C.cx.toFixed(0)}, ${C.cy.toFixed(0)})`, "optical centre in the 1280×720 image"],
    [`${fov.horizontal.toFixed(1)}° × ${fov.vertical.toFixed(1)}°`, "field of view through the centre (derived)"],
    [`${(Math.atan(1 / C.fx) * 180 / Math.PI).toFixed(3)}°`, "one pixel at the image centre (derived)"],
  ].map(([v, s]) => `<div class="stat"><strong>${v}</strong><span>${s}</span></div>`).join("");

  /**
   * Section 1: top-down pinhole triangle for the chosen pixel column.
   * @returns {void}
   */
  function drawPinhole() {
    const u = Number($("column").value);
    $("column-out").textContent = `u = ${u}`;
    const s = 200 / C.fx, lensX = 280, lensY = 300, planeY = lensY - 200;
    const px = lensX + (u - C.cx) * s, left = lensX - C.cx * s, right = lensX + (C.width - 1 - C.cx) * s;
    const d = u - C.cx, theta = Math.atan2(d, C.fx);
    const far = { x: lensX + Math.tan(theta) * 280, y: lensY - 280 };
    const arcR = 46, ax = lensX + arcR * Math.sin(theta), ay = lensY - arcR * Math.cos(theta);
    paint($("pinhole"), `
      <line x1="${lensX}" y1="${lensY}" x2="${lensX}" y2="18" stroke="${MUTED}" stroke-dasharray="4 5"/>
      <text x="${lensX + 6}" y="30" fill="${MUTED}" font-size="12">optical axis (yaw 0°)</text>
      <line x1="${left}" y1="${planeY}" x2="${right}" y2="${planeY}" stroke="${INK}" stroke-width="3"/>
      <text x="${left}" y="${planeY - 10}" fill="${MUTED}" font-size="12">image plane: column 0</text>
      <text x="${right}" y="${planeY - 10}" fill="${MUTED}" font-size="12" text-anchor="end">column 1279</text>
      <line x1="${lensX}" y1="${lensY}" x2="${far.x}" y2="${far.y}" stroke="${GREEN}" stroke-width="2.5"/>
      <circle cx="${px}" cy="${planeY}" r="6" fill="${GREEN}"/>
      <path d="M${lensX},${lensY - arcR} A${arcR},${arcR} 0 0 ${theta >= 0 ? 1 : 0} ${ax},${ay}" fill="none" stroke="${ORANGE}" stroke-width="2"/>
      <text x="${lensX + (theta >= 0 ? 10 : -10)}" y="${lensY - arcR - 8}" fill="${ORANGE}" font-size="13" text-anchor="${theta >= 0 ? "start" : "end"}">θ = ${signed(theta * 180 / Math.PI)}°</text>
      <path d="M${lensX - 30},${planeY + 20} L${lensX - 30},${lensY - 6}" stroke="${BLUE}" stroke-width="1.5" marker-end="url(#a)" marker-start="url(#a)"/>
      <defs><marker id="a" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="${BLUE}"/></marker></defs>
      <text x="${lensX - 36}" y="${(planeY + lensY) / 2}" fill="${BLUE}" font-size="12" text-anchor="end">focal length</text>
      <text x="${lensX - 36}" y="${(planeY + lensY) / 2 + 15}" fill="${BLUE}" font-size="12" text-anchor="end">${C.fx.toFixed(1)} px</text>
      <circle cx="${lensX}" cy="${lensY}" r="7" fill="${INK}"/>
      <text x="${lensX + 12}" y="${lensY + 18}" fill="${MUTED}" font-size="12">lens (optical centre)</text>
      <text x="${px + (theta >= 0 ? 12 : -12)}" y="${planeY + 22}" fill="${INK}" font-size="12" text-anchor="${theta >= 0 ? "start" : "end"}">pixel u = ${u}</text>`);
    const lensYaw = G.bearing(u, C.cy).yaw, pin = theta * 180 / Math.PI;
    $("pinhole-math").textContent =
      `column u               = ${u} px\n` +
      `image centre cx       = ${C.cx.toFixed(1)} px\n` +
      `offset d = u − cx     = ${signed(d)} px\n` +
      `pinhole angle         = atan(${d.toFixed(1)} / ${C.fx.toFixed(1)}) = ${signed(pin, 2)}°\n` +
      `with lens correction  = ${signed(lensYaw, 2)}°\n` +
      `lens effect here      = ${signed(lensYaw - pin, 2)}°`;
  }
  $("column").addEventListener("input", drawPinhole);
  drawPinhole();

  // Section 2: angle grid over a recorded frame, with a movable marker.
  const grid = $("angle-grid"), gctx = grid.getContext("2d");
  const photo = new Image();
  let marker = [900, 300];
  photo.onload = drawGrid;
  photo.src = "images/detection-lesson-scene.png";

  /**
   * Stroke a polyline through bearings, skipping directions the model cannot map.
   * @param {CanvasRenderingContext2D} ctx Drawing context.
   * @param {Array<number[]|null>} points Pixel points or null gaps.
   * @param {number} [ox] X offset added to every point.
   * @param {number} [oy] Y offset added to every point.
   * @returns {void}
   */
  function polyline(ctx, points, ox = 0, oy = 0) {
    ctx.beginPath();
    let pen = false;
    for (const p of points) {
      if (!p) { pen = false; continue; }
      if (pen) ctx.lineTo(p[0] + ox, p[1] + oy); else ctx.moveTo(p[0] + ox, p[1] + oy);
      pen = true;
    }
    ctx.stroke();
  }

  /**
   * Pinhole-only pixel for a bearing (distortion switched off).
   * @param {number} yaw Degrees.
   * @param {number} pitch Degrees.
   * @returns {number[]} Pixel [u, v].
   */
  function pinholePixel(yaw, pitch) {
    const [x, y] = G.rayOf(yaw, pitch);
    return [C.fx * x + C.cx, C.fy * y + C.cy];
  }

  /**
   * Draw the frame, unreliable region, equal-angle lines and the marker.
   * @returns {void}
   */
  function drawGrid() {
    const W = grid.width, H = grid.height;
    gctx.clearRect(0, 0, W, H);
    gctx.fillStyle = "#0b131d"; gctx.fillRect(0, 0, W, H);
    if (photo.complete && photo.naturalWidth) gctx.drawImage(photo, 0, 0, W, H);
    gctx.fillStyle = "rgba(12,17,24,.38)"; gctx.fillRect(0, 0, W, H);

    // Outside this ellipse the fitted polynomial has no inverse (see section 3).
    gctx.beginPath();
    gctx.rect(0, 0, W, H);
    gctx.ellipse(C.cx, C.cy, C.fx * G.FOLD.distorted, C.fy * G.FOLD.distorted, 0, 0, Math.PI * 2);
    gctx.fillStyle = "rgba(239,183,123,.42)"; gctx.fill("evenodd");
    gctx.beginPath();
    gctx.ellipse(C.cx, C.cy, C.fx * G.FOLD.distorted, C.fy * G.FOLD.distorted, 0, 0, Math.PI * 2);
    gctx.strokeStyle = ORANGE; gctx.lineWidth = 2; gctx.setLineDash([]); gctx.stroke();

    // Equal-yaw and equal-pitch curves through the real lens model.
    gctx.font = "600 22px system-ui, sans-serif";
    for (let yaw = -40; yaw <= 40; yaw += 10) {
      const pts = [];
      for (let p = -35; p <= 35; p += 0.25) pts.push(G.pixelOf(yaw, p));
      gctx.strokeStyle = GREEN; gctx.lineWidth = yaw === 0 ? 3.5 : 2; gctx.globalAlpha = .9;
      polyline(gctx, pts);
      const top = G.pixelOf(yaw, 20);
      if (top && top[0] > 10 && top[0] < W - 50) { gctx.fillStyle = GREEN; gctx.fillText(`${yaw > 0 ? "+" : ""}${yaw}°`, top[0] + 6, 70); }
    }
    for (let pitch = -20; pitch <= 20; pitch += 10) {
      const pts = [];
      for (let y = -60; y <= 60; y += 0.25) pts.push(G.pixelOf(y, pitch));
      gctx.strokeStyle = BLUE; gctx.lineWidth = pitch === 0 ? 3.5 : 2;
      polyline(gctx, pts);
      const lab = G.pixelOf(30, pitch);
      if (lab) { gctx.fillStyle = BLUE; gctx.fillText(`${pitch > 0 ? "+" : ""}${pitch}°`, W - 70, lab[1] - 8); }
    }
    gctx.globalAlpha = 1;
    if ($("show-pinhole").checked) {
      gctx.setLineDash([10, 8]); gctx.strokeStyle = "rgba(255,255,255,.75)"; gctx.lineWidth = 1.5;
      for (let yaw = -40; yaw <= 40; yaw += 10) { const pts = []; for (let p = -35; p <= 35; p += 0.5) pts.push(pinholePixel(yaw, p)); polyline(gctx, pts); }
      for (let pitch = -20; pitch <= 20; pitch += 10) { const pts = []; for (let y = -60; y <= 60; y += 0.5) pts.push(pinholePixel(y, pitch)); polyline(gctx, pts); }
      gctx.setLineDash([]);
    }

    // Marker and its readout.
    const [u, v] = marker, b = G.bearing(u, v);
    gctx.strokeStyle = b.valid ? "#ffffff" : ORANGE; gctx.lineWidth = 3;
    gctx.beginPath(); gctx.arc(u, v, 16, 0, Math.PI * 2); gctx.stroke();
    gctx.beginPath(); gctx.moveTo(u - 28, v); gctx.lineTo(u - 8, v); gctx.moveTo(u + 8, v); gctx.lineTo(u + 28, v);
    gctx.moveTo(u, v - 28); gctx.lineTo(u, v - 8); gctx.moveTo(u, v + 8); gctx.lineTo(u, v + 28); gctx.stroke();
    $("grid-readout").textContent =
      `pixel (u, v)           = (${u.toFixed(0)}, ${v.toFixed(0)}) of 1280×720\n` +
      `ideal ray (x, y, 1)    = (${b.x.toFixed(4)}, ${b.y.toFixed(4)}, 1)   after removing lens distortion\n` +
      `direction (lens model) = yaw ${signed(b.yaw, 2)}°, pitch ${signed(b.pitch, 2)}°\n` +
      `without lens model     = yaw ${signed(b.pinholeYaw, 2)}°, pitch ${signed(b.pinholePitch, 2)}°\n` +
      (b.valid ? `status                 = inside the region where the lens model inverts (round trip ${b.roundTripPx.toFixed(3)} px)`
        : `status                 = UNRELIABLE: distorted radius ${b.distortedRadius.toFixed(3)} ≥ ${G.FOLD.distorted.toFixed(3)}; the fitted lens model cannot be inverted here`);
  }

  /**
   * Move the marker to a pointer position on the canvas.
   * @param {MouseEvent} e Pointer event.
   * @returns {void}
   */
  function pointAt(e) {
    const r = grid.getBoundingClientRect();
    marker = [Math.max(0, Math.min(1279, (e.clientX - r.left) * grid.width / r.width)),
      Math.max(0, Math.min(719, (e.clientY - r.top) * grid.height / r.height))];
    drawGrid();
  }
  grid.addEventListener("mousemove", pointAt);
  grid.addEventListener("click", pointAt);
  grid.addEventListener("keydown", (e) => {
    const step = e.shiftKey ? 50 : 10, moves = { ArrowLeft: [-step, 0], ArrowRight: [step, 0], ArrowUp: [0, -step], ArrowDown: [0, step] };
    if (!moves[e.key]) return;
    e.preventDefault();
    marker = [Math.max(0, Math.min(1279, marker[0] + moves[e.key][0])), Math.max(0, Math.min(719, marker[1] + moves[e.key][1]))];
    drawGrid();
  });
  $("show-pinhole").addEventListener("change", drawGrid);
  drawGrid();

  // Section 3: displacement arrows (ideal pinhole pixel → lens pixel), magnified.
  const dist = $("distortion"), dctx = dist.getContext("2d"), OX = 100, OY = 70;

  /**
   * Draw one arrow from a start to an end point on the distortion canvas.
   * @param {number[]} a Start [x, y] in image pixels.
   * @param {number[]} b End [x, y] in image pixels.
   * @returns {void}
   */
  function arrow(a, b) {
    const dx = b[0] - a[0], dy = b[1] - a[1], len = Math.hypot(dx, dy);
    dctx.beginPath(); dctx.moveTo(a[0] + OX, a[1] + OY); dctx.lineTo(b[0] + OX, b[1] + OY); dctx.stroke();
    if (len < 4) return;
    const ux = dx / len, uy = dy / len, h = Math.min(12, len * 0.45);
    dctx.beginPath();
    dctx.moveTo(b[0] + OX, b[1] + OY);
    dctx.lineTo(b[0] + OX - h * ux + h * 0.5 * uy, b[1] + OY - h * uy - h * 0.5 * ux);
    dctx.lineTo(b[0] + OX - h * ux - h * 0.5 * uy, b[1] + OY - h * uy + h * 0.5 * ux);
    dctx.closePath(); dctx.fill();
  }

  /**
   * Draw the image frame, the true fold ring and the magnified displacement field.
   * @returns {void}
   */
  function drawDistortion() {
    const m = Number($("magnify").value);
    $("magnify-out").textContent = `×${m}`;
    dctx.clearRect(0, 0, dist.width, dist.height);
    dctx.fillStyle = "#0b131d"; dctx.fillRect(0, 0, dist.width, dist.height);
    dctx.strokeStyle = "#5c6b7c"; dctx.lineWidth = 2; dctx.strokeRect(OX, OY, 1280, 720);
    dctx.beginPath();
    dctx.ellipse(C.cx + OX, C.cy + OY, C.fx * G.FOLD.distorted, C.fy * G.FOLD.distorted, 0, 0, Math.PI * 2);
    dctx.strokeStyle = ORANGE; dctx.lineWidth = 3; dctx.stroke();
    // One arrow per 0.1 step of the ideal ray grid that lands on or near the image.
    for (let x = -1.0; x <= 0.9001; x += 0.1) {
      for (let y = -0.5; y <= 0.6001; y += 0.1) {
        const start = [C.fx * x + C.cx, C.fy * y + C.cy];
        if (start[0] < -30 || start[0] > 1310 || start[1] < -30 || start[1] > 750) continue;
        if (Math.hypot(x, y) >= G.FOLD.ideal) {
          dctx.strokeStyle = ORANGE; dctx.lineWidth = 3;
          dctx.beginPath(); dctx.moveTo(start[0] + OX - 8, start[1] + OY - 8); dctx.lineTo(start[0] + OX + 8, start[1] + OY + 8);
          dctx.moveTo(start[0] + OX + 8, start[1] + OY - 8); dctx.lineTo(start[0] + OX - 8, start[1] + OY + 8); dctx.stroke();
          continue;
        }
        const end = G.project(x, y);
        dctx.fillStyle = "#98a8bb"; dctx.beginPath(); dctx.arc(start[0] + OX, start[1] + OY, 3, 0, Math.PI * 2); dctx.fill();
        dctx.strokeStyle = GREEN; dctx.fillStyle = GREEN; dctx.lineWidth = 2.5;
        arrow(start, [start[0] + m * (end[0] - start[0]), start[1] + m * (end[1] - start[1])]);
      }
    }
    dctx.fillStyle = MUTED; dctx.font = "24px system-ui, sans-serif";
    dctx.fillText(`arrow length = lens displacement × ${m}`, OX, OY - 22);
  }
  $("magnify").addEventListener("input", drawDistortion);
  drawDistortion();

  // True (unmagnified) horizontal shift along the principal row.
  const shift = [];
  for (let a = -45; a <= 45.001; a += 0.25) {
    const x = Math.tan(a * Math.PI / 180);
    shift.push([a, G.project(x, 0)[0] - (C.fx * x + C.cx)]);
  }
  window.EdgeCharts.lines($("radial-chart"), {
    title: "Lens shift along the middle row",
    note: "Pixels the lens model moves a point, versus where a perfect pinhole lens would put it. Positive = moved right. Shaded: beyond the image edges.",
    series: [{ name: "lens shift", color: "var(--s1)", points: shift }],
    x: { min: -45, max: 45, label: "direction from optical axis (°)", step: 10, format: (v) => `${Math.round(v)}°` },
    y: { min: -40, max: 40, label: "shift (px)", step: 10, format: (v) => `${v.toFixed(0)}` },
    bands: [{ from: -45, to: -fov.left, color: "rgba(239,183,123,.12)" }, { from: fov.right, to: 45, color: "rgba(239,183,123,.12)" }],
    height: 280,
  });
  const inside = shift.filter((p) => p[0] > -fov.left && p[0] < fov.right);
  const peak = inside.reduce((best, p) => (Math.abs(p[1]) > Math.abs(best[1]) ? p : best), [0, 0]);
  $("fold-callout").innerHTML = `<strong>Where the lens model stops being trustworthy.</strong> Inside the image the fitted lens moves points by at most about ${Math.abs(peak[1]).toFixed(0)} px along the middle row (largest near ${Math.abs(peak[0]).toFixed(0)}° off-axis), then the curve bends back hard. Beyond <strong>${(Math.atan(G.FOLD.ideal) * 180 / Math.PI).toFixed(1)}°</strong> off-axis it folds, so pixels farther than a normalized radius of ${G.FOLD.distorted.toFixed(3)} from the centre have <em>no</em> inverse: OpenCV returns a wrong direction there instead of an error. That cuts off three image corners and a strip of the left edge (shaded in section 2). The likely reason: the checkerboard centres covered only about 37% of the image width and height, so the outer polynomial is extrapolated. <strong>For step 1:</strong> flag detections in that region rather than trusting their bearing, or recalibrate with the board reaching the corners.`;

  // Section 4: calibration error and focal-length spread (benchmarks/results/camera-calibration-screen-01.json).
  window.EdgeCharts.bars($("rms-chart"), {
    title: "Per-view reprojection error",
    note: "Lower is better. Held-out views were not used to fit the lens.",
    series: [{ name: "Fitted views (111)", color: "var(--s1)" }, { name: "Held-out views (27)", color: "var(--s2)" }],
    rows: [{ label: "median", values: [0.2366415, 0.1879799] }, { label: "95th percentile", values: [1.3355114, 1.1072748] }, { label: "worst view", values: [2.0596883, 1.2384021] }],
    unit: "px", digits: 2, labelWidth: 120, max: 2.5,
  });
  const edge = (f) => Math.atan(C.cx / f) * 180 / Math.PI;
  const fits = [C.fx, 726.9594, 730.7817];
  const spread = Math.max(...fits.map(edge)) - Math.min(...fits.map(edge));
  $("focal-stats").innerHTML = [
    [`${C.fx.toFixed(1)} px`, "full fit, 111 views"],
    ["727.0 / 730.8 px", "first / second half of a 45-view sample"],
    [`${spread.toFixed(2)}°`, "spread in the left-edge direction across the three fits (derived)"],
  ].map(([v, s]) => `<div class="stat"><strong>${v}</strong><span>${s}</span></div>`).join("");

  // Section 5: step-1 preview with two remembered objects at fixed bearings.
  const OBJECTS = [{ name: "bottle", bearing: -20, r: 165, color: GREEN }, { name: "chair", bearing: 28, r: 205, color: BLUE }];

  /**
   * Point on the top-down plot for a bearing and radius.
   * @param {number} bearing Degrees from straight ahead of the base, right positive.
   * @param {number} r Radius in SVG units.
   * @returns {number[]} SVG [x, y].
   */
  function polar(bearing, r) {
    const a = bearing * Math.PI / 180;
    return [260 + r * Math.sin(a), 300 - r * Math.cos(a)];
  }

  /**
   * Redraw the top-down plot, the camera image and the readout for a head pan.
   * @returns {void}
   */
  function drawPreview() {
    const pan = Number($("pan").value);
    $("pan-out").textContent = `${signed(pan, 0)}°`;
    const [l1, l2] = [polar(pan - fov.left, 245), polar(pan + fov.right, 245)];
    let top = `<path d="M260,300 L${l1[0]},${l1[1]} A245,245 0 0 1 ${l2[0]},${l2[1]} Z" fill="rgba(101,216,187,.10)" stroke="rgba(101,216,187,.45)"/>`;
    for (let b = -90; b <= 90; b += 10) {
      const [a, c] = [polar(b, 252), polar(b, b % 30 === 0 ? 266 : 258)];
      top += `<line x1="${a[0]}" y1="${a[1]}" x2="${c[0]}" y2="${c[1]}" stroke="${LINE}" stroke-width="1.5"/>`;
      if (b % 30 === 0) { const t = polar(b, 282); top += `<text x="${t[0]}" y="${t[1] + 4}" fill="${MUTED}" font-size="11" text-anchor="middle">${b > 0 ? "+" : ""}${b}°</text>`; }
    }
    const tip = polar(pan, 92);
    top += `<line x1="260" y1="300" x2="${tip[0]}" y2="${tip[1]}" stroke="${INK}" stroke-width="3"/><circle cx="${tip[0]}" cy="${tip[1]}" r="4" fill="${INK}"/>`;
    top += `<rect x="236" y="296" width="48" height="22" rx="4" fill="#25364a" stroke="#405269"/><text x="260" y="311" fill="${MUTED}" font-size="10" text-anchor="middle">base</text>`;
    let image = `<rect x="10" y="10" width="500" height="281.25" rx="4" fill="#0b131d" stroke="#405269"/>` +
      `<line x1="10" y1="${10 + C.cy * 500 / 1280}" x2="510" y2="${10 + C.cy * 500 / 1280}" stroke="${LINE}" stroke-dasharray="4 5"/>` +
      `<text x="16" y="28" fill="${MUTED}" font-size="11">camera image (1280×720, scaled)</text>`;
    const lines = [`head pan (gyro)             ${signed(pan)}°`];
    for (const o of OBJECTS) {
      const rel = o.bearing - pan, p = polar(o.bearing, o.r);
      const visible = rel > -fov.left && rel < fov.right;
      top += `<line x1="260" y1="300" x2="${p[0]}" y2="${p[1]}" stroke="${o.color}" stroke-dasharray="3 5" opacity=".7"/>` +
        `<circle cx="${p[0]}" cy="${p[1]}" r="9" fill="${visible ? o.color : "none"}" stroke="${o.color}" stroke-width="2.5"/>` +
        `<text x="${p[0]}" y="${p[1] - 15}" fill="${INK}" font-size="12" text-anchor="middle">${o.name} ${o.bearing > 0 ? "+" : ""}${o.bearing}°</text>`;
      if (visible) {
        const px = G.pixelOf(rel, 0), x = 10 + px[0] * 500 / 1280, y = 10 + px[1] * 500 / 1280;
        image += `<rect x="${x - 9}" y="${y - 30}" width="18" height="44" rx="6" fill="${o.color}" opacity=".9"/><text x="${x}" y="${y + 32}" fill="${INK}" font-size="12" text-anchor="middle">${o.name} · u ${px[0].toFixed(0)}</text>`;
        lines.push(`${o.name.padEnd(7)} image yaw ${signed(rel)}° (pixel u ${px[0].toFixed(0).padStart(4)}) → bearing ${signed(rel + pan)}°`);
      } else {
        const leftSide = rel <= -fov.left, x = leftSide ? 22 : 498, enter = leftSide ? o.bearing + fov.left : o.bearing - fov.right;
        image += `<text x="${x}" y="${10 + C.cy * 500 / 1280 - 8}" fill="${ORANGE}" font-size="12" text-anchor="${leftSide ? "start" : "end"}">${leftSide ? "← " : ""}${o.name} out of view${leftSide ? "" : " →"}</text>`;
        lines.push(`${o.name.padEnd(7)} remembered at ${signed(o.bearing)}°, outside the view; re-enters when head pan ${leftSide ? "<" : ">"} ${signed(enter)}°`);
      }
    }
    paint($("topdown"), top);
    paint($("camera-view"), image);
    $("preview-readout").textContent = lines.join("\n");
  }
  $("pan").addEventListener("input", drawPreview);
  drawPreview();
  $("placement-callout").innerHTML = `<strong>Practical consequence for the step-1 demo.</strong> The lens sees ${fov.horizontal.toFixed(0)}° across, nearly as wide as the ±40° pan range. With the head panned fully right (+40°) the view still reaches ${signed(40 - fov.left)}°, so an object straight ahead never leaves view. Place the bottle well to one side, about 20° or more, so that panning the other way actually takes it out of view (a bottle at −20° leaves once the head passes ${signed(-20 + fov.left)}°).`;
})();
