/* Shared navigation for every EdgeXR learning page.
   One ordered list defines the study path. Each page includes this script once;
   it inserts a top bar and previous/next links without touching page layouts.
   Styles are namespaced (edgexr-nav-*) so they cannot restyle page content. */
(function () {
  "use strict";

  // Study order: the whole program first, then each component, then the processor.
  const PAGES = [
    { href: "index.html", label: "Start here" },
    { href: "program-flow-explorer.html", label: "Program map" },
    { href: "hann-fft-explorer.html", label: "Image motion" },
    { href: "detection-architecture.html", label: "Detector model" },
    { href: "basic-tracker.html", label: "Tracker IDs" },
    { href: "orientation-explorer.html", label: "Head orientation" },
    { href: "camera-geometry.html", label: "Pixel → direction" },
    { href: "orb-scene-explorer.html", label: "Scene memory" },
    { href: "sparse-scene-01.html", label: "3D from two views" },
    { href: "edgexr-worker-rates.html", label: "Workers & storage" },
    { href: "processor-evidence.html", label: "Processor evidence" },
  ];

  const STYLE = `
.edgexr-nav{position:relative;z-index:50;background:#0c1118;border-bottom:1px solid #2b394a;font:13px/1.4 system-ui,-apple-system,"Segoe UI",sans-serif}
.edgexr-nav-inner{display:flex;align-items:center;gap:2px 4px;max-width:1440px;margin:auto;padding:7px 16px;overflow-x:auto;scrollbar-width:thin}
@media (min-width:900px){.edgexr-nav-inner{flex-wrap:wrap;overflow-x:visible}}
.edgexr-nav-brand{color:#65d8bb;font-weight:650;letter-spacing:.08em;font-size:11px;text-decoration:none;white-space:nowrap;margin-right:8px}
.edgexr-nav a.edgexr-nav-link{color:#98a8bb;text-decoration:none;white-space:nowrap;padding:4px 8px;border-radius:6px;font-size:12.5px}
.edgexr-nav a.edgexr-nav-link:hover{color:#e5edf6;background:#192636}
.edgexr-nav a.edgexr-nav-link[aria-current=page]{color:#0c1118;background:#65d8bb;font-weight:600}
.edgexr-nav a:focus-visible,.edgexr-nav-steps a:focus-visible{outline:2px solid #65d8bb;outline-offset:2px}
.edgexr-nav-num{opacity:.6;margin-right:4px;font-variant-numeric:tabular-nums}
.edgexr-nav-steps{display:flex;justify-content:space-between;gap:12px;max-width:1380px;margin:30px auto 40px;padding:0 30px;font:14px/1.4 system-ui,-apple-system,"Segoe UI",sans-serif}
.edgexr-nav-steps a{display:block;flex:0 1 48%;padding:12px 16px;border:1px solid #2b394a;border-radius:10px;color:#e5edf6;text-decoration:none;background:#121b26}
.edgexr-nav-steps a:hover{border-color:#65d8bb}
.edgexr-nav-steps small{display:block;color:#98a8bb;font-size:11px;letter-spacing:.08em;text-transform:uppercase;margin-bottom:3px}
.edgexr-nav-steps .next{text-align:right;margin-left:auto}
@media (max-width:600px){.edgexr-nav-steps{padding:0 16px;flex-direction:column}.edgexr-nav-steps a{flex-basis:auto}}
@media print{.edgexr-nav,.edgexr-nav-steps{display:none}}`;

  /**
   * Name of the current page file, treating a folder URL as the hub.
   * @returns {string} File name such as "camera-geometry.html".
   */
  function currentFile() {
    const last = window.location.pathname.split("/").pop();
    return last && last.endsWith(".html") ? last : "index.html";
  }

  /**
   * Build one previous/next link.
   * @param {{href:string,label:string}} page Destination page.
   * @param {string} kind "previous" or "next"; also the CSS class.
   * @returns {HTMLAnchorElement} Link element.
   */
  function stepLink(page, kind) {
    const link = document.createElement("a");
    link.href = page.href;
    link.className = kind;
    link.innerHTML = `<small>${kind === "next" ? "Next →" : "← Previous"}</small>${page.label}`;
    return link;
  }

  /**
   * Insert the top bar and the previous/next strip once the page has parsed.
   * @returns {void}
   */
  function install() {
    if (document.querySelector(".edgexr-nav")) return;
    const style = document.createElement("style");
    style.textContent = STYLE;
    document.head.appendChild(style);

    // Top bar: every page in study order, current page highlighted.
    const file = currentFile();
    const index = PAGES.findIndex((page) => page.href === file);
    const nav = document.createElement("nav");
    nav.className = "edgexr-nav";
    nav.setAttribute("aria-label", "EdgeXR learning pages");
    const inner = document.createElement("div");
    inner.className = "edgexr-nav-inner";
    inner.innerHTML = `<a class="edgexr-nav-brand" href="index.html">EDGEXR · LEARN</a>` +
      PAGES.slice(1).map((page, i) =>
        `<a class="edgexr-nav-link" href="${page.href}"${page.href === file ? ' aria-current="page"' : ""}>` +
        `<span class="edgexr-nav-num">${i + 1}</span>${page.label}</a>`).join("");
    nav.appendChild(inner);
    document.body.insertBefore(nav, document.body.firstChild);
    const active = inner.querySelector("[aria-current=page]");
    if (active) active.scrollIntoView({ block: "nearest", inline: "center" });

    // Bottom strip: neighbours in the same order, so the path can be read end to end.
    if (index < 0) return;
    const steps = document.createElement("div");
    steps.className = "edgexr-nav-steps";
    if (index > 0) steps.appendChild(stepLink(PAGES[index - 1], "previous"));
    if (index < PAGES.length - 1) steps.appendChild(stepLink(PAGES[index + 1], "next"));
    document.body.appendChild(steps);
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", install);
  else install();
})();
