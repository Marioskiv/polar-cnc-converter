/*
 * Polar CNC — geometry helpers.
 * Pure functions, no DOM, no globals. Usable in the browser (PolarCNC.geometry)
 * and in Node (require('./geometry.js')).
 *
 * Copyright (c) 2026 Marioskiv
 * https://github.com/Marioskiv/polar-cnc-converter
 * SPDX-License-Identifier: MIT
 */
(function (root, factory) {
  'use strict';
  var isNode = typeof module === 'object' && module.exports;
  var api = isNode ? factory() : factory();
  if (isNode) module.exports = api;
  else { root.PolarCNC = root.PolarCNC || {}; root.PolarCNC.geometry = api; }
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  // Signed angular difference in (-180, +180].
  function angdiff(a0, a1) {
    var d = a1 - a0;
    while (d >  180) d -= 360;
    while (d < -180) d += 360;
    // NOTE: an exact 180 deg difference returns +180 (the `d > 180` test excludes
    // 180 itself), so the rotation direction for a perfect reversal is
    // deterministic but arbitrary. Left as-is: either direction is equally valid.
    return d;
  }

  // ─── nearestEquivalentAngle ──────────────────────────────────────────────────
  // FIX 2 helper. Returns the value rotationally equivalent to `target`
  // (i.e. target + k*360 for integer k) that lies closest to `current`.
  // Used to return to a saved orientation after the centre pocket fill without
  // unwinding the revolutions the fill accumulated: C = 20 and C = 3620 put the
  // part in exactly the same place, but only one of them is 10 turns away.
  function nearestEquivalentAngle(target, current) {
    return target + Math.round((current - target) / 360) * 360;
  }

  // Linearize G2/G3 arc into [{x, y, z, arcSegLen}, ...] points.
  // Supports I/J-format and R-format arcs, including full circles.
  // chordTol: chordal deviation tolerance (mm) — drives adaptive segment density.
  //   Segment length = 2*sqrt(2*r*chordTol), clamped to [0.02, 2.0] mm.
  function linearizeArc(x0, y0, z0, x1, y1, z1, I, J, R, isG2, chordTol) {
    var tol = (chordTol > 0) ? chordTol : 0.01;
    var cx, cy, r;

    if (R !== null && R !== undefined) {
      var dx = x1 - x0, dy = y1 - y0;
      var dist = Math.hypot(dx, dy);
      var absR = Math.abs(R);
      if (dist < 1e-9) return [{ x: x1, y: y1, z: z1, arcSegLen: 0 }];
      if (absR < dist / 2 - 1e-9) return [{ x: x1, y: y1, z: z1, arcSegLen: Math.hypot(dx, dy) }];
      var h  = Math.sqrt(Math.max(0, absR * absR - (dist / 2) * (dist / 2)));
      var mx = (x0 + x1) / 2, my = (y0 + y1) / 2;
      var px = -dy / dist, py = dx / dist;
      // RS274/NGC: R>0 = minor arc (<= 180 deg), R<0 = major arc (> 180 deg)
      var sign = (R > 0) ? (isG2 ? -1 : 1) : (isG2 ? 1 : -1);
      cx = mx + px * h * sign;
      cy = my + py * h * sign;
      r  = absR;
    } else {
      cx = x0 + (I || 0);
      cy = y0 + (J || 0);
      r  = Math.hypot(x0 - cx, y0 - cy);
      if (r < 1e-9) return [{ x: x1, y: y1, z: z1, arcSegLen: Math.hypot(x1 - x0, y1 - y0) }];
    }

    // Adaptive segment length based on arc radius and chordal tolerance
    var arcAdaptSeg = Math.min(Math.max(2 * Math.sqrt(2 * r * tol), 0.02), 2.0);

    var a0a = Math.atan2(y0 - cy, x0 - cx);
    var a1a = Math.atan2(y1 - cy, x1 - cx);
    var isFullCircle = Math.hypot(x1 - x0, y1 - y0) < 1e-9;
    var sweep;
    if (isFullCircle) {
      sweep = isG2 ? -2 * Math.PI : 2 * Math.PI;
    } else if (isG2) {
      sweep = a1a - a0a;
      if (sweep > 1e-9) sweep -= 2 * Math.PI;
    } else {
      sweep = a1a - a0a;
      if (sweep < -1e-9) sweep += 2 * Math.PI;
    }

    var arcLen = Math.abs(sweep) * r;
    if (arcLen < 1e-9) return [];
    var n = Math.max(1, Math.ceil(arcLen / arcAdaptSeg));
    var arcSegLen = arcLen / n;
    var pts = [];
    for (var i = 1; i <= n; i++) {
      var t = i / n;
      var a = a0a + sweep * t;
      pts.push({ x: cx + r * Math.cos(a), y: cy + r * Math.sin(a),
                 z: z0 + (z1 - z0) * t, arcSegLen: arcSegLen });
    }
    return pts;
  }
  return { angdiff: angdiff, nearestEquivalentAngle: nearestEquivalentAngle, linearizeArc: linearizeArc };
});
