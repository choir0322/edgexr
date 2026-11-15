/* Hardware-free checks of the learning pages' arithmetic, not visual QA.
   Usage (repository root): node scripts/check_learning_pages.js
   Compares docs/learning page math with reference values produced by the real
   implementations on 2026-11-16:
   - camera geometry: OpenCV 4.11.0 cv.undistortPoints (default 5 iterations) and
     cv.projectPoints via scripts/learning_geometry_fixtures.py;
   - tracker: vision.basic_tracker.BasicTracker / box_iou;
   - orientation: spatial.live_orientation.RelativeCameraOrientation.add().
   Exit code 0 when every check passes; an assertion error otherwise. */
'use strict';
const path = require('node:path');
const assert = require('node:assert/strict');
const root = path.resolve(__dirname, '../docs/learning');
const G = require(path.join(root, 'camera-geometry-math.js'));
const O = require(path.join(root, 'orientation-math.js'));
const T = require(path.join(root, 'tracker-example.js'));

/**
 * Assert two numbers agree within a tolerance, with a readable message.
 * @param {number} actual Value computed by the page code.
 * @param {number} expected Reference value.
 * @param {number} tol Absolute tolerance.
 * @param {string} what Description for the failure message.
 * @returns {void}
 */
function close(actual, expected, tol, what) {
  assert.ok(Math.abs(actual - expected) <= tol, `${what}: ${actual} vs ${expected} (tolerance ${tol})`);
}

// Camera geometry: pixel -> ideal ray -> bearing, against OpenCV.
const PIXEL_TO_BEARING = [
  [[640, 360], [-0.04132668053819164, 0.03983601024792671], -2.366497746314249, -2.279285565326406],
  [[900, 300], [0.31076680222648256, -0.041722850136901996], 17.26351008787543, 2.281642391557194],
  [[100, 600], [-0.7767541862790299, 0.36655410087652635], -37.838423633614035, -16.14487521583366],
  [[1279, 330.78], [0.8251108968842117, -0.00036712913737855965], 39.52641175613413, 0.016224914707212233],
  [[0, 330.78], [-0.9320276044269549, -0.00047967693240070163], -42.98505687301505, 0.02010501992052212],
  [[670.33, 0], [5.490352338390326e-05, -0.44527483130819107], 0.003145740167134644, 24.002206496551988],
  [[670.33, 719], [7.309616138191748e-05, 0.5201640465863928], 0.00418810153833195, -27.481829663346673],
  [[1100, 650], [0.5757103791478846, 0.4275780427072821], 29.929480876739152, -20.332504010193393],
  [[300, 120], [-0.4955119755374304, -0.28240807902130005], -26.35896621042835, 14.20038774566787],
];
for (const [[u, v], [x, y], yaw, pitch] of PIXEL_TO_BEARING) {
  const b = G.bearing(u, v);
  close(b.x, x, 1e-9, `ideal x at (${u}, ${v})`);
  close(b.y, y, 1e-9, `ideal y at (${u}, ${v})`);
  close(b.yaw, yaw, 1e-7, `yaw at (${u}, ${v})`);
  close(b.pitch, pitch, 1e-7, `pitch at (${u}, ${v})`);
  assert.ok(b.valid, `(${u}, ${v}) should be inside the invertible region`);
}
const BEARING_TO_PIXEL = [
  [0, 0, [670.3268907651697, 330.7822888690044]], [15, 0, [867.988127824363, 330.81059868854345]],
  [-30, 10, [238.478620966289, 178.7453972063517]], [35, -20, [1186.7585633853853, 658.6656621844057]],
  [-5, 22, [605.3363917279195, 29.89123127059244]],
];
for (const [yaw, pitch, [u, v]] of BEARING_TO_PIXEL) {
  const p = G.pixelOf(yaw, pitch);
  close(p[0], u, 1e-6, `u for yaw ${yaw}, pitch ${pitch}`);
  close(p[1], v, 1e-6, `v for yaw ${yaw}, pitch ${pitch}`);
}
// Fold of the fitted polynomial and corner validity (converged OpenCV: corners fail to invert).
close(G.FOLD.ideal, 1.0946, 2e-4, 'fold ideal radius');
close(G.FOLD.distorted, 0.9734, 2e-4, 'fold distorted radius');
assert.equal(G.bearing(0, 0).valid, false, 'top-left corner must be flagged');
assert.equal(G.bearing(0, 719).valid, false, 'bottom-left corner must be flagged');
assert.equal(G.bearing(1279, 0).valid, true, 'top-right corner is inside the fold');
const fov = G.fieldOfView();
close(fov.left, 42.987, 0.01, 'left half field of view (converged OpenCV)');
close(fov.right, 39.526, 0.01, 'right half field of view');
close(fov.up, 24.002, 0.01, 'upper half field of view');
close(fov.down, 27.482, 0.01, 'lower half field of view');

// Tracker: IoU and greedy matching against vision.basic_tracker.
const IOU = [
  [[180, 140, 480, 700], [230, 150, 530, 712], 0.6906077348066298],
  [[820, 380, 900, 600], [835, 385, 915, 605], 0.6584216725559482],
  [[820, 380, 900, 600], [955, 385, 1035, 605], 0.0],
  [[0, 0, 10, 10], [5, 5, 15, 15], 0.14285714285714285],
];
for (const [a, b, expected] of IOU) close(T.iou(a, b), expected, 1e-12, `IoU ${a} / ${b}`);
const tracks = [
  { id: 1, cls: 'person', box: [180, 140, 480, 700], missed: 0 },
  { id: 2, cls: 'bottle', box: [820, 380, 900, 600], missed: 0 },
  { id: 3, cls: 'chair', box: [960, 300, 1250, 700], missed: 1 },
];
// Python BasicTracker on the same history: shift 0 -> IDs [1, 2, 4]; shift 120 -> [1, 4, 5], #2 kept.
for (const [shift, ids, kept] of [[0, [1, 2, 4], [1, 2]], [120, [1, 4, 5], [1, 2]]]) {
  const dets = [
    { name: 'A', cls: 'person', box: [230, 150, 530, 712] },
    { name: 'B', cls: 'bottle', box: [835 + shift, 385, 915 + shift, 605] },
    { name: 'C', cls: 'bottle', box: [600, 420, 660, 580] },
  ];
  const r = T.match(tracks, dets, 4);
  assert.deepEqual(dets.map((d) => r.assigned[d.name] || r.newIds[d.name]), ids, `IDs at shift ${shift}`);
  assert.deepEqual(r.forgotten, [3], `chair forgotten at shift ${shift}`);
  const survivors = tracks.map((t) => t.id).filter((id) => !r.forgotten.includes(id));
  assert.deepEqual(survivors, kept, `remembered old IDs at shift ${shift}`);
}

// Orientation: quaternion composition against RelativeCameraOrientation.add().
const SEQUENCE = [[0.0, [0, 30, 0]], [0.0129, [0, 30, 0]], [0.0258, [20, 0, 5]], [0.0387, [20, 0, 5]]];
let q = [1, 0, 0, 0];
for (let i = 1; i < SEQUENCE.length; i++) q = O.step(q, SEQUENCE[i - 1][1], SEQUENCE[i][1], SEQUENCE[i][0] - SEQUENCE[i - 1][0]);
[0.9999811096288128, 0.0033809712701819462, 0.005065771097565272, 0.0008290850290702453]
  .forEach((c, i) => close(q[i], c, 1e-12, `quaternion component ${i}`));
// Simulation sanity: the true path returns to zero; dense sampling integrates it closely.
close(O.trueAngle(O.CAPTURE_S, 0.03), 0, 1e-9, 'true path returns to 0°');
close(O.trueAngle(6.5, 0.03), -20, 1e-9, 'true path reaches −20° after the first leg');
assert.ok(Math.abs(O.simulate({ sleepMs: 0, stepMs: 30, phase: 0.3, biasDps: 0, noiseDps: 0 }).error) < 0.05, 'dense sampling stays accurate');
const read50 = O.simulate({ sleepMs: 50, stepMs: 30, phase: 0, biasDps: 0, noiseDps: 0 });
assert.equal(read50.samples.length, 407, '50 ms pause gives the measured 407 reads per 21.5 s window');

console.log(`PASS: ${PIXEL_TO_BEARING.length} pixel→bearing and ${BEARING_TO_PIXEL.length} bearing→pixel cases vs OpenCV, fold/FOV, ` +
  `${IOU.length} IoU and 2 matching cases vs BasicTracker, quaternion vs RelativeCameraOrientation, simulation sanity. Visual layout not checked.`);
