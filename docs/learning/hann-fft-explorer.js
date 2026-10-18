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
  let playing = null;
  const selectedPatch = 7;
  const frameImages = {};

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
    for (const id of ['input-a', 'grid-a']) $(id).src = data.framePaths['313'];
    for (const id of ['input-b', 'grid-b', 'consensus-frame', 'browser-frame']) $(id).src = data.framePaths[later];
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

  /** Outline all nine sample regions and fix patch 8 as the detailed example. */
  function renderPatchGrid() {
    const p = pair();
    for (const id of ['grid-overlay-a', 'grid-overlay-b']) {
      const svg = $(id); svg.replaceChildren();
      p.patches.forEach((patch, index) => {
        const rect = shape('rect', {x:patch.x,y:patch.y,width:W,height:H,
          class:'patch-box' + (index === selectedPatch ? '' : ' dim')});
        const label = shape('text', {x:patch.x+3,y:patch.y+11,class:'patch-num'});
        label.textContent = String(index+1); svg.append(rect,label);
      });
    }
    callout('patch-selection', 'Follow patch 8: x=117…196, y=119…174 in both frames. The detailed images below all come from this same 80×56 region.', false);
  }

  /** Reproduce the 2D Hann weight used by NumPy's hanning on this patch. */
  function hann(x, y) {
    return (0.5 - 0.5 * Math.cos(2 * Math.PI * x / (W - 1)))
      * (0.5 - 0.5 * Math.cos(2 * Math.PI * y / (H - 1)));
  }

  /** Fade the recorded patch toward zero at each boundary, showing the seam. */
  function renderHann() {
    const p = pair();
    const value = (array,mean,x,y,weighted) => (array[y*W+x]-mean)*(weighted ? hann(x,y) : 1);
    paint('hann-map',W,H,(x,y)=>Array(3).fill(255*hann(x,y)));
    for (const [id,array,mean,weighted] of [
      ['centered-a',p.a,p.meanA,false],['centered-b',p.b,p.meanB,false],
      ['weighted-a',p.a,p.meanA,true],['weighted-b',p.b,p.meanB,true]]) {
      paint(id,W,H,(x,y)=>Array(3).fill(128+1.4*value(array,mean,x,y,weighted)));
    }
    for (const [id,weighted] of [['repeated-before',false],['repeated-a',true]]) {
      const ctx=paint(id,3*W,H,(x,y)=>Array(3).fill(128+1.4*value(p.a,p.meanA,x%W,y,weighted)));
      ctx.fillStyle='#72baff'; ctx.fillRect(W,0,1,H);ctx.fillRect(2*W,0,1,H);
    }
    const seam = Array.from({length:H},(_,y)=>Math.abs(p.a[y*W]-p.a[y*W+W-1])).reduce((a,b)=>a+b,0)/H;
    callout('hann-readout', 'Mean A: '+p.meanA.toFixed(2)+'; mean B: '+p.meanB.toFixed(2)+
      '. Mean absolute left/right seam in A: '+seam.toFixed(3)+' → 0.000 levels after full Hann weighting. Zero is middle gray in the signed displays. The weight covers the entire patch; it is not a blur around each pixel.',false);
  }

  /** Render log-magnitude and cross-phase maps computed from this recorded pair. */
  function renderFFT() {
    const p=pair(), max=Math.max(...p.spectrumA,...p.spectrumB);
    for (const [id,values] of [['fft-a',p.spectrumA],['fft-b',p.spectrumB]]) {
      paint(id,W,H,(x,y)=>Array(3).fill(255*values[y*W+x]/max));
    }
    paint('fft-phase',W,H,(x,y)=>{
      const angle=p.phase[y*W+x];
      return [128+110*Math.cos(angle),128+110*Math.cos(angle-2*Math.PI/3),128+110*Math.cos(angle+2*Math.PI/3)];
    });
    $('frequency-readout').textContent='Both magnitude maps share one log display scale. Phase hue encodes angle (−π to +π, wrapping around); it is not brightness or object color. The array is normalized before inverse FFT. These display maps center zero frequency; the estimator uses original array order.';
  }

  /** Convert the centered teaching map to NumPy's unshifted FFT indices. */
  function surfaceAt(p, displayX, displayY) {
    return p.surface[((displayY + H / 2) % H) * W + ((displayX + W / 2) % W)];
  }

  /** Compare zero shift with the strongest measured integer candidate. */
  function renderInverse() {
    const p=pair();
    const dx=p.peak[0]>W/2 ? p.peak[0]-W : p.peak[0];
    const dy=p.peak[1]>H/2 ? p.peak[1]-H : p.peak[1];
    const peakValue=p.surface[p.peak[1]*W+p.peak[0]];
    paint('correlation',W,H,(x,y)=>{
      const brightness=clamp(90+165*surfaceAt(p,x,y)/peakValue,0,255);
      return x === dx+W/2 && y === dy+H/2 ? [80,170,255] : [brightness,brightness,brightness];
    });
    for (const [id,shiftX,shiftY] of [['alignment-before',0,0],['alignment',dx,dy]]) {
      paint(id,W,H,(x,y)=>{
        const bx=x+shiftX,by=y+shiftY,a=p.a[y*W+x];
        if(bx<0||bx>=W||by<0||by>=H)return [a/2,a/2,a/2];
        const b=p.b[by*W+bx];return [a,(a+b)/2,b];
      });
    }
    callout('candidate-readout','No-shift score: '+p.surface[0].toFixed(4)+
      '. Strongest integer candidate: ('+fmt(dx,0)+', '+fmt(dy,0)+') px, score '+peakValue.toFixed(4)+
      '. Move B back by that displacement for the visual overlay. Gray means agreement; colored fringes show differences. The next stage refines this integer candidate.',false);
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
      if (patch.match) {
        const cx=patch.x+W/2, cy=patch.y+H/2;
        const ex=cx+patch.match[0]*2, ey=cy+patch.match[1]*2;
        svg.append(shape('line',{x1:cx,y1:cy,x2:ex,y2:ey,stroke:color,'stroke-width':2}));
        svg.append(shape('circle',{cx:ex,cy:ey,r:2,fill:color}));
      }
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
      const endX = 160 + length * result[0] / (magnitude || 1);
      const endY = 90 + length * result[1] / (magnitude || 1);
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

  /** Keep every pipeline thumbnail tied to the selected recorded pair. */
  function renderThumbnails() {
    const later=pairKey === 'adjacent' ? '314' : '316';
    const sources={2:'hann-map',3:'fft-a',4:'correlation',5:'quality-map'};
    for(let i=0;i<8;i++){
      const ctx=$('thumb-'+i).getContext('2d');ctx.clearRect(0,0,160,90);
      if(sources[i]){ctx.drawImage($(sources[i]),0,0,160,90);continue;}
      const image=frameImages[i===1 ? '313' : later];
      if(!image || !image.complete || !image.naturalWidth)continue;
      if(i===0){
        if(frameImages['313'].complete && frameImages['313'].naturalWidth)ctx.drawImage(frameImages['313'],0,22,78,44);
        ctx.drawImage(image,82,22,78,44);
      }else ctx.drawImage(image,0,0,160,90);
      if(i===1||i===6)pair().patches.forEach((p,index)=>{
        ctx.strokeStyle=i===6 ? (p.agrees ? '#65d8bb':'#efb77b') : index===7 ? '#65d8bb':'#98a8bb';
        ctx.lineWidth=index===7?2:1;ctx.strokeRect(p.x/2,p.y/2,W/2,H/2);
      });
      if(i===7){
        ctx.fillStyle=pair().wholeResult ? '#65d8bb':'#efb77b';
        ctx.fillRect(0,78,160,12);
        ctx.fillStyle='#10161e';ctx.font='9px system-ui';
        ctx.fillText(pair().wholeResult?'Reliable · arrow shown':'Unreliable · no arrow',5,87);
      }
    }
  }

  /** Keep the full pipeline visible while displaying one detailed stage. */
  function renderNavigation() {
    document.querySelectorAll('[data-panel]').forEach(panel=>{panel.hidden=Number(panel.dataset.panel)!==stage;});
    document.querySelectorAll('[data-stage]').forEach(button=>{
      if(Number(button.dataset.stage)===stage)button.setAttribute('aria-current','step');
      else button.removeAttribute('aria-current');
    });
    $('stage-count').textContent='STAGE '+(stage+1)+' / 8';
    $('next').disabled=stage===7;
    $('play').textContent=playing!==null?'Pause':stage===7?'Replay':'Play';
  }

  /** Stop autoplay before a learner manually changes context. */
  function stopPlaying() {
    if(playing!==null)window.clearInterval(playing);
    playing=null;
  }

  /** Rerender every measured view when switching between the two Pi frame pairs. */
  function renderPair() {
    setImageSources();renderInputs();renderPatchGrid();renderHann();renderFFT();
    renderInverse();renderQuality();renderConsensus();renderState();
    renderThumbnails();renderNavigation();
  }

  /** Wire accessible controls and initialize the fully local recording replay. */
  function initialize() {
    if(!data?.pairs?.adjacent||!data?.pairs?.walkthrough){
      $('ready').textContent='Recorded arrays missing: keep images/hann-fft-data.js with this page.';return;
    }
    for(const key of ['313','314','316']){
      const image=new Image();frameImages[key]=image;
      image.onload=renderThumbnails;image.src=data.framePaths[key];
    }
    $('pair-choice').addEventListener('change',()=>{
      stopPlaying();pairKey=$('pair-choice').value;renderPair();
    });
    document.querySelectorAll('[data-stage]').forEach(button=>button.addEventListener('click',()=>{
      stopPlaying();stage=Number(button.dataset.stage);renderNavigation();
    }));
    $('next').addEventListener('click',()=>{stopPlaying();stage=Math.min(7,stage+1);renderNavigation();});
    $('reset').addEventListener('click',()=>{stopPlaying();stage=0;renderNavigation();});
    $('play').addEventListener('click',()=>{
      if(playing!==null){stopPlaying();renderNavigation();return;}
      if(stage===7)stage=0;
      playing=window.setInterval(()=>{
        stage=Math.min(7,stage+1);
        if(stage===7)stopPlaying();
        renderNavigation();
      },3600);
      renderNavigation();
    });
    document.addEventListener('visibilitychange',()=>{if(document.hidden){stopPlaying();renderNavigation();}});
    renderPair();$('ready').textContent='Recorded data · no camera or network needed';
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', initialize);
  else initialize();
})();
