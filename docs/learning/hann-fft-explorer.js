/* An offline, recorded-data explanation of the estimator in visual_motion.py.
 * The Python generator computes the Fourier arrays; this file only visualizes
 * those arrays and replays the decisions made by the existing application.
 */
(() => {
  'use strict';

  const data = window.HANN_FFT_LESSON_DATA;
  const W = 80;
  const H = 56;
  const FW = 320;
  const FH = 180;
  const SVG = 'http://www.w3.org/2000/svg';
  const $ = (id) => document.getElementById(id);
  const fmt = (n, digits = 2) => `${n >= 0 ? '+' : ''}${n.toFixed(digits)}`;
  const clamp = (v, low, high) => Math.max(low, Math.min(high, v));
  let pairKey = 'adjacent';
  let stage = 0;
  let mode = 'overview';
  let playing = null;
  let selectedPatch = 7;

  /** Return the measured arrays for the selected pair of recorded frames. */
  function pair() { return data.pairs[pairKey]; }

  /** Build an SVG shape without interpreting recorded values as HTML. */
  function shape(name, attributes) {
    const element = document.createElementNS(SVG, name);
    Object.entries(attributes).forEach(([key, value]) => element.setAttribute(key, String(value)));
    return element;
  }

  /** Select the same source photographs in every stage of the lesson. */
  function setImageSources() {
    const later = pairKey === 'adjacent' ? '314' : '316';
    for (const id of ['overview-a', 'input-a', 'grid-a']) $(id).src = data.framePaths['313'];
    for (const id of ['overview-b', 'input-b', 'grid-b', 'consensus-frame', 'browser-frame']) {
      $(id).src = data.framePaths[later];
    }
    $('raw-a').src = data.patchPaths['313'];
    $('raw-b').src = data.patchPaths[later];
  }

  /** Draw a measured scalar field or an RGB field into a tiny pixel canvas. */
  function paint(id, width, height, colorAt) {
    const canvas = $(id);
    const context = canvas.getContext('2d');
    const image = context.createImageData(width, height);
    for (let y = 0; y < height; y += 1) {
      for (let x = 0; x < width; x += 1) {
        const [r, g, b] = colorAt(x, y);
        const i = 4 * (y * width + x);
        image.data[i] = clamp(Math.round(r), 0, 255);
        image.data[i + 1] = clamp(Math.round(g), 0, 255);
        image.data[i + 2] = clamp(Math.round(b), 0, 255);
        image.data[i + 3] = 255;
      }
    }
    context.putImageData(image, 0, 0);
    return context;
  }

  /** Set class and plain-text content for a measured pass/fail callout. */
  function callout(id, message, failure) {
    $(id).textContent = message;
    $(id).classList.toggle('fail', Boolean(failure));
  }

  /** Show timing and the outcome without pretending this was a live capture. */
  function renderInputs() {
    const p = pair();
    const later = pairKey === 'adjacent' ? 314 : 316;
    const elapsed = Math.round((p.pts[1] - p.pts[0]) * 1000);
    $('input-timing').textContent = `Recorded frames 313 → ${later}: camera presentation timestamps ${p.pts[0].toFixed(3)} s → ${p.pts[1].toFixed(3)} s (${elapsed} ms apart). This is frame-to-frame image displacement, not an angle or velocity.`;
    $('pair-note').textContent = pairKey === 'adjacent'
      ? 'Adjacent frames: eight sampled regions agree, so the whole-image estimate is accepted.'
      : 'Three frame intervals apart: the chosen patch has a strong peak, but only three regions agree. No whole-image shift is accepted.';
    const result = p.wholeResult;
    callout('overview-outcome', result
      ? `Whole image: reliable shift ${fmt(result[0])} px right / ${fmt(result[1])} px down; ${result[2]} agreeing patches. The arrow reflects image content, not camera yaw.`
      : 'Whole image: unreliable. Patch 8 has a clear shift, but only three of nine patches agree closely enough; the browser must not draw a motion arrow.', !result);
  }

  /** Outline the nine actual sample coordinates; selecting a box changes its readout. */
  function renderPatchGrid() {
    const p = pair();
    for (const id of ['grid-overlay-a', 'grid-overlay-b']) {
      const svg = $(id);
      svg.replaceChildren();
      p.patches.forEach((patch, index) => {
        const rect = shape('rect', { x: patch.x, y: patch.y, width: W, height: H,
          class: `patch-box${selectedPatch === index ? '' : ' dim'}` });
        const label = shape('text', { x: patch.x + 3, y: patch.y + 11, class: 'patch-num' });
        label.textContent = String(index + 1);
        svg.append(rect, label);
      });
    }
    const buttons = $('patch-buttons');
    buttons.replaceChildren();
    p.patches.forEach((patch, index) => {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = `${patch.agrees ? 'agree' : 'outlier'}${selectedPatch === index ? ' selected' : ''}`;
      button.setAttribute('aria-pressed', String(selectedPatch === index));
      button.textContent = `Patch ${index + 1} · (${patch.x}, ${patch.y})`;
      const detail = document.createElement('span');
      detail.textContent = patch.match
        ? `${fmt(patch.match[0], 1)}, ${fmt(patch.match[1], 1)} px · ${patch.agrees ? 'agrees' : 'differs'}`
        : 'no usable shift';
      button.append(detail);
      button.addEventListener('click', () => { selectedPatch = index; renderPatchGrid(); });
      buttons.append(button);
    });
    const selected = p.patches[selectedPatch];
    callout('patch-selection', `Patch ${selectedPatch + 1} samples x=${selected.x}…${selected.x + W - 1}, y=${selected.y}…${selected.y + H - 1} in each 320×180 frame. ${selected.match ? `Its measured content shift is (${fmt(selected.match[0])}, ${fmt(selected.match[1])}) px with Q=${selected.match[2].toFixed(1)}.` : 'Its shift was rejected.'} The next math stages follow patch 8.`, !selected.agrees);
  }

  /** Reproduce the 2D Hann weight used by NumPy's hanning on this patch. */
  function hann(x, y) {
    return (0.5 - 0.5 * Math.cos(2 * Math.PI * x / (W - 1)))
      * (0.5 - 0.5 * Math.cos(2 * Math.PI * y / (H - 1)));
  }

  /** Fade the recorded patch toward zero at each boundary, showing the seam. */
  function renderHann() {
    const p = pair();
    const amount = Number($('hann-amount').value) / 100;
    $('hann-percent').textContent = `${Math.round(amount * 100)}%`;
    const value = (array, mean, x, y) => (array[y * W + x] - mean) * (1 - amount + amount * hann(x, y));
    paint('hann-map', W, H, (x, y) => Array(3).fill(255 * hann(x, y)));
    paint('weighted-a', W, H, (x, y) => Array(3).fill(128 + 1.4 * value(p.a, p.meanA, x, y)));
    paint('weighted-b', W, H, (x, y) => Array(3).fill(128 + 1.4 * value(p.b, p.meanB, x, y)));
    const context = paint('repeated-a', 3 * W, H, (x, y) => Array(3).fill(
      128 + 1.4 * value(p.a, p.meanA, x % W, y)));
    context.fillStyle = '#72baff';
    context.fillRect(W, 0, 1, H);
    context.fillRect(2 * W, 0, 1, H);
    let seam = 0;
    for (let y = 0; y < H; y += 1) {
      seam += Math.abs(value(p.a, p.meanA, 0, y) - value(p.a, p.meanA, W - 1, y));
    }
    callout('hann-readout', `Actual patch A mean: ${p.meanA.toFixed(2)}; patch B mean: ${p.meanB.toFixed(2)} gray levels. Mean absolute left/right seam in A: ${(seam / H).toFixed(3)} levels. The estimator always uses 100% Hann; this slider only reveals the transition.`, false);
  }

  /** Render log-magnitude and cross-phase maps computed from this recorded pair. */
  function renderFFT() {
    const p = pair();
    const max = Math.max(...p.spectrumA, ...p.spectrumB);
    const fx = Number($('freq-x').value);
    const fy = Number($('freq-y').value);
    $('freq-x-label').textContent = String(fx);
    $('freq-y-label').textContent = String(fy);
    const marker = (x, y) => x === fx || y === fy;
    for (const [id, values] of [['fft-a', p.spectrumA], ['fft-b', p.spectrumB]]) {
      paint(id, W, H, (x, y) => {
        const brightness = 255 * values[y * W + x] / max;
        return marker(x, y) ? [80, 160, 255] : [brightness, brightness, brightness];
      });
    }
    paint('fft-phase', W, H, (x, y) => {
      const angle = p.phase[y * W + x];
      return marker(x, y) ? [255, 255, 255] : [
        128 + 110 * Math.cos(angle),
        128 + 110 * Math.cos(angle - 2 * Math.PI / 3),
        128 + 110 * Math.cos(angle + 2 * Math.PI / 3)];
    });
    const index = fy * W + fx;
    callout('frequency-readout', `Selected display bin (${fx}, ${fy}): log-magnitude A ${p.spectrumA[index].toFixed(2)}, B ${p.spectrumB[index].toFixed(2)}; phase of B × conjugate(A) ${p.phase[index].toFixed(2)} rad. White/blue crosshairs are teaching markers, not pixels in the FFT.`, false);
  }

  /** Convert the centered teaching map to NumPy's unshifted FFT indices. */
  function surfaceAt(p, displayX, displayY) {
    return p.surface[((displayY + H / 2) % H) * W + ((displayX + W / 2) % W)];
  }

  /** Let the learner compare any integer shift with the actual correlation peak. */
  function renderInverse() {
    const p = pair();
    const dx = Number($('candidate-x').value);
    const dy = Number($('candidate-y').value);
    $('candidate-x-label').textContent = String(dx);
    $('candidate-y-label').textContent = String(dy);
    const peakValue = p.surface[p.peak[1] * W + p.peak[0]];
    paint('correlation', W, H, (x, y) => {
      const brightness = clamp(90 + 165 * surfaceAt(p, x, y) / peakValue, 0, 255);
      return (x === dx + W / 2 && y === dy + H / 2)
        ? [80, 170, 255] : [brightness, brightness, brightness];
    });
    // Shift B back by the proposed displacement to compare like coordinates.
    paint('alignment', W, H, (x, y) => {
      const bx = x + dx;
      const by = y + dy;
      const a = p.a[y * W + x];
      if (bx < 0 || bx >= W || by < 0 || by >= H) return [a / 2, a / 2, a / 2];
      const b = p.b[by * W + bx];
      return [a, (a + b) / 2, b];
    });
    const score = p.surface[((dy + H) % H) * W + ((dx + W) % W)];
    const peakDx = p.peak[0] > W / 2 ? p.peak[0] - W : p.peak[0];
    const peakDy = p.peak[1] > H / 2 ? p.peak[1] - H : p.peak[1];
    callout('candidate-readout', `Candidate (${fmt(dx, 0)}, ${fmt(dy, 0)}) px: measured correlation ${score.toFixed(4)}. Strongest integer cell is (${fmt(peakDx, 0)}, ${fmt(peakDy, 0)}) px at ${peakValue.toFixed(4)}. The displayed overlay is a visual check; the estimator chooses from the correlation surface.`, false);
  }

  /** Draw a small measured three-point interpolation about the X peak. */
  function renderRefinement(p) {
    const svg = $('refine-graph');
    svg.replaceChildren();
    const [px, py] = p.peak;
    const scores = [-1, 0, 1].map(offset => p.surface[py * W + ((px + offset + W) % W)]);
    const denominator = scores[0] - 2 * scores[1] + scores[2];
    const fraction = Math.abs(denominator) <= 1e-12 ? 0
      : clamp(0.5 * (scores[0] - scores[2]) / denominator, -0.5, 0.5);
    const minimum = Math.min(...scores);
    const maximum = Math.max(...scores);
    const vertical = (value) => 180 - 115 * (value - minimum) / Math.max(maximum - minimum, 0.000001);
    const fitted = (t) => scores[1] + (scores[2] - scores[0]) * t / 2 + denominator * t * t / 2;
    const path = [];
    for (let step = 0; step <= 80; step += 1) {
      const t = -1 + step / 40;
      path.push(`${step ? 'L' : 'M'}${(210 + 130 * t).toFixed(1)},${vertical(fitted(t)).toFixed(1)}`);
    }
    svg.append(shape('path', { d: path.join(' '), fill: 'none', stroke: '#72baff', 'stroke-width': 3 }));
    [-1, 0, 1].forEach((t, i) => {
      svg.append(shape('circle', { cx: 210 + 130 * t, cy: vertical(scores[i]), r: 5, fill: '#68d5a5' }));
      const label = shape('text', { x: 210 + 130 * t, y: 209, fill: '#e6edf5', 'text-anchor': 'middle', 'font-size': 12 });
      label.textContent = `${t >= 0 ? '+' : ''}${t} cell`;
      svg.append(label);
    });
    const x = 210 + 130 * fraction;
    svg.append(shape('line', { x1: x, y1: 30, x2: x, y2: 186, stroke: '#ffb573', 'stroke-width': 2, 'stroke-dasharray': '5,4' }));
    const label = shape('text', { x: 210, y: 23, fill: '#ffb573', 'text-anchor': 'middle', 'font-size': 14 });
    label.textContent = `Fitted X offset: ${fmt(fraction, 3)} cell`;
    svg.append(label);
  }

  /** Exclude the wrapped 5×5 peak region before estimating background noise. */
  function renderQuality() {
    const p = pair();
    const [px, py] = p.peak;
    const peakValue = p.surface[py * W + px];
    paint('quality-map', W, H, (x, y) => {
      const rawX = (x + W / 2) % W;
      const rawY = (y + H / 2) % H;
      const wrappedX = Math.min((rawX - px + W) % W, (px - rawX + W) % W);
      const wrappedY = Math.min((rawY - py + H) % H, (py - rawY + H) % H);
      if (rawX === px && rawY === py) return [104, 220, 165];
      if (wrappedX <= 2 && wrappedY <= 2) return [255, 181, 115];
      const gray = clamp(90 + 165 * p.surface[rawY * W + rawX] / peakValue, 0, 255);
      return [gray, gray, gray];
    });
    const background = [];
    for (let y = 0; y < H; y += 1) {
      for (let x = 0; x < W; x += 1) {
        const wrappedX = Math.min((x - px + W) % W, (px - x + W) % W);
        const wrappedY = Math.min((y - py + H) % H, (py - y + H) % H);
        if (wrappedX > 2 || wrappedY > 2) background.push(p.surface[y * W + x]);
      }
    }
    const mean = background.reduce((sum, value) => sum + value, 0) / background.length;
    const stdev = Math.sqrt(background.reduce((sum, value) => sum + (value - mean) ** 2, 0) / background.length);
    const [dx, dy, quality] = p.patchResult;
    callout('quality-readout', `Strongest cell ${peakValue.toFixed(4)}; background ${background.length} cells, mean ${mean.toFixed(4)}, σ ${stdev.toFixed(4)}. Q=${quality.toFixed(2)} (not a probability). After X/Y subpixel refinement and signed-index unwrapping, patch 8 reports (${fmt(dx, 3)}, ${fmt(dy, 3)}) px. It passes Q ≥ 8 and the ¼-patch displacement limit.`, false);
    renderRefinement(p);
  }

  /** Compare independently measured patches with the 1.5-pixel median gate. */
  function renderConsensus() {
    const p = pair();
    const svg = $('consensus-overlay');
    const votes = $('consensus-votes');
    svg.replaceChildren();
    votes.replaceChildren();
    p.patches.forEach((patch, index) => {
      const color = patch.agrees ? '#68d5a5' : '#ffb573';
      svg.append(shape('rect', { x: patch.x, y: patch.y, width: W, height: H,
        fill: 'none', stroke: color, 'stroke-width': 2 }));
      const label = shape('text', { x: patch.x + 3, y: patch.y + 12, fill: color,
        'font-size': 10, 'font-weight': 700 });
      label.textContent = String(index + 1);
      svg.append(label);
      const vote = document.createElement('div');
      vote.className = `notice ${patch.agrees ? 'agree' : 'outlier'}`;
      vote.textContent = `Patch ${index + 1}: ${patch.match ? `${fmt(patch.match[0], 2)}, ${fmt(patch.match[1], 2)} px · ${patch.distance.toFixed(2)} px from median` : 'rejected'} · ${patch.agrees ? 'agrees' : 'differs'}`;
      votes.append(vote);
    });
    const accepted = p.patches.filter(patch => patch.agrees).length;
    const median = p.medianBeforeAgreement;
    const final = p.wholeResult;
    callout('consensus-readout', `${accepted}/9 patches agree within 1.5 px of median (${fmt(median[0])}, ${fmt(median[1])}). ${final ? `At least four agree: image_shift() returns (${fmt(final[0])}, ${fmt(final[1])}) px, ${final[2]} retained, median Q=${final[3].toFixed(2)}.` : 'Fewer than four agree: image_shift() returns None even though patch 8 passed its own quality gate.'}`, !final);
  }

  /** Replay publish_result and the browser's reliable-only arrow rule. */
  function renderState() {
    const result = pair().wholeResult;
    const fields = result
      ? { motion: 'reliable', dx: Number(result[0].toFixed(3)), dy: Number(result[1].toFixed(3)), patches: result[2], quality: Number(result[3].toFixed(2)) }
      : { motion: 'unreliable', dx: null, dy: null, patches: 0, quality: null };
    $('state-fields').textContent = JSON.stringify(fields, null, 2);
    const arrow = $('browser-arrow');
    arrow.replaceChildren();
    if (result) {
      const length = Math.min(60, Math.max(15, 10 * Math.hypot(result[0], result[1])));
      const magnitude = Math.hypot(result[0], result[1]);
      const endX = 160 + length * result[0] / magnitude;
      const endY = 90 + length * result[1] / magnitude;
      arrow.append(shape('line', { x1: 160, y1: 90, x2: endX, y2: endY,
        stroke: '#72baff', 'stroke-width': 5, 'stroke-linecap': 'round' }));
      const angle = Math.atan2(result[1], result[0]);
      const wing = (sign) => [endX - 12 * Math.cos(angle + sign * Math.PI / 5), endY - 12 * Math.sin(angle + sign * Math.PI / 5)];
      arrow.append(shape('polyline', { points: `${wing(1).join(',')} ${endX},${endY} ${wing(-1).join(',')}`,
        fill: 'none', stroke: '#72baff', 'stroke-width': 5, 'stroke-linecap': 'round', 'stroke-linejoin': 'round' }));
    }
    $('browser-message').className = `browser-footer ${result ? 'reliable' : 'unreliable'}`;
    $('browser-message').textContent = result
      ? `Reliable image shift. The blue arrow exaggerates direction (${fmt(result[0])}, ${fmt(result[1])}) px per analyzed pair.`
      : 'Unreliable image shift. No motion arrow is drawn; the image can still be displayed.';
  }

  /** Keep the horizontal image traveler attached to the selected processing stage. */
  function renderTraveler() {
    const later = pairKey === 'adjacent' ? '314' : '316';
    const imageA = stage >= 2 && stage <= 5 ? data.patchPaths['313'] : data.framePaths['313'];
    const imageB = stage >= 2 && stage <= 5 ? data.patchPaths[later] : data.framePaths[later];
    $('travel-a').src = imageA;
    $('travel-b').src = imageB;
    const button = document.querySelector(`[data-stage="${stage}"]`);
    $('traveler').style.left = `${button.offsetLeft + 9}px`;
    if (mode === 'walk') {
      const wrap = $('rail-wrap');
      wrap.scrollLeft = Math.max(0, button.offsetLeft - wrap.clientWidth / 3);
    }
  }

  /** Display one stage or the structural overview, with synchronized controls. */
  function renderNavigation() {
    $('overview').hidden = mode !== 'overview';
    document.querySelectorAll('[data-panel]').forEach(panel => {
      panel.hidden = mode !== 'walk' || Number(panel.dataset.panel) !== stage;
    });
    document.querySelectorAll('[data-stage]').forEach(button => {
      if (mode === 'walk' && Number(button.dataset.stage) === stage) button.setAttribute('aria-current', 'step');
      else button.removeAttribute('aria-current');
    });
    $('overview-mode').setAttribute('aria-pressed', String(mode === 'overview'));
    $('walk-mode').setAttribute('aria-pressed', String(mode === 'walk'));
    $('stage-range').value = String(stage);
    $('stage-count').textContent = `${stage + 1} / 8`;
    $('prev').disabled = mode === 'overview' || stage === 0;
    $('next').disabled = mode === 'overview' || stage === 7;
    renderTraveler();
  }

  /** Stop autoplay before a learner manually changes context. */
  function stopPlaying() {
    if (playing !== null) window.clearInterval(playing);
    playing = null;
    $('play').textContent = 'Play';
  }

  /** Rerender every measured view when switching between the two Pi frame pairs. */
  function renderPair() {
    document.querySelectorAll('[data-pair]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.pair === pairKey)));
    setImageSources();
    renderInputs();
    renderPatchGrid();
    renderHann();
    renderFFT();
    renderInverse();
    renderQuality();
    renderConsensus();
    renderState();
    renderNavigation();
  }

  /** Wire accessible controls and initialize the fully local recording replay. */
  function initialize() {
    if (!data || !data.pairs || !data.pairs.adjacent || !data.pairs.walkthrough) {
      $('ready').textContent = 'Recorded arrays are missing. Keep hann-fft-data.js beside this page.';
      return;
    }
    document.querySelectorAll('[data-pair]').forEach(button => button.addEventListener('click', () => {
      stopPlaying();
      pairKey = button.dataset.pair;
      selectedPatch = 7;
      $('candidate-x').value = '0';
      $('candidate-y').value = '0';
      renderPair();
    }));
    $('overview-mode').addEventListener('click', () => { stopPlaying(); mode = 'overview'; renderNavigation(); });
    $('walk-mode').addEventListener('click', () => { mode = 'walk'; renderNavigation(); });
    document.querySelectorAll('[data-stage]').forEach(button => button.addEventListener('click', () => {
      stopPlaying();
      stage = Number(button.dataset.stage);
      mode = 'walk';
      renderNavigation();
    }));
    $('prev').addEventListener('click', () => { stopPlaying(); stage = Math.max(0, stage - 1); renderNavigation(); });
    $('next').addEventListener('click', () => { stopPlaying(); stage = Math.min(7, stage + 1); renderNavigation(); });
    $('stage-range').addEventListener('input', () => { stopPlaying(); stage = Number($('stage-range').value); mode = 'walk'; renderNavigation(); });
    $('play').addEventListener('click', () => {
      if (playing !== null) { stopPlaying(); return; }
      mode = 'walk';
      if (stage === 7) stage = 0;
      renderNavigation();
      $('play').textContent = 'Pause';
      playing = window.setInterval(() => {
        if (stage === 7) { stopPlaying(); return; }
        stage += 1;
        renderNavigation();
      }, 3200);
    });
    $('hann-amount').addEventListener('input', renderHann);
    for (const id of ['freq-x', 'freq-y']) $(id).addEventListener('input', renderFFT);
    for (const id of ['candidate-x', 'candidate-y']) $(id).addEventListener('input', renderInverse);
    $('choose-peak').addEventListener('click', () => {
      const [x, y] = pair().peak;
      $('candidate-x').value = String(x > W / 2 ? x - W : x);
      $('candidate-y').value = String(y > H / 2 ? y - H : y);
      renderInverse();
    });
    $('correlation').addEventListener('click', event => {
      const rect = event.currentTarget.getBoundingClientRect();
      const x = clamp(Math.floor((event.clientX - rect.left) * W / rect.width), 0, W - 1);
      const y = clamp(Math.floor((event.clientY - rect.top) * H / rect.height), 0, H - 1);
      $('candidate-x').value = String(x - W / 2);
      $('candidate-y').value = String(y - H / 2);
      renderInverse();
    });
    renderPair();
    $('ready').textContent = 'Ready · derived from your Pi recording; no video or network needed.';
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', initialize);
  else initialize();
})();
