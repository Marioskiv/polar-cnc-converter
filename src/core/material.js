/*
 * Polar CNC — material removal (depth map) for face machining.
 * Pure: no DOM, no globals. Browser: PolarCNC.material   Node: require('./material.js')
 *
 * Face milling on a polar (XZC) machine is 2.5D: every point of the face has one
 * height. So instead of solid (CSG) booleans — what Kiri:Moto does for full
 * 3D — a square grid of heights in the WORKPIECE frame is enough, and fast.
 * The grid is fixed to the part, so in the 3D view it turns with the chuck.
 *
 * Each toolpath segment is walked in small steps and the cutter footprint
 * (flat end mill: a disk of the tool radius) is stamped: every cell under the
 * disk gets height = min(height, tool tip Z). A RAPID (G0) step that lowers any
 * cell has cut material at rapid speed — a collision — and is recorded.
 *
 * Copyright (c) 2026 Marioskiv
 * https://github.com/Marioskiv/polar-cnc-converter
 * SPDX-License-Identifier: MIT
 */
(function (root, factory) {
  'use strict';
  var isNode = typeof module === 'object' && module.exports;
  var api = factory();
  if (isNode) module.exports = api;
  else { root.PolarCNC = root.PolarCNC || {}; root.PolarCNC.material = api; }
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  var EPS = 0.01;   // mm: changes smaller than this are not counted as cutting

  // cfg: { stockR, surfaceZ, toolDia, maxCells (grid side, default 300) }
  function createMaterial(cfg) {
    var R = Math.max(cfg.stockR || 1, 1);
    var surfaceZ = cfg.surfaceZ || 0;
    var defaultToolR = Math.max((cfg.toolDia || 6) / 2, 0.05);
    var n = Math.min(cfg.maxCells || 300, Math.max(20, Math.ceil(2 * R / 0.2)));
    var cell = 2 * R / n;
    var x0 = -R + cell / 2;                       // centre of cell (0, *)

    var z = new Float32Array(n * n);
    var inside = new Uint8Array(n * n);
    var rapidHit = new Uint8Array(n * n);
    for (var j = 0; j < n; j++) {
      for (var i = 0; i < n; i++) {
        var cx = x0 + i * cell, cy = x0 + j * cell;
        inside[j * n + i] = (cx * cx + cy * cy <= R * R) ? 1 : 0;
      }
    }

    var done = -1;     // index of the last toolpath point already stamped
    var stats;
    var changed = false;

    function reset() {
      z.fill(surfaceZ);
      rapidHit.fill(0);
      done = -1;
      changed = true;
      stats = { cutCells: 0, rapidCutCells: 0, rapidLines: [], minZ: surfaceZ };
    }

    function stamp(x, y, tz, isRapid, lineNum, toolR) {
      if (tz >= surfaceZ - EPS) return;
      var i0 = Math.max(0, Math.floor((x - toolR - x0) / cell)),
          i1 = Math.min(n - 1, Math.ceil((x + toolR - x0) / cell)),
          j0 = Math.max(0, Math.floor((y - toolR - x0) / cell)),
          j1 = Math.min(n - 1, Math.ceil((y + toolR - x0) / cell));
      var r2 = toolR * toolR, hitRapid = false;
      for (var j = j0; j <= j1; j++) {
        var dy = x0 + j * cell - y;
        for (var i = i0; i <= i1; i++) {
          var k = j * n + i;
          if (!inside[k]) continue;
          var dx = x0 + i * cell - x;
          if (dx * dx + dy * dy > r2) continue;
          if (tz < z[k] - EPS) {
            if (z[k] >= surfaceZ - EPS) stats.cutCells++;
            if (isRapid) {
              if (!rapidHit[k]) { rapidHit[k] = 1; stats.rapidCutCells++; }
              hitRapid = true;
            }
            z[k] = tz;
            changed = true;
            if (tz < stats.minZ) stats.minZ = tz;
          }
        }
      }
      if (hitRapid && stats.rapidLines.indexOf(lineNum) < 0 && stats.rapidLines.length < 50)
        stats.rapidLines.push(lineNum);
    }

    // Walk one segment between two toolpath points (workpiece frame x3/y3/z3).
    // The cutter is the ACTIVE tool of that segment when the program states it
    // (point.toolD, from the converter's tool-change comments), else the default.
    function stampSegment(a, b) {
      var tr = (b.toolD > 0) ? b.toolD / 2 : defaultToolR;
      if (Math.max(a.z3, b.z3) >= surfaceZ - EPS && Math.min(a.z3, b.z3) >= surfaceZ - EPS) return;
      var isRapid = b.type === 'G0';
      var len = Math.sqrt((b.x3 - a.x3) * (b.x3 - a.x3) + (b.y3 - a.y3) * (b.y3 - a.y3) + (b.z3 - a.z3) * (b.z3 - a.z3));
      var steps = Math.max(1, Math.ceil(len / (cell * 0.5)));
      for (var s = 1; s <= steps; s++) {
        var t = s / steps;
        stamp(a.x3 + (b.x3 - a.x3) * t, a.y3 + (b.y3 - a.y3) * t, a.z3 + (b.z3 - a.z3) * t, isRapid, b.lineNum, tr);
      }
    }

    // Stamp every segment up to point index idx. Going backwards restarts.
    // Returns true if any cell changed (the renderer only redraws then).
    function advanceTo(points, idx) {
      changed = false;
      idx = Math.min(idx, points.length - 1);
      if (idx < done) reset();
      if (done < 0) done = 0;
      for (var p = done + 1; p <= idx; p++) stampSegment(points[p - 1], points[p]);
      if (idx > done) done = idx;
      return changed;
    }

    reset();
    return {
      n: n, cell: cell, x0: x0, surfaceZ: surfaceZ, toolR: defaultToolR,
      z: z, inside: inside, rapidHit: rapidHit,
      reset: reset, advanceTo: advanceTo,
      stats: function () { return stats; }
    };
  }

  return { createMaterial: createMaterial };
});
