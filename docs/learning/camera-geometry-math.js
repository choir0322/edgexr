/* Pixel ↔ direction arithmetic for the camera-geometry page.
   Uses the committed provisional calibration (camera-calibration-screen-01,
   status needs_review) and OpenCV's five-coefficient lens model, so the page
   reproduces what cv.undistortPoints / cv.projectPoints compute. Coordinates:
   pixels are 1280×720 source pixels; normalized camera coordinates are x right,
   y down, at unit distance in front of the lens. Bearings are degrees:
   yaw positive to the right, pitch positive upward. Loaded by the browser page
   and by scripts/check_learning_pages.js (Node). */
(function (global) {
  "use strict";

  // benchmarks/results/camera-calibration-screen-01.json (2026-11-15 review).
  const CAL = {
    fx: 733.5631366263186, fy: 733.1623475650977,
    cx: 670.3268907651697, cy: 330.7822888690044,
    k1: 0.08617737055419306, k2: -0.06566823244223441,
    p1: 0.0005378139251996486, p2: -0.0002592694175888969,
    k3: -0.06962264582501754, width: 1280, height: 720,
  };
  const DEG = 180 / Math.PI;

  /**
   * Apply OpenCV's radial + tangential distortion to an ideal normalized point.
   * @param {number} x Ideal normalized x (unitless, X/Z).
   * @param {number} y Ideal normalized y (unitless, Y/Z).
   * @returns {number[]} Distorted normalized [x, y].
   */
  function distort(x, y) {
    const r2 = x * x + y * y;
    const radial = 1 + CAL.k1 * r2 + CAL.k2 * r2 * r2 + CAL.k3 * r2 * r2 * r2;
    return [x * radial + 2 * CAL.p1 * x * y + CAL.p2 * (r2 + 2 * x * x),
      y * radial + CAL.p1 * (r2 + 2 * y * y) + 2 * CAL.p2 * x * y];
  }

  /**
   * Project an ideal normalized point to a source pixel (cv.projectPoints).
   * @param {number} x Ideal normalized x.
   * @param {number} y Ideal normalized y.
   * @returns {number[]} Pixel [u, v] in 1280×720 coordinates.
   */
  function project(x, y) {
    const [xd, yd] = distort(x, y);
    return [CAL.fx * xd + CAL.cx, CAL.fy * yd + CAL.cy];
  }

  /**
   * Remove distortion from a pixel with OpenCV's fixed-point iteration.
   * cv.undistortPoints defaults to five iterations; the page uses the same.
   * @param {number} u Pixel column.
   * @param {number} v Pixel row.
   * @param {number} [iterations] Iteration count (default 5, as OpenCV).
   * @returns {number[]} Ideal normalized [x, y].
   */
  function undistort(u, v, iterations) {
    const x0 = (u - CAL.cx) / CAL.fx, y0 = (v - CAL.cy) / CAL.fy;
    let x = x0, y = y0;
    for (let i = 0; i < (iterations || 5); i++) {
      const r2 = x * x + y * y;
      const icdist = 1 / (1 + ((CAL.k3 * r2 + CAL.k2) * r2 + CAL.k1) * r2);
      const dx = 2 * CAL.p1 * x * y + CAL.p2 * (r2 + 2 * x * x);
      const dy = CAL.p1 * (r2 + 2 * y * y) + 2 * CAL.p2 * x * y;
      x = (x0 - dx) * icdist;
      y = (y0 - dy) * icdist;
    }
    return [x, y];
  }

  /**
   * Largest distorted radius the fitted lens model can produce. The polynomial
   * has a negative k3, so beyond an ideal radius it folds back; distorted points
   * farther out have no ideal point at all (the model is being extrapolated).
   * @returns {{ideal:number, distorted:number}} Fold radii (normalized units).
   */
  function foldRadius() {
    let best = { ideal: 0, distorted: 0 };
    for (let r = 0; r <= 1.6; r += 1e-5) {
      const r2 = r * r;
      const rd = r * (1 + CAL.k1 * r2 + CAL.k2 * r2 * r2 + CAL.k3 * r2 * r2 * r2);
      if (rd < best.distorted) break;
      best = { ideal: r, distorted: rd };
    }
    return best;
  }
  const FOLD = foldRadius();

  /**
   * Convert ideal normalized coordinates to a bearing.
   * @param {number} x Ideal normalized x.
   * @param {number} y Ideal normalized y.
   * @returns {{yaw:number, pitch:number}} Degrees; yaw right-positive, pitch up-positive.
   */
  function anglesOf(x, y) {
    return { yaw: Math.atan2(x, 1) * DEG, pitch: Math.atan2(-y, Math.hypot(x, 1)) * DEG };
  }

  /**
   * Inverse of anglesOf: the ideal normalized point for a bearing.
   * @param {number} yaw Degrees, right positive.
   * @param {number} pitch Degrees, up positive.
   * @returns {number[]} Ideal normalized [x, y].
   */
  function rayOf(yaw, pitch) {
    const a = yaw / DEG, b = pitch / DEG;
    return [Math.tan(a), -Math.tan(b) / Math.cos(a)];
  }

  /**
   * Full pixel → bearing conversion with a validity check.
   * @param {number} u Pixel column (1280-wide image).
   * @param {number} v Pixel row (720-high image).
   * @returns {{x:number,y:number,yaw:number,pitch:number,pinholeYaw:number,
   *   pinholePitch:number,distortedRadius:number,valid:boolean,roundTripPx:number}}
   *   Ideal coordinates, lens-corrected bearing, uncorrected bearing and validity.
   */
  function bearing(u, v) {
    const xd = (u - CAL.cx) / CAL.fx, yd = (v - CAL.cy) / CAL.fy;
    const [x, y] = undistort(u, v);
    const [pu, pv] = project(x, y);
    const roundTripPx = Math.hypot(pu - u, pv - v);
    const corrected = anglesOf(x, y), pinhole = anglesOf(xd, yd);
    const distortedRadius = Math.hypot(xd, yd);
    return { x, y, yaw: corrected.yaw, pitch: corrected.pitch,
      pinholeYaw: pinhole.yaw, pinholePitch: pinhole.pitch, distortedRadius,
      valid: distortedRadius < FOLD.distorted && roundTripPx < 0.5, roundTripPx };
  }

  /**
   * Bearing → pixel, or null when the direction is outside the usable lens model.
   * @param {number} yaw Degrees, right positive.
   * @param {number} pitch Degrees, up positive.
   * @returns {number[]|null} Pixel [u, v], possibly outside the image bounds.
   */
  function pixelOf(yaw, pitch) {
    if (Math.abs(yaw) >= 89 || Math.abs(pitch) >= 89) return null;
    const [x, y] = rayOf(yaw, pitch);
    if (Math.hypot(x, y) >= FOLD.ideal) return null;
    return project(x, y);
  }

  /**
   * Field of view along the principal row and column (lens-corrected).
   * @returns {{left:number,right:number,up:number,down:number,horizontal:number,vertical:number}} Degrees.
   */
  function fieldOfView() {
    const left = -bearing(0, CAL.cy).yaw, right = bearing(CAL.width - 1, CAL.cy).yaw;
    const up = bearing(CAL.cx, 0).pitch, down = -bearing(CAL.cx, CAL.height - 1).pitch;
    return { left, right, up, down, horizontal: left + right, vertical: up + down };
  }

  const api = { CAL, FOLD, distort, project, undistort, anglesOf, rayOf, bearing, pixelOf, fieldOfView };
  global.EdgeGeometry = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})(typeof window !== "undefined" ? window : globalThis);
