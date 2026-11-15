/* Recorded evidence stays immutable; controls select the explanation and point. */
(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const frames = $('frames'), ctx = frames.getContext('2d');
  const geometry = $('geometry'), g = geometry.getContext('2d');
  const green = '#65d8bb', amber = '#efb77b', white = '#dce6ee';
  let trial = 0, stage = 0, selected = 0, generation = 0;
  let pictures = [null, null];
  const urls = [null, null];
  const stages = [
    ['Two views, not just a camera turn', 'Translation gives different viewpoints and depth information. Rotation also occurred here. Pixel displacement alone is not a measurement of rotation or distance.'],
    ['Find recognizable texture', 'ORB finds textured corners and describes their neighborhoods. These are regenerated keypoints from the actual snapshots, sampled for readability. A green square is not yet a 3D point.'],
    ['Match the same detail across images', 'Hamming descriptor distance, a 0.75 ratio test and mutual matching produce candidate pairs. Essential-matrix RANSAC and pose recovery subsequently reject incompatible geometry. The faint lines are candidate matches, not all accepted 3D points.'],
    ['Triangulate using both camera rays', 'Undistort matched pixels, estimate relative rotation and translation, then triangulate their rays. The drawing below uses the original reconstructed coordinates, viewed from above. Y is omitted; real rays are three-dimensional.'],
    ['Project the 3D point back into the image', 'Transform the point into each camera, divide by depth, apply lens distortion and camera intrinsics. Compare this prediction with the observed feature. The check must pass in both images.'],
    ['Inspect where the evidence actually is', 'Every green cross is an original accepted 3D point projected back into this image. Amber lines mark the calibrated principal-point height. Image coverage is useful, but cannot prove the points cover different physical depths.']
  ];
  const data = () => window.SPARSE_EVIDENCE[trial];
  const point = () => data().samples[selected];
  const fmt = (v, n = 3) => v.map(x => Number(x).toFixed(n)).join(', ');
  const xy = (p, view) => [view * 700 + p[0] / 2, 30 + p[1] / 2];
  /** Draw a segment. @param {CanvasRenderingContext2D} c @param {number[]} a @param {number[]} b @param {string} color @param {number} width @returns {void} */
  function line(c, a, b, color, width = 1) {
    c.strokeStyle = color; c.lineWidth = width; c.beginPath();
    c.moveTo(...a); c.lineTo(...b); c.stroke();
  }
  /** Mark an observed or projected point. @param {CanvasRenderingContext2D} c @param {number[]} p @param {string} color @param {boolean} circle @param {number} r @returns {void} */
  function mark(c, p, color, circle = false, r = 4) {
    c.strokeStyle = color; c.lineWidth = 1.5; c.beginPath();
    if (circle) c.arc(...p, r, 0, Math.PI * 2);
    else { c.moveTo(p[0]-r,p[1]); c.lineTo(p[0]+r,p[1]); c.moveTo(p[0],p[1]-r); c.lineTo(p[0],p[1]+r); }
    c.stroke();
  }
  /** Label canvas geometry. @param {CanvasRenderingContext2D} c @param {string} text @param {number} x @param {number} y @param {string} color @returns {void} */
  function label(c, text, x, y, color = white) {
    c.fillStyle = color; c.font = '14px sans-serif'; c.fillText(text, x, y);
  }
  /** Render originals and stage-specific evidence in pixel coordinates. @returns {void} */
  function drawFrames() {
    ctx.clearRect(0, 0, frames.width, frames.height);
    for (let v = 0; v < 2; v++) {
      label(ctx, `View ${v+1} · ${v ? 15 : 5} seconds`, v*700+10, 20);
      if (pictures[v]) ctx.drawImage(pictures[v], v*700, 30, 640, 360);
      else label(ctx, 'Load the matching original PNG below', v*700+100, 210);
    }
    if (!$('overlay').checked) return;
    const d = data(), p = point();
    if (stage === 1) d.keypoints.forEach((points, v) => points.forEach(q => {
      const [x,y] = xy(q,v); ctx.strokeStyle=green; ctx.strokeRect(x-3,y-3,6,6);
    }));
    if (stage === 2) {
      ctx.globalAlpha=.25;
      d.matches.forEach(pair => line(ctx,xy(pair[0],0),xy(pair[1],1),green));
      ctx.globalAlpha=1;
      line(ctx,xy(p.observed[0],0),xy(p.observed[1],1),amber,2);
    }
    if (stage === 5) d.projections.forEach((points,v) => {
      points.forEach(q=>mark(ctx,xy(q,v),green,false,2));
      ctx.setLineDash([6,5]); line(ctx,xy([0,d.matrix[1][2]],v),xy([1280,d.matrix[1][2]],v),amber); ctx.setLineDash([]);
    });
    for (let v=0;v<2;v++) {
      mark(ctx,xy(p.observed[v],v),green,true,7);
      mark(ctx,xy(p.projected[v],v),amber,false,5);
    }
  }
  /** Render an X–Z projection or magnified measured residual, never metric depth. @returns {void} */
  function drawGeometry() {
    g.clearRect(0,0,620,380);
    const d=data(), p=point();
    if (stage === 4) {
      const a=[300,180], b=[a[0]+60*(p.projected[1][0]-p.observed[1][0]),a[1]+60*(p.projected[1][1]-p.observed[1][1])];
      label(g,'View 2 residual · displacement magnified 60×',20,28);
      line(g,a,b,white,2); mark(g,a,green,true,8); mark(g,b,amber,false,8);
      label(g,'Observed feature (circle)',20,320,green);
      label(g,`Predicted projection (cross): error ${p.residual_px[1].toFixed(3)} px`,20,346,amber);
      return;
    }
    const points=d.samples.map(q=>q.xyz), c=d.camera_center;
    const all=[[0,0,0],c,...points];
    const loX=Math.min(...all.map(q=>q[0]))-.3, hiX=Math.max(...all.map(q=>q[0]))+.3;
    const loZ=Math.min(...all.map(q=>q[2]))-.3, hiZ=Math.max(...all.map(q=>q[2]))+.3;
    const scale=Math.min(520/(hiX-loX),270/(hiZ-loZ));
    const screen=q=>[50+(q[0]-loX)*scale,330-(q[2]-loZ)*scale];
    label(g,'Top-down X–Z view · arbitrary baseline units',20,25);
    points.forEach(q=>mark(g,screen(q),'#405b67',false,2));
    line(g,screen([0,0,0]),screen(p.xyz),green,2);
    line(g,screen(c),screen(p.xyz),amber,2);
    line(g,screen(c),screen(c.map((x,i)=>x+.6*d.camera_forward[i])),white,3);
    mark(g,screen(p.xyz),green,true,6);
    [[0,0,0],c].forEach((q,i)=> { const pos=screen(q); mark(g,pos,white,true,6); label(g,`C${i+1}`,pos[0]+10,pos[1]+15); });
    label(g,'White segment: estimated camera 2 forward direction',20,370);
  }
  /** Refresh the explanation from the selected immutable evidence record. @returns {void} */
  function render() {
    const d=data(), p=point(), r=d.report;
    $('title').textContent=stages[stage][0]; $('caption').textContent=stages[stage][1];
    document.querySelectorAll('[data-stage]').forEach(b=>{
      b.classList.toggle('active',Number(b.dataset.stage)===stage);
      b.setAttribute('aria-current',Number(b.dataset.stage)===stage?'step':'false');
    });
    $('back').disabled=stage===0; $('next').disabled=stage===5;
    $('point').max=d.samples.length-1; $('point').value=selected;
    $('point-label').textContent=`Cloud point ${p.id} · example ${selected+1}/${d.samples.length}`;
    $('legend').textContent='Green circle: recovered observed feature. Amber cross: original cloud projection. At normal scale they nearly overlap; Project back magnifies the difference.';
    const pose=r.camera_2_world_to_camera;
    const q=pose.slice(0,3).map(row=>row[0]*p.xyz[0]+row[1]*p.xyz[1]+row[2]*p.xyz[2]+row[3]);
    $('math-title').textContent=stage===4?'Actual projection calculation':'Actual pair geometry';
    $('math').textContent=stage===4
      ? `Point in camera 1: (${fmt(p.xyz)})\nX₂ = R₂ X₁ + t₂ = (${fmt(q)})\nNormalized x = X₂/Z₂ = ${(q[0]/q[2]).toFixed(5)}\nNormalized y = Y₂/Z₂ = ${(q[1]/q[2]).toFixed(5)}\nApply calibrated radial + tangential distortion.\nu = fₓ × x_distorted + cₓ\nv = fᵧ × y_distorted + cᵧ\nfₓ=${d.matrix[0][0].toFixed(2)}, fᵧ=${d.matrix[1][1].toFixed(2)}\ncₓ=${d.matrix[0][2].toFixed(2)}, cᵧ=${d.matrix[1][2].toFixed(2)}\nPredicted pixel: (${fmt(p.projected[1])})\nObserved pixel: (${fmt(p.observed[1])})\nError = √((u−u_obs)²+(v−v_obs)²)\nView 1 / 2 errors: ${fmt(p.residual_px)} px\nGate: ≤2 px in EACH image; not a depth guarantee.`
      : `Camera 1: C₁ = (0, 0, 0)\nCamera 2: C₂ = −R₂ᵀt₂\nC₂ = (${fmt(d.camera_center)})\nEstimated relative turn: ${d.turn_deg.toFixed(2)}°\nTranslation scale: |C₂−C₁| = 1 unit\nSelected point: (${fmt(p.xyz)})\nObserved pixel displacement: (${fmt(p.observed[1].map((x,i)=>x-p.observed[0][i]))}) px\nPixel shift mixes translation, rotation and depth.\nTriangulation also checks positive depth and ≥1° parallax.\nThese coordinates are NOT measured meters.`;
    $('metric').textContent=`Original Pi: ${r.descriptor_matches} descriptor matches → ${r.essential_inliers} essential inliers → ${r.accepted_points} accepted points.\nMedian maximum reprojection error: ${r.median_max_reprojection_px.toFixed(3)} px. Median parallax: ${r.median_parallax_deg.toFixed(2)}°.\nView 1 projected points by image thirds (top / middle / bottom): ${d.image_third_counts.join(' / ')}.\n${d.association_count} unambiguous point associations recovered on Mac; ${d.samples.length} selectable examples. Candidate reconstruction, not validated 3D accuracy.`;
    drawFrames(); drawGeometry();
  }
  /* Local snapshot loading never uploads footage. Generation guards avoid stale loads. */
  /** Load a local original with a stale-response guard. @param {number} view @param {string} src @param {number} token @returns {void} */
  function loadImage(view, src, token) {
    const image=new Image();
    image.onload=()=>{ if(token!==generation)return;
      if(image.naturalWidth!==1280||image.naturalHeight!==720){$('load-status').textContent='Use the original 1280×720 snapshots.';return;}
      pictures[view]=image; $('load-status').textContent=`${pictures.filter(Boolean).length}/2 snapshots loaded for ${data().name}.`; render();
    };
    image.onerror=()=>{if(token===generation)$('load-status').textContent='Automatic loading unavailable. Select this trial’s view-1.png and view-2.png below.';};
    image.src=src;
  }
  /** Reset point and image resources when switching recorded trials. @returns {void} */
  function loadTrial() {
    generation++; pictures=[null,null]; selected=0;
    urls.forEach((url,i)=>{if(url)URL.revokeObjectURL(url);urls[i]=null;});
    $('file1').value='';$('file2').value='';
    for(let v=0;v<2;v++)loadImage(v,`../../../${data().folder}/view-${v+1}.png`,generation);
    render();
  }
  document.querySelectorAll('[data-stage]').forEach(b=>b.onclick=()=>{stage=Number(b.dataset.stage);render();});
  $('back').onclick=()=>{stage=Math.max(0,stage-1);render();};
  $('next').onclick=()=>{stage=Math.min(5,stage+1);render();};
  $('trial').onchange=()=>{trial=Number($('trial').value);loadTrial();};
  $('point').oninput=()=>{selected=Number($('point').value);render();};
  $('overlay').onchange=render;
  frames.onclick=event=>{
    const rect=frames.getBoundingClientRect(), x=(event.clientX-rect.left)*1340/rect.width, y=(event.clientY-rect.top)*410/rect.height;
    let best=Infinity;
    data().samples.forEach((p,i)=>p.projected.forEach((q,v)=>{const pos=xy(q,v),distance=Math.hypot(x-pos[0],y-pos[1]);if(distance<best){best=distance;selected=i;}}));render();
  };
  [0,1].forEach(v=>$(`file${v+1}`).onchange=event=>{
    const file=event.target.files[0];if(!file)return;
    if(urls[v])URL.revokeObjectURL(urls[v]);urls[v]=URL.createObjectURL(file);loadImage(v,urls[v],generation);
  });
  loadTrial();
})();
