/* Offline teaching trace for src/vision/basic_tracker.py; no camera or model is run. */
(function () {
  "use strict";

  const MIN_IOU = 0.3;
  const MAX_MISSED = 2;
  const STAGES = ["Input", "Validate", "Compare", "IoU", "Rank", "Claim", "Age old", "Assign ID", "Return"];
  const LIVE = {
    create: {title:"1 · Create once", rule:"detect_latest() creates the detector and one BasicTracker before its loop. Both belong to the same sequential worker; the tracker survives between completed results.",
      data:"detector = factory()  →  tracker = BasicTracker()", effect:"Restarting the worker begins a new session of IDs.", code:"detect_latest · worker setup"},
    infer: {title:"2 · Infer newest frame", rule:"The worker chooses a new eligible 1280×720 grayscale frame. The CPU detector returns a list of current boxes without IDs; even an empty list continues into tracking.",
      data:"boxes = detector(frame[2])  →  finished = clock()", effect:"Inference timing stops here, before tracker.update().", code:"detect_latest · inference and timing"},
    match: {title:"3 · Match IDs", rule:"This is a call into BasicTracker.update(boxes), not a separate parallel worker. The nine decisions below expand that call in code order.",
      data:"identified = tracker.update(boxes)", effect:"Follow the solid arrow downward; the dotted top edge is only a collapsed overview.", code:"detect_latest · tracker handoff"},
    publish: {title:"4 · Publish result", rule:"After update() returns, DetectionState.publish stores the ID-bearing current boxes with the original frame sequence and host receipt timestamp.",
      data:"state.detector.publish(frame, identified, inference_ms, finished)", effect:"The API exposes track_id. The browser shows provisional #ID only while boxes are ready and the camera is live; the 1.5-second source-age rule is unchanged.", code:"detect_latest · DetectionState.publish"}
  };
  const FLOW_IDS = ["create", "infer", "match", ...STAGES.map((_, i) => `tracker-${i}`), "publish"];

  /** Return intersection and union values using the Python box_iou() formula. */
  function overlap(first, second) {
    const width = Math.max(0, Math.min(first[2], second[2]) - Math.max(first[0], second[0]));
    const height = Math.max(0, Math.min(first[3], second[3]) - Math.max(first[1], second[1]));
    const intersection = width * height;
    const firstArea = (first[2] - first[0]) * (first[3] - first[1]);
    const secondArea = (second[2] - second[0]) * (second[3] - second[1]);
    const union = firstArea + secondArea - intersection;
    return {width, height, intersection, firstArea, secondArea, union, iou:intersection / union};
  }

  /** Copy the ID-keyed memory so the example never mutates its input state. */
  function copyTracks(tracks) {
    return tracks.map(t => ({id:t.id, class_id:t.class_id, box:t.box.slice(), missed:t.missed}));
  }

  /** Validate all detector boxes before any saved-track state can change. */
  function validate(input) {
    return input.map(d => {
      if (!Number.isInteger(d.class_id) || !Array.isArray(d.box_xyxy) || d.box_xyxy.length !== 4)
        throw new Error("class_id or box_xyxy is malformed");
      const box = d.box_xyxy.map(Number);
      if (!box.every(Number.isFinite) || box[2] <= box[0] || box[3] <= box[1])
        throw new Error("box_xyxy must be finite and have positive area");
      return box;
    });
  }

  /** Mirror one complete BasicTracker.update() call and retain its decisions. */
  function traceUpdate(state, input) {
    const boxes = validate(input);
    const before = copyTracks(state.tracks);
    const pairs = [], candidates = [];
    for (const track of before) {
      input.forEach((d, index) => {
        const sameClass = track.class_id === d.class_id;
        const math = sameClass ? overlap(track.box, boxes[index]) : null;
        const eligible = sameClass && math.iou >= MIN_IOU;
        const pair = {id:track.id, index, sameClass, math, eligible};
        pairs.push(pair);
        if (eligible) candidates.push(pair);
      });
    }
    candidates.sort((a, b) => b.math.iou - a.math.iou || a.id - b.id || a.index - b.index);

    // Greedy assignment claims each old ID and current index at most once.
    const assignments = new Map(), matched = new Set(), decisions = [];
    for (const pair of candidates) {
      const reason = matched.has(pair.id) ? "old ID already claimed" :
        assignments.has(pair.index) ? "current box already claimed" : "accepted";
      decisions.push({...pair, reason});
      if (reason === "accepted") {
        assignments.set(pair.index, pair.id);
        matched.add(pair.id);
      }
    }

    // A missing old track remains hidden for one completed result, then retires.
    const aged = copyTracks(before), ageEvents = [];
    for (let i = aged.length - 1; i >= 0; i--) {
      const track = aged[i];
      if (matched.has(track.id)) continue;
      track.missed++;
      const retired = track.missed >= MAX_MISSED;
      ageEvents.push({id:track.id, missed:track.missed, retired});
      if (retired) aged.splice(i, 1);
    }

    // Matched boxes refresh memory; unmatched boxes receive a never-reused ID.
    const after = copyTracks(aged), identified = [];
    let nextId = state.nextId;
    input.forEach((d, index) => {
      let id = assignments.get(index);
      if (id === undefined) {
        id = nextId++;
        after.push({id, class_id:d.class_id, box:boxes[index].slice(), missed:0});
      } else {
        const track = after.find(t => t.id === id);
        track.box = boxes[index].slice();
        track.missed = 0;
      }
      identified.push({...d, track_id:id});
    });
    return {input, boxes, before, pairs, candidates, decisions, assignments,
      ageEvents, after, identified, nextId};
  }

  /** Make a two-update teaching fixture with one old ID claimed by two boxes. */
  function example() {
    const chair = box => ({class_id:9, label:"chair", confidence:0.9, box_xyxy:box});
    const table = box => ({class_id:11, label:"diningtable", confidence:0.9, box_xyxy:box});
    const first = traceUpdate({tracks:[], nextId:1}, [
      chair([690, 320, 1000, 570]), table([100, 500, 1250, 720])
    ]);
    return traceUpdate({tracks:first.after, nextId:first.nextId}, [
      chair([700, 325, 1010, 575]), chair([755, 330, 1065, 580]),
      table([100, 505, 1250, 720])
    ]);
  }

  /** Derive all node explanations from the same trace used in tests. */
  function descriptions(trace) {
    const d0 = trace.input[0], old = trace.before.find(t => t.id === 1);
    const pair = trace.pairs.find(p => p.id === 1 && p.index === 0);
    const m = pair.math;
    const competing = trace.decisions.find(p => p.id === 1 && p.index === 1);
    const once = traceUpdate({tracks:[old], nextId:3}, []);
    const twice = traceUpdate({tracks:once.after, nextId:once.nextId}, []);
    return [
      {rule:"A completed detector result supplies current records. Earlier update() calls supplied the ID-keyed _tracks memory; this is not a previous image or a cached full detection list.",
        data:`d₀ = {class_id: ${d0.class_id}, label: ${d0.label}, confidence: ${d0.confidence}, box_xyxy: [${d0.box_xyxy}]}  ·  old #1 = [${old.box}]`,
        effect:"d₀ enters without a track_id.", code:"update(detections) · _Track"},
      {rule:"Convert all current XYXY coordinates to finite floats; require right > left and bottom > top. Validation finishes before _tracks changes.",
        data:`d₀ [${trace.boxes[0]}] → [x₁=${trace.boxes[0][0]}, y₁=${trace.boxes[0][1]}, x₂=${trace.boxes[0][2]}, y₂=${trace.boxes[0][3]}]`,
        effect:"A bad record aborts the entire call; it is not merely skipped.", code:"BasicTracker.update · boxes validation loop"},
      {rule:"For each old/current pair, compare class_id first. Only equal-class pairs reach box_iou(). Coordinates use the original 1280×720 image space.",
        data:`old #1 class ${old.class_id} ↔ d₀ class ${d0.class_id}: compare boxes.  old #2 class 11 ↔ d₀ class 9: reject this pair before IoU.`,
        effect:"Rejecting a pair does not discard d₀.", code:"BasicTracker.update · candidates loop"},
      {rule:`Measure intersection / union, then keep same-class pairs with IoU ≥ ${MIN_IOU}. A lower score rejects this candidate pair only.`,
        data:`shared = ${m.width} × ${m.height} = ${m.intersection} px²; union = ${m.firstArea} + ${m.secondArea} − ${m.intersection} = ${m.union} px²; IoU = ${m.iou.toFixed(3)}`,
        effect:`old #1 ↔ d₀ qualifies (${m.iou.toFixed(3)} ≥ ${MIN_IOU}).`, code:"box_iou · BasicTracker.update"},
      {rule:"Sort every eligible pair by (−IoU, old ID, current index): strongest overlap first, then lower ID and lower input position. This is greedy, not globally optimal matching.",
        data:trace.candidates.map(p => `#${p.id} ↔ d${p.index}: ${p.math.iou.toFixed(3)}`).join("  →  "),
        effect:"d₀'s pair reaches the claim step ahead of its competitor.", code:"BasicTracker.update · sorted(candidates)"},
      {rule:"Accept a pair only if neither its old ID nor its current detection has already been claimed. A second box cannot inherit the same ID.",
        data:`d₀ → #${trace.assignments.get(0)} accepted; d₁ → #1 ${competing.reason}; assignments = {0: 1, 2: 2}.`,
        effect:"d₀ keeps #1; d₁ will need a fresh ID.", code:"BasicTracker.update · assignments / matched_tracks"},
      {rule:"After matching, increment missed for each unmatched old track. One miss retains it internally but draws no box; two consecutive completed detector results retire it.",
        data:`In this example both old IDs matched. Separate empty-result check: #1 missed 0 → ${once.ageEvents[0].missed} (hidden, retained) → ${twice.ageEvents[0].missed} (${twice.ageEvents[0].retired ? "retired" : "retained"}).`,
        effect:"Only old unmatched tracks can be discarded here; d₀ continues.", code:"BasicTracker.update · unmatched-track aging loop"},
      {rule:"Walk current detections in input order. A matched box refreshes its saved geometry and resets missed; an unmatched box gets _next_id, which only increases.",
        data:`d₀ matched #${trace.identified[0].track_id}; d₁ new #${trace.identified[1].track_id}; d₂ matched #${trace.identified[2].track_id}; next ID = ${trace.nextId}.`,
        effect:"d₀ becomes a new output dictionary with track_id: 1; its input record stays unchanged.", code:"BasicTracker.update · identified loop"},
      {rule:"Return only current detections, now carrying IDs. _tracks persists for the next completed detector result; a missing remembered box is not returned or drawn.",
        data:`returned IDs = [${trace.identified.map(d => d.track_id)}]; memory IDs = [${trace.after.map(t => t.id)}].`,
        effect:"d₀ exits as chair #1; the live worker publishes this ID-bearing result.", code:"BasicTracker.update · return identified"}
    ];
  }

  if (typeof module !== "undefined" && module.exports)
    module.exports = {MIN_IOU, MAX_MISSED, STAGES, LIVE, FLOW_IDS,
      overlap, validate, traceUpdate, example, descriptions};
  if (typeof document === "undefined") return;

  const $ = id => document.getElementById(id);
  const svgNS = "http://www.w3.org/2000/svg";
  const flow = [
    {id:"create", name:"Create once", x:100, y:85, kind:"worker"},
    {id:"infer", name:"Infer frame", x:310, y:85, kind:"worker"},
    {id:"match", name:"Match IDs", x:510, y:85, kind:"worker"},
    ...STAGES.map((name, i) => ({id:`tracker-${i}`, name, x:510 + i * 130, y:310, kind:"tracker"})),
    {id:"publish", name:"Publish", x:1550, y:85, kind:"worker"}
  ];
  const trace = example();
  const detail = descriptions(trace);
  let current = 0, pinned = null, timer = null;

  /** Use tiny diagrams for the decisions that are harder to infer from text. */
  function visualFor(index) {
    const chip = (label, tone="") => `<span class="chip ${tone}">${label}</span>`;
    const arrow = '<span class="arrow">→</span>';
    if (index === 3) {
      const old = trace.before.find(t => t.id === 1).box, now = trace.boxes[0];
      const x = value => (value - 680) * 0.8 + 8;
      const y = value => (value - 310) * 0.4 + 8;
      const rect = (box, color) => `<rect x="${x(box[0])}" y="${y(box[1])}" width="${(box[2]-box[0])*0.8}" height="${(box[3]-box[1])*0.4}" fill="none" stroke="${color}" stroke-width="3"/>`;
      const both = [Math.max(old[0], now[0]), Math.max(old[1], now[1]),
        Math.min(old[2], now[2]), Math.min(old[3], now[3])];
      return `<svg viewBox="0 0 300 130" aria-label="Old and current rectangles overlap"><rect x="${x(both[0])}" y="${y(both[1])}" width="${(both[2]-both[0])*0.8}" height="${(both[3]-both[1])*0.4}" fill="#417f68"/>${rect(old,"#79dcec")}${rect(now,"#e8b478")}<text x="8" y="127" font-size="11" fill="#79dcec">old #1</text><text x="75" y="127" font-size="11" fill="#e8b478">d₀</text></svg>${arrow}${chip(`overlap ÷ union = ${trace.pairs.find(p => p.id === 1 && p.index === 0).math.iou.toFixed(3)}`, "accept")}`;
    }
    if (index === 5) return `${chip("d₀ → #1", "accept")}${chip("d₁ → #1", "reject")}${arrow}${chip("d₁ needs new ID")}`;
    if (index === 6) return `${chip("missed 0")}${arrow}${chip("missed 1 · hidden")}${arrow}${chip("missed 2 · retired", "reject")}`;
    const paths = [
      ["detector list", "d₀ has no ID"], ["box_xyxy", "valid float box"],
      ["old #1 + d₀", "same class"], [],
      ["eligible pairs", "highest IoU first"], [], [],
      ["d₀ + old #1", "d₀ gets track_id 1"],
      ["current detections", "returned IDs [1, 3, 2]"]
    ];
    return `${chip(paths[index][0])}${arrow}${chip(paths[index][1], "accept")}`;
  }

  /** Show the payload changing at the surrounding worker stages. */
  function liveVisual(key) {
    const labels = {
      create:["worker starts", "persistent tracker"],
      infer:["newest frame", "boxes without IDs"],
      match:["detector boxes", "enter nine decisions ↓"],
      publish:["ID-bearing boxes", "latest API result"]
    };
    const [before, after] = labels[key];
    return `<span class="chip">${before}</span><span class="arrow">→</span><span class="chip accept">${after}</span>`;
  }

  /** Draw one executable route through the nested call and one dotted overview. */
  function buildGraph() {
    const routes = ["M 133 85 H 277", "M 343 85 H 477", "M 510 118 V 278"];
    for (let i = 0; i < STAGES.length - 1; i++)
      routes.push(`M ${flow[3 + i].x + 30} 310 H ${flow[4 + i].x - 30}`);
    routes.push("M 1550 278 V 118");
    for (const route of routes) {
      const edge = document.createElementNS(svgNS, "path");
      edge.setAttribute("d", route);
      edge.setAttribute("class", "edge");
      edge.setAttribute("marker-end", "url(#edge-arrow)");
      $("edges").appendChild(edge);
    }
    const overview = document.createElementNS(svgNS, "path");
    overview.setAttribute("d", "M 548 85 H 1512");
    overview.setAttribute("class", "overview");
    overview.setAttribute("marker-end", "url(#edge-arrow)");
    $("edges").appendChild(overview);
    const caption = document.createElementNS(svgNS, "text");
    caption.setAttribute("x", "1030");
    caption.setAttribute("y", "64");
    caption.setAttribute("class", "overview-label");
    caption.textContent = "collapsed overview only · no bypass";
    $("edges").appendChild(caption);

    flow.forEach((step, i) => {
      const group = document.createElementNS(svgNS, "g");
      group.setAttribute("class", `node ${step.kind}`);
      group.setAttribute("transform", `translate(${step.x},${step.y})`);
      group.setAttribute("tabindex", "0");
      group.setAttribute("role", "button");
      group.setAttribute("aria-label", `Step ${i + 1}: ${step.name}`);
      const number = step.kind === "tracker" ? i - 2 : i === 12 ? 4 : i + 1;
      group.innerHTML = `<circle r="30"></circle><text class="number" y="1">${number}</text><text class="label" y="56">${step.name}</text>`;
      group.addEventListener("mouseenter", () => showDetail(i));
      group.addEventListener("mouseleave", () => restoreDetail());
      group.addEventListener("focus", () => showDetail(i));
      group.addEventListener("blur", () => restoreDetail());
      group.addEventListener("click", () => select(i));
      group.addEventListener("keydown", event => {
        if (event.key === "Enter" || event.key === " ") { event.preventDefault(); select(i); }
      });
      $("nodes").appendChild(group);
    });
  }

  /** Reveal the selected node's rule and concrete before/after values. */
  function showDetail(index) {
    const step = flow[index];
    const inTracker = step.kind === "tracker";
    const item = inTracker ? detail[index - 3] : LIVE[step.id];
    $("detail").hidden = false;
    $("detail-stage").textContent = inTracker ?
      `Inside BasicTracker.update · decision ${index - 2} / ${STAGES.length}` :
      `Live worker · step ${index === 12 ? 4 : index + 1} / 4`;
    $("detail-title").textContent = inTracker ? step.name : item.title;
    $("detail-rule").textContent = item.rule;
    $("detail-visual").innerHTML = inTracker ? visualFor(index - 3) : liveVisual(step.id);
    $("detail-data").textContent = item.data;
    $("detail-effect").textContent = item.effect;
    $("detail-link").textContent = item.code;
    $("detail-link").setAttribute("href", inTracker ?
      "../../src/vision/basic_tracker.py" : "../../src/vision/live_detector.py");
  }

  /** Restore the pinned node after a hover, or hide details after Reset. */
  function restoreDetail() {
    if (pinned === null) $("detail").hidden = true;
    else showDetail(pinned);
  }

  /** Move the changing payload along the solid execution route only. */
  function render() {
    const nodes = $("nodes").children, edges = $("edges").children;
    for (let i = 0; i < nodes.length; i++)
      nodes[i].setAttribute("class", `node ${flow[i].kind} ${i === current ? "current" : i < current ? "done" : ""}`);
    for (let i = 0; i < flow.length - 1; i++)
      edges[i].setAttribute("class", `edge ${i < current ? "done" : ""}`);
    const step = flow[current];
    $("object-token").style.transform = `translate(${step.x}px, ${step.y - 55}px)`;
    $("token-label").textContent = current === 0 ? "worker" : current === 1 ? "frame" :
      current === 2 ? "boxes" : current === flow.length - 1 ? "IDs" : "d₀";
    $("position").textContent = `${current + 1} of ${flow.length} · ${step.name}`;
    $("previous").disabled = current === 0;
    $("next").disabled = current === flow.length - 1;
  }

  /** Stop playback when a person takes control or the token reaches Publish. */
  function stop() {
    if (timer !== null) clearInterval(timer);
    timer = null;
    $("play").textContent = "Play";
  }

  /** Select one node; manual selection pins its explanation. */
  function select(index) {
    stop();
    current = index;
    pinned = index;
    render();
    showDetail(index);
  }

  buildGraph();
  $("previous").addEventListener("click", () => select(Math.max(0, current - 1)));
  $("next").addEventListener("click", () => select(Math.min(flow.length - 1, current + 1)));
  $("reset").addEventListener("click", () => {
    stop(); current = 0; pinned = null; render(); restoreDetail();
  });
  $("play").addEventListener("click", () => {
    if (timer !== null) { stop(); return; }
    if (current === flow.length - 1) { current = 0; render(); }
    $("play").textContent = "Pause";
    timer = setInterval(() => {
      current++;
      pinned = current;
      render();
      showDetail(current);
      if (current === flow.length - 1) stop();
    }, 1100);
  });
  render();
})();
