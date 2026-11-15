/* Small dependency-free SVG charts for the EdgeXR learning pages.
   Pages must work offline from a clone, so no charting library is loaded.
   Every chart draws at the container's real width (text stays at true size),
   shows a tooltip on hover or keyboard focus, and adds a table twin so no value
   is reachable only by hovering. Colours come from CSS variables in
   learning-site.css; text always uses ink colours, never the series colour. */
(function (global) {
  "use strict";
  const NS = "http://www.w3.org/2000/svg";

  /**
   * Create an SVG element with attributes and optionally append it.
   * @param {string} name SVG tag name.
   * @param {Object<string,(string|number)>} attrs Attribute map.
   * @param {Element} [parent] Element that receives the new node.
   * @returns {SVGElement} New element.
   */
  function el(name, attrs, parent) {
    const node = document.createElementNS(NS, name);
    for (const key of Object.keys(attrs || {})) node.setAttribute(key, attrs[key]);
    if (parent) parent.appendChild(node);
    return node;
  }

  /**
   * Format a number with a sensible number of decimals for its size.
   * @param {number} value Value to print.
   * @param {number} [digits] Fixed decimals; automatic when omitted.
   * @returns {string} Display text.
   */
  function fmt(value, digits) {
    if (value === null || value === undefined || !Number.isFinite(value)) return "not measured";
    if (digits !== undefined) return value.toFixed(digits);
    const size = Math.abs(value);
    if (size >= 1000) return Math.round(value).toLocaleString("en-US");
    if (size >= 100) return value.toFixed(0);
    if (size >= 10) return value.toFixed(1);
    return value.toFixed(2);
  }

  /**
   * Axis tick text without trailing zeros (2 rather than 2.00, 0.5 rather than 0.50).
   * @param {number} value Tick value.
   * @returns {string} Display text.
   */
  function tick(value) {
    return Number(value.toPrecision(10)).toLocaleString("en-US", { maximumFractionDigits: 2 });
  }

  /**
   * Round a maximum up to a readable axis end and produce evenly spaced ticks.
   * @param {number} max Largest value that must fit.
   * @param {number} [count] Approximate number of intervals.
   * @returns {number[]} Ticks from zero to the rounded maximum.
   */
  function niceTicks(max, count) {
    const target = count || 5;
    if (!(max > 0)) return [0, 1];
    const raw = max / target;
    const power = Math.pow(10, Math.floor(Math.log10(raw)));
    const step = [1, 2, 2.5, 5, 10].map((m) => m * power).find((s) => s >= raw);
    const ticks = [];
    for (let t = 0; t <= max + step * 0.999; t += step) ticks.push(Number(t.toPrecision(12)));
    return ticks;
  }

  /**
   * Powers of ten covering a positive range, for logarithmic axes.
   * @param {number} min Smallest positive value.
   * @param {number} max Largest value.
   * @returns {number[]} Ticks such as [1, 10, 100, 1000].
   */
  function logTicks(min, max) {
    const ticks = [];
    for (let p = Math.floor(Math.log10(min)); p <= Math.ceil(Math.log10(max)); p++) ticks.push(Math.pow(10, p));
    return ticks;
  }

  /**
   * Path for a horizontal bar whose free (value) end has rounded corners.
   * The baseline end stays square so the bar visibly starts at the axis.
   * @param {number} x Baseline x.
   * @param {number} y Top y.
   * @param {number} w Width in pixels.
   * @param {number} h Height in pixels.
   * @returns {string} SVG path data.
   */
  function barPath(x, y, w, h) {
    const r = Math.max(0, Math.min(4, h / 2, w));
    return `M${x},${y}H${x + w - r}A${r},${r} 0 0 1 ${x + w},${y + r}V${y + h - r}` +
      `A${r},${r} 0 0 1 ${x + w - r},${y + h}H${x}Z`;
  }

  /**
   * Re-render a chart whenever its container changes width.
   * @param {HTMLElement} box Element whose width drives the drawing.
   * @param {function(number):void} draw Renders at the given width.
   * @returns {void}
   */
  function responsive(box, draw) {
    let last = -1;
    /** Draw only when the usable width actually changed. @returns {void} */
    function redraw() {
      const width = Math.max(300, Math.floor(box.clientWidth || 640));
      if (width === last) return;
      last = width;
      draw(width);
    }
    redraw();
    if (typeof ResizeObserver !== "undefined") new ResizeObserver(redraw).observe(box);
    else window.addEventListener("resize", redraw);
  }

  /**
   * Build the shared chart frame: title, note, legend, plot box, tooltip, table.
   * @param {HTMLElement} container Empty element that receives the chart.
   * @param {object} o Options with title, note, series, table headers and rows.
   * @returns {{plot:HTMLElement, tip:{show:Function, hide:Function}}} Plot box and tooltip.
   */
  function frame(container, o) {
    container.classList.add("chart-frame");
    container.innerHTML = "";
    if (o.title) {
      const title = document.createElement("p");
      title.className = "chart-title";
      title.innerHTML = o.title;
      container.appendChild(title);
    }
    if (o.note) {
      const note = document.createElement("p");
      note.className = "chart-note";
      note.innerHTML = o.note;
      container.appendChild(note);
    }
    // A legend is present whenever colour distinguishes two or more series.
    if (o.series && o.series.length > 1) {
      const legend = document.createElement("div");
      legend.className = "legend";
      legend.innerHTML = o.series.map((s) => `<span><i style="background:${s.color}"></i>${s.name}</span>`).join("");
      container.appendChild(legend);
    }
    const plot = document.createElement("div");
    plot.className = "chart";
    container.appendChild(plot);
    const tipNode = document.createElement("div");
    tipNode.className = "tooltip";
    tipNode.setAttribute("role", "status");
    plot.appendChild(tipNode);
    const tip = {
      /** Show tooltip HTML near a point in plot coordinates. @param {string} html Content. @param {number} x Left px. @param {number} y Top px. @returns {void} */
      show(html, x, y) {
        tipNode.innerHTML = html;
        tipNode.classList.add("show");
        const maxLeft = plot.clientWidth - tipNode.offsetWidth - 4;
        tipNode.style.left = `${Math.max(0, Math.min(maxLeft, x + 14))}px`;
        tipNode.style.top = `${Math.max(0, y - tipNode.offsetHeight - 10)}px`;
      },
      /** Hide the tooltip. @returns {void} */
      hide() { tipNode.classList.remove("show"); },
    };
    if (o.table) {
      const details = document.createElement("details");
      details.className = "table-view";
      const head = o.table.headers.map((h, i) => `<th${i ? ' class="n"' : ""}>${h}</th>`).join("");
      const body = o.table.rows.map((r) => `<tr>${r.map((c, i) => `<td${i ? ' class="n"' : ""}>${c}</td>`).join("")}</tr>`).join("");
      details.innerHTML = `<summary>Table view</summary><table class="data"><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table>`;
      container.appendChild(details);
    }
    return { plot, tip };
  }

  /**
   * Attach hover and keyboard-focus tooltip behaviour to a hit target.
   * @param {SVGElement} hit Transparent target larger than the mark.
   * @param {{show:Function, hide:Function}} tip Tooltip controller.
   * @param {HTMLElement} plot Plot box used for coordinates.
   * @param {string} html Tooltip content.
   * @param {SVGElement[]} marks Marks to brighten while active.
   * @returns {void}
   */
  function bindTip(hit, tip, plot, html, marks) {
    hit.setAttribute("tabindex", "0");
    hit.setAttribute("role", "img");
    hit.setAttribute("aria-label", html.replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim());
    /** Show for a pointer event. @param {MouseEvent} e Event. @returns {void} */
    function move(e) {
      const box = plot.getBoundingClientRect();
      marks.forEach((m) => m.classList.add("hover"));
      tip.show(html, e.clientX - box.left, e.clientY - box.top);
    }
    /** Show for keyboard focus at the target's position. @returns {void} */
    function focus() {
      const box = plot.getBoundingClientRect(), r = hit.getBoundingClientRect();
      marks.forEach((m) => m.classList.add("hover"));
      tip.show(html, r.left - box.left + r.width / 2, r.top - box.top);
    }
    /** Hide and un-highlight. @returns {void} */
    function leave() { marks.forEach((m) => m.classList.remove("hover")); tip.hide(); }
    hit.addEventListener("mousemove", move);
    hit.addEventListener("focus", focus);
    hit.addEventListener("mouseleave", leave);
    hit.addEventListener("blur", leave);
  }

  /**
   * Horizontal bar chart: one bar per row, grouped series, or colour by row kind.
   * @param {HTMLElement} container Target element.
   * @param {object} o Options: rows [{label, sub, values[], kind, note}], series
   *   [{name,color}], unit, log, max, labelWidth, valueLabels, digits, title, note.
   * @returns {void}
   */
  function bars(container, o) {
    const series = o.series || [{ name: "", color: "var(--s1)" }];
    const byKind = o.rows.some((r) => r.kind !== undefined);
    const perRow = byKind ? 1 : series.length;
    const headers = ["", ...(byKind ? ["Kind", `Value (${o.unit || ""})`] : series.map((s) => s.name || `Value (${o.unit || ""})`))];
    const tableRows = o.rows.map((r) => [r.label + (r.sub ? ` · ${r.sub}` : ""),
      ...(byKind ? [series[r.kind].name, fmt(r.values[0], o.digits)] : r.values.map((v) => fmt(v, o.digits)))]);
    const { plot, tip } = frame(container, { ...o, series: series.length > 1 ? series : null, table: { headers, rows: tableRows } });
    const all = o.rows.flatMap((r) => r.values).filter((v) => Number.isFinite(v));
    responsive(plot, (width) => {
      plot.querySelectorAll("svg").forEach((s) => s.remove());
      const labelW = Math.min(o.labelWidth || 200, width * 0.42);
      const valueW = o.valueLabels === false ? 14 : 70;
      const barH = o.barHeight || (perRow > 1 ? 10 : 12), gap = 3;
      const rowH = Math.max(o.rowHeight || 0, perRow * barH + (perRow - 1) * gap + (o.rowPad === undefined ? 16 : o.rowPad));
      const plotW = Math.max(60, width - labelW - valueW), top = 4, axisH = 40;
      const height = top + o.rows.length * rowH + axisH;
      let ticks, x;
      if (o.log) {
        const lo = o.min || Math.pow(10, Math.floor(Math.log10(Math.min(...all))));
        ticks = logTicks(lo, o.max || Math.max(...all));
        const a = Math.log10(ticks[0]), b = Math.log10(ticks[ticks.length - 1]);
        x = (v) => labelW + plotW * (Math.log10(Math.max(v, ticks[0])) - a) / (b - a);
      } else {
        ticks = niceTicks(o.max || Math.max(...all), o.ticks || 5);
        const end = ticks[ticks.length - 1];
        x = (v) => labelW + plotW * v / end;
      }
      const svg = el("svg", { viewBox: `0 0 ${width} ${height}`, width, height, role: "group", "aria-label": o.ariaLabel || o.title || "Bar chart" });
      plot.insertBefore(svg, plot.firstChild);

      // Recessive grid and tick labels first, so marks draw on top.
      const grid = el("g", { class: "grid" }, svg);
      ticks.forEach((t) => {
        el("line", { x1: x(t), x2: x(t), y1: top, y2: height - axisH + 4 }, grid);
        const label = el("text", { x: x(t), y: height - axisH + 20, class: "tick", "text-anchor": "middle" }, svg);
        label.textContent = o.tickFormat ? o.tickFormat(t) : tick(t);
      });
      const unit = el("text", { x: labelW + plotW, y: height - 2, class: "sub", "text-anchor": "end" }, svg);
      unit.textContent = o.unit || "";
      el("line", { x1: labelW, x2: labelW, y1: top, y2: height - axisH + 4, class: "", stroke: "var(--axis)" }, svg);

      // One row per label; a transparent full-row target carries the tooltip.
      o.rows.forEach((row, i) => {
        const y0 = top + i * rowH;
        const name = el("text", { x: labelW - 10, y: y0 + rowH / 2 + (row.sub ? -2 : 4), class: "label", "text-anchor": "end" }, svg);
        name.textContent = row.label;
        if (row.sub) {
          const sub = el("text", { x: labelW - 10, y: y0 + rowH / 2 + 12, class: "sub", "text-anchor": "end" }, svg);
          sub.textContent = row.sub;
        }
        const block = perRow * barH + (perRow - 1) * gap;
        const marks = [];
        const values = byKind ? [row.values[0]] : row.values;
        values.forEach((v, j) => {
          const by = y0 + (rowH - block) / 2 + j * (barH + gap);
          const color = (byKind ? series[row.kind] : series[j]).color;
          if (!Number.isFinite(v)) {
            const t = el("text", { x: labelW + 6, y: by + barH - 2, class: "sub" }, svg);
            t.textContent = "not measured";
            return;
          }
          const base = o.log ? x(ticks[0]) : labelW;
          marks.push(el("path", { d: barPath(base, by, Math.max(1, x(v) - base), barH), fill: color, class: "mark" }, svg));
          if (o.valueLabels !== false) {
            const t = el("text", { x: x(v) + 6, y: by + barH - 1, class: "value" }, svg);
            t.textContent = (o.valueFormat ? o.valueFormat(v) : fmt(v, o.digits)) + (o.valueUnit ? ` ${o.valueUnit}` : "");
          }
        });
        const hit = el("rect", { x: 0, y: y0, width, height: rowH, class: "hit" }, svg);
        const lines = byKind
          ? [`${series[row.kind].name}: <b>${fmt(row.values[0], o.digits)}</b> ${o.unit || ""}`]
          : row.values.map((v, j) => `${series[j].name ? series[j].name + ": " : ""}<b>${fmt(v, o.digits)}</b> ${Number.isFinite(v) ? o.unit || "" : ""}`);
        bindTip(hit, tip, plot, `<b>${row.label}</b>${row.sub ? ` · ${row.sub}` : ""}<br>${lines.join("<br>")}${row.note ? `<br><span class="muted">${row.note}</span>` : ""}`, marks);
      });
    });
  }

  /**
   * One stacked horizontal bar showing parts of a fixed whole.
   * @param {HTMLElement} container Target element.
   * @param {object} o Options: segments [{label, value, color, note}], total, unit, title, note.
   * @returns {void}
   */
  function stack(container, o) {
    const series = o.segments.map((s) => ({ name: s.label, color: s.color }));
    const { plot, tip } = frame(container, { ...o, series,
      table: { headers: ["Part", `Value (${o.unit})`, "Share"], rows: o.segments.map((s) => [s.label, fmt(s.value, 2), `${(100 * s.value / o.total).toFixed(1)}%`]) } });
    responsive(plot, (width) => {
      plot.querySelectorAll("svg").forEach((s) => s.remove());
      const h = 30, top = 4, labelsH = 44, height = top + h + labelsH + 22;
      const svg = el("svg", { viewBox: `0 0 ${width} ${height}`, width, height, role: "group", "aria-label": o.title || "Stacked bar" });
      plot.insertBefore(svg, plot.firstChild);
      let cursor = 0;
      const scale = (v) => (width - 2) * v / o.total;
      o.segments.forEach((s, i) => {
        // 2 px surface gap between neighbouring segments instead of borders.
        const x0 = scale(cursor) + (i ? 1 : 0), w = Math.max(1, scale(s.value) - (i ? 2 : 1));
        const mark = el("rect", { x: x0, y: top, width: w, height: h, rx: 3, fill: s.color, class: "mark" }, svg);
        const hit = el("rect", { x: x0, y: top - 2, width: Math.max(w, 24), height: h + 4, class: "hit" }, svg);
        bindTip(hit, tip, plot, `<b>${s.label}</b><br>${fmt(s.value, 2)} ${o.unit} · ${(100 * s.value / o.total).toFixed(1)}% of ${fmt(o.total, 0)}${s.note ? `<br><span class="muted">${s.note}</span>` : ""}`, [mark]);
        if (w > 74) {
          const name = el("text", { x: x0, y: top + h + 18, class: "label" }, svg);
          name.textContent = s.label;
          const val = el("text", { x: x0, y: top + h + 34, class: "value" }, svg);
          val.textContent = `${fmt(s.value, 2)} ${o.unit}`;
        }
        cursor += s.value;
      });
      // Whole-number guides (for example, one tick per CPU core).
      if (o.guides) for (let g = 0; g <= o.total; g += o.guides) {
        el("line", { x1: scale(g), x2: scale(g), y1: top + h + 2, y2: top + h + 6, stroke: "var(--axis)" }, svg);
        const t = el("text", { x: Math.min(width - 4, Math.max(4, scale(g))), y: height - 2, class: "tick", "text-anchor": g === 0 ? "start" : g === o.total ? "end" : "middle" }, svg);
        t.textContent = o.guideFormat ? o.guideFormat(g) : g;
      }
    });
  }

  /**
   * Scatter plot with direct point labels, for a handful of measured runs.
   * @param {HTMLElement} container Target element.
   * @param {object} o Options: points [{x,y,series,label,note}], series, x/y {label,min,max}, height.
   * @returns {void}
   */
  function scatter(container, o) {
    const { plot, tip } = frame(container, { ...o,
      table: { headers: ["Run", "Series", o.x.label, o.y.label], rows: o.points.map((p) => [p.label || "", o.series[p.series].name, fmt(p.x), fmt(p.y)]) } });
    responsive(plot, (width) => {
      plot.querySelectorAll("svg").forEach((s) => s.remove());
      const m = { l: 52, r: 18, t: 12, b: 44 }, height = o.height || 280;
      const xt = niceTicks(o.x.max || Math.max(...o.points.map((p) => p.x)), 5);
      const yt = niceTicks(o.y.max || Math.max(...o.points.map((p) => p.y)), 5);
      const X = (v) => m.l + (width - m.l - m.r) * v / xt[xt.length - 1];
      const Y = (v) => height - m.b - (height - m.t - m.b) * v / yt[yt.length - 1];
      const svg = el("svg", { viewBox: `0 0 ${width} ${height}`, width, height, role: "group", "aria-label": o.title || "Scatter plot" });
      plot.insertBefore(svg, plot.firstChild);
      const grid = el("g", { class: "grid" }, svg);
      yt.forEach((t) => { el("line", { x1: m.l, x2: width - m.r, y1: Y(t), y2: Y(t) }, grid); const s = el("text", { x: m.l - 8, y: Y(t) + 4, class: "tick", "text-anchor": "end" }, svg); s.textContent = tick(t); });
      xt.forEach((t) => { const s = el("text", { x: X(t), y: height - m.b + 18, class: "tick", "text-anchor": "middle" }, svg); s.textContent = tick(t); });
      el("line", { x1: m.l, x2: width - m.r, y1: Y(0), y2: Y(0), stroke: "var(--axis)" }, svg);
      const xl = el("text", { x: width - m.r, y: height - 6, class: "sub", "text-anchor": "end" }, svg); xl.textContent = o.x.label;
      const yl = el("text", { x: m.l, y: m.t - 2, class: "sub" }, svg); yl.textContent = o.y.label;
      o.points.forEach((p) => {
        // 2 px surface ring keeps overlapping markers separable.
        const mark = el("circle", { cx: X(p.x), cy: Y(p.y), r: 5.5, fill: o.series[p.series].color, stroke: "var(--panel)", "stroke-width": 2, class: "mark" }, svg);
        if (p.label) { const t = el("text", { x: X(p.x) + 10, y: Y(p.y) + 4, class: "value" }, svg); t.textContent = p.label; }
        const hit = el("circle", { cx: X(p.x), cy: Y(p.y), r: 13, class: "hit" }, svg);
        bindTip(hit, tip, plot, `<b>${p.label || o.series[p.series].name}</b><br>${o.x.label}: <b>${fmt(p.x)}</b><br>${o.y.label}: <b>${fmt(p.y)}</b>${p.note ? `<br><span class="muted">${p.note}</span>` : ""}`, [mark]);
      });
    });
  }

  /**
   * Line chart with a crosshair tooltip and optional end labels.
   * @param {HTMLElement} container Target element.
   * @param {object} o Options: series [{name,color,points:[[x,y]],dash,width}], x/y {label,min,max,format}, height, endLabels.
   * @returns {{redraw:function(object):void}} Handle that redraws with new series.
   */
  function lines(container, o) {
    let opts = o;
    const { plot, tip } = frame(container, { ...o, table: null });
    let drawAt = null;
    responsive(plot, (width) => { drawAt = width; draw(width); });
    /**
     * Render all series at a width.
     * @param {number} width Pixel width.
     * @returns {void}
     */
    function draw(width) {
      plot.querySelectorAll("svg").forEach((s) => s.remove());
      const m = { l: 50, r: opts.endLabels ? 96 : 16, t: 12, b: 38 }, height = opts.height || 260;
      const xmin = opts.x.min, xmax = opts.x.max, ymin = opts.y.min, ymax = opts.y.max;
      const X = (v) => m.l + (width - m.l - m.r) * (v - xmin) / (xmax - xmin);
      const Y = (v) => height - m.b - (height - m.t - m.b) * (v - ymin) / (ymax - ymin);
      const svg = el("svg", { viewBox: `0 0 ${width} ${height}`, width, height, role: "img", "aria-label": opts.ariaLabel || opts.title || "Line chart" });
      plot.insertBefore(svg, plot.firstChild);
      const grid = el("g", { class: "grid" }, svg);
      const ystep = opts.y.step || niceTicks(ymax - ymin, 5)[1];
      for (let t = Math.ceil(ymin / ystep) * ystep; t <= ymax + 1e-9; t += ystep) {
        el("line", { x1: m.l, x2: width - m.r, y1: Y(t), y2: Y(t) }, grid);
        const s = el("text", { x: m.l - 8, y: Y(t) + 4, class: "tick", "text-anchor": "end" }, svg);
        s.textContent = opts.y.format ? opts.y.format(t) : tick(t);
      }
      const xstep = opts.x.step || niceTicks(xmax - xmin, 6)[1];
      for (let t = Math.ceil(xmin / xstep) * xstep; t <= xmax + 1e-9; t += xstep) {
        const s = el("text", { x: X(t), y: height - m.b + 18, class: "tick", "text-anchor": "middle" }, svg);
        s.textContent = opts.x.format ? opts.x.format(t) : tick(t);
      }
      if (ymin < 0 && ymax > 0) el("line", { x1: m.l, x2: width - m.r, y1: Y(0), y2: Y(0), stroke: "var(--axis)" }, svg);
      const xl = el("text", { x: width - m.r, y: height - 4, class: "sub", "text-anchor": "end" }, svg); xl.textContent = opts.x.label;
      const yl = el("text", { x: m.l, y: m.t - 2, class: "sub" }, svg); yl.textContent = opts.y.label;
      (opts.bands || []).forEach((b) => el("rect", { x: X(b.from), y: m.t, width: Math.max(0, X(b.to) - X(b.from)), height: height - m.t - m.b, fill: b.color || "rgba(130,188,255,.06)" }, svg));
      // Marks are clipped to the plot area so out-of-range values never cover text.
      const clipId = `clip-${Math.random().toString(36).slice(2, 9)}`;
      const clip = el("clipPath", { id: clipId }, el("defs", {}, svg));
      el("rect", { x: m.l, y: m.t - 2, width: Math.max(0, width - m.l - m.r), height: height - m.t - m.b + 4 }, clip);
      const marks = el("g", { "clip-path": `url(#${clipId})` }, svg);
      opts.series.forEach((s) => {
        if (s.stems) {
          s.points.forEach(([px, py]) => {
            el("line", { x1: X(px), x2: X(px), y1: Y(0), y2: Y(py), stroke: s.color, "stroke-width": 1.5, opacity: 0.9 }, marks);
            el("circle", { cx: X(px), cy: Y(py), r: 3, fill: s.color }, marks);
          });
          return;
        }
        const d = s.points.map(([px, py], i) => `${i ? "L" : "M"}${X(px).toFixed(1)},${Y(py).toFixed(1)}`).join("");
        el("path", { d, fill: "none", stroke: s.color, "stroke-width": s.width || 2, "stroke-dasharray": s.dash || "", "stroke-linejoin": "round" }, marks);
        if (opts.endLabels && s.points.length) {
          const [lx, ly] = s.points[s.points.length - 1];
          el("circle", { cx: X(lx), cy: Y(ly), r: 3, fill: s.color }, svg);
          const t = el("text", { x: X(lx) + 8, y: Y(ly) + 4, class: "label" }, svg);
          t.textContent = s.name;
        }
      });

      // Crosshair: nearest sample of each line to the pointer's x position.
      const cross = el("line", { y1: m.t, y2: height - m.b, stroke: "var(--muted)", "stroke-width": 1, opacity: 0 }, svg);
      const hit = el("rect", { x: m.l, y: m.t, width: Math.max(0, width - m.l - m.r), height: height - m.t - m.b, class: "hit" }, svg);
      /** Update crosshair and tooltip for a pointer position. @param {MouseEvent} e Event. @returns {void} */
      function move(e) {
        const box = svg.getBoundingClientRect();
        const px = (e.clientX - box.left) * (width / box.width);
        const xv = xmin + (px - m.l) / (width - m.l - m.r) * (xmax - xmin);
        const rows = opts.series.filter((s) => s.points.length && !s.noTip).map((s) => {
          let best = s.points[0];
          for (const p of s.points) if (Math.abs(p[0] - xv) < Math.abs(best[0] - xv)) best = p;
          return `<i style="display:inline-block;width:8px;height:8px;border-radius:2px;background:${s.color};margin-right:6px"></i>${s.name}: <b>${opts.y.format ? opts.y.format(best[1]) : fmt(best[1])}</b>`;
        });
        cross.setAttribute("x1", px); cross.setAttribute("x2", px); cross.setAttribute("opacity", 0.6);
        const pbox = plot.getBoundingClientRect();
        tip.show(`<b>${opts.x.label}: ${opts.x.format ? opts.x.format(xv) : fmt(xv)}</b><br>${rows.join("<br>")}`, e.clientX - pbox.left, e.clientY - pbox.top);
      }
      hit.addEventListener("mousemove", move);
      hit.addEventListener("mouseleave", () => { cross.setAttribute("opacity", 0); tip.hide(); });
    }
    return {
      /** Replace options (for example new simulated series) and redraw. @param {object} next New options. @returns {void} */
      redraw(next) { opts = { ...opts, ...next }; if (drawAt) draw(drawAt); },
    };
  }

  const api = { bars, stack, scatter, lines, niceTicks, fmt, tick };
  global.EdgeCharts = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})(typeof window !== "undefined" ? window : globalThis);
