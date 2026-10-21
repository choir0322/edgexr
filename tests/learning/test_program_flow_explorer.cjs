/** Audit the unified learning graph without camera hardware or a browser. */
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const root = path.resolve(__dirname, "../..");
const lesson = path.join(root, "docs/learning");
const html = fs.readFileSync(path.join(lesson, "program-flow-explorer.html"), "utf8");
const context = vm.createContext({ window: {} });
vm.runInContext(fs.readFileSync(path.join(lesson, "program-flow-map.js"), "utf8"), context);
const nodes = context.window.EDGEXR_FLOW;

// The entry point remains offline and loads the data, map, and UI in dependency order.
assert.doesNotMatch(html, /<script[^>]+https?:\/\//, "the explorer works offline");
const scripts = [...html.matchAll(/<script src="([^"]+)"/g)].map(match => match[1]);
assert.deepEqual(scripts, [
  "images/hann-fft-data.js",
  "program-flow-map.js",
  "program-flow-explorer.js",
]);
for (const relative of scripts) assert.ok(fs.existsSync(path.join(lesson, relative)), relative);
assert.match(html, /program-flow-inline\.css/);
assert.ok(fs.existsSync(path.join(lesson, "program-flow-inline.css")));
const ui = fs.readFileSync(path.join(lesson, "program-flow-explorer.js"), "utf8");
assert.match(ui, /expanded-node/);
assert.match(ui, /function measureNode/);
assert.match(ui, /function rootLayout/);
assert.doesNotMatch(ui, /inline-branch/, "expansion is not appended below the graph");
assert.doesNotMatch(ui, /current\.id === 'root'/, "the graph does not switch to a replacement page");

// Every declared child is valid, every node is reachable, and every source link resolves.
const visited = new Set();
function visit(id) {
  assert.ok(nodes[id], `declared node exists: ${id}`);
  if (visited.has(id)) return;
  visited.add(id);
  for (const child of nodes[id].children) visit(child);
}
visit("root");
assert.equal(visited.size, Object.keys(nodes).length, "no orphaned learning nodes");
for (const node of Object.values(nodes)) {
  assert.ok(node.input && node.output && node.explanation && node.policy);
  assert.ok(fs.existsSync(path.join(root, "src", node.source)), `source exists: ${node.source}`);
}

// Keep the easily confused live policies explicit and separate.
assert.match(nodes.parse.badge, /0\.30/);
assert.match(nodes.iou.badge, /0\.30/);
assert.match(nodes.memory.policy, /0\.85/);
assert.match(nodes.selectDetection.policy, /Zero boxes is a valid completed result/);
assert.match(nodes.root.explanation, /does not wait for a synchronized/);
assert.match(nodes.hann.policy, /not blur, cropping, object attention/);
assert.match(nodes.inverse.output, /candidate shift/);

// Exercise in-place expansion with the DOM subset used before a concept canvas opens.
const ids = new Set([...html.matchAll(/id="([^"]+)"/g)].map(match => match[1]));
const elements = new Map();
function element(id) {
  const attributes = new Map(), listeners = new Map(), children = [];
  const node = {
    id, attributes, listeners, children, dataset: {}, style: {}, innerHTML: "",
    textContent: "", disabled: false, open: false,
    setAttribute(name, value) { attributes.set(name, String(value)); },
    addEventListener(name, handler) { listeners.set(name, handler); },
    append(...items) { children.push(...items); },
    replaceChildren(...items) { children.length = 0; children.push(...items); },
    click() { listeners.get("click")?.({ currentTarget: node }); },
  };
  elements.set(id, node);
  return node;
}
function get(id) {
  assert.ok(ids.has(id), `known HTML id: ${id}`);
  return elements.get(id) || element(id);
}
const fakeDocument = {
  hidden: false,
  getElementById: get,
  createElement: tag => element(`generated-${tag}-${elements.size}`),
  createElementNS: (_namespace, tag) => element(`svg-${tag}-${elements.size}`),
  addEventListener() {},
};
const uiContext = vm.createContext({
  window: {}, document: fakeDocument,
  setInterval() { return 1; }, clearInterval() {},
});
vm.runInContext(fs.readFileSync(path.join(lesson, "images/hann-fft-data.js"), "utf8"), uiContext);
vm.runInContext(fs.readFileSync(path.join(lesson, "program-flow-map.js"), "utf8"), uiContext);
vm.runInContext(ui, uiContext);
function graphButtons() {
  const found = [];
  function walk(node) {
    if (node.dataset?.node) found.push(node);
    for (const child of node.children || []) walk(child);
  }
  walk(get("nodes"));
  return found;
}
function clickNode(id) {
  const button = graphButtons().find(item => item.dataset.node === id);
  assert.ok(button, `visible graph button: ${id}`);
  button.click();
}
assert.equal(graphButtons().length, 8);
const compactWidth = get("graph").style.width;
clickNode("detection");
assert.equal(graphButtons().filter(item => item.dataset.node === "detection").length, 1);
const detectionGroup = get("nodes").children.find(item => item.dataset.rootNode === "detection");
assert.ok(detectionGroup.className.includes("expanded-node"), "the detection node itself grows into a group");
assert.notEqual(get("graph").style.width, compactWidth, "neighbor positions reflow onto a wider graph");
assert.equal(get("nodes").children.length, 8, "no extra graph is appended below the eight root nodes");
clickNode("network");
const nestedNetwork = graphButtons().find(item => item.dataset.node === "network");
assert.ok(nestedNetwork.className.includes("expanded-node"), "a child grows inside its already-expanded parent");
assert.equal(get("nodes").children.length, 8, "nested expansion remains inside the original graph");
const expandedDetection = get("nodes").children.find(item => item.dataset.rootNode === "detection");
expandedDetection.children[0].click();
assert.equal(graphButtons().length, 8, "clicking the enlarged node header collapses it back to one compact node");
assert.equal(get("graph").style.width, compactWidth, "collapse restores the compact layout width");

console.log(`PASS: ${visited.size} reachable nodes, local assets, source links, and distinct thresholds.`);
