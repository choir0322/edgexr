/* Hub page: system map, study cards and the five-step plan, drawn from data so
   the status of each component is stated once. Status meanings:
   measured = runs today with committed Pi measurements; pending = runs today
   but its accuracy or Pi behaviour is not yet validated; planned = not built. */
(function () {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const COLORS = { measured: "#65d8bb", pending: "#82bcff", planned: "#d6b0f3", sensor: "#98a8bb" };

  // Columns: sensors, processing, spatial awareness, outputs. Coordinates are SVG units.
  const NODES = [
    { id: "camera", col: 0, y: 70, title: "Camera", sub: "OV9281 · 1280×720 · 30 fps", status: "sensor", href: "program-flow-explorer.html" },
    { id: "imu", col: 0, y: 270, title: "Gyro (IMU)", sub: "SH3001 · ≈78 reads/s", status: "sensor", href: "orientation-explorer.html" },
    { id: "servo", col: 0, y: 450, title: "Pan/tilt servos", sub: "moves camera + IMU", status: "sensor", href: "orientation-explorer.html" },
    { id: "motion", col: 1, y: 20, title: "Image motion", sub: "Hann + FFT phase corr.", status: "measured", href: "hann-fft-explorer.html" },
    { id: "detector", col: 1, y: 95, title: "Object detector", sub: "MobileNet-SSD · 2 Hz", status: "measured", href: "detection-architecture.html" },
    { id: "scene", col: 1, y: 170, title: "Scene memory", sub: "ORB views + view map", status: "measured", href: "orb-scene-explorer.html" },
    { id: "orientation", col: 1, y: 270, title: "Head orientation", sub: "gyro → quaternion", status: "pending", href: "orientation-explorer.html" },
    { id: "geometry", col: 1, y: 360, title: "Camera geometry", sub: "calibration · needs review", status: "pending", href: "camera-geometry.html" },
    { id: "depth", col: 1, y: 450, title: "Depth network", sub: "near / far · step 4", status: "planned", href: "detection-architecture.html" },
    { id: "tracker", col: 2, y: 95, title: "Tracker IDs", sub: "IoU · short-term", status: "measured", href: "basic-tracker.html" },
    { id: "bearings", col: 2, y: 225, title: "Object bearings", sub: "step 1 · Pi trial pending", status: "pending", href: "camera-geometry.html" },
    { id: "memory", col: 2, y: 330, title: "Object memory", sub: "predict · step 2", status: "planned", href: "basic-tracker.html" },
    { id: "drift", col: 2, y: 440, title: "Drift correction", sub: "step 3", status: "planned", href: "orientation-explorer.html" },
    { id: "browser", col: 3, y: 95, title: "Browser preview", sub: "Mac over SSH", status: "measured", href: "program-flow-explorer.html" },
    { id: "recorder", col: 3, y: 225, title: "Recorder + profiler", sub: "bounded queue", status: "measured", href: "edgexr-worker-rates.html" },
    { id: "profile", col: 3, y: 380, title: "Processor profile", sub: "per stage · step 5", status: "planned", href: "processor-evidence.html" },
  ];
  const X = [20, 300, 590, 880], W = 205, H = 56;
  const EDGES = [
    ["camera", "motion"], ["camera", "detector"], ["camera", "scene"], ["camera", "depth", "planned"],
    ["imu", "orientation"], ["servo", "camera", "physical"], ["servo", "imu", "physical"],
    ["detector", "tracker"], ["detector", "bearings"], ["orientation", "bearings"], ["geometry", "bearings"],
    ["bearings", "memory", "planned"], ["depth", "memory", "planned"], ["scene", "drift", "planned"], ["motion", "drift", "planned"],
    ["motion", "browser"], ["tracker", "browser"], ["scene", "recorder"], ["orientation", "recorder"], ["memory", "browser", "planned"],
  ];

  /**
   * Find a node record by id.
   * @param {string} id Node id.
   * @returns {object} Node.
   */
  function node(id) { return NODES.find((n) => n.id === id); }

  /**
   * Cubic curve from the right edge of one node to the left edge of another;
   * same-column links (servo → sensors) bend around the left side instead.
   * @param {object} a Source node.
   * @param {object} b Target node.
   * @returns {string} SVG path data.
   */
  function curve(a, b) {
    if (a.col === b.col) {
      const x = X[a.col] - 4, y1 = a.y + H / 2, y2 = b.y + H / 2;
      return `M${x},${y1} C${x - 18},${y1} ${x - 18},${y2} ${x},${y2}`;
    }
    const x1 = X[a.col] + W, y1 = a.y + H / 2, x2 = X[b.col], y2 = b.y + H / 2, mid = (x1 + x2) / 2;
    return `M${x1},${y1} C${mid},${y1} ${mid},${y2} ${x2 - 6},${y2}`;
  }

  // System map.
  let svg = `<defs>${["built", "planned", "physical"].map((k) => `<marker id="arrow-${k}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="${k === "planned" ? COLORS.planned : "#5c6b7c"}"/></marker>`).join("")}</defs>`;
  ["Sensors", "Processing", "Spatial awareness", "Outputs"].forEach((name, i) => {
    svg += `<text x="${X[i]}" y="12" fill="#6f8196" font-size="11" letter-spacing="1.5">${name.toUpperCase()}</text>`;
  });
  for (const [from, to, kind = "built"] of EDGES) {
    const dash = kind === "planned" ? ' stroke-dasharray="6 5"' : kind === "physical" ? ' stroke-dasharray="2 4"' : "";
    svg += `<path d="${curve(node(from), node(to))}" fill="none" stroke="${kind === "planned" ? COLORS.planned : "#5c6b7c"}" stroke-width="${kind === "planned" ? 1.6 : 1.8}" opacity="${kind === "planned" ? 0.8 : 1}"${dash} marker-end="url(#arrow-${kind})"/>`;
  }
  for (const n of NODES) {
    const color = COLORS[n.status], x = X[n.col];
    const dash = n.status === "planned" ? ' stroke-dasharray="7 5"' : "";
    const tag = { measured: "built · measured", pending: "built · not yet validated", planned: "planned", sensor: "hardware" }[n.status];
    svg += `<a href="${n.href}" aria-label="${n.title}: ${n.sub} (${tag})"><rect class="node" x="${x}" y="${n.y}" width="${W}" height="${H}" rx="9" fill="${n.status === "planned" ? "#1d1826" : "#121b26"}" stroke="${color}" stroke-width="1.8"${dash}/>` +
      `<circle cx="${x + 14}" cy="${n.y + 18}" r="4" fill="${color}"/>` +
      `<text x="${x + 26}" y="${n.y + 23}" fill="#e5edf6" font-size="14" font-weight="600">${n.title}</text>` +
      `<text x="${x + 14}" y="${n.y + 43}" fill="#98a8bb" font-size="12">${n.sub}</text></a>`;
  }
  $("system-map").innerHTML = svg;
  $("map-legend").innerHTML = [["measured", "built and measured on the Pi"], ["pending", "built; accuracy or Pi validation pending"], ["planned", "planned step"], ["sensor", "hardware"]]
    .map(([k, t]) => `<span><i style="background:${COLORS[k]}"></i>${t}</span>`).join("") +
    `<span>solid arrow: data today · pink dashed: planned data flow · dotted: physical movement</span>`;
  const count = (s) => NODES.filter((n) => n.status === s).length;
  $("status-counts").innerHTML = [
    [count("measured"), "parts built and measured on the Pi"],
    [count("pending"), "built, accuracy not yet validated"],
    [count("planned"), "planned steps before the FPGA work"],
    ["4 cores", "Raspberry Pi 4 CPU; no neural accelerator"],
  ].map(([v, s]) => `<div class="stat"><strong>${v}</strong><span>${s}</span></div>`).join("");

  // Study path, in the same order as the navigation bar.
  const CARDS = [
    ["program-flow-explorer.html", "Program map", "What runs, and what talks to what?", "Expandable graph of the live program: workers, latest-frame slots, browser snapshot."],
    ["hann-fft-explorer.html", "Image motion", "How does the program know the picture shifted?", "Two real Pi frames through patches, Hann window, FFT phase correlation and consensus."],
    ["detection-architecture.html", "Detector model", "How does MobileNet-SSD find a bottle, and what does it cost?", "Convolutions, depthwise-separable layers, SSD boxes, and where 1.12 billion operations go."],
    ["basic-tracker.html", "Tracker IDs", "How do boxes keep an ID, and why is it lost when the head looks away?", "IoU overlap, greedy matching, a worked example, and the bridge to object memory."],
    ["orientation-explorer.html", "Head orientation", "Where is the head pointing?", "Gyro integration, sampling luck, bias drift, IMU axes, quaternions, polling cost."],
    ["camera-geometry.html", "Pixel → direction", "Which way is a pixel?", "Pinhole model, the camera’s angle grid, lens distortion, calibration, step-1 preview."],
    ["orb-scene-explorer.html", "Scene memory", "How does a view become familiar?", "ORB keypoints, 256-bit descriptors, Hamming matching, RANSAC, known or unknown."],
    ["sparse-scene-01.html", "3D from two views", "How do two photos give depth, and why can’t a pan/tilt head do it?", "Triangulation on recorded scenes, and rotation versus translation."],
    ["edgexr-worker-rates.html", "Workers & storage", "How do threads, queues and the microSD card interact?", "Worker rates, latest slots, bounded writer queue, kernel I/O evidence."],
    ["processor-evidence.html", "Processor evidence", "Where do the four cores and the milliseconds go?", "Measured CPU, rates, latency, heat and storage stalls, with gaps for step 5."],
  ];
  $("study-cards").innerHTML = CARDS.map(([href, title, q, d], i) =>
    `<a class="card" href="${href}"><span class="num">${String(i + 1).padStart(2, "0")}</span><h3>${title}</h3><p class="q">${q}</p><p>${d}</p></a>`).join("");

  // Five-step plan with reading and the processor question for each step.
  const PLAN = [
    ["Detections become directions", "Undistort the box centre with the calibration, rotate it by the head quaternion at that frame’s time, report the bearing.", [["camera-geometry.html", "Pixel → direction"], ["orientation-explorer.html", "Head orientation"]], "Timing: matching a camera frame to the gyro reading from the same moment (two clocks, latency)."],
    ["Object memory and prediction", "Remember class, bearing, appearance and depth rank; predict where remembered objects should reappear; report matched / missing / moved over repeated sweeps.", [["basic-tracker.html", "Tracker IDs"], ["orb-scene-explorer.html", "Scene memory"]], "Data structures and memory bounds; cost per lookup as the memory grows."],
    ["Drift correction", "Compare the gyro with phase-correlation shift and re-anchor when ORB recognizes a remembered view.", [["orientation-explorer.html", "Head orientation"], ["hann-fft-explorer.html", "Image motion"]], "Several workers at different rates on four cores: scheduling, freshness, contention."],
    ["Near / far", "A small monocular depth network on the CPU at a low rate; relative depth per box. Needs your approval of a specific model.", [["detection-architecture.html", "Detector model"], ["sparse-scene-01.html", "3D from two views"]], "Heavy convolution compute and memory traffic; float versus int8."],
    ["Whole-program profile", "One documented integrated run with per-stage CPU, latency percentiles, memory and temperature; rank kernels for NEON or FPGA work.", [["processor-evidence.html", "Processor evidence"], ["edgexr-worker-rates.html", "Workers & storage"]], "Which kernel is worth optimizing first, measured rather than assumed."],
  ];
  $("plan-steps").innerHTML = PLAN.map(([title, what, reads, sys], i) =>
    `<div class="step"><div class="n">${i + 1}</div><div><h3>${title}</h3><p>${what}</p><p class="reads">Read first: ${reads.map(([h, t]) => `<a href="${h}">${t}</a>`).join("")}</p></div><div class="sys"><b>Processor question</b>${sys}</div></div>`).join("");
})();
