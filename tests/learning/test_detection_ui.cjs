/** Offline checks of the real lesson script. DOM doubles do not verify layout. */
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const folder = path.resolve(__dirname, "../../docs/learning");
const html = fs.readFileSync(path.join(folder, "detection-architecture.html"), "utf8");
const elements = new Map();
let callback = null, focused = null;
/** Minimal DOM node for the actual event handlers. @param {string} id Node identifier. @returns {object} */
function element(id) {
  return {innerHTML:"", textContent:"", disabled:false, events:{},
    addEventListener(name, fn) { this.events[name] = fn; },
    dispatch(name, event = {}) { this.events[name](event); },
    focus() { focused = id; }};
}
for (const match of html.matchAll(/id="([^"]+)"/g)) elements.set(match[1], element(match[1]));
const comparison = element("comparison");
const document = {
  hidden:false, events:{},
  getElementById(id) { assert(elements.has(id), "Known DOM id: "+id); return elements.get(id); },
  querySelector(selector) {
    if (selector === ".comparison") return comparison;
    assert.match(selector, /^\[data-select=/);
    return element(selector);
  },
  addEventListener(name, fn) { this.events[name] = fn; }
};
const context = vm.createContext({window:{}, document,
  setInterval(fn) { assert.equal(callback,null,"Only one timer"); callback = fn; return 1; },
  clearInterval() { callback = null; }
});
vm.runInContext(fs.readFileSync(path.join(folder,"images/detection-lesson-data.js"),"utf8"), context);
let script = fs.readFileSync(path.join(folder,"detection-architecture.js"),"utf8");
// Inspect the calculated tensors without adding a test API to the published page.
script = script.replace(/\}\)\(\);\s*$/, "window.testResults = results; })();");
vm.runInContext(script, context);
const get = id => elements.get(id);
const click = id => get(id).dispatch("click");
const choose = (id, keyboard = false) => comparison.dispatch(keyboard ? "keydown" : "click", {
  key:"Enter", preventDefault(){}, target:{closest:() => ({dataset:{select:id}})}
});

// Hand-calculated fixtures check channel summation and pointwise mixing.
const results = JSON.parse(JSON.stringify(context.window.testResults));
assert.deepEqual(results.depth, [[4,6,5,6],[4,5,3,4],[4,4,2,4]]);
assert.deepEqual(results.dense, [[13,16,11,15],[11,15,8,11]]);
assert.deepEqual(results.separate, [[10,14,11,12],[7,6,1,5]]);
assert.match(get("detail-title").textContent, /Standard filter 1/);
choose("p0");
assert.match(get("detail-body").innerHTML, /4×\(1\) \+ 4×\(2\) \+ 4×\(-1\) \+ bias \(2\)/);
choose("d2", true);
assert.match(get("detail-title").textContent, /Depthwise C3/);
assert.equal(focused, '[data-select="d2"]');

// Playback must progress, pause on inspection, end, replay and reset deterministically.
click("play"); assert(callback);
callback(); assert.match(get("progress").textContent, /Multiply/);
choose("s1"); assert.equal(callback,null);
click("step"); assert.match(get("progress").textContent, /Sum spatial/);
click("play");
for (let i=0; i<17; i++) { assert(callback); callback(); }
assert.equal(callback,null);
assert.equal(get("step").disabled,true);
assert.match(get("progress").textContent,/Cell 4\/4/);
assert.equal(get("play").textContent,"Replay");
for (const id of ["standard-diagram","separable-diagram"]) {
  assert(!/NaN|undefined|Infinity/.test(get(id).innerHTML));
  assert(get(id).innerHTML.includes("<"));
}
click("play"); assert(callback);
document.hidden = true; document.events.visibilitychange();
assert.equal(callback,null);
click("reset");
assert.equal(get("step").disabled,false);
assert.match(get("progress").textContent,/Cell 1\/4/);
assert.match(get("detail-title").textContent,/Standard filter 1/);
for (const id of ["play", "step", "reset"]) assert.match(html, new RegExp(`id="${id}"`));
console.log("PASS: known convolution results, both paths, selection/keyboard, playback, pause, completion and reset. Browser layout remains unverified.");
