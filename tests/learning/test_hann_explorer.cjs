/** Exercise the complete offline lesson without needing camera hardware or a browser. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const lesson = path.resolve(__dirname, '../../docs/learning');
const elements = new Map();
const html = fs.readFileSync(path.join(lesson, 'hann-fft-explorer.html'), 'utf8');
const ids = new Set([...html.matchAll(/id="([^"]+)"/g)].map(match=>match[1]));
const painted = new Map();

/** Model the small DOM subset used by the website. */
function makeElement(id, dataset = {}) {
  const attributes = new Map();
  const listeners = new Map();
  const children = [];
  const element = {
    id, dataset, attributes, listeners, children, value: '0', textContent: '',
    hidden: false, style: {}, offsetLeft: Number(dataset.stage || 0) * 155,
    clientWidth: 450, scrollLeft: 0,
    classList: {toggle(){}},
    setAttribute(name, value) { attributes.set(name, String(value)); },
    removeAttribute(name) { attributes.delete(name); },
    getAttribute(name) { return attributes.get(name); },
    addEventListener(name, handler) { listeners.set(name, handler); },
    dispatch(name, event = {}) { assert.ok(listeners.has(name), `${id} has ${name}`); listeners.get(name)({currentTarget: element, ...event}); },
    append(...nodes) { children.push(...nodes); },
    replaceChildren(...nodes) { children.length = 0; children.push(...nodes); },
    getBoundingClientRect() { return {left: 0, top: 0, width: 800, height: 560}; },
    getContext() { return {createImageData(w, h) { return {data: new Uint8ClampedArray(w * h * 4)}; }, putImageData(image){ painted.set(id,image.data); }, fillRect(){}, clearRect(){}, drawImage(){}, strokeRect(){}, fillText(){}, set fillStyle(_value) {}}; },
  };
  elements.set(id, element);
  return element;
}

/** Return one stable element for each ID used by the page. */
function get(id) { assert(ids.has(id), 'Existing HTML element: '+id); return elements.get(id) || makeElement(id); }

const stageButtons = Array.from({length: 8}, (_, index) => makeElement(`stage-${index}`, {stage: String(index)}));
const panels = Array.from({length: 8}, (_, index) => makeElement(`panel-${index}`, {panel: String(index)}));
let intervalCallback;
const document = {
  readyState: 'complete', hidden:false, listeners:new Map(),
  addEventListener(name,fn){this.listeners.set(name,fn);}, getElementById: get,
  createElement: name => makeElement(`generated-${name}-${elements.size}`),
  createElementNS: (_namespace, name) => makeElement(`svg-${name}-${elements.size}`),
  querySelector: selector => stageButtons[Number(selector.match(/data-stage="(\d+)"/)[1])],
  querySelectorAll: selector => {
    if (selector === '[data-stage]') return stageButtons;
    if (selector === '[data-panel]') return panels;
    throw new Error(`Unexpected selector: ${selector}`);
  },
};
class FakeImage { set src(value){ this.path=value; this.complete=true; this.naturalWidth=320; if(this.onload)this.onload(); } }
const context = vm.createContext({Image:FakeImage, window: {setInterval(callback) { intervalCallback = callback; return 1; }, clearInterval() { intervalCallback = undefined; }}, document});
vm.runInContext(fs.readFileSync(path.join(lesson, 'images/hann-fft-data.js'), 'utf8'), context);
vm.runInContext(fs.readFileSync(path.join(lesson, 'hann-fft-explorer.js'), 'utf8'), context);

const data = context.window.HANN_FFT_LESSON_DATA;
assert.match(html, /src="images\/hann-fft-data\.js"/);
assert.match(html, /src="hann-fft-explorer\.js"/);
assert.doesNotMatch(html, /<script[^>]+https?:\/\//, 'the website works offline');
for (const imagePath of Object.values({...data.framePaths, ...data.patchPaths})) {
  const png = fs.readFileSync(path.join(lesson, imagePath));
  assert.equal(png.subarray(0, 8).toString('hex'), '89504e470d0a1a0a');
  assert.equal(png.readUInt32BE(16), imagePath.includes('patch') ? 80 : 320);
  assert.equal(png.readUInt32BE(20), imagePath.includes('patch') ? 56 : 180);
}
for (const [name, p] of Object.entries(data.pairs)) {
  assert.equal(p.a.length, 80 * 56);
  assert.equal(p.surface.length, 80 * 56);
  assert.equal(p.patches.length, 9);
  const score = p.surface[p.peak[1] * 80 + p.peak[0]];
  assert.equal(score, Math.max(...p.surface), `${name} peak is the strongest cell`);
  assert.equal(p.patches.filter(patch => patch.agrees).length, name === 'adjacent' ? 8 : 3);
  assert.equal(p.wholeResult !== null, name === 'adjacent');
}

assert.match(get('ready').textContent, /Recorded data/);
assert.equal(panels[0].hidden, false);
assert.equal(get('input-b').src, data.framePaths['314']);
assert.equal(get('grid-overlay-a').children.length,18);
assert.match(get('consensus-readout').textContent,/8\/9 patches agree/);
assert.match(get('state-fields').textContent,/"motion": "reliable"/);
assert.equal(get('browser-arrow').children.length,2);
assert.match(get('hann-readout').textContent,/→ 0\.000 levels/);
assert.notDeepEqual(painted.get('centered-a'),painted.get('weighted-a'),'Hann visibly changes the data');
assert.notDeepEqual(painted.get('repeated-before'),painted.get('repeated-a'),'seam comparison differs');
assert.notDeepEqual(painted.get('alignment-before'),painted.get('alignment'),'peak alignment visibly changes overlay');
assert.match(get('candidate-readout').textContent,/\(-4, \+0\)/);
for(const button of stageButtons){
  button.dispatch('click');
  assert.equal(panels.filter(p=>!p.hidden).length,1);
  assert.equal(panels[Number(button.dataset.stage)].hidden,false);
}
get('pair-choice').value='walkthrough';get('pair-choice').dispatch('change');
assert.equal(get('input-b').src,data.framePaths['316']);
assert.match(get('consensus-readout').textContent,/3\/9 patches agree/);
assert.match(get('state-fields').textContent,/"motion": "unreliable"/);
assert.equal(get('browser-arrow').children.length,0);
assert.match(get('quality-readout').textContent,/Q=51\.93/);
get('reset').dispatch('click');
get('play').dispatch('click');assert.equal(get('play').textContent,'Pause');
for(let i=0;i<7;i++)intervalCallback();
assert.equal(intervalCallback,undefined);
assert.equal(get('next').disabled,true);
assert.equal(get('play').textContent,'Replay');
get('play').dispatch('click');assert(intervalCallback);
document.hidden=true;document.listeners.get('visibilitychange')();
assert.equal(intervalCallback,undefined);
get('reset').dispatch('click');assert.equal(panels[0].hidden,false);
get('next').dispatch('click');assert.equal(panels[1].hidden,false);
assert.doesNotMatch(html,/type="range"/,'No sliders');
console.log('PASS: recorded maps, Hann/alignment changes, reliable/rejected consensus, thumbnails and simplified playback. Browser layout remains unverified.');
