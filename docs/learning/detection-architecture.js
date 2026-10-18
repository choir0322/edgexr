/* Fixed teaching tensors expose the difference in connectivity. Saved image
 * samples are real; weights and resulting activations are illustrative. */
(() => {
  "use strict";
  const data = window.DETECTION_LESSON_DATA;
  const colors = ["#82bcff", "#65d8bb", "#efad92"];
  const names = ["C1", "C2", "C3"];
  const sampleIndices = [0,2,3,5];
  const input = Array.from({length:16}, (_, i) =>
    Math.round(data.sample[sampleIndices[Math.floor(i / 4)] * 6 + sampleIndices[i % 4]] * 9 / 255));
  const kernels = [
    [0,0,0,1,1,1,0,0,0],
    [0,1,0,0,1,0,0,1,0],
    [1,0,0,0,1,0,0,0,1]
  ];
  const standard = [kernels, [
    [1,0,1,0,1,0,1,0,1],
    [0,0,0,1,0,-1,0,0,0],
    [0,1,0,1,0,1,0,1,0]
  ]];
  const pointwise = [[1,2,-1], [-1,1,2]];
  // One illustrative bias per output channel, shared across spatial positions.
  // The project's actual MobileNet backbone disables convolution biases.
  const biases = {standard:[1,-2], depthwise:[1,0,-1], pointwise:[2,-1]};
  const phases = ["Select the 3×3 neighborhoods", "Multiply pixels by spatial weights",
    "Sum spatial products", "Mix channels in the pointwise filters", "Write both output channels"];
  let tick = 0, timer = null, selected = "s0";
  const $ = id => document.getElementById(id);

  /** Extract the nine inputs at an output position. @param {number} p Position 0–3. @returns {number[]} */
  function patch(p) {
    const row = Math.floor(p / 2), col = p % 2;
    return Array.from({length:9}, (_, i) => input[(row + Math.floor(i / 3)) * 4 + col + i % 3]);
  }
  /** Sum pairwise products, reusing a filter at each location. @param {number[]} a Values. @param {number[]} b Weights. @returns {number} */
  function dot(a, b) { return a.reduce((sum, value, i) => sum + value * b[i], 0); }
  /** Calculate all outputs independently of animation state. @returns {Object} */
  function calculate() {
    const depth = kernels.map((k,c) => [0,1,2,3].map(p => dot(patch(p), k) + biases.depthwise[c]));
    const dense = standard.map((filter,f) => [0,1,2,3].map(p =>
      filter.reduce((sum, k) => sum + dot(patch(p), k), 0) + biases.standard[f]));
    const separate = pointwise.map((weights,f) => [0,1,2,3].map(p =>
      dot(depth.map(channel => channel[p]), weights) + biases.pointwise[f]));
    return {depth, dense, separate};
  }
  const results = calculate();

  /** SVG text helper; all content is from fixed lesson data. @param {number} x X. @param {number} y Y. @param {string|number} value Text. @param {string} color Color. @param {number} size Font size. @returns {string} */
  function text(x, y, value, color = "#98a8bb", size = 12) {
    return '<text x="' + x + '" y="' + y + '" fill="' + color + '" font-size="' + size + '">' + value + '</text>';
  }
  /** Draw a small grid, optionally selecting a window or output cell. @param {number[]} values Cells. @param {number} n Side. @param {number} x X. @param {number} y Y. @param {number} size Cell size. @param {string} color Channel color. @param {string} kind Grid role. @returns {string} */
  function grid(values, n, x, y, size, color, kind = "kernel") {
    const p = Math.floor(tick / 5), phase = tick % 5;
    let markup = "";
    values.forEach((value, i) => {
      const row = Math.floor(i / n), col = i % n;
      const active = kind === "input" ?
        row >= Math.floor(p / 2) && row < Math.floor(p / 2) + 3 && col >= p % 2 && col < p % 2 + 3 : kind === "kernel" || i === p;
      const visible = kind === "output" ? i < p || (i === p && phase === 4) :
        kind === "depth" ? i < p || (i === p && phase >= 2) : true;
      const fill = active && (kind === "input" || kind === "output" || kind === "depth") ? color + "38" : "#182431";
      markup += '<rect class="cell" x="' + (x + col * size) + '" y="' + (y + row * size) +
        '" width="' + (size - 1) + '" height="' + (size - 1) + '" rx="2" fill="' + fill +
        '" stroke="' + (active ? color : "#334255") + '" stroke-width=".6"/>' +
        '<text x="' + (x + col * size + (size - 1) / 2) + '" y="' + (y + row * size + size * .68) +
        '" text-anchor="middle" font-size="' + (n === 2 ? 12 : 10) + '" fill="#e5edf6">' + (visible ? value : "·") + '</text>';
    });
    return markup;
  }
  /** Connect two diagram positions. @param {number} x X start. @param {number} y Y start. @param {number} xx X end. @param {number} yy Y end. @param {string} color Color. @returns {string} */
  function wire(x, y, xx, yy, color = "#42576b") {
    return '<path d="M' + x + ' ' + y + ' L' + xx + ' ' + yy + '" stroke="' + color + '" fill="none" stroke-width="1.2"/>' +
      '<path d="M' + (xx-3) + ' ' + (yy-5) + ' L' + xx + ' ' + yy + ' L' + (xx+3) + ' ' + (yy-5) + '" stroke="' + color + '" fill="none"/>';
  }
  /** Begin an accessible, selectable group. @param {string} id Selection id. @param {string} label Accessible label. @returns {string} */
  function group(id, label) {
    return '<g class="inspect" role="button" tabindex="0" data-select="' + id + '" aria-label="' + label +
      '" aria-pressed="' + (selected === id) + '">';
  }
  /** Draw shared input channels. @returns {string} */
  function inputs() {
    return [0,1,2].map(c => text(45+c*170, 18, names[c] + " · 4×4", colors[c]) +
      grid(input, 4, 45+c*170, 30, 18, colors[c], "input")).join("");
  }
  /** Render both complete routes with synchronized highlighted positions. @returns {void} */
  function diagrams() {
    const p = Math.floor(tick / 5), phase = tick % 5;
    let left = inputs(), right = inputs();
    // Each standard filter groups one distinct spatial kernel per input channel.
    standard.forEach((filter, f) => {
      const y = 145 + f * 135;
      left += group("s"+f, "Inspect standard filter "+(f+1)) +
        '<rect class="filter-frame" x="25" y="' + y + '" width="490" height="110" rx="8" fill="#192132" stroke="' + (selected === "s"+f ? "#bca2f4" : "#3b425a") + '"/>' +
        text(37,y+19,"FILTER "+(f+1)+(phase === 1 ? " · showing input × weight products" : " · 3×3×3 · 27 weights"),"#bca2f4",11);
      filter.forEach((k,c) => {
        left += grid(phase === 1 ? k.map((w,i)=>w*patch(p)[i]) : k,3,57+c*170,y+30,16,colors[c]) +
          text(115+c*170,y+61,phase >= 2 ? dot(patch(p), k) : "Σ",colors[c]);
      });
      left += text(39,y+98,"Sum + bias ("+biases.standard[f]+") → output "+(f+1)+": "+(phase >= 2 ? results.dense[f][p] : "…"),"#c8b9ed",11) + "</g>";
    });
    [0,1,2].forEach(c => {left += wire(81+c*170,105,81+c*170,139,colors[c]);});
    left += text(37,273,"Filter 2 receives the same three input windows.","#98a8bb",10);
    left += '<path d="M25 200 H12 V440 H150" fill="none" stroke="#bca2f4" stroke-width="1.2"/>';
    left += text(37,415,"Each filter reuses its kernels at every position.","#98a8bb",11);
    [0,1].forEach(f => {
      left += wire(150+f*210,f === 0 ? 440 : 392,150+f*210,452,"#bca2f4") +
        grid(results.dense[f],2,124+f*210,460,26,"#bca2f4","output") +
        text(124+f*210,533,"OUTPUT "+(f+1),"#bca2f4",11);
    });

    // Depthwise preserves channel lanes. Both pointwise filters consume all lanes.
    right += text(25,133,phase === 1 ? "DEPTHWISE · showing input × weight products" : "DEPTHWISE · 3 independent 3×3 kernels","#65d8bb",11);
    kernels.forEach((k,c) => {
      const x = 57+c*170;
      right += wire(x+24,105,x+24,146,colors[c]) + group("d"+c,"Inspect depthwise channel "+(c+1)) +
        '<rect class="filter-frame" x="' + (x-7) + '" y="148" width="62" height="64" rx="6" fill="#152a2a" stroke="' + colors[c] + '"/>' +
        grid(phase === 1 ? k.map((w,i)=>w*patch(p)[i]) : k,3,x,156,16,colors[c]) + "</g>" + wire(x+24,214,x+24,242,colors[c]) +
        text(x+32,232,"+ bias ("+biases.depthwise[c]+")",colors[c],10) +
        grid(results.depth[c],2,x,249,24,colors[c],"depth") + text(x-8,315,"C"+(c+1)+" kept separate",colors[c],10);
    });
    [0,1].forEach(f => {
      const x = 22+f*267;
      [0,1,2].forEach(c => {right += wire(81+c*170,321,x+53+c*48,355,colors[c]);});
      right += group("p"+f,"Inspect pointwise filter "+(f+1)) +
        '<rect class="filter-frame" x="' + x + '" y="358" width="229" height="78" rx="8" fill="#142b29" stroke="' + (selected === "p"+f ? "#65d8bb" : "#31564f") + '"/>' +
        text(x+10,376,phase === 3 ? "FILTER "+(f+1)+" · value × weight" : "POINTWISE FILTER "+(f+1)+" · 1×1×3","#65d8bb",10);
      pointwise[f].forEach((w,c) => {
        right += grid([phase === 3 ? w*results.depth[c][p] : w],1,x+39+c*48,386,25,colors[c]) +
          text(x+41+c*48,426,names[c],colors[c],9);
      });
      right += "</g>" + wire(x+113,439,x+113,452,"#65d8bb") +
        text(x+124,450,"+ bias ("+biases.pointwise[f]+")","#65d8bb",10) +
        grid(results.separate[f],2,x+87,460,26,"#65d8bb","output") +
        text(x+87,533,"OUTPUT "+(f+1),"#65d8bb",11);
    });
    const svg = (body,label) => '<svg viewBox="0 0 540 550" role="group" aria-label="' + label + '">' + body + '</svg>';
    $("standard-diagram").innerHTML = svg(left,"Standard convolution: two filters, each containing three channel kernels");
    $("separable-diagram").innerHTML = svg(right,"Depthwise channel filtering followed by two pointwise mixing filters");
  }

  /** Explain the selected filter with the current input patch's actual arithmetic. @returns {void} */
  function detail() {
    const p = Math.floor(tick/5), phase = tick%5, kind = selected[0], index = Number(selected[1]);
    const values = patch(p), depth = results.depth.map(channel => channel[p]);
    $("detail-kicker").textContent = "POSITION (" + Math.floor(p/2) + ", " + p%2 + ") · " + phases[phase];
    let title, body;
    if (kind === "s") {
      const terms = standard[index].map(k => dot(values,k));
      title = "Standard filter " + (index+1) + ": three kernels create one output channel";
      body = "<p>Each colored 3×3 kernel multiplies the matching input channel’s nine selected values. Add within each channel, then across channels.</p>" +
        '<p class="equation">' + terms.map((v,c)=>names[c]+": "+v).join(" + ") + " + bias ("+biases.standard[index]+") = <b>" + results.dense[index][p] + "</b></p>" +
        '<p class="equation">C1 detail: ' + values.map((v,i)=>v+"×("+standard[index][0][i]+")").join(" + ") + " = "+terms[0]+"</p>";
    } else if (kind === "d") {
      title = "Depthwise C" + (index+1) + ": one channel in, one channel out";
      body = "<p>Only this channel contributes. Its nine products are added; the other channels are kept separate.</p>" +
        '<p class="equation">' + values.map((v,i)=>v+"×("+kernels[index][i]+")").join(" + ") + " + bias ("+biases.depthwise[index]+") = <b>"+depth[index]+"</b></p>" +
        "<p>The three intermediate values at this position are ["+depth.join(", ")+"]. Pointwise filters will mix these next.</p>";
    } else {
      title = "Pointwise filter "+(index+1)+": 1×1 in space, three weights through depth";
      body = "<p>Take one value at the same position from each intermediate channel. Multiply by this filter’s three colored weights, then add.</p>" +
        '<p class="equation">'+depth.map((v,c)=>v+"×("+pointwise[index][c]+")").join(" + ")+" + bias ("+biases.pointwise[index]+") = <b>"+results.separate[index][p]+"</b></p>" +
        "<p>A second filter uses a different set of three weights to produce another output channel. The number of filters determines the number of output channels.</p>";
    }
    $("detail-title").textContent = title;
    $("detail-body").innerHTML = body + "<p>Bias is added once after this output’s weighted sum. The same bias is reused at every position in that output channel.</p>";
  }
  /** Render a synchronized teaching step without starting timers. @returns {void} */
  function render() {
    diagrams(); detail();
    $("progress").textContent = "Cell "+(Math.floor(tick/5)+1)+"/4 · "+phases[tick%5];
    $("step").disabled = tick === 19;
    $("play").textContent = timer !== null ? "Pause" : tick === 19 ? "Replay" : "Play";
  }
  /** Stop playback; manual selection never silently advances calculations. @returns {void} */
  function pause() { if (timer !== null) clearInterval(timer); timer = null; }
  /** Advance one stage and stop after all four output positions. @returns {void} */
  function advance() {
    if (tick < 19) tick++;
    if (tick % 5 === 3) selected = "p0";
    if (tick % 5 === 0) selected = "s0";
    if (tick === 19) pause();
    render();
  }
  // Delegation survives SVG rerenders and supports both pointer and keyboard.
  document.querySelector(".comparison").addEventListener("click", event => {
    const target = event.target.closest("[data-select]");
    if (target) { pause(); selected = target.dataset.select; render(); }
  });
  document.querySelector(".comparison").addEventListener("keydown", event => {
    if (event.key !== "Enter" && event.key !== " ") return;
    const target = event.target.closest("[data-select]");
    if (target) {
      event.preventDefault(); pause(); selected = target.dataset.select; render();
      document.querySelector('[data-select="'+selected+'"]').focus();
    }
  });
  $("play").addEventListener("click", () => {
    if (timer !== null) pause();
    else { if (tick === 19) tick = 0; timer = setInterval(advance, 1300); }
    render();
  });
  $("step").addEventListener("click", () => { pause(); advance(); });
  $("reset").addEventListener("click", () => { pause(); tick = 0; selected = "s0"; render(); });
  document.addEventListener("visibilitychange", () => { if (document.hidden) { pause(); render(); } });

  // Draw only saved measured detections here; teaching tensors never become boxes.
  $("saved-boxes").innerHTML = data.detections.map(box => {
    const [x,y,right,bottom] = box.box_xyxy;
    return '<rect x="'+x+'" y="'+y+'" width="'+(right-x)+'" height="'+(bottom-y)+'" fill="none" stroke="#65d8bb" stroke-width="7"/>' +
      text(Math.max(8,x),Math.max(32,y-10),box.label+" "+box.confidence.toFixed(2),"#65d8bb",30);
  }).join("");
  render();
})();
