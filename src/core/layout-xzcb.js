/*
 * Polar CNC — machine layout "XZC + B": the XZC machine plus a router that
 * TILTS in the X-Z plane (the radial plane through the chuck axis), like the
 * nozzle of Joshua Bird's Core R-Theta printer. Letter B by ISO 841 / LinuxCNC
 * (rotation about a line parallel to Y); A only as a rename.
 * Pure: no DOM, no globals. Browser: PolarCNC.layoutXZCB   Node: require('./layout-xzcb.js')
 *
 * What it does (2.7.0): with a BALL-END tool it leans the router by the wanted
 * angle while it cuts, as far as the X travel and the B limits allow, and keeps
 * the ball CENTRE exactly on the CAM path - so the cut surface is unchanged
 * (a ball looks the same from every direction). Other tools stay at B 0.
 *
 * Geometry (machine frame: X = radius, Z = axial, B > 0 = tool tip leaning
 * toward the chuck axis, i.e. the top of the tool leaning outward):
 *   K = pivot -> tool holder face (setting) + tool length (tool table) - ball radius
 *     = distance from the tilt pivot to the BALL CENTRE.
 *   The machine X/Z read the tool tip when B = 0 (touch-off at B 0, G43 as usual).
 *   For a tool tip (r, z) - the CAM point - and a tilt B:
 *       X = r + K sin B,   Z = z + K (cos B - 1),   C unchanged.
 *   G43 H stays valid: it shifts Z by the tool length at every B alike, and the
 *   formula above already contains the tool length in K.
 *
 * How: the XZC layout converts the program exactly as for a machine without
 * tilt (its blocks are already checked against the CAM path); this layout takes
 * every block, picks B for its points, and splits it so that the extra error
 * from interpolating B in joint space stays under TILT_TOL:
 *   error of one piece <= K * dB^2 / 8  ->  dB <= sqrt(8 * TILT_TOL / K).
 *
 * Copyright (c) 2026 Marioskiv
 * https://github.com/Marioskiv/polar-cnc-converter
 * SPDX-License-Identifier: MIT
 */
(function (root, factory) {
  'use strict';
  var isNode = typeof module === 'object' && module.exports;
  var api = isNode ? factory(require('./layout-xzc.js')) : factory(root.PolarCNC.layoutXZC);
  if (isNode) module.exports = api;
  else { root.PolarCNC = root.PolarCNC || {}; root.PolarCNC.layoutXZCB = api; }
})(typeof self !== 'undefined' ? self : this, function (layoutXZC) {
  'use strict';
  var D2R = Math.PI / 180, R2D = 180 / Math.PI;

  // LinuxCNC tool.tbl lines: "T1 P1 X0 Y0 Z25.400 D6.000 ;6 mm ball". Only T, Z
  // (tool length) and D (diameter) are used, plus the word "ball" in the comment.
  function parseToolTable(text) {
    var tools = {};
    String(text || '').split(/\r?\n/).forEach(function (raw) {
      var semi = raw.indexOf(';');
      var code = (semi >= 0 ? raw.slice(0, semi) : raw).toUpperCase();
      var comment = semi >= 0 ? raw.slice(semi + 1) : '';
      var t = code.match(/\bT\s*(\d+)/);
      if (!t) return;
      var z = code.match(/\bZ\s*([-+]?\d*\.?\d+)/), d = code.match(/\bD\s*([-+]?\d*\.?\d+)/);
      tools[String(parseInt(t[1], 10))] = {
        len: z ? parseFloat(z[1]) : null,
        dia: d ? parseFloat(d[1]) : null,
        ball: /\bball/i.test(comment)
      };
    });
    return tools;
  }

  function create(O, out) {
    var TILT_TOL  = O.chordTol * 0.08;  // mm: extra error allowed from the tilt on a cut (block split)
    var RAPID_TOL = 0.5;                // mm: the same for rapids (as the XZC layout's rapids)
    var ROT = O.rotaryAxis, TILT = O.tiltAxis;
    if (ROT === TILT) throw new Error('The rotary axis and the tilt axis have the same letter (' + ROT + ').');

    // Machine limits mapped into the internal frame (X = radius on the tool side,
    // B > 0 = tip toward the chuck axis), exactly as the XZC layout maps X.
    var X_SCALE = O.xDiameter ? 2 : 1;
    var X_MIN = O.invertX ? -O.xMax / X_SCALE : O.xMin / X_SCALE;
    var X_MAX = O.invertX ? -O.xMin / X_SCALE : O.xMax / X_SCALE;
    var B_MIN = O.tiltMin === null ? null : (O.invertTilt ? -O.tiltMax : O.tiltMin);
    var B_MAX = O.tiltMax === null ? null : (O.invertTilt ? -O.tiltMin : O.tiltMax);
    var LEAN = O.tiltLean;
    var tools = parseToolTable(O.toolTable);
    var ballList = {};
    String(O.ballTools || '').split(/[\s,;]+/).forEach(function (t) { if (/^\d+$/.test(t)) ballList[String(parseInt(t, 10))] = true; });

    if (LEAN !== 0) {
      // Nothing about the tilt head is assumed: these must come from the machine.
      if (O.tiltPivot === null)
        throw new Error('Tilt layout: "pivot to tool holder" is not set (measure it on the machine).');
      if (B_MIN === null || B_MAX === null)
        throw new Error('Tilt layout: the tilt travel (min/max) is not set.');
      if (B_MIN > B_MAX) throw new Error('Tilt layout: tilt min is larger than tilt max.');
    }

    function wx(r) { var v = (O.invertX ? -r : r) * X_SCALE; return 'X' + (Math.abs(v) < 5e-5 ? 0 : v).toFixed(4); }
    function wc(c) { var v = O.invertC ? -c : c; return ROT + (Math.abs(v) < 5e-5 ? 0 : v).toFixed(4); }
    function wb(b) { var v = O.invertTilt ? -b : b; return TILT + (Math.abs(v) < 5e-5 ? 0 : v).toFixed(4); }
    function f4(v) { return (Math.abs(v) < 5e-5 ? 0 : v).toFixed(4); }

    // ---- the active tool -----------------------------------------------------
    var K = null;            // pivot -> ball centre (mm) of the active tool, null = no lean
    var leanOn = false;      // does the active tool lean?
    function setTool(dia, number) {
      inner.setTool(dia);
      var n = number === undefined || number === null ? null : String(parseInt(number, 10));
      var t = n !== null ? tools[n] : null;
      var isBall = n !== null && (ballList[n] || (t && t.ball));
      leanOn = false; K = null;
      if (LEAN === 0) return;
      if (!isBall) {
        out.push('( polar-cnc tilt: T' + n + ' is not a ball-end tool - ' + TILT + ' stays 0 )');
        return;
      }
      if (!t || t.len === null)
        throw new Error('Tilt layout: tool T' + n + ' has no length in the tool table (needed to tilt it).');
      var rad = (t.dia !== null ? t.dia : dia) / 2;
      K = O.tiltPivot + t.len - rad;
      if (!(K > 0)) throw new Error('Tilt layout: tool T' + n + ' gives a pivot-to-ball-centre distance <= 0.');
      leanOn = true;
      out.push('( polar-cnc tilt: T' + n + ' K=' + K.toFixed(4) + ' ball R' + rad.toFixed(4)
               + ' lean ' + LEAN.toFixed(1) + ' deg )');
    }

    // B for a point at radius r: the wanted lean, limited by the B travel and by
    // the X travel (X = r + K sin B must stay inside [X_MIN, X_MAX]).
    function bTarget(r) {
      if (!leanOn) return 0;
      var lo = B_MIN, hi = B_MAX;
      var sHi = (X_MAX - r) / K, sLo = (X_MIN - r) / K;
      if (sHi < 1) hi = Math.min(hi, Math.asin(Math.max(sHi, -1)) * R2D);
      if (sLo > -1) lo = Math.max(lo, Math.asin(Math.min(sLo, 1)) * R2D);
      if (lo > hi) return 0;                       // nothing fits: stay upright (X limit is reported)
      return Math.min(Math.max(LEAN, lo), hi);
    }

    // ---- state of the machine (tool tip r, C, z; tilt b) ---------------------
    var cur = { r: null, c: null, z: null, b: 0 };
    var lastB = 0;            // last B value written
    var xViolations = 0;

    function machineX(r, b) { return r + (K ? K * Math.sin(b * D2R) : 0); }
    function machineZ(z, b) { return z + (K ? K * (Math.cos(b * D2R) - 1) : 0); }

    function writeBlock(kind, r, c, z, b, F) {
      var X = machineX(r, b);
      if (X < X_MIN - 1e-6 || X > X_MAX + 1e-6) xViolations++;
      var line = kind + ' ' + wx(X) + ' ' + wc(c);
      if (z !== null) line += ' Z' + f4(machineZ(z, b));
      if (Math.abs(b - lastB) > 5e-5) { line += ' ' + wb(b); lastB = b; }
      if (F !== null) line += ' F' + F.toFixed(4);
      out.push(line);
    }

    // A block of the XZC layout from `cur` to (r1, c1, z1), split in joint space.
    function block(kind, r1, c1, z1, F, zOnly) {
      var r0 = cur.r, c0 = cur.c, z0 = cur.z, b0 = cur.b;
      if (r0 === null) r0 = r1;
      if (c0 === null) c0 = c1;
      if (z0 === null) z0 = z1;
      var lean = leanOn && z1 !== null;
      var off = lean ? b0 - bTarget(r0) : 0;       // a start that is not on the lean rule blends in
      function bAt(t) {
        var r = r0 + (r1 - r0) * t;
        return lean ? bTarget(r) + off * (1 - t) : b0 * (1 - t);
      }
      // a Z-only line of the XZC layout and no tilt change: write it as Z only, the same way
      if (zOnly && Math.abs(bAt(1) - b0) < 5e-5) {
        out.push(kind + ' Z' + f4(machineZ(z1, b0)) + (F === null ? '' : ' F' + F.toFixed(4)));
        cur = { r: r1, c: c1, z: z1, b: b0 };
        return;
      }
      var tol = kind === 'G0' ? RAPID_TOL : TILT_TOL;
      var dbMax = K ? Math.sqrt(8 * tol / K) * R2D : Infinity;   // degrees per piece
      var n = Math.max(1, Math.ceil(Math.abs(bAt(1) - b0) / dbMax));
      for (var guard = 0; guard < 12; guard++) {   // B may not be linear in t: check every piece
        var ok = true, prev = b0;
        for (var i = 1; i <= n && ok; i++) { var bi = bAt(i / n); if (Math.abs(bi - prev) > dbMax) ok = false; prev = bi; }
        if (ok) break;
        n *= 2;
      }
      for (var k = 1; k <= n; k++) {
        var t = k / n;
        var z = (z0 === null || z1 === null) ? null : z0 + (z1 - z0) * t;
        writeBlock(kind, r0 + (r1 - r0) * t, c0 + (c1 - c0) * t, z, bAt(t), F === null ? null : F * n);
      }
      cur = { r: r1, c: c1, z: z1, b: bAt(1) };
    }

    // Turn B to bNew keeping the tool tip where it is (only rapids, above the part).
    function reorient(bNew) {
      if (Math.abs(cur.b - bNew) < 5e-5) return;
      if (cur.z === null || cur.r === null) {      // Z unknown (after a machine retract): just turn
        out.push('G0 ' + wb(bNew));
        lastB = bNew; cur.b = bNew; return;
      }
      var b0 = cur.b, dbMax = K ? Math.sqrt(8 * RAPID_TOL / K) * R2D : Infinity;
      var n = Math.max(1, Math.ceil(Math.abs(bNew - b0) / dbMax));
      for (var k = 1; k <= n; k++) writeBlock('G0', cur.r, cur.c, cur.z, b0 + (bNew - b0) * k / n, null);
      cur.b = bNew;
    }

    // ---- the XZC layout writes into this proxy; its motion lines are tilted ----
    var proxy = { push: function () { for (var i = 0; i < arguments.length; i++) line(arguments[i]); } };
    function word(s, k) { var m = s.match(new RegExp('\\b' + k + '(-?\\d+\\.?\\d*)')); return m ? parseFloat(m[1]) : null; }
    function line(s) {
      // the XZC layout's own X-travel warning counts the tool tip; ours counts the machine X
      if (/^\( WARNING: \d+ moves exceed configured X travel/.test(s)) return;
      var m = /^(G[01]) /.exec(s);
      if (!m) { out.push(s); return; }
      var kind = m[1];
      var r = word(s, 'X'), c = word(s, 'C'), z = word(s, 'Z'), F = word(s, 'F');
      if (r === null && c === null) {             // Z only
        if (z === null) { out.push(s); return; }
        if (cur.r === null) { out.push(kind + ' Z' + f4(z) + (F !== null ? ' F' + F.toFixed(4) : '')); cur.z = z; return; }
        block(kind, cur.r, cur.c, z, kind === 'G1' ? F : null, true);
        return;
      }
      var r1 = r !== null ? r : cur.r, c1 = c !== null ? c : cur.c;
      var z1 = z !== null ? z : cur.z;
      if (z1 === null) {                           // Z still unknown: only upright moves
        if (Math.abs(cur.b) > 5e-5) reorient(0);
        writeBlock(kind, r1, c1, null, 0, kind === 'G1' ? F : null);
        cur = { r: r1, c: c1, z: null, b: 0 };
        return;
      }
      block(kind, r1, c1, z1, kind === 'G1' ? F : null);
    }

    var innerO = Object.assign({}, O, {
      rotaryAxis: 'C', invertC: false, invertX: false, xDiameter: false,
      xMin: X_MIN, xMax: X_MAX                   // the XZC layout works in the internal frame
    });
    var inner = layoutXZC.create(innerO, proxy);

    function header() {
      var h = inner.header();
      return [
        '( Polar G-code - G93 inverse time | radial X, rotary ' + ROT + ', axial Z, tilt ' + TILT + ' in the X-Z plane )',
        '( Output profile: rotary ' + ROT + (O.invertC ? ' inverted' : '') + ', X ' + (O.xDiameter ? 'diameter' : 'radius')
          + (O.invertX ? ' inverted' : '') + ', tilt ' + TILT + (O.invertTilt ? ' inverted' : '')
          + '  |  X travel [' + O.xMin.toFixed(1) + ', ' + O.xMax.toFixed(1) + ']'
          + (B_MIN !== null ? '  ' + TILT + ' travel [' + O.tiltMin.toFixed(1) + ', ' + O.tiltMax.toFixed(1) + ']' : '') + ' )',
        h[2],
        '( Tilt: ball-end tools lean ' + LEAN.toFixed(1) + ' deg where X and ' + TILT + ' allow; '
          + (O.tiltPivot !== null ? 'pivot to tool holder ' + O.tiltPivot.toFixed(2) + ' mm' : 'pivot not set') + ' )',
        '( ' + TILT + ' must be 0 at the start: home it. Touch off Z with ' + TILT + ' 0. )'
      ];
    }

    return {
      header: header,
      move: function (ev) { return inner.move(ev); },
      flush: function (feed) { inner.flush(feed); },
      setTool: setTool,
      // before a tool change the router goes upright, keeping the tip in place
      text: function (s) {
        if (/\bM0*6(?![.\d])/i.test(String(s).replace(/\([^)]*\)/g, '').replace(/;.*$/, ''))) reorient(0);
        out.push(s);
        if (/^G53 G0 Z/.test(s)) {
          // machine retract (written by the input stage): Z is now unknown;
          // the router goes upright up there, the tip radius becomes the X it stood at
          cur.z = null;
          if (Math.abs(cur.b) > 5e-5) {
            var X = machineX(cur.r, cur.b);
            out.push('G0 ' + wb(0) + '  ( upright after the retract )');
            lastB = 0; cur.b = 0; cur.r = X;
          }
        }
      },
      beforeEnd: function () { reorient(0); },
      finish: function () {
        inner.finish();
        reorient(0);
        if (xViolations > 0)
          out.push('( WARNING: ' + xViolations + ' moves exceed configured X travel ['
                   + X_MIN.toFixed(1) + ', ' + X_MAX.toFixed(1) + '] mm — check machine limits! )');
      }
    };
  }
  return { create: create, parseToolTable: parseToolTable };
});
