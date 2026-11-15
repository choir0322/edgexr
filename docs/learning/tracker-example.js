/* Worked example and "looking away" timeline for basic-tracker.html.
   iou() and match() follow vision/basic_tracker.py: same-class pairs only,
   IoU >= 0.30, strongest pair claimed first (ties: lower ID, then earlier box),
   unmatched IDs miss one update and are forgotten at two misses.
   Boxes are illustrative [left, top, right, bottom] in 1280×720 source pixels. */
(function (global) {
  "use strict";
  const MIN_IOU = 0.3, MAX_MISSED = 2;

  /**
   * Intersection over union of two boxes (basic_tracker.box_iou).
   * @param {number[]} a Earlier box [l, t, r, b].
   * @param {number[]} b Current box [l, t, r, b].
   * @returns {number} Shared area / combined area, 0..1.
   */
  function iou(a, b) {
    const w = Math.max(0, Math.min(a[2], b[2]) - Math.max(a[0], b[0]));
    const h = Math.max(0, Math.min(a[3], b[3]) - Math.max(a[1], b[1]));
    const inter = w * h;
    return inter / ((a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter);
  }

  /**
   * Greedy same-class matching, as BasicTracker.update() does without motion or re-ID.
   * @param {Array<{id:number, cls:string, box:number[], missed:number}>} tracks Remembered tracks.
   * @param {Array<{name:string, cls:string, box:number[]}>} dets Current detections.
   * @param {number} nextId Next unused ID.
   * @returns {{pairs:Array, assigned:Object<string,number>, newIds:Object<string,number>, aged:Array, forgotten:number[]}}
   *   Candidate pairs sorted strongest first, claimed IDs, new IDs, aged and forgotten tracks.
   */
  function match(tracks, dets, nextId) {
    const pairs = [];
    tracks.forEach((t) => dets.forEach((d, j) => {
      if (t.cls !== d.cls) return;
      const v = iou(t.box, d.box);
      if (v >= MIN_IOU) pairs.push({ id: t.id, det: d.name, j, iou: v });
    }));
    pairs.sort((a, b) => b.iou - a.iou || a.id - b.id || a.j - b.j);
    const assigned = {}, used = new Set();
    for (const p of pairs) {
      p.won = !used.has(p.id) && !(p.det in assigned);
      if (p.won) { assigned[p.det] = p.id; used.add(p.id); }
    }
    const newIds = {};
    for (const d of dets) if (!(d.name in assigned)) newIds[d.name] = nextId++;
    const aged = tracks.filter((t) => !used.has(t.id)).map((t) => ({ id: t.id, missed: t.missed + 1 }));
    return { pairs, assigned, newIds, aged, forgotten: aged.filter((t) => t.missed >= MAX_MISSED).map((t) => t.id) };
  }

  const api = { iou, match, MIN_IOU, MAX_MISSED };
  global.EdgeTracker = api;
  if (typeof module !== "undefined" && module.exports) { module.exports = api; return; }

  // ---- Browser-only drawing below. ----
  const $ = (id) => document.getElementById(id);
  const COLORS = { person: "#79dcec", bottle: "#8ce9bb", chair: "#e8b478" };
  const TRACKS = [
    { id: 1, cls: "person", box: [180, 140, 480, 700], missed: 0 },
    { id: 2, cls: "bottle", box: [820, 380, 900, 600], missed: 0 },
    { id: 3, cls: "chair", box: [960, 300, 1250, 700], missed: 1 },
  ];

  /**
   * Current detections for a given bottle shift (the slider).
   * @param {number} shift Horizontal movement of the bottle in source pixels.
   * @returns {Array<{name:string, cls:string, box:number[]}>} Detections A–C.
   */
  function detections(shift) {
    return [
      { name: "A", cls: "person", box: [230, 150, 530, 712] },
      { name: "B", cls: "bottle", box: [835 + shift, 385, 915 + shift, 605] },
      { name: "C", cls: "bottle", box: [600, 420, 660, 580] },
    ];
  }

  /**
   * Redraw the frame, the IoU table and the outcome for the slider position.
   * @returns {void}
   */
  function render() {
    const shift = Number($("bottle-shift").value), dets = detections(shift), s = 0.5;
    $("bottle-shift-out").textContent = `${shift} px`;
    const result = match(TRACKS, dets, 4);
    let svg = `<rect x="0" y="0" width="640" height="360" rx="6" fill="#0b1720" stroke="#395365"/>`;
    for (const t of TRACKS) {
      const [l, tp, r, b] = t.box.map((v) => v * s);
      svg += `<rect x="${l}" y="${tp}" width="${r - l}" height="${b - tp}" fill="none" stroke="${COLORS[t.cls]}" stroke-width="2" stroke-dasharray="6 5" opacity=".75"/>` +
        `<text x="${l + 4}" y="${tp - 5}" fill="${COLORS[t.cls]}" font-size="12">#${t.id} ${t.cls} (earlier)</text>`;
    }
    for (const d of dets) {
      const [l, tp, r, b] = d.box.map((v) => v * s), id = result.assigned[d.name] || result.newIds[d.name];
      svg += `<rect x="${l}" y="${tp}" width="${r - l}" height="${b - tp}" fill="${COLORS[d.cls]}22" stroke="${COLORS[d.cls]}" stroke-width="2.5"/>` +
        `<text x="${l + 4}" y="${b + 15}" fill="#e9f4f6" font-size="12" font-weight="700">${d.name} → #${id}${d.name in result.newIds ? " (new)" : ""}</text>`;
    }
    $("example-frame").innerHTML = svg;

    // IoU table: every remembered track against every current detection.
    const head = `<tr><th>remembered</th>${dets.map((d) => `<th>${d.name} · ${d.cls}</th>`).join("")}</tr>`;
    const rows = TRACKS.map((t) => `<tr><th>#${t.id} · ${t.cls}</th>${dets.map((d) => {
      if (t.cls !== d.cls) return `<td class="na">other class</td>`;
      const v = iou(t.box, d.box), won = result.assigned[d.name] === t.id;
      return `<td class="${won ? "won" : v >= MIN_IOU ? "ok" : "low"}">${v.toFixed(3)}${won ? " ✓" : v < MIN_IOU ? " &lt; 0.30" : ""}</td>`;
    }).join("")}</tr>`).join("");
    $("iou-table").innerHTML = head + rows;
    const lines = [];
    result.pairs.forEach((p) => lines.push(`${p.won ? "claim" : "skip "}  #${p.id} ↔ ${p.det}   IoU ${p.iou.toFixed(3)}${p.won ? "" : "  (one side already taken)"}`));
    Object.entries(result.newIds).forEach(([d, id]) => lines.push(`new    ${d} gets #${id}: no remembered same-class box overlaps ≥ 0.30`));
    result.aged.forEach((t) => lines.push(`miss   #${t.id} unmatched → missed = ${t.missed}${t.missed >= MAX_MISSED ? "  → forgotten" : "  (kept, not drawn)"}`));
    $("match-steps").textContent = lines.join("\n");
  }
  $("bottle-shift").addEventListener("input", render);
  render();

  // Timeline: detector updates every 0.5 s while the head pans away and back.
  const visible = [1, 1, 1, 0, 0, 0, 0, 0, 1, 1, 1];
  let today = "", memory = "", nextId = 7, missed = 0, id = 7;
  const W = 62;
  visible.forEach((v, i) => {
    const x = 160 + i * W;
    today += `<text x="${x}" y="22" fill="#adc2cc" font-size="11" text-anchor="middle">${(i * 0.5).toFixed(1)} s</text>`;
    let label, fill;
    if (v) {
      if (missed >= MAX_MISSED) { id = ++nextId; missed = 0; }
      label = `#${id}`; fill = "#1b483d"; missed = 0;
    } else {
      missed += 1;
      label = missed >= MAX_MISSED ? (missed === MAX_MISSED ? "forgot" : "—") : "miss";
      fill = missed >= MAX_MISSED ? "#3a2a2a" : "#2b3a46";
    }
    today += `<rect x="${x - 29}" y="34" width="58" height="30" rx="6" fill="${fill}" stroke="#395365"/><text x="${x}" y="54" fill="#e9f4f6" font-size="12" text-anchor="middle">${label}</text>`;
    const mLabel = v ? (i >= 8 ? "same ✓" : "bottle") : (i === 7 ? "expect →" : "remembered"), mFill = v ? "#1b483d" : "#24203a";
    memory += `<rect x="${x - 29}" y="92" width="58" height="30" rx="6" fill="${mFill}" stroke="${v ? "#395365" : "#8d7bb0"}" stroke-dasharray="${v ? "" : "4 3"}"/><text x="${x}" y="111" fill="#e9f4f6" font-size="${v ? 12 : 9}" text-anchor="middle">${mLabel}</text>`;
  });
  $("lookaway").innerHTML = `<text x="8" y="54" fill="#e9f4f6" font-size="12">tracker today</text>` +
    `<text x="8" y="104" fill="#e9f4f6" font-size="12">object memory</text><text x="8" y="119" fill="#adc2cc" font-size="11">(planned, step 2)</text>` +
    `<line x1="${160 + 2.5 * W}" y1="140" x2="${160 + 2.5 * W}" y2="150" stroke="#adc2cc"/><text x="${160 + 2.5 * W}" y="164" fill="#adc2cc" font-size="11" text-anchor="middle">head pans away</text>` +
    `<line x1="${160 + 7.5 * W}" y1="140" x2="${160 + 7.5 * W}" y2="150" stroke="#adc2cc"/><text x="${160 + 7.5 * W}" y="164" fill="#adc2cc" font-size="11" text-anchor="middle">head returns</text>` + today + memory;
})(typeof window !== "undefined" ? window : globalThis);
