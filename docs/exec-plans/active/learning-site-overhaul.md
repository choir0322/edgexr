# Learning site overhaul for the spatial-awareness plan

## Purpose / big picture

The user builds EdgeXR with an LLM and does not read every line of code. The
`docs/learning/` pages are how they keep a deep understanding of what the program
computes, how it runs on the Pi's processor and how its models work. On
2026-11-16 they asked to improve every HTML page: cut what does not help that
understanding, add what is missing, and add more visuals and graphs, aligned with
the five-step [spatial-awareness plan](spatial-awareness-integration.md).

## Context and orientation

Seven existing pages, each self-contained and offline: program flow, worker
rates/storage, Hann/FFT motion, MobileNet-SSD architecture, basic tracker, ORB
scene memory and sparse reconstruction, plus a calibration target. The README
index had become a changelog. Missing topics: gyro orientation, pixel-to-direction
camera geometry, and a single place for measured processor evidence.

## Progress

- [x] 2026-11-16 Render and review all pages in headless Chrome on localhost.
- [x] Add a "Start here" hub, shared navigation and shared chart helpers.
- [x] New pages: orientation, camera geometry, processor evidence.
- [x] Targeted edits to existing pages (compute chart, IoU worked example,
  rotation-versus-translation, pixel-to-degree bridge, outdated text).
- [x] Rewrite README as a short index to the hub.
- [x] Hardware-free checks of page math against OpenCV; re-render screenshots.
- [x] Pipeline diagram reviewed; unchanged because no runtime code changed.

## Plan of work

Keep each page's existing visual language. New charts use only committed,
measured results; derived numbers (calculated, not measured) and illustrations
are labelled. Nothing private (snapshots, clouds, videos) is added.

## Validation and acceptance

`node scripts/check_learning_pages.js` checks the new pages' arithmetic against
values computed with OpenCV 4.11.0 on the Mac (undistortion, bearings) and the
tracker's IoU rule. `node scripts/check_sparse_learning.js` must still pass.
Every page is rendered in headless Chrome from a localhost server and inspected.

## Decision log

2026-11-16: Inject one navigation bar with a small script rather than rewriting
each page's header, so existing layouts stay intact. Use hand-written SVG charts,
not a charting library, because the pages must work offline from a clone.

## Surprises and discoveries

The camera-geometry page exposed a real limitation: the provisional lens model
cannot be inverted near three image corners (recorded in the
[spatial-awareness plan](spatial-awareness-integration.md)). The class integrating
the gyro is `RelativeCameraOrientation`; the program-map data had called it
`LiveOrientation` and was corrected. Headless Chrome on a localhost server renders
the pages for review; private Desktop snapshots do not load that way (expected).

## Outcomes and retrospective

2026-11-16: hub plus three new pages; all ten study pages share navigation.
Removed: the README changelog, the program map's "legacy" disclaimer and the
sparse page's outdated third-view "next step". Checks: `check_learning_pages.js`
and `check_sparse_learning.js` pass; 233 unit tests pass on the Mac (OpenCV
4.11.0 temp env); `git diff --check` clean. Every page was rendered at 1300 px and
inspected; phone-width rendering was spot-checked on the new pages. Not done:
automated visual regression, and Markdown guides were not rewritten.
