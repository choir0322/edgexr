/** Exercise the complete offline lesson without needing camera hardware or a browser. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const lesson = path.resolve(__dirname, '../../docs/learning');
const elements = new Map();

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
    getContext() { return {createImageData(w, h) { return {data: new Uint8ClampedArray(w * h * 4)}; }, putImageData(){}, fillRect(){}, set fillStyle(_value) {}}; },
  };
  elements.set(id, element);
  return element;
}

/** Return one stable element for each ID used by the page. */
function get(id) { return elements.get(id) || makeElement(id); }
const pairButtons = ['adjacent', 'walkthrough'].map(value => makeElement(`pair-${value}`, {pair: value}));
const stageButtons = Array.from({length: 8}, (_, index) => makeElement(`stage-${index}`, {stage: String(index)}));
const panels = Array.from({length: 8}, (_, index) => makeElement(`panel-${index}`, {panel: String(index)}));
let intervalCallback;
const document = {
  readyState: 'complete', getElementById: get,
  createElement: name => makeElement(`generated-${name}-${elements.size}`),
  createElementNS: (_namespace, name) => makeElement(`svg-${name}-${elements.size}`),
  querySelector: selector => stageButtons[Number(selector.match(/data-stage="(\d+)"/)[1])],
  querySelectorAll: selector => {
    if (selector === '[data-pair]') return pairButtons;
    if (selector === '[data-stage]') return stageButtons;
    if (selector === '[data-panel]') return panels;
    throw new Error(`Unexpected selector: ${selector}`);
  },
};
const context = vm.createContext({window: {setInterval(callback) { intervalCallback = callback; return 1; }, clearInterval() { intervalCallback = undefined; }}, document});
vm.runInContext(fs.readFileSync(path.join(lesson, 'images/hann-fft-data.js'), 'utf8'), context);
vm.runInContext(fs.readFileSync(path.join(lesson, 'hann-fft-explorer.js'), 'utf8'), context);

const data = context.window.HANN_FFT_LESSON_DATA;
const html = fs.readFileSync(path.join(lesson, 'hann-fft-explorer.html'), 'utf8');
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
assert.match(get('ready').textContent, /Ready/);
assert.equal(get('overview').hidden, false);
assert.equal(get('overview-b').src, data.framePaths['314']);
assert.equal(get('grid-overlay-a').children.length, 18, 'nine real patch rectangles and labels');
assert.match(get('consensus-readout').textContent, /8\/9 patches agree/);
assert.match(get('state-fields').textContent, /"motion": "reliable"/);
assert.equal(get('browser-arrow').children.length, 2, 'line and arrowhead');

get('walk-mode').dispatch('click');
assert.equal(get('overview').hidden, true);
assert.equal(panels[0].hidden, false);
stageButtons[2].dispatch('click');
assert.equal(panels[2].hidden, false);
for (const button of stageButtons) {
  button.dispatch('click');
  assert.equal(panels[Number(button.dataset.stage)].hidden, false);
}
stageButtons[2].dispatch('click');
get('hann-amount').value = '100';
get('hann-amount').dispatch('input');
assert.match(get('hann-readout').textContent, /seam in A: 0\.000/);
get('choose-peak').dispatch('click');
assert.equal(get('candidate-x').value, '-4');
assert.equal(get('candidate-y').value, '0');
assert.match(get('candidate-readout').textContent, /Strongest integer cell/);
get('freq-x').value = '52';
get('freq-x').dispatch('input');
assert.match(get('frequency-readout').textContent, /\(52, 0\)/);

pairButtons[1].dispatch('click');
assert.equal(get('overview-b').src, data.framePaths['316']);
assert.equal(get('raw-b').src, data.patchPaths['316']);
assert.match(get('consensus-readout').textContent, /3\/9 patches agree/);
assert.match(get('state-fields').textContent, /"motion": "unreliable"/);
assert.equal(get('browser-arrow').children.length, 0, 'unreliable shift has no arrow');
assert.match(get('quality-readout').textContent, /Q=51\.93/);
assert.match(get('overview-outcome').textContent, /unreliable/);

get('play').dispatch('click');
assert.equal(get('play').textContent, 'Pause');
intervalCallback();
assert.equal(get('stage-count').textContent, '4 / 8');
get('play').dispatch('click');
assert.equal(get('play').textContent, 'Play');
console.log('PASS: real pair switching, Hann control, peak choice, consensus, State and navigation.');
