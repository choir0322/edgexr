/* Hardware-free interaction/data checks, not a substitute for browser visual QA. */
'use strict';
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const assert = require('node:assert/strict');
const root = path.resolve(__dirname, '../docs/learning');
const html = fs.readFileSync(path.join(root, 'sparse-scene-01.html'), 'utf8');
const context2d = new Proxy({}, {get: (target, key) => target[key] || (() => {})});
const elements = Object.fromEntries([...html.matchAll(/id="([^"]+)"/g)].map(m => [m[1], {
  value: '0', checked: true, textContent: '', width: 1340, height: 410,
  getContext: () => context2d,
  getBoundingClientRect: () => ({left: 0, top: 0, width: 1340, height: 410})
}]));
const stages = Array.from({length: 6}, (_, i) => ({dataset: {stage: String(i)},
  classList: {toggle() {}}, setAttribute() {}}));
const sandbox = {
  window: {}, document: {getElementById: id => {
    assert.ok(elements[id], `Missing HTML element ${id}`); return elements[id];
  }, querySelectorAll: () => stages},
  Image: class {
    constructor() { this.naturalWidth = 1280; this.naturalHeight = 720; }
    set src(value) { this.onload(); }
  }, URL: {createObjectURL: () => 'blob:test', revokeObjectURL() {}}
};
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync(path.join(root, 'images/sparse-scene-evidence.js'), 'utf8'), sandbox);
vm.runInContext(fs.readFileSync(path.join(root, 'sparse-scene-explorer.js'), 'utf8'), sandbox);

// Exercise every explanation with both trials and every selectable association.
for (let trial = 0; trial < 2; trial++) {
  elements.trial.value = String(trial); elements.trial.onchange();
  const d = sandbox.window.SPARSE_EVIDENCE[trial];
  assert.equal(d.projections[0].length, d.report.accepted_points);
  assert.equal(d.projections[1].length, d.report.accepted_points);
  assert.ok(d.samples.length > 0);
  for (let stage = 0; stage < 6; stage++) {
    stages[stage].onclick();
    for (let i = 0; i < d.samples.length; i++) {
      elements.point.value = String(i); elements.point.oninput();
      assert.ok(elements.title.textContent);
      assert.ok(!elements.math.textContent.includes('NaN'));
    }
  }
  elements.overlay.checked = false; elements.overlay.onchange();
  elements.overlay.checked = true; elements.overlay.onchange();
  elements.frames.onclick({clientX: 100, clientY: 100});
  elements.file1.onchange({target: {files: [{}]}});
  elements.back.onclick(); elements.next.onclick();
  for (const p of d.samples) {
    for (let v = 0; v < 2; v++) {
      const error = Math.hypot(...p.projected[v].map((x, i) => x-p.observed[v][i]));
      assert.ok(Math.abs(error-p.residual_px[v]) < 1e-8);
      assert.ok(error <= 2.0);
    }
  }
}
console.log('PASS: 2 trials × 6 stages × 48 points, controls, association residuals. Browser layout not checked.');
