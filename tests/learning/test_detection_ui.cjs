/** Offline event smoke test; DOM/canvas doubles do not verify browser layout. */
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const folder = path.resolve(__dirname, "../../docs/learning");
const elements = new Map(),
  nodes = [];
let drawingCalls = 0,
  timerCallback;

/** Minimal visible-element behavior used by the lesson. @param {string} tag @param {object} attrs @returns {object} */
function element(tag, attrs = {}) {
  const classes = new Set(),
    events = new Map();
  const e = {
    tag,
    attrs,
    dataset: {},
    children: [],
    connected: true,
    value: attrs.value || "",
    textContent: "",
    hidden: false,
    style: {},
    classList: {
      toggle(name, on) {
        if (on) classes.add(name);
        else classes.delete(name);
      },
      contains(name) {
        return classes.has(name);
      },
    },
    setAttribute(name, value) {
      this.attrs[name] = String(value);
    },
    removeAttribute(name) {
      delete this.attrs[name];
    },
    addEventListener(name, handler) {
      events.set(name, handler);
    },
    dispatch(name, event = {}) {
      assert.ok(events.has(name), `${attrs.id || tag} event ${name}`);
      events.get(name)({ currentTarget: e, ...event });
    },
    replaceChildren() {
      this.children.forEach((child) => {
        child.connected = false;
      });
      this.children = [];
    },
    getBoundingClientRect() {
      return { left: 0, top: 0, width: 1000, height: 570 };
    },
    getContext() {
      return new Proxy(
        {},
        {
          get(_target, key) {
            return (...args) => {
              drawingCalls += 1;
              for (const value of args) {
                if (typeof value === "number")
                  assert.ok(
                    Number.isFinite(value),
                    `Nonfinite canvas ${String(key)}`,
                  );
              }
            };
          },
          set() {
            return true;
          },
        },
      );
    },
  };
  for (const [name, value] of Object.entries(attrs))
    if (name.startsWith("data-")) e.dataset[name.slice(5)] = value;
  Object.defineProperty(e, "innerHTML", {
    set(html) {
      this.replaceChildren();
      this.children = parse(html);
    },
    get() {
      return "";
    },
  });
  if (attrs.id) elements.set(attrs.id, e);
  nodes.push(e);
  return e;
}

/** Parse only the static tags/attributes needed to bind actual event code. @param {string} html @returns {object[]} */
function parse(html) {
  const result = [];
  for (const match of html.matchAll(/<([a-z][\w-]*)\b([^>]*)>/gi)) {
    const attrs = {};
    for (const a of match[2].matchAll(/([\w-]+)="([^"]*)"/g))
      attrs[a[1]] = a[2];
    result.push(element(match[1], attrs));
  }
  return result;
}
parse(
  fs.readFileSync(path.join(folder, "detection-architecture.html"), "utf8"),
);
elements.get("speed").value = "500";
const document = {
  getElementById(id) {
    assert.ok(elements.has(id), `Element exists: ${id}`);
    return elements.get(id);
  },
  querySelectorAll(selector) {
    const name = selector.match(/^\[([^\]]+)\]$/)[1];
    return nodes.filter((e) => e.connected && Object.hasOwn(e.attrs, name));
  },
};
class FakeImage {
  set src(value) {
    this.path = value;
    if (this.onload) this.onload();
  }
}
const context = vm.createContext({
  window: {
    DetectionMath: require("../../docs/learning/detection-math.js"),
    setInterval(callback) {
      timerCallback = callback;
      return 1;
    },
    clearInterval() {
      timerCallback = undefined;
    },
  },
  document,
  Image: FakeImage,
});
vm.runInContext(
  fs.readFileSync(path.join(folder, "images/detection-lesson-data.js"), "utf8"),
  context,
);
vm.runInContext(
  fs.readFileSync(path.join(folder, "detection-architecture.js"), "utf8"),
  context,
);
const get = (id) => document.getElementById(id);
const go = (i) =>
  document
    .querySelectorAll("[data-scene]")
    .find((e) => Number(e.dataset.scene) === i)
    .dispatch("click");
const input = (id, value) => {
  get(id).value = String(value);
  get(id).dispatch("input");
};
assert.match(get("status").textContent, /Ready/);
for (let i = 0; i < 11; i += 1) {
  go(i);
  assert.equal(get("lesson").hidden, false);
  assert.ok(get("scene-title").textContent.length > 10);
  get("step").dispatch("click");
  get("play").dispatch("click");
  assert.ok(timerCallback);
  timerCallback();
  get("play").dispatch("click");
  get("reset").dispatch("click");
}
go(0);
get("split-source").dispatch("click");
assert.ok(get("channel-stack").classList.contains("expanded"));
input("sample-index", 35);
go(1);
input("filter", 2);
input("bias", 5);
get("padding").value = "1";
get("padding").dispatch("change");
get("stride").value = "2";
get("stride").dispatch("change");
get("finish-cell").dispatch("click");
go(3);
get("channel-count").value = "32";
get("channel-count").dispatch("change");
input("point-output", 63);
input("point-channel", 31);
input("point-weight", 2);
input("point-position", 15);
go(5);
input("bridge-head", 5);
go(6);
input("anchor-head", 5);
input("anchor-shape", 5);
get("all-centers").dispatch("click");
get("diagram").dispatch("click", { clientX: 300, clientY: 300 });
go(7);
input("offset-0", 4);
input("offset-2", -4);
get("class-id").value = "0";
get("class-id").dispatch("change");
input("class-logit", 8);
go(8);
input("nms-stage", 3);
input("nms-iou", 0);
input("app-score", 1);
input("candidate", 6);
go(10);
get("saved-chair").dispatch("click");
assert.ok(drawingCalls > 1000);
console.log(
  "PASS: all 11 scenes, image split, arithmetic controls, 32-channel view, SSD selectors and playback execute. Browser layout remains a separate check.",
);
