/** Exercise the lesson controllers against a small document double. This checks
 * navigation/data contracts, not browser layout or accessibility rendering. */
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const root = path.resolve(__dirname, "../../docs/learning");

/** Minimal element storage and event registration used by the lesson. @param {object} dataset Button data. @returns {object} */
function element(dataset = {}) {
  return {
    dataset, attributes: {}, events: {}, innerHTML: "", textContent: "", hidden: false,
    classList: { toggle() {} }, focus() {},
    setAttribute(name, value) { this.attributes[name] = value; },
    removeAttribute(name) { delete this.attributes[name]; },
    addEventListener(name, callback) { this.events[name] = callback; },
    closest() { return this; },
  };
}
const ids = new Map(), selectors = new Map();
const stages = Array.from({ length: 6 }, (_, i) => element({ ssdStage: String(i) }));
const document = {
  getElementById(id) {
    if (!ids.has(id)) ids.set(id, element());
    return ids.get(id);
  },
  querySelector(selector) {
    if (!selectors.has(selector)) selectors.set(selector, element());
    return selectors.get(selector);
  },
  querySelectorAll(selector) {
    assert.equal(selector, "[data-ssd-stage]");
    return stages;
  },
  addEventListener() {},
};
const context = vm.createContext({ document, window: { DetectionMath: require(path.join(root, "detection-math.js")) }, setInterval, clearInterval });
for (const file of ["images/detection-lesson-data.js", "detection-architecture.js", "detection-ssd.js"]) {
  vm.runInContext(fs.readFileSync(path.join(root, file), "utf8"), context, { filename: file });
}

/** Dispatch a click through the actual registered callback. @param {object} node Listener target. @param {object} data Clicked button data. @returns {void} */
function click(node, data = {}) { node.events.click({ target: element(data) }); }

// Both controllers must initialize; SSD events must not change convolution state.
assert.match(ids.get("standard-diagram").innerHTML, /Standard convolution/);
const originalProgress = ids.get("progress").textContent;
assert.match(ids.get("ssd-explain").innerHTML, /19×19×512/);
click(selectors.get(".ssd-stages"), { ssdStage: "1" });
assert.match(ids.get("ssd-explain").innerHTML, /361 × 3 = 1083/);
click(ids.get("ssd-scales"), { ssdHead: "1" });
assert.match(ids.get("ssd-explain").innerHTML, /100 × 6 = 600/);
click(ids.get("ssd-priors"), { ssdPrior: "2" });
assert.match(ids.get("ssd-explain").innerHTML, /wide 2:1/);
click(ids.get("ssd-next"));
assert.match(ids.get("ssd-explain").innerHTML, /6×4 = 24/);
assert.equal(ids.get("ssd-scales").hidden, true);
click(ids.get("ssd-next"));
assert.match(ids.get("ssd-explain").innerHTML, /CENTER_SIZE/);
assert.match(ids.get("ssd-picture").innerHTML, /Solid: decoded candidate/);
click(ids.get("ssd-next"));
assert.match(ids.get("ssd-explain").innerHTML, /NMS: IoU with A/);
assert.match(ids.get("ssd-stage-label").textContent, /GRAPH \+ EDGEXR FILTER/);
click(ids.get("ssd-next"));
assert.equal(ids.get("ssd-picture").attributes.viewBox, "0 0 1280 720");
assert.match(ids.get("ssd-explain").innerHTML, /\[3, 321, 353, 535\]/);
assert.match(ids.get("ssd-picture").innerHTML, /diningtable/);
assert.equal(ids.get("progress").textContent, originalProgress);
click(ids.get("ssd-next"));
assert.match(ids.get("ssd-explain").innerHTML, /19×19×512/);
assert.equal(ids.get("ssd-back").disabled, true);

// Exercise every scale/shape through the numeric decode and filtering stages.
for (let h = 0; h < 6; h++) {
  for (let p = 0; p < (h === 0 ? 3 : 6); p++) {
    click(selectors.get(".ssd-stages"), { ssdStage: "1" });
    click(ids.get("ssd-scales"), { ssdHead: String(h) });
    click(ids.get("ssd-priors"), { ssdPrior: String(p) });
    for (const stage of ["2", "3", "4"]) {
      click(selectors.get(".ssd-stages"), { ssdStage: stage });
      assert.doesNotMatch(ids.get("ssd-picture").innerHTML + ids.get("ssd-explain").innerHTML, /NaN|undefined|Infinity/);
    }
  }
}
click(ids.get("step"));
assert.notEqual(ids.get("progress").textContent, originalProgress);
console.log("PASS: six SSD stages, all scale/prior combinations, measured-result boundary and independent convolution controls.");
