/* Local UI for the declarative program map. Recorded arrays remain separate
 * from illustrative arithmetic and from the independent-worker teaching trace.
 */
(() => {
  'use strict';
  const map = window.EDGEXR_FLOW;
  const recorded = window.HANN_FFT_LESSON_DATA;
  const $ = id => document.getElementById(id);
  const NS = 'http://www.w3.org/2000/svg';
  let path = ['root'];
  let selected = 'root';
  let pairKey = 'adjacent';
  let tick = 0;
  let timer = null;
  const escape = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const number = value => (value >= 0 ? '+' : '') + value.toFixed(3);

  /** Make a typed SVG element. @param {string} tag @param {Object} attrs @returns {SVGElement} */
  function svg(tag, attrs) {
    const element = document.createElementNS(NS, tag);
    Object.entries(attrs).forEach(([key, value]) => element.setAttribute(key, String(value)));
    return element;
  }

  /** Expand a node in place, or inspect a leaf without changing the graph.
   * @param {string} id Child node identifier.
   * @param {number} parentDepth Parent index in path.
   * @returns {void}
   */
  function open(id, parentDepth = 0) {
    if (!map[id]) return;
    selected = id;
    path = path.slice(0, parentDepth + 1);
    if (map[id].children.length) path.push(id);
    render();
  }

  /** Return to an existing ancestor and retain the recorded-pair selection.
   * @param {number} index Breadcrumb index. @returns {void}
   */
  function goTo(index) {
    path = path.slice(0, index + 1);
    selected = path.at(-1);
    render();
  }

  /** Draw one edge between the measured boundaries of two graph nodes.
   * @param {Object} a Source rectangle. @param {Object} b Target rectangle.
   * @param {string} label Edge label. @returns {void}
   */
  function edge(a, b, label = '') {
    const x1 = a.x + a.width, x2 = b.x;
    const y1 = a.y + a.height / 2, y2 = b.y + b.height / 2;
    const middle = (x1 + x2) / 2;
    $('edges').append(svg('path', {d:`M${x1},${y1} C${middle},${y1} ${middle},${y2} ${x2},${y2}`,class:'edge','marker-end':'url(#tip)'}));
    if (label) {
      const text = svg('text', {x:middle,y:(y1+y2)/2-9,'text-anchor':'middle',class:'edge-label'});
      text.textContent = label;
      $('edges').append(text);
    }
  }

  /** Measure a node after accounting for the one expanded lineage.
   * @param {string} id Node identifier. @param {number} depth Index in path.
   * @returns {{width:number,height:number,children:Array}}
   */
  function measureNode(id, depth) {
    const n = map[id], expanded = path[depth] === id && n.children.length > 0;
    if (!expanded) return {width:132, height:77, children:[]};
    const children = n.children.map(child => ({id:child, ...measureNode(child, depth + 1)}));
    return {
      width: Math.max(260, 32 + children.reduce((sum, child) => sum + child.width, 0) + Math.max(0, children.length - 1) * 34),
      height: 84 + Math.max(...children.map(child => child.height), 77),
      children,
    };
  }

  /** Create either a compact node or an expanded group occupying that node's place.
   * @param {string} id Node identifier. @param {Object} box Measured rectangle.
   * @param {number} depth Index in expansion path. @param {boolean} topLevel Whether positioning is absolute.
   * @returns {HTMLElement}
   */
  function renderNode(id, box, depth, topLevel = false) {
    const n = map[id], expanded = path[depth] === id && n.children.length > 0;
    if (!expanded) {
      const button=document.createElement('button');
      button.type='button';button.className=`graph-node ${n.lane || 'display'} ${selected===id?'selected':''}`;
      button.dataset.node=id;button.setAttribute('aria-expanded','false');
      button.setAttribute('aria-label',`${n.title}: ${n.children.length?'expand this node in the current graph':'inspect calculation and contract'}`);
      button.innerHTML=`<span class="cue">${n.children.length?'↳':'⊙'}</span><b>${escape(n.title)}</b><small>${escape(n.badge)}</small>`;
      button.addEventListener('click',()=>open(id,depth-1));
      if(topLevel){button.className+=' top-level-node';button.dataset.rootNode=id;button.style.left=`${box.x}px`;button.style.top=`${box.y}px`;}
      return button;
    }

    const group=document.createElement('section');
    group.className=`expanded-node ${n.lane || 'display'} ${selected===id?'selected':''}${topLevel?' top-level-node':''}`;
    group.dataset.node=id;if(topLevel)group.dataset.rootNode=id;
    group.setAttribute('aria-label',`${n.title}, expanded inside the current graph`);
    group.setAttribute('aria-expanded','true');
    group.style.width=`${box.width}px`;group.style.height=`${box.height}px`;
    if(topLevel){group.style.left=`${box.x}px`;group.style.top=`${box.y}px`;}
    const header=document.createElement('button');header.type='button';header.className='expanded-heading';
    header.innerHTML=`<span><b>${escape(n.title)}</b><small>${escape(n.badge)}</small></span><span class="collapse-cue">− collapse</span>`;
    header.addEventListener('click',()=>goTo(depth-1));group.append(header);
    const flow=document.createElement('div');flow.className='nested-flow';
    box.children.forEach((child,index)=>{
      if(index){const arrow=document.createElement('span');arrow.className='nested-arrow';arrow.textContent='→';flow.append(arrow);}
      flow.append(renderNode(child.id, child, depth+1, false));
    });
    group.append(flow);
    return group;
  }

  /** Lay out the original root topology using expanded node measurements.
   * @returns {{positions:Object,width:number,height:number}}
   */
  function rootLayout() {
    const sizes=Object.fromEntries(map.root.children.map(id=>[id,measureNode(id,1)]));
    const laneIds=['motion','detection','imu'], sideIds=['transport','support'];
    const gapX=70,gapY=24,padX=28,padY=58;
    const laneWidth=Math.max(...laneIds.map(id=>sizes[id].width));
    const laneHeight=laneIds.reduce((sum,id)=>sum+sizes[id].height,0)+gapY*(laneIds.length-1);
    const sideWidth=Math.max(...sideIds.map(id=>sizes[id].width));
    const sideHeight=sideIds.reduce((sum,id)=>sum+sizes[id].height,0)+gapY;
    const contentHeight=Math.max(laneHeight,sideHeight,sizes.capture.height,sizes.snapshot.height,sizes.browser.height);
    const height=contentHeight+padY*2;
    const columns=[sizes.capture.width,laneWidth,sizes.snapshot.width,sideWidth,sizes.browser.width];
    const starts=[];let cursor=padX;
    columns.forEach(width=>{starts.push(cursor);cursor+=width+gapX;});
    const positions={};
    const centerY=id=>(height-sizes[id].height)/2;
    positions.capture={x:starts[0],y:centerY('capture'),...sizes.capture};
    let laneY=(height-laneHeight)/2;
    laneIds.forEach(id=>{positions[id]={x:starts[1]+(laneWidth-sizes[id].width)/2,y:laneY,...sizes[id]};laneY+=sizes[id].height+gapY;});
    positions.snapshot={x:starts[2],y:centerY('snapshot'),...sizes.snapshot};
    let sideY=(height-sideHeight)/2;
    sideIds.forEach(id=>{positions[id]={x:starts[3]+(sideWidth-sizes[id].width)/2,y:sideY,...sizes[id]};sideY+=sizes[id].height+gapY;});
    positions.browser={x:starts[4],y:centerY('browser'),...sizes.browser};
    return {positions,width:cursor-gapX+padX,height};
  }

  /** Render one graph whose selected node physically expands and collapses in place.
   * @returns {void}
   */
  function renderGraph() {
    const root=map.root,{positions,width,height}=rootLayout();
    $('map-title').textContent=root.title;
    $('depth').textContent=`${path.length-1} NODE${path.length===2?'':'S'} EXPANDED / ONE RESIZING GRAPH`;
    $('map-kind').textContent='Click a node to resize it in place';
    $('map-note').textContent='An opened node becomes a larger container for its own steps. The original graph, neighboring nodes and edges reflow around it.';
    $('nodes').replaceChildren();$('edges').replaceChildren();
    $('graph').style.width=`${Math.max(1040,width)}px`;$('graph').style.height=`${height}px`;
    $('edges').setAttribute('viewBox',`0 0 ${Math.max(1040,width)} ${height}`);
    const defs=svg('defs',{}),marker=svg('marker',{id:'tip',viewBox:'0 0 10 10',refX:9,refY:5,markerWidth:6,markerHeight:6,orient:'auto-start-reverse'});
    marker.append(svg('path',{d:'M0 0 L10 5 L0 10 z',fill:'#6b839a'}));defs.append(marker);$('edges').append(defs);
    const piRight=positions.transport.x+positions.transport.width+18;
    $('edges').append(svg('rect',{x:13,y:25,width:piRight-13,height:height-38,rx:12,class:'zone'}));
    for(const [x,label] of [[28,'RASPBERRY PI / CAMERA + SENSOR INPUTS'],[positions.browser.x,'MACBOOK']]){const text=svg('text',{x,y:19,class:'zone-label'});text.textContent=label;$('edges').append(text);}
    edge(positions.capture,positions.motion,'small');edge(positions.capture,positions.detection,'full');
    for(const id of ['motion','detection','imu'])edge(positions[id],positions.snapshot);
    edge(positions.snapshot,positions.transport,'JSON');edge(positions.transport,positions.browser,'SSH');
    const requestY=34, browserMid=positions.browser.x+positions.browser.width/2, snapshotMid=positions.snapshot.x+positions.snapshot.width/2;
    $('edges').append(svg('path',{d:`M${browserMid} ${positions.browser.y} V${requestY} H${snapshotMid} V${positions.snapshot.y}`,class:'edge','stroke-dasharray':'4 5','marker-end':'url(#tip)'}));
    const requestLabel=svg('text',{x:(browserMid+snapshotMid)/2,y:requestY-6,'text-anchor':'middle',class:'edge-label'});requestLabel.textContent='browser request → snapshot';$('edges').append(requestLabel);
    for(const id of root.children)$('nodes').append(renderNode(id,positions[id],1,true));
  }

  /** Build reversible breadcrumbs and the selected operation contract. @returns {void} */
  function render() {
    $('breadcrumbs').replaceChildren();
    path.forEach((id,i)=>{
      if(i){const separator=document.createElement('span');separator.textContent='›';$('breadcrumbs').append(separator);}
      const button=document.createElement('button');button.textContent=map[id].title;button.type='button';
      if(i===path.length-1)button.setAttribute('aria-current','location');
      button.addEventListener('click',()=>goTo(i));$('breadcrumbs').append(button);
    });
    renderGraph();
    const n=map[selected];
    $('detail-title').textContent=n.title;
    $('detail-kind').textContent=n.children.length?'BOUNDARY / WHAT ENTERS & LEAVES':'INSIDE THE OPERATION / WHAT CHANGES';
    $('contract').innerHTML=`<div><label>INPUT · FROM THE PREVIOUS STAGE</label>${escape(n.input)}</div><div class="arrow">→</div><div><label>OUTPUT · TO THE NEXT STAGE</label>${escape(n.output)}</div>`;
    $('explanation').textContent=n.explanation;$('policy').textContent=n.policy;
    $('source').innerHTML=`Source: <a href="../../src/${escape(n.source)}">${escape(n.source)}</a> · <code>${escape(n.symbol)}</code>`;
    $('back').disabled=path.length===1 && selected==='root';
    $('rules').open=false;
    renderVisual(n.visual);
  }

  /** Draw measured scalar data using a supplied display function.
   * @param {string} id @param {number} width @param {number} height @param {Function} color @returns {void}
   */
  function paint(id,width,height,color) {
    const canvas=$(id); if(!canvas)return;
    canvas.width=width;canvas.height=height;
    const ctx=canvas.getContext('2d'), pixels=ctx.createImageData(width,height);
    for(let y=0;y<height;y++)for(let x=0;x<width;x++){
      const rgb=color(x,y),i=4*(y*width+x);
      for(let k=0;k<3;k++)pixels.data[i+k]=Math.max(0,Math.min(255,rgb[k]));pixels.data[i+3]=255;
    }
    ctx.putImageData(pixels,0,0);
  }

  /** Two-dimensional NumPy-compatible Hann weight. @param {number} x @param {number} y @returns {number} */
  function hann(x,y) {return (0.5-0.5*Math.cos(2*Math.PI*x/79))*(0.5-0.5*Math.cos(2*Math.PI*y/55));}

  /** Render one mathematical or data-flow visual; all injected prose is local authored content.
   * @param {string} kind Visual identifier. @returns {void}
   */
  function renderVisual(kind) {
    const out=$('visual'), p=recorded.pairs[pairKey];
    const later=pairKey==='adjacent'?'314':'316';
    const canvas=(id,caption)=>`<figure><canvas id="${id}" role="img" aria-label="${caption}"></canvas><figcaption>${caption}</figcaption></figure>`;
    const picture=(src,caption)=>`<figure><img src="${src}" alt="${caption}"><figcaption>${caption}</figcaption></figure>`;
    const formula=(text,note='')=>`<div class="formula">${text}<small>${note}</small></div>`;
    const chips=(values)=>`<div class="chips">${values.map(([big,small])=>`<div class="chip"><b>${big}</b><small>${small}</small></div>`).join('')}</div>`;
    const lesson=(href,title)=>`<a class="return-link" href="${href}">${title} ↗</a>`;
    const pairControl=`<div class="control-row"><span>Recorded Pi pair:</span><button type="button" id="pair-adjacent" aria-pressed="${pairKey==='adjacent'}">313 → 314 · accepted</button><button type="button" id="pair-walkthrough" aria-pressed="${pairKey==='walkthrough'}">313 → 316 · rejected</button></div>`;
    out.replaceChildren();
    if(['pair','patches','texture','hann','fft','cross','inverse','quality','refine','consensus','publish'].includes(kind)) {
      out.innerHTML=pairControl;
      if(kind==='pair')out.innerHTML+=`<div class="visual">${picture(recorded.framePaths['313'],'A · previous processed image, 320×180')}${picture(recorded.framePaths[later],'B · later image, 320×180')}</div>`+formula(`Δt = ${((p.pts[1]-p.pts[0])*1000).toFixed(0)} ms`,'These saved pair times are camera PTS, not the live host receipt clock.');
      if(kind==='patches'||kind==='consensus'){
        out.innerHTML+=`<div class="visual"><figure><div class="patch-wrap"><img src="${recorded.framePaths['313']}" alt="Recorded camera frame with nine sampled patch positions"><svg id="patch-overlay" viewBox="0 0 320 180" role="img" aria-label="Nine patch regions"></svg></div><figcaption>Nine sampled 80×56 regions. Patch 8 is our detailed example.</figcaption></figure><figure id="vote-summary"></figure></div>`;
        p.patches.forEach((patch,i)=>{
          const color=kind==='consensus'?(patch.agrees?'#8ce0c0':'#edc17e'):(i===7?'#86c9fb':'#9bafc1');
          $('patch-overlay').append(svg('rect',{x:patch.x,y:patch.y,width:80,height:56,fill:'none',stroke:color,'stroke-width':i===7?2:1}));
          const label=svg('text',{x:patch.x+4,y:patch.y+13,fill:color,'font-size':11});label.textContent=i+1;$('patch-overlay').append(label);
          if(kind==='consensus'&&patch.match)$('patch-overlay').append(svg('path',{d:`M${patch.x+40} ${patch.y+28} l${patch.match[0]*2} ${patch.match[1]*2}`,stroke:color,'stroke-width':2}));
        });
        $('vote-summary').innerHTML=kind==='consensus'?formula(`${p.patches.filter(v=>v.agrees).length} / 9 agree<br>${p.wholeResult?`dx ${number(p.wholeResult[0])}, dy ${number(p.wholeResult[1])} px`:'None → no reliable arrow'}`,'Green = within 1.5 px of median; amber = outside. Vectors enlarged ×2 for visibility.'):formula('9 patch pairs → 9 independent attempts','A patch can be rejected; the whole image still needs four agreeing valid estimates.');
      }
      if(kind==='texture')out.innerHTML+=chips([[p.stdA.toFixed(2),'stddev of patch A'],[p.stdB.toFixed(2),'stddev of patch B'],['3','minimum texture threshold']])+formula('σ = √mean((pixel − mean(pixel))²)','Both recorded patches pass. A constant-valued patch has σ = 0 and is rejected.');
      if(kind==='hann'){
        out.innerHTML+=`<div class="visual">${canvas('centered','A − mean(A) · signed values')}${canvas('window','Hann weights · black=0, white≈1')}${canvas('weighted','Weighted patch · zero is middle gray')}</div><div class="control-row"><label for="hann-amount">Reveal weighting</label><input id="hann-amount" type="range" min="0" max="100" value="100"><output id="hann-value">100%</output></div><div class="visual">${canvas('seam','Periodic copies · blue lines show the joins')}</div><p id="seam-value" class="status"></p>`+formula('w(x,y) = ½[1 − cos(2πx/79)] × ½[1 − cos(2πy/55)]','The slider is a teaching interpolation. The real algorithm always uses the full window. Zero-centered patches fade toward zero, displayed as gray—not black.');
        paint('centered',80,56,(x,y)=>Array(3).fill(128+1.4*(p.a[y*80+x]-p.meanA)));
        paint('window',80,56,(x,y)=>Array(3).fill(255*hann(x,y)));
        /** Update visible weighting and measured seam; no Fourier data is recomputed. */
        function revealHann(){
          const alpha=Number($('hann-amount').value)/100;
          $('hann-value').textContent=`${Math.round(alpha*100)}%`;
          const value=(x,y)=>(p.a[y*80+x]-p.meanA)*(1-alpha+alpha*hann(x,y));
          paint('weighted',80,56,(x,y)=>Array(3).fill(128+1.4*value(x,y)));
          paint('seam',240,56,(x,y)=>x===80||x===160?[134,201,251]:Array(3).fill(128+1.4*value(x%80,y)));
          let gap=0;for(let y=0;y<56;y++)gap+=Math.abs(value(0,y)-value(79,y));
          $('seam-value').textContent=`Mean absolute left/right boundary mismatch: ${(gap/56).toFixed(3)} intensity levels. This reduces an artificial seam, not actual object motion.`;
        }
        $('hann-amount').addEventListener('input',revealHann);revealHann();
      }
      if(kind==='fft'||kind==='cross'){
        out.innerHTML+=`<div class="visual">${canvas('spectrum-a','A · log magnitude, zero frequency centered')}${canvas('spectrum-b','B · same magnitude display scale')}${canvas('phase','Relative phase · hue represents angle')}</div>`;
        const maximum=Math.max(...p.spectrumA,...p.spectrumB);
        for(const [id,values] of [['spectrum-a',p.spectrumA],['spectrum-b',p.spectrumB]])paint(id,80,56,(x,y)=>Array(3).fill(255*values[y*80+x]/maximum));
        paint('phase',80,56,(x,y)=>[0,2*Math.PI/3,4*Math.PI/3].map(offset=>128+110*Math.cos(p.phase[y*80+x]-offset)));
        out.innerHTML+=formula(kind==='fft'?'FA = FFT(Awindowed) · FB = FFT(Bwindowed)':'R = [FB × conj(FA)] / max(|FB × conj(FA)|, 10⁻⁹)',kind==='fft'?'Complex values contain magnitude and phase. These are precomputed results from the recorded pair.':'Example: phases A=30°, B=80° → relative phase 50°. The inverse transform combines all such frequency agreements.');
        // innerHTML replacement would erase canvases; repaint after the formula is appended.
        for(const [id,values] of [['spectrum-a',p.spectrumA],['spectrum-b',p.spectrumB]])paint(id,80,56,(x,y)=>Array(3).fill(255*values[y*80+x]/maximum));
        paint('phase',80,56,(x,y)=>[0,2*Math.PI/3,4*Math.PI/3].map(offset=>128+110*Math.cos(p.phase[y*80+x]-offset)));
      }
      if(['inverse','quality','refine'].includes(kind)){
        const [px,py]=p.peak,dx=px>40?px-80:px,dy=py>28?py-56:py;
        out.innerHTML+=`<div class="visual">${canvas('surface','Candidate displacement map · zero shift in center')}${picture(recorded.patchPaths[later],'Actual later patch, not the correlation map')}</div>`;
        const peak=p.surface[py*80+px];
        paint('surface',80,56,(x,y)=>{
          const ix=(x+40)%80,iy=(y+28)%56;
          if(ix===px&&iy===py)return[134,201,251];
          if(kind==='quality'&&Math.min((ix-px+80)%80,(px-ix+80)%80)<=2&&Math.min((iy-py+56)%56,(py-iy+56)%56)<=2)return[237,193,126];
          return Array(3).fill(55+200*Math.max(0,p.surface[iy*80+ix]/peak));
        });
        const extra=document.createElement('div');
        extra.innerHTML=formula(kind==='quality'?`Q = ${p.patchResult[2].toFixed(2)} ≥ 8`:kind==='refine'?`(${dx}, ${dy}) → (${number(p.patchResult[0])}, ${number(p.patchResult[1])}) px`:`peak at shift (${dx}, ${dy}) → subpixel (${number(p.patchResult[0])}, ${number(p.patchResult[1])})`,'Blue cell = strongest candidate; axes are shift dx (horizontal) and dy (vertical). '+(kind==='quality'?'Amber = wrapped peak neighborhood excluded from background.':'This is one patch; whole-image consensus is still required.'));
        out.append(extra);
      }
      if(kind==='publish')out.innerHTML+=chips([[p.wholeResult?'reliable':'unreliable','motion status'],[p.wholeResult?number(p.wholeResult[0]):'—','dx pixels per pair'],[p.wholeResult?'draw arrow':'hide arrow','browser behavior']]);
      const deep=document.createElement('a');deep.href='hann-fft-explorer.html';deep.className='return-link';deep.textContent='Open the standalone recorded Hann/FFT lesson ↗';out.append(deep);
      for(const key of ['adjacent','walkthrough'])$(`pair-${key}`).addEventListener('click',()=>{pairKey=key;renderVisual(kind);});
      return;
    }

    // Non-Fourier calculations use clearly labeled teaching values, not fake sensor outputs.
    const views={
      overview:chips([['1 camera','One stream, two image consumers'],['1 IMU','Independent physical input'],['3 result types','Motion · boxes / IDs · gyro']]),
      sizes:chips([['921,600 B','1280×720 gray frame'],['57,600 B','320×180 gray copy'],['16×','Full/small pixel payload ratio']]),
      resize:`<div class="visual">${picture(recorded.framePaths['313'],'Saved Pi scene · full-source branch represented by this thumbnail')}<span>→ ×¼ per dimension →</span>${picture(recorded.framePaths['313'],'Motion copy: 320×180; detector retains full 1280×720')}</div>`,
      slots:formula('F1 processing · F2 waiting → F3 replaces F2','A consumer finishes F1, then takes F3. Nothing cancels its in-progress F1.'),
      normalize:formula('0 → −1.000 · 127.5 → 0 · 255 → +1.000','(pixel − 127.5) × 0.007843. A continuous range of values, not only −1, 0 and +1.')+chips([['300×300','spatial model input'],['3 identical','grayscale channel copies'],['1×3×300×300','NCHW model blob']]),
      network:chips([['MobileNet','pixels → learned features'],['SSD','features → object candidates'],['OpenCV DNN','executes the pretrained network']]),
      convolution:formula('Standard weights: k² × Cin × Cout<br>Depthwise + pointwise: k² × Cin + Cin × Cout','Example k=3, Cin=32, Cout=64: 18,432 vs 2,336 weights (excluding bias). Parameters are reused at every output position; operation count also depends on output spatial size.')+lesson('detection-architecture.html','See channels, filters, depthwise and pointwise visually'),
      ssd:formula('x = prior center x + 0.1 × predicted Δx × prior width<br>w = prior width × exp(0.2 × predicted Δw)','The pinned model’s box variances scale offsets; y/height follow the same form. Zero offsets retain the reference box. Class scoring and overlap suppression select outputs.')+lesson('detection-architecture.html','Open the feature maps → default boxes → SSD visual explanation'),
      boxes:formula('Normalized [0.1, 0.2, 0.4, 0.8]<br>→ source xyxy [128, 144, 512, 576]','Illustrative 1280×720 source. Multiply x by 1280 and y by 720; then clip/validate.'),
      claim:`<div class="number-line"><span>Old #7 → A: IoU <strong>0.70</strong></span><span>Old #7 → B: IoU 0.45</span><span>A claims #7 · B cannot</span></div>`+lesson('basic-tracker.html','Explore the full tracker decision graph'),
      age:`<div class="number-line"><span>Seen #7</span>→<span>Miss 1: hidden, retained</span>→<span>Miss 2: retired</span>→<span>Next new object: new ID</span></div>`,
      cosine:formula('v = (64 cell means − their mean) / vector length<br>similarity = Σ(vᵢ × rememberedᵢ)','Unit-vector cosine lies in [−1,1]; 0.85 is a provisional rule, not an 85% identity probability. Different crop/body portions can change the vector strongly.')+lesson('../REIDENTIFICATION_TRIAL_01_RESULTS.md','See why ID 8 → 9 failed despite the person being the same'),
      history:formula('Analysis shift (−5, +1) px × 4 → source shift (−20, +4) px','Illustrative units conversion. Translate both old box corners equally; preserve width/height. This is not gyro fusion.'),
      bias:formula('Raw Y = +15.10 °/s<br>Stationary Y offset = +15.00 °/s<br>Corrected Y = +0.10 °/s','Illustrative values. This produces angular rate, not accumulated angle or compass heading.'),
      imuTime:formula('Read starts 1.000 s · ends 1.002 s<br>Timestamp midpoint = 1.001 s · read duration = 2 ms','Illustrative host timing. Then wait 50 ms; one idealized cycle is 52 ms ≈19.23 Hz, before other scheduling costs.'),
      rate:formula('Rate = (N − 1) / (tlast − tfirst)<br>20 samples spanning 1.00 s → 19 Hz','Illustrative calculation: 20 samples contain 19 intervals. Do not divide by the 2 ms read duration.'),
      ageMath:formula('Now 12.50 s − source receipt 12.00 s = 500 ms old<br>Inference finished 12.24 s: compute ≈240 ms','Illustrative times. Source age grows after completion; it is not inference duration or total camera-to-screen latency.'),
      snapshot:chips([['F15','latest motion image'],['F10','older detector source'],['I9','separate IMU sample']])+formula('snapshot ≠ synchronized bundle','Illustrative IDs. Timestamps and freshness describe the mismatch instead of hiding it.'),
      transport:`<div class="number-line"><span>Mac browser request</span>→<span>SSH port forwarding</span>→<span>Pi /api/frame</span>→<span>JSON response</span></div>`,
      browser:`<div class="visual">${picture(recorded.framePaths['314'],'Saved image illustrating the browser background; no live overlay data is fabricated')}</div>`+formula('Source box [128,144,512,576] × ¼<br>→ 320×180 display box [32,36,128,144]','Illustrative coordinate scaling. Overlaying old boxes does not warp them using motion.'),
      recording:chips([['MJPEG copy','video side output'],['Selected PNGs','exact detector inputs'],['JSONL','decisions + host timing']]),
      profiling:formula('188% process CPU ≈ 1.88 logical cores of work','On a four-core Pi that is about 47% of total CPU capacity; other processes also consume CPU. CPU time is not measured electrical power.'),
      config:chips([['CLI','Choose workers / modes'],['prototxt','Network graph'],['caffemodel','Learned parameters']]),
      lifecycle:formula('Ctrl+C → stop event → workers stop → FFmpeg exits','Errors remain visible as status. Unavailable data is not silently replaced with zero movement.')
    };
    if(kind==='iou'){
      out.innerHTML=`<div class="visual"><svg class="demo-svg" viewBox="0 0 300 180" role="img" aria-label="Two boxes with adjustable overlap"><rect x="40" y="35" width="100" height="100" fill="#86c9fb33" stroke="#86c9fb"/><rect id="iou-new" x="80" y="35" width="100" height="100" fill="#8ce0c033" stroke="#8ce0c0"/><text x="40" y="25" fill="#86c9fb">previous</text><text id="iou-label" x="80" y="155" fill="#8ce0c0">current</text></svg><div><label for="iou-shift">Move the current box horizontally</label><input id="iou-shift" type="range" min="0" max="120" value="40"><p id="iou-value"></p></div></div>`;
      /** Recompute simple equal-square IoU for the teaching slider. */
      function updateIou(){const dx=Number($('iou-shift').value),area=Math.max(0,100-dx)*100,union=20000-area,iou=area/union;$('iou-new').setAttribute('x',40+dx);$('iou-label').setAttribute('x',40+dx);$('iou-value').textContent=`Intersection ${area} / union ${union} = ${iou.toFixed(3)} → ${iou>=.3?'eligible':'below 0.30; no raw-overlap match'}`;}
      $('iou-shift').addEventListener('input',updateIou);updateIou();
    }else out.innerHTML=views[kind]||'';
  }

  // Explicit pedagogical events show asynchronous ownership, not benchmark timing.
  const events=[
    {values:['empty','waiting','waiting','calibrated; no new sample','no request'],active:[],text:'Start of this illustration: startup calibration has already completed. F = camera frame, I = IMU sample.'},
    {values:['F1','starts F1 reference','starts F1 inference','I1 published','no request'],active:[0,1,2,3],text:'F1 is published to both latest slots. Motion and detection take their own inputs. I1 arrives independently.'},
    {values:['F2','working on F1','still working on F1','I2 replaces I1','no request'],active:[0,3],text:'Capture publishes F2 while consumers are busy. The current worker inputs are not overwritten.'},
    {values:['F3 replaces F2','takes F3; compares F1→F3','still working on F1','I2 latest','no request'],active:[0,1],text:'Motion finishes F1, selects the latest F3 and bypasses F2. That is a skipped source—not a rejected motion estimate.'},
    {values:['F3 latest','publishes image F3 + shift F1→F3','publishes F1 boxes; waits until due','I3 latest','request arrives'],active:[1,2,3,4],text:'Motion and detector publish independently. Detection does not immediately consume every intervening frame.'},
    {values:['F3 latest','image F3 + shift F1→F3','boxes sourced from F1','I3 latest','F3 image + F1 boxes + I3'],active:[4],text:'The browser gets the latest independent records. It renders, then waits 200 ms before polling again. This is not a frame-synchronized bundle.'}
  ];

  /** Draw one deterministic teaching event. @returns {void} */
  function renderEvent(){
    const event=events[tick],labels=['Latest image slots','Motion worker','Detector worker','IMU store','Browser snapshot'];
    $('slots').innerHTML=labels.map((label,i)=>`<div class="slot ${event.active.includes(i)?'active':''}"><b>${label}</b><span>${escape(event.values[i])}</span></div>`).join('');
    $('event').textContent=`${tick+1}/${events.length} · ${event.text}`;
    $('step').disabled=tick===events.length-1;
  }
  /** Cancel playback; navigation never starts it implicitly. @returns {void} */
  function pause(){if(timer)clearInterval(timer);timer=null;$('play').textContent='Play';}
  /** Advance one meaningful event and stop at the final state. @returns {void} */
  function step(){if(tick<events.length-1)tick++;renderEvent();if(tick===events.length-1)pause();}
  $('play').addEventListener('click',()=>{if(timer){pause();return;}if(tick===events.length-1)tick=0;renderEvent();$('play').textContent='Pause';timer=setInterval(step,2200);});
  $('step').addEventListener('click',()=>{pause();step();});
  $('reset').addEventListener('click',()=>{pause();tick=0;renderEvent();});
  $('home').addEventListener('click',()=>goTo(0));
  $('back').addEventListener('click',()=>{if(selected!==path.at(-1)){selected=path.at(-1);render();}else goTo(Math.max(0,path.length-2));});
  document.addEventListener('visibilitychange',()=>{if(document.hidden)pause();});
  render();renderEvent();
})();
