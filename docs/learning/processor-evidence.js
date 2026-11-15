/* Charts for processor-evidence.html.
   Every value is copied from a committed result file named next to it; derived
   values are calculated here from those numbers and labelled on the page. */
(function () {
  "use strict";
  const Charts = window.EdgeCharts;
  const $ = (id) => document.getElementById(id);

  // benchmarks/results/ap-baseline-basic-2026-10-18.md (medians over 297 polls).
  const base = { pythonPct: 188.39, ffmpegPct: 34.54, systemBusyPct: 56.93, pythonRss: 145.90, ffmpegRss: 158.12 };
  const busyCores = 4 * base.systemBusyPct / 100;
  const other = Math.max(0, busyCores - (base.pythonPct + base.ffmpegPct) / 100);
  Charts.stack($("cores-chart"), {
    title: "Four cores, median during the full live workload",
    note: "Core-equivalents: 1.0 = one core fully busy for the whole run.",
    unit: "cores", total: 4, guides: 1, guideFormat: (g) => `${g} core${g === 1 ? "" : "s"}`,
    segments: [
      { label: "EdgeXR Python", value: base.pythonPct / 100, color: "var(--s1)", note: "Preview process: motion, detector, IMU, tracker, web server threads (188.39% of one core)" },
      { label: "FFmpeg decode", value: base.ffmpegPct / 100, color: "var(--s2)", note: "Separate process decoding MJPEG frames (34.54% of one core)" },
      { label: "Other", value: other, color: "var(--s3)", note: "Everything else: system busy minus the two processes (derived)" },
      { label: "Idle", value: 4 - busyCores, color: "#2b394a", note: "Capacity not used, 4 − 4 × 56.93%" },
    ],
  });
  $("baseline-stats").innerHTML = [
    [`${busyCores.toFixed(2)} of 4`, "cores busy on average (56.93% system busy)"],
    [`${base.pythonRss.toFixed(0)} MiB`, "EdgeXR Python resident memory"],
    [`${base.ffmpegRss.toFixed(0)} MiB`, "FFmpeg resident memory"],
    ["2.23 cores", "Python + FFmpeg together; the rest is idle or other work"],
  ].map(([v, s]) => `<div class="stat"><strong>${v}</strong><span>${s}</span></div>`).join("");

  Charts.bars($("rates-chart"), {
    title: "Completed updates per second (median)",
    rows: [
      { label: "camera capture", sub: "frames into the app", values: [30.09] },
      { label: "motion analysis", sub: "phase correlation", values: [26.16] },
      { label: "IMU reads", sub: "50 ms pause at the time", values: [18.87] },
      { label: "detector", sub: "MobileNet-SSD, throttled", values: [2.00] },
    ],
    unit: "Hz", digits: 2, labelWidth: 150, max: 35, rowHeight: 40,
  });

  // Latency rows come from different runs; each sub-label names its source.
  Charts.bars($("latency-chart"), {
    title: "Time per step: median and 95th percentile",
    series: [{ name: "median", color: "var(--s1)" }, { name: "95th percentile", color: "var(--s2)" }],
    rows: [
      { label: "IMU I2C read", sub: "IMU policy runs, Oct 24", values: [2.62, null], note: "Median read duration; p95 not reported." },
      { label: "motion estimate", sub: "AP baseline, Oct 18", values: [30.98, 53.55] },
      { label: "scene memory", sub: "ORB + match + RANSAC, Nov 2", values: [116.15, 126.04], note: "640×360, detector off, 1 Hz (scheduling A/B run A)." },
      { label: "detector compute", sub: "AP baseline, Oct 18", values: [226.39, 243.65] },
      { label: "detector box age", sub: "AP baseline, Oct 18", values: [429.76, 706.98], note: "Time from frame receipt until the once-per-second profiler first saw its boxes." },
    ],
    unit: "ms", log: true, min: 1, max: 1000, labelWidth: 170, rowHeight: 44, valueFormat: (v) => v.toFixed(v < 10 ? 1 : 0),
  });

  // benchmarks/results/spatial-stalls-02.json and observer-ram-control-01.json.
  Charts.bars($("tail-chart"), {
    title: "Evidence image writes to microSD (180 writes)",
    note: "Spatial stalls run 02, Nov 6. Logarithmic axis.",
    rows: [
      { label: "median", values: [14.26] },
      { label: "95th percentile", values: [25.65] },
      { label: "worst write", values: [3611.54] },
    ],
    unit: "ms", log: true, min: 1, max: 10000, labelWidth: 120, valueFormat: (v) => v.toFixed(0),
  });
  Charts.bars($("ram-chart"), {
    title: "Worst stall: profiler log on microSD vs in RAM",
    note: "One pair of 180 s runs, reviewed Nov 8. Only the profiler’s own log moved. Logarithmic axis.",
    series: [{ name: "profiler log on microSD", color: "var(--s2)" }, { name: "profiler log in RAM", color: "var(--s1)" }],
    rows: [
      { label: "profiler sample gap", values: [2016.62, 253.90] },
      { label: "app image write", values: [2109.89, 39.21] },
      { label: "writer queue wait", values: [1109.89, 6.11] },
    ],
    unit: "ms", log: true, min: 1, max: 10000, labelWidth: 150, valueFormat: (v) => v.toFixed(0),
  });
})();
