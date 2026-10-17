/* Run with: node tests/unit/test_basic_tracker_page.js */
"use strict";
const assert = require("assert");
const fs = require("fs");
const lessonPath = "../../docs/learning/basic-tracker.js";
const lesson = require(lessonPath);
const markup = fs.readFileSync(require.resolve("../../docs/learning/basic-tracker.html"), "utf8");

// The solid execution path enters all nine tracker decisions and exits to
// publication; the dotted top shortcut is only a labeled overview.
assert.deepStrictEqual(lesson.FLOW_IDS.slice(0, 4),
  ["create", "infer", "match", "tracker-0"]);
assert.deepStrictEqual(lesson.FLOW_IDS.slice(-2), ["tracker-8", "publish"]);
assert.strictEqual(lesson.FLOW_IDS.length, 13);
assert(markup.includes("collapsed overview"));
assert(markup.includes("id=\"graph\""));
assert(lesson.LIVE.infer.effect.includes("before tracker.update"));
assert(lesson.LIVE.publish.effect.includes("browser shows provisional #ID"));

// The lesson's example and math still agree with the Python tracker tests.
const trace = lesson.example();
assert.deepStrictEqual(trace.identified.map(d => d.track_id), [1, 3, 2]);
assert.deepStrictEqual(trace.decisions.map(d => d.reason),
  ["accepted", "accepted", "old ID already claimed"]);
assert.strictEqual(trace.input[0].track_id, undefined);
assert.strictEqual(trace.pairs.find(p => p.id === 2 && p.index === 0).sameClass, false);
assert(lesson.descriptions(trace)[3].data.includes("0.902"));
const area = lesson.overlap([0,0,10,10], [5,0,15,10]);
assert.strictEqual(area.intersection, 50);
assert.strictEqual(area.union, 150);
assert(Math.abs(area.iou - 1/3) < 1e-12);
const old = {tracks:[{id:4, class_id:9, box:[0,0,10,10], missed:0}], nextId:5};
assert.throws(() => lesson.traceUpdate(old, [
  {class_id:9, box_xyxy:[0,0,10,10]}, {class_id:9, box_xyxy:[2,2,2,8]}
]), /positive area/);
assert.strictEqual(old.tracks[0].missed, 0);
const miss1 = lesson.traceUpdate(old, []);
const miss2 = lesson.traceUpdate({tracks:miss1.after, nextId:miss1.nextId}, []);
assert.deepStrictEqual(miss1.ageEvents, [{id:4, missed:1, retired:false}]);
assert.deepStrictEqual(miss2.ageEvents, [{id:4, missed:2, retired:true}]);

// A small DOM/SVG double checks the page controls without claiming visual QA.
const elements = new Map();
function fakeElement(id) {
  if (!elements.has(id)) elements.set(id, {
    id, children:[], handlers:{}, attributes:{}, style:{}, hidden:id === "detail",
    textContent:"", innerHTML:"", disabled:false,
    setAttribute(name, value) {this.attributes[name] = String(value);},
    appendChild(child) {this.children.push(child);},
    addEventListener(name, fn) {this.handlers[name] = fn;},
    fire(name, event={}) {this.handlers[name](event);}
  });
  return elements.get(id);
}
global.document = {
  getElementById:fakeElement,
  createElementNS:() => fakeElement(Symbol("svg"))
};
delete require.cache[require.resolve(lessonPath)];
require(lessonPath);
assert.strictEqual(fakeElement("nodes").children.length, 13);
assert.strictEqual(fakeElement("edges").children.length, 14);
assert.strictEqual(fakeElement("edges").children[2].attributes.d, "M 510 118 V 278");
assert.strictEqual(fakeElement("edges").children[11].attributes.d, "M 1550 278 V 118");
assert.strictEqual(fakeElement("edges").children[12].attributes.class, "overview");
assert.strictEqual(fakeElement("position").textContent, "1 of 13 · Create once");
assert.strictEqual(fakeElement("token-label").textContent, "worker");
assert.strictEqual(fakeElement("detail").hidden, true);

fakeElement("next").fire("click");
assert.strictEqual(fakeElement("position").textContent, "2 of 13 · Infer frame");
assert.strictEqual(fakeElement("token-label").textContent, "frame");
assert(fakeElement("detail-rule").textContent.includes("empty list continues"));
fakeElement("next").fire("click");
assert.strictEqual(fakeElement("token-label").textContent, "boxes");
fakeElement("next").fire("click");
assert.strictEqual(fakeElement("position").textContent, "4 of 13 · Input");
assert.strictEqual(fakeElement("token-label").textContent, "d₀");
assert.strictEqual(fakeElement("edges").children[2].attributes.class, "edge done");
assert.strictEqual(fakeElement("detail-link").attributes.href,
  "../../src/vision/basic_tracker.py");

const iouNode = fakeElement("nodes").children[6];
iouNode.fire("mouseenter");
assert(fakeElement("detail-data").textContent.includes("IoU = 0.902"));
assert(fakeElement("detail-visual").innerHTML.includes("<svg"));
iouNode.fire("mouseleave");
assert.strictEqual(fakeElement("detail-title").textContent, "Input");
iouNode.fire("click");
assert.strictEqual(fakeElement("position").textContent, "7 of 13 · IoU");
fakeElement("nodes").children[9].fire("keydown", {key:"Enter", preventDefault(){}});
assert(fakeElement("detail-data").textContent.includes("retired"));
fakeElement("nodes").children[11].fire("click");
assert.strictEqual(fakeElement("position").textContent, "12 of 13 · Return");
fakeElement("next").fire("click");
assert.strictEqual(fakeElement("position").textContent, "13 of 13 · Publish");
assert.strictEqual(fakeElement("token-label").textContent, "IDs");
assert.strictEqual(fakeElement("edges").children[11].attributes.class, "edge done");
assert.strictEqual(fakeElement("detail-link").attributes.href,
  "../../src/vision/live_detector.py");
assert.strictEqual(fakeElement("next").disabled, true);

fakeElement("reset").fire("click");
assert.strictEqual(fakeElement("position").textContent, "1 of 13 · Create once");
assert.strictEqual(fakeElement("detail").hidden, true);

// Playback follows the same route and stops at Publish without taking the
// overview shortcut or looping back through Match IDs.
const originalSetInterval = global.setInterval, originalClearInterval = global.clearInterval;
let tick = null;
global.setInterval = callback => {tick = callback; return 1;};
global.clearInterval = () => {tick = null;};
fakeElement("play").fire("click");
for (let i = 0; i < 12; i++) tick();
assert.strictEqual(fakeElement("position").textContent, "13 of 13 · Publish");
assert.strictEqual(fakeElement("play").textContent, "Play");
assert.strictEqual(tick, null);
global.setInterval = originalSetInterval;
global.clearInterval = originalClearInterval;
delete global.document;

console.log("basic tracker integrated graph, math and controls: passed");
