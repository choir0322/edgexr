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
  if (!elements.has(id)) elements.set(id, {textContent:"", className:"", children:[],
    addEventListener(){}, replaceChildren(){this.children=[];this.textContent="";},
    append(child){this.children.push(child);}});
  return elements.get(id);
}
const context = vm.createContext({
  document:{getElementById:element,createElement:() => ({textContent:"",className:""})},
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

// Enrollment history is independent of transient recognition and survives stale
// camera state. The server's outcome, never an HTTP acknowledgment, says stored.
const receipts = [
  {label:"View-1",status:"stored",scene_id:1,stored_views:1},
  {label:"View-2",status:"rejected",reason:"weak_image",stored_views:1},
  {label:"View-3",status:"pending",reason:"foreground_evidence_unavailable"}
];
context.render({...base,scene:{status:"starting",enrollments:receipts}});
const history = element("scene-enrollments");
assert(history.children[0].textContent.includes("STORED View-1"));
assert(history.children[1].textContent.includes("NOT STORED View-2 · weak_image"));
assert(history.children[2].textContent.includes("waiting for usable detector evidence"));
context.render({...base,scene:{status:"stale",enrollments:receipts}});
assert.strictEqual(history.children.length,3);
assert.strictEqual(element("scene-enroll").disabled,true);

console.log("live preview ID labels and stale/error gates: passed");
