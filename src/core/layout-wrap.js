/*
 * Polar CNC — machine layout "Wrap": milling the OUTSIDE of a cylinder held in the chuck, with
 * the router turned so that its nose looks at the cylinder (radial), on the same machine axes:
 * X = radius of the tool tip from the chuck axis, Z = along the chuck axis, C = the chuck.
 * Pure: no DOM, no globals. Browser: PolarCNC.layoutWrap   Node: require('./layout-wrap.js')
 *
 * Input: an ordinary 3-axis program of the cylinder's surface UNROLLED flat (any CAM):
 *   CAM X = along the part            -> machine Z
 *   CAM Y = round the part, in mm of  -> C = -Y / R0 (degrees), R0 = the wrap radius
 *           arc length at radius R0          (2.22.0: minus - see wc() below)
 *   CAM Z = height above the surface  -> X = R0 + Z (Z0 on the surface at R0, negative = into it)
 * This is what Fanuc's cylindrical interpolation (G07.1) does inside the control; LinuxCNC has
 * no such mode, so the converter writes the joint moves.
 *
 * Every map is linear, so one straight CAM move is exactly one straight joint move: LinuxCNC
 * interpolates X, Z and C linearly, which IS the unrolled straight line wrapped on the
 * cylinder. Lines are therefore written as one block, whatever their length. Arcs (in the
 * unrolled XY plane, G17) are split into lines within the chord tolerance first.
 *
 * Feed: G93 inverse time. The time of a block is the TRUE length the tool tip travels (along
 * the part, round it at its real radius R0 + Z, and in depth) divided by the CAM feed, so the
 * tip moves at the CAM feed on the real surface. (Under G94 LinuxCNC would apply the feed to
 * X and Z only and let C follow: wrong whenever C moves together with them.)
 *
 * Copyright (c) 2026 Marioskiv
 * https://github.com/Marioskiv/polar-cnc-converter
 * SPDX-License-Identifier: MIT
 */
(function (root, factory) {
  'use strict';
  var isNode = typeof module === 'object' && module.exports;
  var api = isNode ? factory(require('./geometry.js'), require('./layout-xzc.js'))
                   : factory(root.PolarCNC.geometry, root.PolarCNC.layoutXZC);
  if (isNode) module.exports = api;
  else { root.PolarCNC = root.PolarCNC || {}; root.PolarCNC.layoutWrap = api; }
})(typeof self !== 'undefined' ? self : this, function (geometry, layoutXZC) {
  'use strict';
  var linearizeArc = geometry.linearizeArc;
  var MIN_TIME = 0.00001;      // G93 floor [min], as in the XZC layout (guards F = 1/0 only)

  function create(O, out) {
    var R0 = O.wrapRadius;
    var ROT = O.rotaryAxis;
    var X_SCALE = O.xDiameter ? 2 : 1;
    var DEG = 180 / Math.PI;
    var cLo = Infinity, cHi = -Infinity;
    var xLo = Infinity, xHi = -Infinity;
    var srcLine = null;
    var camFeed = null;
    // the last position written, in CAM terms (u along, v round, w height); null = unknown
    var last = { u: null, v: null, w: null };

    function radius(w) { return R0 + w; }
    function wx(w) {
      var r = radius(w);
      if (r <= 0)
        throw new Error('Line ' + srcLine + ': Z ' + w.toFixed(3) + ' would put the tool past the chuck axis '
                        + '(wrap radius ' + R0 + ' mm). Z of the unrolled program is the height above the '
                        + 'surface at the wrap radius.');
      if (r < xLo) xLo = r;
      if (r > xHi) xHi = r;
      // 2.15.1: refused, not only reported - LinuxCNC refuses the file at load anyway
      if (O.xMax !== null && r * X_SCALE > O.xMax + 1e-9)
        throw new Error('Line ' + srcLine + ': X ' + (r * X_SCALE).toFixed(3) + ' goes past X Axis Max '
                        + O.xMax + ' (wrap radius ' + R0 + ' + Z ' + w.toFixed(3) + '). Lower the safe '
                        + 'height of the program or check the wrap radius.');
      var v = (O.invertX ? -r : r) * X_SCALE;
      return 'X' + (Math.abs(v) < 5e-5 ? 0 : v).toFixed(4);
    }
    // FIX 2.22.0: C = -Y / R0 (was +Y / R0). Seen from outside the bar, the unrolled drawing must
    // read the right way round: CAM X (along) x CAM Y (round) must point OUT of the part, as CAM
    // X x Y points up (+Z, towards the viewer) in the CAM. Along the part is +Z of the machine; at
    // C 0 the surface faces +X; with the converter's convention (x = r cos C, y = r sin C, proven
    // by the F test on the real machine) +C moves the point towards +Y, and Z x Y = -X points INTO
    // the part: +Y / R0 wrote every drawing mirrored. -Y / R0 gives Z x (-Y) = +X, out. The FreeCAD
    // Polar Wrap operation (program.unroll) writes Y = -angle x R0 to match, so its parts do not
    // change. Only an asymmetric test cut on the machine proves it, as with the F test.
    function wc(v) {
      var c = -v / R0 * DEG;
      if (O.invertC) c = -c;
      if (c < cLo) cLo = c;
      if (c > cHi) cHi = c;
      return ROT + (Math.abs(c) < 5e-5 ? 0 : c).toFixed(4);
    }
    function wz(u) { return 'Z' + (Math.abs(u) < 5e-5 ? 0 : u).toFixed(4); }

    // True length of the tip's path for one straight joint move: along the part (du), in depth
    // (dr) and round it at the radius it is at (r dTheta, r changing linearly). Simpson's rule;
    // exact for the common cases (dr = 0 or dTheta = 0).
    function tipLength(a, b) {
      var du = b.u - a.u, dw = b.w - a.w, dth = (b.v - a.v) / R0;
      var f = function (t) {
        var r = radius(a.w + dw * t);
        return Math.sqrt(du * du + dw * dw + r * r * dth * dth);
      };
      return (f(0) + 4 * f(0.25) + 2 * f(0.5) + 4 * f(0.75) + f(1)) / 12;
    }

    function feedMove(p) {
      var L = tipLength(last, p);
      if (L < 1e-9) { last = p; return; }
      var T = Math.max(L / camFeed, MIN_TIME);
      out.push('G1 ' + wx(p.w) + ' ' + wz(p.u) + ' ' + wc(p.v) + ' F' + (1 / T).toFixed(4));
      last = p;
    }

    function header() {
      return [
        '( Wrap G-code - G93 inverse time | router radial, X = radius, Z along the part, '
          + ROT + ' round it )',
        '( Unrolled program: CAM X -> Z, CAM Y -> ' + ROT + ' = -Y / ' + R0 + ' mm, CAM Z -> X = '
          + R0 + ' + Z )',
        '( Output profile: rotary ' + ROT + (O.invertC ? ' inverted' : '') + ', X '
          + (O.xDiameter ? 'diameter' : 'radius') + (O.invertX ? ' inverted' : '')
          + (O.xMax !== null ? '  |  X max ' + O.xMax.toFixed(1) : '') + ' )',
        '( Tool length lies along X: give it in the X column of the tool table - G43 applies it )'
      ];
    }

    function move(ev) {
      var w = ev.words;
      srcLine = ev.line === undefined ? null : ev.line;
      camFeed = ev.feed;
      var to = { u: ev.to.x, v: ev.to.y, w: ev.to.z };
      if (ev.kind === 'G0') {
        // only what the line states (the input knows nothing else yet at the program start).
        // A rapid that changes the radius AND moves along or round the part is split, so the
        // tool never sweeps across the part: going out, X first; going in, X last. (A radius not
        // known yet counts as "going out" when the target is outside the wrap radius.)
        // FIX 2.22.0: that last sentence was dead code - with the radius unknown the test below
        // compared with NaN and was always false, so the FIRST rapid of a program (and the first
        // after a tool change) moved X, Z and C in one block, dragging the tip across the part
        // if it started at or near the surface. An unknown radius now always splits.
        var along = [];
        if ('X' in w) along.push(wz(to.u));
        if ('Y' in w) along.push(wc(to.v));
        if ('Z' in w && along.length && (last.w === null || Math.abs(to.w - last.w) > 1e-9)) {
          var outward = last.w === null ? to.w >= 0 : to.w > last.w;
          if (outward) { out.push('G0 ' + wx(to.w)); out.push('G0 ' + along.join(' ')); }
          else { out.push('G0 ' + along.join(' ')); out.push('G0 ' + wx(to.w)); }
        } else {
          var words = [];
          if ('Z' in w) words.push(wx(to.w));
          Array.prototype.push.apply(words, along);
          if (words.length) out.push('G0 ' + words.join(' '));
        }
        if ('X' in w) last.u = to.u;
        if ('Y' in w) last.v = to.v;
        if ('Z' in w) last.w = to.w;
        return null;
      }
      // the input stage has made sure X, Y and Z are known before a cutting move
      last = { u: ev.from.x, v: ev.from.y, w: ev.from.z };
      if (ev.kind === 'G1') {
        feedMove(to);
      } else {
        // 2.22.0: chords at half the tolerance, as the XZC layout (DECISIONS: "chord at tol/2")
        var pts = linearizeArc(ev.from.x, ev.from.y, ev.from.z, ev.to.x, ev.to.y, ev.to.z,
                               ev.arc.I, ev.arc.J, ev.arc.R, ev.kind === 'G2', O.chordTol * 0.5);
        for (var i = 0; i < pts.length; i++) feedMove({ u: pts[i].x, v: pts[i].y, w: pts[i].z });
      }
      return null;
    }

    function finish() {
      var rep = [];
      if (xHi >= xLo)
        rep.push('( X from ' + (xLo * X_SCALE).toFixed(3) + ' to ' + (xHi * X_SCALE).toFixed(3)
                 + (O.xDiameter ? ' (diameter)' : ' (radius)') + ' )');
      if (cHi >= cLo) {
        rep.push('( ' + ROT + ' range ' + cLo.toFixed(1) + ' .. ' + cHi.toFixed(1) + ' deg = '
                 + ((cHi - cLo) / 360).toFixed(2) + ' turns )');
        if (Math.max(Math.abs(cLo), Math.abs(cHi)) > 99999)
          rep.push('( !! ' + ROT + ' goes past 99999 deg - raise [AXIS_' + ROT + '] MIN_LIMIT/MAX_LIMIT first )');
        // 2.15.0 (review): the tool offsets of an UNROLLED program are right only at R0
        rep.push('( Note: in an unrolled program the CAM offsets the cutter at the wrap radius; below it a )');
        rep.push('( radial cutter covers more: walls along the part come out wider. Keep depths small, )');
        rep.push('( or use the FreeCAD Polar Wrap operation, which works on the real part. )');
      }
      layoutXZC.insertReport(out, rep);
    }

    return {
      header: header,
      move: move,
      flush: function (feed) { camFeed = feed; },
      // FIX 2.22.0: a tool change may move the machine (TOOL_CHANGE_POSITION), as the input stage
      // already says: forget the position, so the next rapid is split like the first one.
      setTool: function () { last = { u: null, v: null, w: null }; },
      finish: finish
    };
  }
  return { create: create };
});
