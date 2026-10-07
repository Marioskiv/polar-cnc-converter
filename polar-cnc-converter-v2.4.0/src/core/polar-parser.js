/*
 * Polar CNC — polar XZC G-code parser for the simulator.
 * Pure: no DOM, no globals.
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
  else { root.PolarCNC = root.PolarCNC || {}; root.PolarCNC.parser = api; }
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';
  // ============================================================
  // SECTION 2 - POLAR G-CODE PARSER
  //
  // Parses Polar G-code (X=R, C=Angle deg, Z=depth) into toolpath array.
  // Each entry: { r, theta, z, f, x3, y3, z3, segDist, segDurNom, type, lineNum }
  //
  // segDurNom (nominal segment duration in seconds):
  //   G1 + G94:  F = mm/min  =>  T = segDist / F * 60 seconds
  //   G0 rapid:  treated as 3000 mm/min (50 mm/s)
  //   fallback:  1 mm/s when F not yet known
  // ============================================================
  // Display-only speeds for animating RAPIDS (G0 has no programmed feed). The
  // machine's real velocities and accelerations are its controller's business
  // and are not modelled: G1 blocks take exactly the time the program commands
  // (inverse time), rapids take an indicative time. For exact timing run the
  // program through the controller's own simulation (see linuxcnc/vismach-sim).
  var RAPID_DISPLAY_MM  = 50;    // mm/s
  var RAPID_DISPLAY_DEG = 180;   // deg/s
  var DRAW_TOL = 0.05;           // mm: max gap between a drawn chord and the real path

  // profile: the converter's normalised options. Only the OUTPUT PROFILE is
  // used — rotaryAxis, invertC, invertX, xDiameter — to read the file back the
  // way the machine will execute it. Without a profile: X radius + C.
  function parsePolarGCode(text, profile) {
    var P = profile || {};
    var ROT = String(P.rotaryAxis || 'C').toUpperCase();
    var xScale = P.xDiameter ? 2 : 1;
    function toR(x) { return (P.invertX ? -x : x) / xScale; }        // machine X -> radius
    function toC(c) { return P.invertC ? -c : c; }                    // machine rotary -> part angle
    var drawTol = DRAW_TOL;

    var lines = text.split(/\r?\n/);
    function clean(raw) { return raw.replace(/\(.*?\)/g, '').replace(/;.*$/, '').trim().toUpperCase(); }
    function word(ln, k) {
      var m = ln.match(new RegExp(k + '\\s*([-+]?\\d*\\.?\\d+)'));
      return m ? parseFloat(m[1]) : null;
    }
    function gcodes(ln) {
      var out = {}, m, re = /\bG(\d+(?:\.\d*)?)/g;
      while ((m = re.exec(ln)) !== null) out[Math.round(parseFloat(m[1]) * 10) / 10] = true;
      return out;
    }

    // Pre-scan: highest programmed work Z (-> safe display height for retracts
    // and for the unknown start) and largest radius (-> display park position).
    var maxZ = null, maxAbsR = 0;
    for (var s0 = 0; s0 < lines.length; s0++) {
      var l0 = clean(lines[s0]); if (!l0) continue;
      var g0 = gcodes(l0);
      if (g0[53] || g0[28] || g0[30]) continue;
      var z0 = word(l0, 'Z'), x0 = word(l0, 'X');
      if (z0 !== null && (maxZ === null || z0 > maxZ)) maxZ = z0;
      if (x0 !== null && Math.abs(toR(x0)) > maxAbsR) maxAbsR = Math.abs(toR(x0));
    }
    var SAFE_Z = (maxZ === null ? 0 : maxZ) + 10;

    var result = [];
    // Unknown start: show the tool parked at the outer radius and the safe
    // height — where such machines usually start (at the edge, Z up), not the centre.
    var lastR = maxAbsR, lastC = 0, lastZ = SAFE_Z, lastF = 0;
    var modal = 'G1';
    var feedModal = 'G93';  // our output always opens with G93

    var toolD = null;   // diameter of the active tool, from "( polar-cnc tool: T.. D=.. )"
    for (var i = 0; i < lines.length; i++) {
      var tm = lines[i].match(/polar-cnc tool:\s*T\d+\s+D=([\d.]+)/i);
      if (tm) toolD = parseFloat(tm[1]);
      var ln = clean(lines[i]);
      if (!ln || ln === '%') continue;
      var g = gcodes(ln);
      if (g[93]) feedModal = 'G93';
      if (g[94]) feedModal = 'G94';

      var tR = lastR, tC = lastC, tZ = lastZ, type, machineRef = false, moved = false;
      var xw = word(ln, 'X'), cw = word(ln, ROT), zw = word(ln, 'Z'), fw = word(ln, 'F');
      if (xw !== null) xw = toR(xw);
      if (cw !== null) cw = toC(cw);

      if (g[53] || g[28] || g[30]) {
        // Machine-reference move: the simulator cannot know machine coordinates,
        // so show its PURPOSE — Z up to the safe height, X out to the park radius.
        machineRef = true;  type = 'G0';  modal = 'G0';
        var anyAxis = (xw !== null) || (zw !== null) || (word(ln, 'Y') !== null);
        if (zw !== null || ((g[28] || g[30]) && !anyAxis)) { tZ = SAFE_Z; moved = true; }
        if ((g[28] || g[30]) && (xw !== null || !anyAxis)) { tR = maxAbsR; moved = true; }
        if (!moved) continue;
      } else {
        if (g[0]) modal = 'G0';
        if (g[1]) modal = 'G1';
        if (xw !== null) { tR = xw; moved = true; }
        if (cw !== null) { tC = cw; moved = true; }
        if (zw !== null) { tZ = zw; moved = true; }
        if (fw !== null) lastF = fw;
        if (!moved) continue;
        type = modal;
      }

      var prev = result.length ? result[result.length - 1] : null;
      if (!prev) {
        result.push(makePoint(tR, tC, tZ, lastF, 0, 0.001, null, type, feedModal, i + 1, machineRef, toolD, P));
        lastR = tR; lastC = tC; lastZ = tZ;
        continue;
      }

      // Joint deltas and the time this block really takes.
      var dR = tR - lastR, dC = tC - lastC, dZ = tZ - lastZ;
      var cmdT = null, T;
      if (type === 'G1') {
        if (feedModal === 'G93') cmdT = lastF > 0 ? 60.0 / lastF : 0;
        else cmdT = lastF > 0 ? Math.sqrt(dR * dR + dZ * dZ) / lastF * 60 : 0;
        T = Math.max(cmdT, 0.001);
      } else {
        T = Math.max(Math.abs(dR) / RAPID_DISPLAY_MM, Math.abs(dZ) / RAPID_DISPLAY_MM,
                     Math.abs(dC) / RAPID_DISPLAY_DEG, 0.001);
      }

      // Subdivide in joint space only where a straight chord would visibly
      // differ from the real path: the sagitta r(1 - cos(dC/2)) shrinks with
      // the square of the number of pieces. Fine converter output (already
      // within CHORD_TOL) stays one point per block.
      var halfC = Math.min(Math.abs(dC), 180) * Math.PI / 360;
      var sag = Math.max(Math.abs(lastR), Math.abs(tR)) * (1 - Math.cos(halfC));
      var k = Math.min(360, Math.max(1, Math.ceil(Math.sqrt(sag / drawTol)), Math.ceil(Math.abs(dC) / 90)));
      for (var s = 1; s <= k; s++) {
        var fr = s / k;
        var pr = result[result.length - 1];
        var rr = lastR + dR * fr, cc = lastC + dC * fr, zz = lastZ + dZ * fr;
        var rad = cc * Math.PI / 180;
        var x3 = rr * Math.cos(rad), y3 = rr * Math.sin(rad);
        var sd = Math.sqrt((x3 - pr.x3) * (x3 - pr.x3) + (y3 - pr.y3) * (y3 - pr.y3) + (zz - pr.z3) * (zz - pr.z3));
        result.push(makePoint(rr, cc, zz, lastF, sd, T / k, cmdT === null ? null : cmdT / k,
                              type, feedModal, i + 1, machineRef, toolD, P));
      }
      lastR = tR; lastC = tC; lastZ = tZ;
    }
    return result;
  }

  function makePoint(r, c, z, f, segDist, segDurNom, durCmdSec, type, feedMode, lineNum, machineRef, toolD, P) {
    var rad = c * Math.PI / 180;
    var xm = ((P && P.invertX) ? -r : r) * ((P && P.xDiameter) ? 2 : 1);   // X as written to the file
    return {
      xm: xm,                    // machine X value (for travel-limit checks)
      toolD: toolD,              // active tool diameter, or null (use the setting)
      r: r, theta: c, z: z, f: f,
      x3: r * Math.cos(rad), y3: r * Math.sin(rad), z3: z,
      segDist: segDist,          // Cartesian length of this (sub)segment, for drawing
      segDurNom: segDurNom,      // seconds: commanded time (G1) or indicative time (G0)
      durCmdSec: durCmdSec,      // seconds the program COMMANDED (G1 only), for diagnostics
      type: type, feedMode: feedMode, lineNum: lineNum,
      machineRef: !!machineRef   // G53/G28/G30: displayed position is symbolic
    };
  }

  return { parsePolarGCode: parsePolarGCode };
});
