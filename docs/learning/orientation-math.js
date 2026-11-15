/* Gyro-integration arithmetic for orientation-explorer.html.
   The simulation is ILLUSTRATIVE: it models the real servo test schedule
   (0 → −20 → +20 → 0°, 1° commands every 0.2 s from 2.5 s, 21.5 s capture)
   as short motion bursts, samples them like the IMU polling thread and
   integrates with the same trapezoid rule as RelativeCameraOrientation.add()
   in spatial/live_orientation.py.
   Quaternion helpers follow that file's (w, x, y, z) convention.
   Loaded by the page and by scripts/check_learning_pages.js (Node). */
(function (global) {
  "use strict";
  const STEP_DEG = 1, STEP_INTERVAL_S = 0.2, START_S = 2.5, CAPTURE_S = 21.5;
  // Measured read rates imply ~2.9 ms per loop beyond the sleep:
  // 77.3–77.5 reads/s at 10 ms and 18.9 reads/s at 50 ms (three-policy runs).
  const READ_OVERHEAD_MS = 2.9;

  /**
   * Commanded 1° steps of the pan test, in time order.
   * @returns {Array<{t:number, delta:number}>} Start time (s) and signed degrees.
   */
  function commandedSteps() {
    const steps = [];
    let t = START_S;
    const legs = [[-1, 20], [1, 40], [-1, 20]];
    for (const [sign, count] of legs) for (let i = 0; i < count; i++) { steps.push({ t, delta: sign * STEP_DEG }); t += STEP_INTERVAL_S; }
    return steps;
  }
  const STEPS = commandedSteps();

  /**
   * True angular rate when each step is a raised-cosine burst lasting T seconds.
   * @param {number} t Time in seconds.
   * @param {number} T Burst duration in seconds (> 0).
   * @returns {number} Rate in degrees per second.
   */
  function trueRate(t, T) {
    let rate = 0;
    for (const s of STEPS) {
      const u = (t - s.t) / T;
      if (u > 0 && u < 1) rate += (s.delta / T) * (1 - Math.cos(2 * Math.PI * u));
    }
    return rate;
  }

  /**
   * True head angle: completed steps plus the completed part of an active burst.
   * @param {number} t Time in seconds.
   * @param {number} T Burst duration in seconds.
   * @returns {number} Angle in degrees.
   */
  function trueAngle(t, T) {
    let angle = 0;
    for (const s of STEPS) {
      const u = (t - s.t) / T;
      if (u >= 1) angle += s.delta;
      else if (u > 0) angle += s.delta * (u - Math.sin(2 * Math.PI * u) / (2 * Math.PI));
    }
    return angle;
  }

  /**
   * Deterministic pseudo-random normal numbers (so every reload matches).
   * @param {number} seed Integer seed.
   * @returns {function():number} Generator of standard normal values.
   */
  function gaussian(seed) {
    let s = seed >>> 0 || 1;
    /** One uniform in (0, 1). @returns {number} Value. */
    function uniform() { s = (s * 1664525 + 1013904223) >>> 0; return (s + 0.5) / 4294967296; }
    return () => Math.sqrt(-2 * Math.log(uniform())) * Math.cos(2 * Math.PI * uniform());
  }

  /**
   * Sample the burst motion like the polling thread and integrate it.
   * @param {{sleepMs:number, stepMs:number, phase:number, biasDps:number, noiseDps:number}} o
   *   Sleep after each read (ms), burst duration (ms), sampling phase (0–1 of a period),
   *   residual gyro bias left after calibration (°/s) and noise standard deviation (°/s).
   * @returns {{period:number, readsPerSecond:number, samples:number[][], estimate:number[][],
   *   finalEstimate:number, finalTruth:number, error:number}} Samples [t, rate], running
   *   estimate [t, angle] and the end-of-capture error in degrees.
   */
  function simulate(o) {
    const T = Math.max(0.005, o.stepMs / 1000);
    const period = (o.sleepMs + READ_OVERHEAD_MS) / 1000;
    const noise = gaussian(12345);
    const samples = [], estimate = [];
    let angle = 0, last = null;
    for (let t = (o.phase || 0) * period; t <= CAPTURE_S; t += period) {
      const rate = trueRate(t, T) + (o.biasDps || 0) + (o.noiseDps ? o.noiseDps * noise() : 0);
      // Trapezoid rule: average of adjacent rates times the interval (live_orientation.py).
      if (last) angle += (last[1] + rate) / 2 * (t - last[0]);
      last = [t, rate];
      samples.push(last);
      estimate.push([t, angle]);
    }
    const finalTruth = trueAngle(CAPTURE_S, T);
    return { period, readsPerSecond: 1 / period, samples, estimate,
      finalEstimate: angle, finalTruth, error: angle - finalTruth };
  }

  /**
   * Hamilton product of two quaternions (w, x, y, z).
   * @param {number[]} a Left quaternion.
   * @param {number[]} b Right quaternion.
   * @returns {number[]} a ⊗ b.
   */
  function multiply(a, b) {
    const [aw, ax, ay, az] = a, [bw, bx, by, bz] = b;
    return [aw * bw - ax * bx - ay * by - az * bz,
      aw * bx + ax * bw + ay * bz - az * by,
      aw * by - ax * bz + ay * bw + az * bx,
      aw * bz + ax * by - ay * bx + az * bw];
  }

  /**
   * Quaternion for a rotation vector given in degrees (axis × angle).
   * @param {number[]} v Rotation vector in degrees.
   * @returns {number[]} Unit quaternion (w, x, y, z).
   */
  function fromRotationVector(v) {
    const r = v.map((d) => d * Math.PI / 180), angle = Math.hypot(...r);
    if (!angle) return [1, 0, 0, 0];
    const f = Math.sin(angle / 2) / angle;
    return [Math.cos(angle / 2), r[0] * f, r[1] * f, r[2] * f];
  }

  /**
   * One live_orientation.py update: average two camera-axis rates over dt,
   * compose the small rotation on the right (body frame) and renormalize.
   * @param {number[]} q Current quaternion.
   * @param {number[]} oldRate Previous camera rates (°/s).
   * @param {number[]} newRate Current camera rates (°/s).
   * @param {number} dt Seconds between the two reads.
   * @returns {number[]} Updated unit quaternion.
   */
  function step(q, oldRate, newRate, dt) {
    const turn = oldRate.map((r, i) => (r + newRate[i]) / 2 * dt);
    const next = multiply(q, fromRotationVector(turn));
    const n = Math.hypot(...next);
    return next.map((c) => c / n);
  }

  /**
   * Rotate a vector by a unit quaternion (body-to-reference frame).
   * @param {number[]} q Unit quaternion.
   * @param {number[]} v Vector [x, y, z].
   * @returns {number[]} Rotated vector.
   */
  function rotate(q, v) {
    const p = multiply(multiply(q, [0, ...v]), [q[0], -q[1], -q[2], -q[3]]);
    return p.slice(1);
  }

  const api = { STEPS, START_S, CAPTURE_S, READ_OVERHEAD_MS, trueRate, trueAngle, simulate, multiply, fromRotationVector, step, rotate };
  global.EdgeOrientation = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})(typeof window !== "undefined" ? window : globalThis);
