/* Run with: node tests/unit/test_preview_labels.js */
"use strict";
const assert = require("assert");
const fs = require("fs");
const vm = require("vm");

// Evaluate the browser's actual inline script with fake canvases and a pending
// fetch. This starts no server, downloads nothing and schedules no polling.
const html = fs.readFileSync(require.resolve("../../src/app/preview.html"), "utf8");
const script = html.match(/<script>([\s\S]*?)<\/script>/)[1];
const labels = [], boxesDrawn = [];
const boxctx = {
  clearRect(){}, setLineDash(){},
  strokeRect(...args) {boxesDrawn.push(args);},
  fillText(text, x, y) {labels.push({text, x, y});},
  measureText(text) {return {width:text.length * 8};}
};
const arrow = {clearRect(){}};
const image = {getContext:() => ({})};
const elements = new Map();
function element(id) {
  if (id === "image") return image;
  if (id === "boxes") return {getContext:() => boxctx};
  if (id === "overlay") return {getContext:() => arrow};
  if (!elements.has(id)) elements.set(id, {textContent:"", className:""});
  return elements.get(id);
}
const context = vm.createContext({
  document:{getElementById:element},
  fetch:() => new Promise(() => {}),
  AbortSignal:{timeout:() => null},
  setTimeout:() => {throw new Error("Polling must not schedule in this test");}
});
vm.runInContext(script, context);

// The browser accepts the live ID, but old/manual snapshots remain readable.
assert.strictEqual(vm.runInContext('detectionLabel({track_id:7,label:"chair",confidence:.92})', context),
  "#7 chair 0.92");
assert.strictEqual(vm.runInContext('detectionLabel({label:"chair",confidence:.92})', context),
  "chair 0.92");
assert.strictEqual(vm.runInContext('detectionLabel({track_id:0,label:"chair",confidence:.92})', context),
  "chair 0.92");

// Only a ready detector result with a live camera draws boxes and labels.
const tracked = {track_id:7, label:"chair", confidence:.92,
  box_xyxy:[1220,100,1270,200]};
const noId = {label:"person", confidence:.81, box_xyxy:[100,100,300,400]};
const base = {status:"live", motion:"unreliable", skipped:0,
  detector:{status:"ready", sequence:4, boxes:[tracked,noId], width:1280,
    height:720, rate_hz:2, compute_ms:230, age_ms:400}};
context.render(base);
assert.deepStrictEqual(labels.map(item => item.text), ["#7 chair 0.92", "person 0.81"]);
assert.strictEqual(boxesDrawn.length, 2);
assert(labels[0].x >= 0 && labels[0].x + labels[0].text.length * 8 <= 640);

labels.length = 0;
context.render({...base, detector:{...base.detector, status:"stale"}});
assert.deepStrictEqual(labels, []);
context.render({...base, status:"error"});
assert.deepStrictEqual(labels, []);

console.log("live preview ID labels and stale/error gates: passed");
