/* Local, dependency-free learning view. Illustrations never command the Pi.
 * Measured values are transcribed from the linked experiment records. */
(() => {
  'use strict';
  const root = document.getElementById('storage-learning');
  if (!root) return;
  const configs = {
    inline: {title:'Earlier · inline recording', status:'Historical design · schematic', queue:false, profiler:false, ram:false, filter:false,
      note:'The scene worker saved images/JSON before taking its next query. Storage could delay recognition. The IMU was still a separate worker. This panel does not invent historical performance numbers.'},
    bounded: {title:'Implemented · bounded background writer', status:'Architecture progression · schematic', queue:true, profiler:false, ram:false, filter:false,
      note:'Recognition offers records without waiting for disk. Four waiting records plus one active write are allowed. If the queue is full, a new recording can be dropped; recognition continues. A queue buys time, not unlimited storage throughput.'},
    run02: {title:'Measured · run 02 / all MMC hosts', status:'Measured · partial trace', queue:true, profiler:true, ram:false, filter:false,
      note:'Application and profiler both wrote to microSD. Trace stayed in RAM until stop. CPU 0 overwrote 88,730 older trace events. No scene records were dropped. The earlier missing trace cannot be reconstructed.'},
    run03: {title:'Measured · run 03 / mmc0 filter', status:'Measured · no reported trace loss', queue:true, profiler:true, ram:false, filter:true,
      note:'Same application workload; only MMC diagnostics were narrowed to mmc0. Both filters read back correctly; all 4,009 retained MMC events name mmc0. All per-CPU loss counters are zero. Filtering did not repair or accelerate storage.'},
    ram: {title:'Ready to test · profiler samples in bounded RAM', status:'Implemented · Pi measurement pending', queue:true, profiler:true, ram:true, filter:true,
      note:'Only samples.jsonl is staged in process RAM (64 MiB payload cap by default). Scene images/JSON and preview.log stay on microSD. Export follows collection plus a 45 s delay. No spill on overflow. RAM is pageable; inspect swap evidence. No improvement measured yet.'}
  };
  const definitions = {
    recognize:['Scene worker','Compares camera views with remembered views. It produces a scene record; this workload has MobileNet object detection disabled. A record is a software item, not a network packet.'],
    queue:['Bounded FIFO queue','FIFO means first in, first out. Four slots hold waiting records in RAM; the writer can hold one additional record in flight. Full queues reject new recording submissions rather than waiting for disk. Explicit enrollment also checks capacity.'],
    writer:['Recording worker','A thread inside the spatial application that owns image and JSON writes. Moving this work off the scene worker lets recognition continue during a write delay.'],
    profiler:['Profiler / observer','A separate program that samples application and Linux measurements. It serializes them (turns values into JSON text), then writes its own file. A blocked write delays its next observation. It also adds CPU and storage load.'],
    cpu:['CPU / scheduling','The processor executes instructions. Linux schedules threads onto CPU cores. A waiting writer need not occupy a core continuously; other runnable workers can execute. The CPU chip here is a shared resource, not a stage all data passes through.'],
    imu:['Independent IMU worker','Reads gyro samples over I²C and publishes orientation information. In run 03 the maximum sample gap was 30.91 ms despite multi-second writes. That is measured continuity, not a hard real-time guarantee.'],
    storage:['Shared Linux storage path','Click again to collapse this node. A Python write can copy data into cached RAM before physical storage finishes. File writes, journal activity and device requests are related but not a one-to-one conveyor belt.'],
    cache:['RAM cache / filesystem','RAM is temporary working memory. The ext4 filesystem organizes files; Linux caches file data in RAM and writes it back later. A buffered write can still block for filesystem or resource reasons.'],
    journal:['Journal','Filesystem recovery bookkeeping. A journal commit completes a transaction. It is connected to file operations, not a mandatory container for every image byte. Long commits can share dependencies with long file writes.'],
    block:['Block layer','Linux represents storage work as requests for ranges of blocks. Requests can merge, split, requeue or complete partially. A requeue does not automatically mean an error or lost file.'],
    driver:['Driver + controller','A driver is kernel code communicating with a device. The storage controller is hardware that communicates with the card. Our trace does not isolate which component explains the wait.'],
    sd:['microSD / persistent storage','The card retains files after power-off. The reviewed recordings use ext4 on /dev/mmcblk0p2. A slow request is not proof that the card is defective: controller, driver, filesystem and scheduling interactions also matter.'],
    ram:['Bounded RAM staging','Profiler sample bytes stay in a capped list in its process memory. This is not a tmpfs mount, scene queue or trace ring. Overflow stops collection with an error; no automatic disk spill. Export happens after collection and a delay. RAM is volatile and pageable: inspect recorded VmSwap and system swap activity.'],
    trace:['Kernel trace','Timestamped diagnostic events from inside Linux. This helper collects selected storage events into bounded per-CPU RAM rings, then exports them after tracing stops. It does not record every kernel action.'],
    mmc:['MMC host / filter','MMC is the Linux subsystem serving devices such as this SD storage. mmc0 is the host label seen on the reviewed storage requests; mmc1 is another host, not CPU core 1. The expression name == "mmc0" keeps matching diagnostic entries only. Real device operations continue. Other event groups remain unfiltered.'],
    ring:['Trace ring / overrun','A fixed-size circular RAM log. In overwrite mode, new events replace the oldest when full. Each CPU has its own ring. An overrun counts diagnostic evidence lost, not camera or IMU data loss.'],
    wall:['Wall time / CPU time','Wall time is elapsed time between call start and return, including waiting and descheduling. Process CPU time counts execution across its threads. The difference is not a direct measurement of SD-card waiting.'],
    coverage:['Coverage / completeness','Coverage asks whether tracing was enabled for the entire application interval. Completeness additionally asks whether recorded events were lost. A long-enough trace can still have overwritten events, as run 02 did.'],
    cause:['Correlation / cause','Concurrent intervals show related activity in time. They do not prove which component caused the others to wait. We need a controlled change and additional evidence to distinguish competing explanations.']
  };
  let selected='run03', step=0, expanded=false, branch=false, hardware=false, timer=null;
  const states=[
    {q:0,w:'idle',msg:'A scene result is ready. The profiler independently takes a measurement.'},
    {q:0,w:'R1',msg:'R1 moves to the writer. Both programs send file work toward shared storage.'},
    {q:1,w:'R1',msg:'Saving R1 waits. R2 occupies the first queue slot. IMU polling continues.'},
    {q:2,w:'R1',msg:'R3 arrives. The profiler also waits inside its own write and cannot take its next observation.'},
    {q:3,w:'R1',msg:'R4 arrives. Recognition can still produce records while the recording worker waits.'},
    {q:4,w:'R1',msg:'All four waiting slots are occupied. This illustrates the measured high-water value, not reconstructed event timing.'},
    {q:3,w:'R2',msg:'Storage resumes before another arrival in this illustration. R1 completes; R2 leaves the queue for the writer.'},
    {q:2,w:'R3',msg:'The writer catches up. The profiler can take another observation. A gap in its notes did not imply an IMU gap.'},
    {q:0,w:'idle',msg:'The queued work drains. Run 03 saved all 180 accepted records; it had no drops.'}
  ];
  root.innerHTML=`<div class="eyebrow">Shared resources · architecture and evidence</div>
    <p class="lab-note">Rounded boxes = programs/workers · slots = queued records · chip = CPU · memory bank = RAM · card = microSD. Solid arrows carry work; dashed links show observation or labelled detail/after-run connections. All controls are local illustrations.</p>
    <div class="lab-tools"><label for="lab-config">Architecture / experiment</label><select id="lab-config">${Object.entries(configs).map(([k,v])=>`<option value="${k}" ${k===selected?'selected':''}>${v.title}</option>`).join('')}</select><span id="lab-status" class="lab-badge"></span></div>
    <p id="lab-config-note" class="lab-note"></p>
    <div class="lab-tools"><button id="lab-expand" type="button" aria-expanded="false">Expand recording path</button><button id="lab-play" type="button">Play</button><button id="lab-next" type="button">Next event</button><button id="lab-reset" type="button">Reset</button><span>Storage illustration · independent of the worker-rate clock above</span></div>
    <p id="lab-event" class="lab-state" aria-live="polite"></p>
    <div class="lab-stage"><svg id="lab-flow" role="group" aria-label="Programs and shared resources"></svg></div>
    <div id="lab-detail" class="lab-detail" aria-live="polite"></div>
    <h2>Which diagnostic entries are kept?</h2><p>Compare runs 02 and 03 using the configuration selector. The filter gates the diagnostic branch only; storage operations still run.</p>
    <div class="lab-stage"><svg id="lab-filter" role="group" aria-label="MMC diagnostic filter and per-CPU trace rings"></svg></div>
    <h2>Did the trace cover the application?</h2><p>Measured run 03 · common monotonic clock, seconds since boot. The outer bar encloses the observer/application capture; no trace loss was reported.</p>
    <div class="lab-stage"><svg id="lab-coverage" viewBox="0 0 1100 155" role="img" aria-label="Trace from 130.080 to 340.081 seconds encloses observer from 132.763 to 316.152 seconds"></svg></div>
    <h2>One pause, seen at several layers</h2><p>Measured run 03 · select a row for its definition. Similar lengths motivate investigating a shared storage wait; they do not identify a defective component.</p>
    <div class="lab-stage"><svg id="lab-timeline" viewBox="0 0 1100 205" role="group" aria-label="Overlapping file writes and filesystem journal"></svg></div>
    <div class="lab-metrics"><div class="lab-metric">Profiler write: elapsed clock<strong>4.566943 seconds</strong>Start → return, including waiting</div><div class="lab-metric">Same interval: process CPU counter<strong>0.366056 milliseconds</strong>About 0.008% of the elapsed interval</div><div class="lab-metric">Independent IMU observations<strong>30.91 ms maximum gap</strong>Across run 03; not sample-by-sample replay</div></div>
    <div class="lab-stage"><svg viewBox="0 0 1100 150" role="img" aria-label="Elapsed clock versus process CPU clock, both using a five-second full-circle scale"><circle cx="110" cy="70" r="46" fill="none" stroke="var(--line)" stroke-width="8"/><circle cx="110" cy="70" r="46" fill="none" stroke="var(--orange)" stroke-width="8" stroke-dasharray="264 289" transform="rotate(-90 110 70)"/><text x="180" y="65">Elapsed: 4.567 s</text><text class="sub" x="180" y="90">About 91% of this 5-second dial</text><circle cx="650" cy="70" r="46" fill="none" stroke="var(--line)" stroke-width="8"/><circle cx="650" cy="70" r="46" fill="none" stroke="var(--blue)" stroke-width="8" stroke-dasharray="0.021 289" transform="rotate(-90 650 70)"/><text x="720" y="65">CPU: 0.000366 s</text><text class="sub" x="720" y="90">Too small to see on the same scale</text><text class="sub" x="20" y="137">Both dials: 5 seconds per revolution. Static measured totals; no invented scheduling trace.</text></svg></div>
    <p class="lab-note">These are two measured counters over the same interval, not a reconstruction of when the CPU ran. No CPU-scheduling trace was collected. The CPU-time bar would be smaller than a pixel on this timeline.</p>
    <h2>Terms you can inspect</h2><div class="lab-terms">${Object.entries(definitions).map(([k,v])=>`<button type="button" data-term="${k}">${v[0]}</button>`).join('')}</div><div id="lab-glossary" class="lab-detail" aria-live="polite">Choose a term above. Definitions also appear when you select diagram nodes.</div>
    <p class="lab-note">Measured setup: Pi 4 · Linux 6.12.47+rpt-rpi-v8 · Python 3.11.2 · 720p MJPEG 30 fps requested · 10 ms IMU pause · scene memory, detector off · passive heatsink/no fan · power unknown. No electrical-energy or tracing-overhead claim.</p>
    <p class="source-links"><a href="../SYSTEMS_EXPERIMENTS.md">Configuration and architecture register</a><a href="../KERNEL_IO_RESULTS_03.md">Run 03 evidence</a><a href="../../src/spatial/scene_recorder.py">Queue code</a><a href="../../src/profiling/spatial_stalls.py">Profiler code</a><a href="../../src/profiling/kernel_io_trace.py">Trace/filter code</a></p>`;
  const el=id=>document.getElementById(id);
  // Keep one SVG graph: recording grows inside it, not in a second diagram.
  const graph=el('graph'),flow=el('lab-flow');
  flow.parentElement.remove();
  graph.append(flow);
  flow.setAttribute('x','0');flow.setAttribute('y','460');flow.setAttribute('width','1200');
  const bridge=document.createElementNS('http://www.w3.org/2000/svg','g');
  bridge.id='lab-bridge';
  bridge.innerHTML='<path d="M290 205V445H95V498"/><text x="300" y="437">newest frame → optional scene worker</text><path d="M150 498V475H690V260H710"/><text x="700" y="335">scene result</text><text x="700" y="352">→ snapshot</text>';
  graph.insertBefore(bridge,flow);
  const resources=document.createElementNS('http://www.w3.org/2000/svg','g');
  resources.id='lab-resources';
  // Resource links mean execution, never a measured core assignment or data copy.
  resources.innerHTML='<title>Pi CPU executes these workers; browser runs on the Mac</title>'+[ [90,150],[290,150],[510,75],[510,215],[510,345],[930,210] ].map(([x,y])=>`<path d="M1190 775V${y-45}H${x}V${y-25}"/>`).join('')+'<path d="M510 775H1190"/>';
  graph.insertBefore(resources,bridge);
  // Evidence is available on demand within the existing canvas.
  document.querySelector('.canvas').append(root);
  const evidence=document.createElement('details');
  evidence.id='lab-evidence';
  evidence.innerHTML='<summary>Measured timelines, kernel trace and terminology</summary>';
  const firstEvidence=root.querySelector('h2');
  while(firstEvidence.nextSibling)evidence.append(firstEvidence.nextSibling);
  evidence.insertBefore(firstEvidence,evidence.firstChild.nextSibling);
  root.append(evidence);
  const defs=`<defs><marker id="lab-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M0 0L10 5L0 10" fill="var(--line)"/></marker></defs>`;
  /** Build one keyboard-accessible program or hardware symbol. Coordinates are SVG units. */
  function node(id,x,y,w,label,sub,shape='box'){
    let form=`<rect class="part" x="${x}" y="${y}" width="${w}" height="60" rx="14"/>`;
    if(shape==='ram')form=`<rect class="part hardware" x="${x}" y="${y}" width="${w}" height="60"/>${[0,1,2,3,4].map(i=>`<path stroke="var(--green)" d="M${x+15+i*25} ${y+60}v8"/>`).join('')}`;
    if(shape==='card')form=`<path class="part hardware" d="M${x+18} ${y}H${x+w}V${y+60}H${x}V${y+18}Z"/>`;
    if(shape==='chip')form=`<rect class="part hardware" x="${x}" y="${y}" width="${w}" height="60" rx="3"/><path stroke="var(--green)" d="M${x-8} ${y+15}h8 M${x-8} ${y+30}h8 M${x-8} ${y+45}h8 M${x+w} ${y+15}h8 M${x+w} ${y+30}h8 M${x+w} ${y+45}h8"/>`;
    return `<g role="button" tabindex="0" data-term="${id}" aria-label="Explain ${label.replaceAll('"','&quot;')}">${form}<text x="${x+w/2}" y="${y+24}" text-anchor="middle">${label}</text><text class="sub" x="${x+w/2}" y="${y+45}" text-anchor="middle">${sub}</text></g>`;
  }
  /** Show the selected definition; storage expands within the existing graph. */
  function explain(id){
    const [title,body]=definitions[id];
    el('lab-detail').innerHTML=`<h3>${title}</h3><p>${body}</p>`;
    el('lab-glossary').innerHTML=`<h3>${title}</h3><p>${body}</p>`;
    if(id==='storage'){expanded=!expanded;drawFlow();}
    if(id==='recognize'){branch=!branch;drawFlow();}
  }
  /** Draw configuration-specific routing and a bounded conceptual queue. */
  function drawFlow(){
    const c=configs[selected],s=states[step],blocked=step>=2&&step<=5;
    const svg=el('lab-flow'),height=hardware?(expanded?550:345):240;
    svg.setAttribute('viewBox',`0 0 1100 ${height}`);
    svg.setAttribute('height',String(height*1200/1100));
    graph.setAttribute('viewBox',`0 0 1200 ${460+height*1200/1100}`);
    resources.style.display=hardware?'':'none';
    el('software-mode').setAttribute('aria-pressed',String(!hardware));
    el('hardware-mode').setAttribute('aria-pressed',String(hardware));
    el('architecture-hint').textContent=hardware?'Dotted green links = CPU executes software. Solid arrows = data. No fixed core assignment.':'Software data flow. Hardware resources are hidden.';
    el('lab-expand').textContent=branch?'Collapse recording path':'Expand recording path';
    el('lab-expand').setAttribute('aria-expanded',String(branch));
    let out=defs+node('recognize',25,35,175,'Spatial recognition',!c.queue&&blocked?'scene worker waits':branch?'collapse recording':'expand recording');
    out+=`<path class="wire" d="M200 65H230"/>`;
    if(!branch){
      out+='<text x="245" y="60">recording details hidden</text><path class="wire" d="M410 65H655"/>';
    }else if(c.queue){
      out+=`<g role="button" tabindex="0" data-term="queue" aria-label="Explain four-slot queue"><text x="230" y="25">${hardware?'RAM queue':'Queue'} · ${s.q}/4 waiting</text>`;
      for(let i=0;i<4;i++)out+=`<rect x="${230+i*45}" y="40" width="38" height="50" rx="4" fill="${i<s.q?'var(--blue)':'var(--bg)'}" stroke="var(--line)"/><text x="${249+i*45}" y="70" text-anchor="middle" style="fill:${i<s.q?'var(--bg)':'var(--muted)'}">${i<s.q?'R'+(step>=6?step-3+i:2+i):'·'}</text>`;
      out+='</g><path class="wire" d="M410 65H440"/>';
    }else out+='<text x="245" y="60">same worker saves</text><path class="wire" d="M395 65H440"/>';
    if(branch){
      out+=node('writer',440,35,165,c.queue?'Recording worker':'Inline save',blocked?`${s.w} · waiting`:s.w);
      out+='<path class="wire" d="M605 65H655"/>';
    }
    out+=node('storage',655,35,205,hardware?'Linux storage':'File output',hardware?(expanded?'click to collapse':'click to expand'):'images + JSON');
    if(hardware)out+='<path class="wire" d="M860 65H915"/>'+node('sd',915,35,160,'microSD','images + JSON','card');
    if(c.profiler){
      out+=node('profiler',25,155,175,'Profiler program',blocked&&!c.ram?'write waits; no sample':'observes application');
      out+='<path class="wire observe" d="M110 95V155"/>';
      if(c.ram)out+='<path class="wire" d="M200 185H290"/>'+node('ram',290,155,210,hardware?'Bounded RAM output':'Capped sample buffer','Pi measurement pending',hardware?'ram':'box')+`<path class="wire observe" d="M500 185H${hardware?995:820}V100"/><text class="sub" x="545" y="175">export AFTER collection + delay</text>`;
      else out+='<path class="wire" d="M200 185H755V100"/><text class="sub" x="290" y="175">separate measurement file · same storage</text>';
    }
    if(hardware){
      out+=node('imu',25,260,175,'IMU continues above',`independent of file writes`)+node('cpu',290,260,180,'Shared CPU · 4 cores','Linux schedules threads','chip');
      out+=`<path class="execution" d="M375 260V240H15V65H25 ${c.profiler?'M15 185H25':''} ${branch?'M375 240H530V95':''}"/><text class="sub" x="500" y="280">Dotted links: CPU executes software, not a data-transfer path.</text><text class="sub" x="500" y="305">A waiting thread can leave CPU time for other runnable threads.</text>`;
    }
    if(expanded&&hardware){
      out+='<path class="wire observe" d="M850 95H1090V360H120V390"/>';
      out+=node('cache',25,390,230,'ext4 + RAM cache','file organization / buffering','ram')+'<path class="wire" d="M255 420H320"/>'+node('block',320,390,175,'Block requests','may merge / requeue')+'<path class="wire" d="M495 420H560"/>'+node('driver',560,390,200,'Driver + controller','kernel code + hardware')+'<path class="wire" d="M760 420H915"/>'+node('sd',915,390,160,'microSD','persistent files','card');
      out+='<path class="wire observe" d="M140 450V475"/>'+node('journal',25,475,230,'Journal bookkeeping','recovery transactions');
    }
    svg.innerHTML=out;
    el('lab-event').textContent=!c.queue&&blocked?'Illustration: the scene worker waits inside its own save. The next scene query is delayed; IMU remains independent.':s.msg;
    if(!c.profiler&&step===0)el('lab-event').textContent='A scene result is ready. This architecture view does not include a profiler.';
    if(step===5)el('lab-event').textContent+=' The 4/4 measured value belongs to run 03; run 02 reached only 2/4.';
    if(c.ram)el('lab-event').textContent=`Illustrative event ${step+1}: scene writer ${blocked?'waits on file output':s.w}; ${s.q}/4 scene records waiting. Profiler samples stay in its separate capped buffer until post-collection export. No measured latency benefit is implied.`;
    else if(!c.profiler)el('lab-event').textContent=c.queue?`Illustration: recording worker ${blocked?'waits':s.w}; ${s.q}/4 records queued. No profiler in this configuration. Full queues reject new submissions; this sequence does not simulate a drop.`:blocked?'Illustration: the scene worker waits inside its own save. The next scene query is delayed; IMU remains independent.':'Illustration: scene recognition and file saving share one worker. No profiler in this configuration.';
  }
  /** Contrast selective diagnostic logging with actual device work and ring loss. */
  function drawFilter(){
    const c=configs[selected],old=selected==='run02',svg=el('lab-filter');
    svg.setAttribute('viewBox','0 0 1100 225');
    svg.innerHTML=`<text x="20" y="25">Device operations continue regardless of the diagnostic filter</text>
      <text x="20" y="68">mmc0 · storage host</text><path class="wire" d="M210 62H405"/>
      <text x="20" y="118">mmc1 · other host</text><path class="wire" d="M210 112H405"/>
      ${node('mmc',405,45,220,c.filter?'name == "mmc0"':'all MMC hosts','diagnostic-entry gate')}
      <path class="wire" d="M625 65H715"/><text class="sub" x="640" y="50">${c.filter?'mmc0 only':'all hosts'}</text>
      ${c.filter?'<text x="410" y="143" style="fill:var(--orange)">mmc1 diagnostic entries excluded</text>':''}
      <g role="button" tabindex="0" data-term="ring" aria-label="Explain per-CPU trace rings">${[0,1,2,3].map((i)=>`<circle cx="${755+i*90}" cy="90" r="28" fill="none" stroke="${old&&i===0?'var(--red)':'var(--green)'}" stroke-width="8"/><text x="${755+i*90}" y="95" text-anchor="middle">CPU ${i}</text>`).join('')}</g>
      ${old?'<path d="M742 56 Q790 40 793 87" fill="none" stroke="var(--red)" stroke-width="2" marker-end="url(#lab-arrow)"/><text class="sub" x="715" y="25">new entries replace oldest ↻</text>':''}
      <text x="715" y="151">${old?'CPU 0: 88,730 overwritten entries':selected==='run03'?'Run 03: zero reported loss, all cores':'RAM rings: bounded diagnostic storage'}</text>
      <text class="sub" x="20" y="190">Host numbers identify device interfaces; CPU numbers identify processor cores. They are different things.</text>
      <text class="sub" x="20" y="212">${selected==='run03'?'Measured: 4,009 MMC events, all mmc0; both event filters verified.':old?'Overwrite replaces old diagnostic entries, not camera images. Earlier evidence is missing.':'Schematic configuration. No new measurement is implied.'} Trace is exported after stop.</text>`;
  }
  /** Draw measured intervals on explicit common time scales. */
  function measured(){
    const x=t=>240+(t-130)*3.7;
    el('lab-coverage').innerHTML=`<text x="20" y="45">Kernel trace enabled</text><rect x="${x(130.079887)}" y="25" width="${(340.080574-130.079887)*3.7}" height="30" fill="var(--blue)" rx="5"/><text x="250" y="46" style="fill:var(--bg)">130.080 → 340.081 s</text><text x="20" y="95">Observer + app capture</text><rect x="${x(132.762823)}" y="75" width="${183.388737*3.7}" height="30" fill="var(--green)" rx="5"/><text x="260" y="96" style="fill:var(--bg)">132.763 → 316.152 s</text><text x="20" y="137">Starts inside + ends inside = time coverage. Zero loss counters provide a separate completeness check.</text>`;
    const rows=[['writer','Scene image write',246.543169,251.173268,'var(--green)'],['journal','Journal commit',246.544231,251.165219,'var(--orange)'],['profiler','Profiler write',246.597763,251.164705,'var(--blue)']];
    el('lab-timeline').innerHTML=rows.map(([id,label,a,b,color],i)=>`<g role="button" tabindex="0" data-term="${id}" aria-label="Explain ${label}"><text x="20" y="${48+i*48}">${label}</text><rect class="part" x="${250+(a-246)*145}" y="${27+i*48}" width="${(b-a)*145}" height="28" style="fill:${color}" rx="4"/><text x="${260+(a-246)*145}" y="${47+i*48}" style="fill:var(--bg)">${(b-a).toFixed(3)} s · ${a.toFixed(3)} → ${b.toFixed(3)}</text></g>`).join('')+'<text x="20" y="190">Intervals overlap; do not add them. Shared dependencies can make several layers wait together.</text>';
  }
  /** Stop the local animation; no timers survive page hiding or configuration changes. */
  function pause(){clearInterval(timer);timer=null;el('lab-play').textContent='Play';}
  function advance(){step=Math.min(step+1,states.length-1);drawFlow();if(step===states.length-1)pause();}
  for(const surface of [root,flow]){
    surface.addEventListener('click',event=>{const target=event.target.closest('[data-term]');if(target)explain(target.dataset.term);});
    surface.addEventListener('keydown',event=>{const target=event.target.closest('svg [data-term]');if(target&&['Enter',' '].includes(event.key)){event.preventDefault();explain(target.dataset.term);}});
  }
  el('lab-expand').addEventListener('click',()=>{branch=!branch;drawFlow();});
  el('software-mode').addEventListener('click',()=>{hardware=false;drawFlow();});
  el('hardware-mode').addEventListener('click',()=>{hardware=true;drawFlow();});
  document.addEventListener('expand-recording',()=>{branch=!branch;drawFlow();});
  el('lab-config').addEventListener('change',event=>{pause();selected=event.target.value;step=0;render();});
  el('lab-next').addEventListener('click',()=>{pause();branch=true;advance();});
  el('lab-reset').addEventListener('click',()=>{pause();step=0;drawFlow();});
  el('lab-play').addEventListener('click',()=>{if(timer){pause();return;}branch=true;if(step===states.length-1)step=0;drawFlow();el('lab-play').textContent='Pause';timer=setInterval(advance,1600);});
  document.addEventListener('visibilitychange',()=>{if(document.hidden)pause();});
  function render(){el('lab-status').textContent=configs[selected].status;el('lab-config-note').textContent=configs[selected].note;drawFlow();drawFilter();}
  render();measured();explain('coverage');
})();
