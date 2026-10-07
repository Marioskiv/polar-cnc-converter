/*
 * Polar CNC — machine layout "XZC": the polar transform for a lathe-type machine
 * (radial X, rotary C on the spindle axis, axial Z). Receives the motion of a
 * Cartesian program as events from gcode-input.js and writes polar G93 blocks.
 * Pure: no DOM, no globals. Browser: PolarCNC.layoutXZC   Node: require('./layout-xzc.js')
 *
 * Copyright (c) 2026 Marioskiv
 * https://github.com/Marioskiv/polar-cnc-converter
 * SPDX-License-Identifier: MIT
 */
(function (root, factory) {
  'use strict';
  var isNode = typeof module === 'object' && module.exports;
  var api = isNode ? factory(require('./geometry.js')) : factory(root.PolarCNC.geometry);
  if (isNode) module.exports = api;
  else { root.PolarCNC = root.PolarCNC || {}; root.PolarCNC.layoutXZC = api; }
})(typeof self !== 'undefined' ? self : this, function (geometry) {
  'use strict';
  var angdiff = geometry.angdiff;
  var nearestEquivalentAngle = geometry.nearestEquivalentAngle;
  var linearizeArc = geometry.linearizeArc;

  // RESTRUCTURED 2.6.0: this is the polar part of the old single converter
  // function, moved here unchanged. O = normalised options, out = the output
  // line array (shared with the input stage, so everything stays in order).
  function create(O, out) {
    // Read live values from Converter Settings panel; fall back to safe defaults
    var CHORD_TOL   = O.chordTol;
    var THRESHOLD   = O.threshold;
    // G94 OUTPUT REMOVED (2026-09-11). Output is now always G93 inverse-time.
    //
    // Why: LinuxCNC applies a G94 F word only to the LINEAR distance.
    //   interp_find.cc find_straight_length(): "If any of the X, Y, or Z axes
    //   move ... any rotary axis motion is ignored."
    //   tc.c pmLine9Target(): returns xyz.tmag first, abc.tmag only if xyz is zero.
    // The converter's feed physics is computed over the full 3D path INCLUDING
    // the C arc (dist3D = sqrt(dR^2 + (dC_rad*rAvg)^2 + dZ^2)). On a mostly
    // tangential move those two differ enormously — e.g. r=50, dC=5deg, dR=0.1mm
    // gives a 4.36mm arc but LinuxCNC sees only 0.1mm, so a programmed 500mm/min
    // ran at roughly 4700mm/min of real surface feed once getStraightVelocity's
    // 90deg/s axis cap was applied. Feed control was effectively defeated.
    //
    // G93 has no such problem: LinuxCNC computes rate = length * F, so with
    // F = 1/T the move takes exactly T whatever length metric is used.
    // A "fixed" G94 (F = linDist/T) would be mathematically equivalent but adds
    // a rounding hazard: a block that is nearly all arc has linDist ~ 0, so F
    // rounds to 0.000 at 3 decimals. Not worth keeping a redundant, riskier path.
    // 'signed': always freeze C for the whole line and let X sweep negative for any
    //           line that comes within THRESHOLD of the centre (no abrupt C rotation).
    // 'auto':   smart choice — Signed X only for genuine diameter-like crossings
    //           (enters one side, exits the far side) AND only if it stays inside
    //           the configured X travel limits; everything else falls back to Fill.
    // 'fill':   legacy behaviour — concentric-circle pocket fill at first entry per Z.
    var CENTER_CROSS_MODE = O.centerMode;
    // Physical X (radial) axis travel limits, in mm. Signed-X output for a given
    // line is only accepted when its full excursion stays inside [X_MIN, X_MAX];
    // otherwise the converter falls back to Pocket Fill for that line so the
    // machine is never asked to move beyond its real travel.
    // X_MIN/X_MAX are entered in MACHINE terms (what is written to the file).
    // Internally X is always a radius counting away from the centre on the
    // tool's side, so map the machine limits into that frame once, here.
    var X_SCALE = O.xDiameter ? 2 : 1;
    var X_MIN_LIMIT = O.invertX ? -O.xMax / X_SCALE : O.xMin / X_SCALE;
    var X_MAX_LIMIT = O.invertX ? -O.xMin / X_SCALE : O.xMax / X_SCALE;
    var ROT = O.rotaryAxis;
    // Every X and rotary word is written through these two functions, so the
    // output profile (letter, direction, radius/diameter) is applied in ONE place.
    function wx(r) { var v = (O.invertX ? -r : r) * X_SCALE; return 'X' + (Math.abs(v) < 5e-5 ? 0 : v).toFixed(4); }
    function wc(c) { var v = O.invertC ? -c : c; return ROT + (Math.abs(v) < 5e-5 ? 0 : v).toFixed(4); }
    // Minimum entry/exit angular separation (degrees) for a centre crossing to be
    // considered "diameter-like" in Auto mode. Close to 180° = truly radial cut;
    // lower values would accept more oblique crossings at the cost of larger
    // geometric approximation error (C is frozen for the whole line either way).
    var AUTO_ANGLE_THRESH = 150.0;
    // Running count of emitted moves whose X fell outside [X_MIN_LIMIT, X_MAX_LIMIT] —
    // reported to the user at the end of conversion (see xLimitViolations below).
    var xLimitViolations = 0;


    // Effective C-axis velocity limit: minimum of programmed limit and physical motor limit
    // RAPID_TOL: path tolerance for SEGMENTED RAPIDS, deliberately much looser
    // than CHORD_TOL. A rapid removes no material, so only the topology of the
    // path matters (does it stay clear of the part?), not its accuracy. 0.5 mm
    // keeps the spiral bulge small enough to be safe while costing few blocks.
    var RAPID_TOL = 0.5;
    // FIX (2026-09-12): MAX_DEG_PER_SEG used to be declared INSIDE the G1 branch.
    // JavaScript hoists the name but not the value, so until the first G1 line
    // had run it was undefined. The segmented-rapid code divides by it, which
    // gave nRapid = NaN, the emit loop never ran, and the rapid was DROPPED
    // silently. A program with two XY rapids before its first G1 therefore
    // plunged at the wrong place. Declared here, once, for every branch.
    var MAX_DEG_PER_SEG = 45.0;   // max C rotation per block (degrees)
    // CHANGED 2.5.0: was 0.001 min (0.06 s, F_g93 <= 1000). That floor silently
    // SLOWED THE CUT on every short block: measured on a circle r20, F1500 ran at
    // ~844 mm/min, F3000 at ~856. Machine dynamics are the controller's job
    // (DECISIONS.md), and LinuxCNC cannot run a block in less than one servo
    // period (1 ms) anyway. The floor is now 0.6 ms - below that - so it only
    // guards against F = 1/0 (a block with no length) and never changes motion.
    var MIN_TIME    = 0.00001; // G93 floor [min] (0.6 ms) -> max F_g93 = 100000
    var MAX_F_G93   = 1 / MIN_TIME;
    var MIN_SEG      = 0.02;  // absolute floor (mm)
    var MAX_SEG_G    = 5.0;   // segment length cap (mm) — larger = fewer segments at big R
    // Minimum 3D distance between two consecutively emitted G1 points.
    // When the input CAM file has many fine segments near centre (e.g. < 0.05 mm each),
    // those segments all hit the MIN_TIME floor and produce many indistinguishable blocks.
    // Deferring emission until accumulated dist3D ≥ MIN_EMIT_DIST produces fewer, longer
    // blocks whose F_g93 is calculated from the real physics-based feed — the simulator
    // correctly shows the tool decelerating near centre.  Path shape is preserved because
    // all intermediate points lie on the already-chord-limited Cartesian path.
    var MIN_EMIT_DIST = 0.15;  // mm

    // Centre-zone fill: angular stepover (mm, measured at freeze radius) and Z retract clearance.
    // FIX 5: cutter diameter drives the centre pocket fill.
    // TOOLS (2026-10-02): the cutter matters, so it follows the program. The
    // diameter of the ACTIVE tool (after T.. M6) is taken from the CAM's tool
    // comments when present — e.g. Fusion writes "(T2 D=3. CR=0. ...)" — and
    // otherwise from the Tool Diameter setting. The pocket fill uses it, and a
    // machine-readable "( polar-cnc tool: T2 D=3.0000 )" comment is written
    // after each tool change so the simulator's material map uses it too.
    var TOOL_DIA  = O.toolDia;                 // diameter of the ACTIVE tool (mm)
    var AUTO_STEP = O.autoStepover;
    var CENTER_STEP_SETTING = O.centerStep;    // 0 = fill disabled
    function centerStepover() {
      // Auto mode: 50% of the ACTIVE cutter's diameter. 0 still disables the fill.
      return (AUTO_STEP && CENTER_STEP_SETTING > 0) ? TOOL_DIA * 0.5 : CENTER_STEP_SETTING;
    }
    var CENTER_RETRACT  = O.centerRetract;
    // Tracks which Z depths have already received a centre-zone fill pass (key = z.toFixed(2)).
    // FIX 1 (was: centerFillZ = {} keyed on interpolated Z).
    //
    // DECISION (2026-09-11, MODULO/REZERO evaluated):
    // FreeCAD CAM's rotary generators name three C-unwind strategies —
    // UNWOUND (cumulative, what this converter does), MODULO (always emit
    // C in [0,360)), REZERO (emit in [0,360) and mark each revolution
    // crossing for the post to inject a modal reset like G92 C0).
    // Staying with UNWOUND deliberately: MODULO is unsafe mid-cut — a cut
    // whose C value crosses a revolution boundary would jump 360 deg in one
    // block. REZERO is the "correct" professional answer but G92 offsets
    // persist globally in LinuxCNC and stay active until explicitly cleared,
    // which is a new class of mistake (forgetting an active offset) for a
    // single-operator hobby machine to manage. The chuck rotates continuously
    // with no mechanical stop, so pure cumulative growth is not a safety
    // issue — the only cost is float precision over MANY revolutions, and
    // Fix 2 (nearestEquivalentAngle) already trims the worst source of
    // unnecessary winding (the centre-fill return move). Revisit only if a
    // real program is seen accumulating an impractical C value.
    // The old dictionary was keyed on the INTERPOLATED Z of each sub-point, so a
    // ramping/helical move through the centre produced a different key at every
    // sub-point and re-ran the whole centre pocket fill each time (~3000 wasted
    // blocks from a single line, plus re-cutting air).
    // Material at the centre is always removed top-down and the fill always
    // clears the same disk, so the only thing that matters is the DEEPEST Z
    // already cleared. Anything at or above that depth needs no new fill.
    var centerFilledZ = null;   // deepest Z already cleared at centre (null = none)

    // Chordal-deviation adaptive segment length for Cartesian line (x0,y0)->(x1,y1).
    // Finds closest approach r_min of the segment to origin (conservative bound),
    // then L_max = 2*sqrt(2*r_used*CHORD_TOL), clamped to [MIN_SEG, MAX_SEG_G].

    // Closest approach of the straight segment (x0,y0)->(x1,y1) to the origin.
    // Used both for chordal-deviation segment sizing and to detect lines whose
    // path passes through/near the machine centre (r_min < THRESHOLD).
    function lineClosestApproachR(x0, y0, x1, y1) {
      var ddx = x1 - x0, ddy = y1 - y0;
      var lenSq = ddx * ddx + ddy * ddy;
      if (lenSq < 1e-18) return Math.hypot(x0, y0);
      var tc = -(x0 * ddx + y0 * ddy) / lenSq;
      tc = Math.max(0, Math.min(1, tc));
      return Math.hypot(x0 + tc * ddx, y0 + tc * ddy);
    }

    function getAdaptiveSegLen(x0, y0, x1, y1) {
      var rMin  = lineClosestApproachR(x0, y0, x1, y1);
      var rUsed = Math.max(rMin, THRESHOLD);
      return Math.min(Math.max(2 * Math.sqrt(2 * rUsed * CHORD_TOL), MIN_SEG), MAX_SEG_G);
    }

    // ADDED 2.4.0: LOCAL segmentation. getAdaptiveSegLen sizes every piece of a
    // line by the line's closest approach to the pole, so a long facing pass
    // that crosses the centre was cut into tiny pieces along its WHOLE length.
    // The joint-interpolation error of a piece depends on its own distance from
    // the pole (about ds^2 / (8 r)), so each piece is sized by the closest
    // approach of THAT piece: short only near the centre, long elsewhere - the
    // same accuracy with far fewer blocks (which also matters to LinuxCNC: it
    // does not blend moves that involve a rotary axis, so many tiny blocks cost
    // speed). Also keeps every piece within MAX_DEG_PER_SEG of C rotation.
    // cb(t) is called for each new point, in order, ending exactly at tB.
    function segLenAt(r) {
      return Math.min(Math.max(2 * Math.sqrt(2 * Math.max(r, THRESHOLD) * CHORD_TOL), MIN_SEG), MAX_SEG_G);
    }
    // Exact error of one block: the machine moves X and C LINEARLY between the
    // two ends (joint space), the program wants the straight line between them.
    // Sample the joint path and return its largest distance from that line.
    // (Replaces the small-angle estimate ds^2/(8r), which ran slightly over the
    // tolerance at its limit - measured 0.0267 mm against 0.025.)
    function jointChordErr(ra, ca, rb, cb2) {
      var a0 = ca * Math.PI / 180, a1 = cb2 * Math.PI / 180;
      var ax = ra * Math.cos(a0), ay = ra * Math.sin(a0);
      var bx = rb * Math.cos(a1), by = rb * Math.sin(a1);
      var vx = bx - ax, vy = by - ay, vv = vx * vx + vy * vy, worst = 0;
      for (var k = 1; k < 8; k++) {
        var f = k / 8, r = ra + (rb - ra) * f, a = a0 + (a1 - a0) * f;
        var px = r * Math.cos(a), py = r * Math.sin(a), tt = 0;
        if (vv > 1e-18) tt = Math.max(0, Math.min(1, ((px - ax) * vx + (py - ay) * vy) / vv));
        var e = Math.hypot(px - (ax + vx * tt), py - (ay + vy * tt));
        if (e > worst) worst = e;
      }
      return worst;
    }
    var ERR_BUDGET = CHORD_TOL * 0.9;   // 10% margin for Z and rounding

    function walkLine(x0, y0, dx, dy, tA, tB, cb, budget) {
      var BUDGET = budget || ERR_BUDGET;
      var L = Math.hypot(dx, dy);
      if (L < 1e-12 || tB <= tA) { cb(tB); return; }
      // ADDED 2.5.0: a RADIAL line (on a ray from the pole, not passing through
      // it here) keeps C constant, so X alone traces it exactly: a piece of any
      // length is exact, as in the Signed-X branch. It was cut into pieces
      // sized for a curving joint path (1.4 mm at r = 10) for nothing.
      var tPole = -(x0 * dx + y0 * dy) / (L * L);
      var radial = Math.abs(x0 * dy - y0 * dx) / L < 1e-6 && !(tPole > tA - 1e-9 && tPole < tB + 1e-9);
      var t = tA, guard = 0;
      while (t < tB - 1e-12 && guard++ < 2000000) {
        var px = x0 + dx * t, py = y0 + dy * t, rp = Math.hypot(px, py);
        var len = Math.min(radial ? MAX_SEG_G : segLenAt(rp), (tB - t) * L);
        // Inside the centre zone the points are skipped (C frozen), so the next
        // emitted block joins the last point BEFORE the zone to the first point
        // AFTER it. Leave the zone exactly at its edge, so that crossing block
        // stays within about one zone radius of the pole (measured 0.027 mm on a
        // line 0.01 mm from the centre when the step ran past the edge).
        // ...and ENTER it exactly at its edge too, so the last point before the
        // zone is on the edge (a long step landing inside the zone left that
        // point far away: measured 0.085 mm on a line 0.01 mm from the centre).
        if (rp >= THRESHOLD) {
          var ea = dx * dx + dy * dy, eb = 2 * (px * dx + py * dy), ec = rp * rp - THRESHOLD * THRESHOLD;
          var edisc = eb * eb - 4 * ea * ec;
          if (edisc >= 0) {
            var dtEnter = (-eb - Math.sqrt(edisc)) / (2 * ea);  // first crossing ahead
            if (dtEnter > 1e-12 && dtEnter * L < len && t + dtEnter < tB) len = dtEnter * L * (1 - 1e-7);
          }
        }
        if (rp < THRESHOLD) {
          var qa = dx * dx + dy * dy, qb = 2 * (px * dx + py * dy), qc = rp * rp - THRESHOLD * THRESHOLD;
          var disc = qb * qb - 4 * qa * qc;
          if (disc >= 0) {
            var dtExit = (-qb + Math.sqrt(disc)) / (2 * qa);   // >= 0 because qc < 0
            if (dtExit > 0 && t + dtExit < tB) len = Math.min(len, dtExit * L * (1 + 1e-9) + 1e-9);
          }
        }
        for (var k = 0; k < 60; k++) {
          var tn = Math.min(t + len / L, tB);
          var qx = x0 + dx * tn, qy = y0 + dy * tn, rq = Math.hypot(qx, qy);
          // Skip the error check only for the piece that STARTS inside the zone
          // (it crosses the zone; its error is bounded by the zone radius). A
          // piece that only reaches the zone edge is checked like any other -
          // rounding put its end a hair inside and the check was skipped
          // (measured 0.0287 mm on a ramp 0.008 mm from the centre).
          var inZone = rp < THRESHOLD;
          var aP = Math.atan2(py, px) * 180 / Math.PI;
          var dA = angdiff(aP, Math.atan2(qy, qx) * 180 / Math.PI);
          var ok = inZone || (Math.abs(dA) <= MAX_DEG_PER_SEG && jointChordErr(rp, aP, rq, aP + dA) <= BUDGET);
          if (ok || len <= MIN_SEG) break;
          len = Math.max(len * 0.7, MIN_SEG);
        }
        var tNext = Math.min(t + len / L, tB);
        if (tB - tNext < 1e-9) tNext = tB;
        cb(tNext);
        t = tNext;
      }
    }

    // ─── analyzeCenterCrossing ────────────────────────────────────────────────────────
    // Used by Auto mode to classify how a line (x0,y0)->(x1,y1) relates to the
    // centre-freeze circle of the given radius. Solves |P(t) - origin| = radius
    // for t (line/circle intersection, quadratic in t) to find where the segment
    // actually crosses the boundary circle, then reports:
    //   insideStart / insideEnd — is each endpoint already inside the circle?
    //   tEntry / tExit          — parametric t (0..1) of the two boundary
    //                             crossings, or null if that side has none
    //                             (endpoint starts/ends inside, or no crossing).
    function analyzeCenterCrossing(x0, y0, x1, y1, radius) {
      var ddx = x1 - x0, ddy = y1 - y0;
      var a = ddx * ddx + ddy * ddy;
      var b = 2 * (x0 * ddx + y0 * ddy);
      var c = x0 * x0 + y0 * y0 - radius * radius;
      var insideStart = (x0 * x0 + y0 * y0) < radius * radius;
      var insideEnd   = (x1 * x1 + y1 * y1) < radius * radius;
      var tEntry = null, tExit = null;
      if (a > 1e-18) {
        var disc = b * b - 4 * a * c;
        if (disc >= 0) {
          var sq  = Math.sqrt(disc);
          var lo  = (-b - sq) / (2 * a);
          var hi  = (-b + sq) / (2 * a);
          if (lo >= -1e-9 && lo <= 1 + 1e-9) tEntry = Math.max(0, Math.min(1, lo));
          if (hi >= -1e-9 && hi <= 1 + 1e-9) tExit  = Math.max(0, Math.min(1, hi));
        }
      }
      return { insideStart: insideStart, insideEnd: insideEnd, tEntry: tEntry, tExit: tExit };
    }

    // C-axis continuous unwrap — accumulates degrees across multi-turn paths.
    // Frozen (returns cumC unchanged) whenever r < THRESHOLD.
    function updateC(r, rawAngle) {
      if (r < THRESHOLD) return cumC;
      if (!cInit) { cumC = rawAngle; cInit = true; }
      else {
        var n0 = ((cumC      % 360) + 360) % 360;
        var n1 = ((rawAngle  % 360) + 360) % 360;
        cumC += angdiff(n0, n1);
      }
      return cumC;
    }

    // ─── insertCenterFill ────────────────────────────────────────────────────────────
    // Machines the centre disk with a concentric-circle pocket (same strategy the
    // CAM pocket operation uses), working from a small inner radius outward to
    // THRESHOLD in steps of CENTER_STEPOVER:
    //
    //   1. Retract Z by CENTER_RETRACT mm (safe lift before moving to centre)
    //   2. Rapid to inner circle start position at safe height
    //   3. Feed-plunge back to cutting depth
    //   4. For each circle radius r = CENTER_STEPOVER .. THRESHOLD:
    //        a) If not the first circle: feed outward (G1 radial move, C frozen)
    //        b) Full 360° circle at radius r — C rotates, X stays constant
    //           → naturally slow at small r (correct physics), speeds up at larger r
    //   5. Retract Z again so the caller's G0 return is safe
    //
    // This produces clean spiral-in pocket motion, physically correct speed
    // profile throughout, and complete coverage of the entire centre disk.
    function insertCenterFill(z) {
      var CENTER_STEPOVER = centerStepover();
      if (CENTER_STEPOVER <= 0) return;
      var feedFill = camFeed > 0 ? camFeed : 500;  // mm/min
      // FIX 5: the plunge at the centre already removes a disk of radius
      // TOOL_DIA/2, so the first concentric circle only has to start there — not
      // at one stepover. Circles are then only needed to cover the annulus from
      // TOOL_DIA/2 out to THRESHOLD, which is what nCircles now counts.
      var rStart   = Math.min(Math.max(TOOL_DIA * 0.5, 0.1), THRESHOLD);
      var nCircles = Math.max(1, Math.ceil(Math.max(THRESHOLD - rStart, 0) / CENTER_STEPOVER) + 1);
      var zSafe    = z + CENTER_RETRACT;

      out.push('( --- Center Pocket Fill: concentric circles from r=' + rStart.toFixed(2) +
               'mm  step=' + CENTER_STEPOVER.toFixed(2) +
               'mm  ' + nCircles + ' circles --- )');

      // 1. Retract
      if (CENTER_RETRACT > 1e-6) {
        out.push('G0 Z' + zSafe.toFixed(4));
        prevZ = zSafe;
      }
      // 2. Rapid to inner start
      out.push('G0 ' + wx(rStart) + ' ' + wc(cumC) + ' Z' + zSafe.toFixed(4));
      prevR = rStart;  prevC = cumC;  prevZ = zSafe;

      // 3. Feed-plunge to cutting depth
      if (CENTER_RETRACT > 1e-6) {
        var T_plunge = Math.max(CENTER_RETRACT / feedFill, MIN_TIME);
        var F_plunge = Math.min(1.0 / T_plunge, MAX_F_G93);
        out.push('G1 ' + wx(rStart) + ' ' + wc(cumC) +
                 ' Z' + z.toFixed(4) + ' F' + F_plunge.toFixed(4));
        prevZ = z;
      }

      // 4. Concentric circles: inside → outside
      for (var ci = 0; ci < nCircles; ci++) {
        var r = rStart + ci * CENTER_STEPOVER;
        if (r > THRESHOLD + 0.001) break;
        r = Math.min(r, THRESHOLD);

        if (ci > 0) {
          // Radial outward step between circles (C frozen, X advances)
          emitG1(r, cumC, z);
        }

        // Full 360° circle at radius r using chordal adaptive segmentation.
        // emitG1 will call _doEmitG1 which now uses actual r (not THRESHOLD floor)
        // for C-rotating segments → correct slow speed near centre.
        var segLen = Math.min(Math.max(2 * Math.sqrt(2 * r * CHORD_TOL), MIN_SEG), 2.0);
        var nSeg   = Math.max(4, Math.ceil(2 * Math.PI * r / segLen));
        var dCdeg  = 360.0 / nSeg;
        for (var seg = 1; seg <= nSeg; seg++) {
          emitG1(r, cumC + seg * dCdeg, z);
        }
        cumC += 360;   // track full circle (prevC is kept in sync by emitG1)
        cInit = true;
      }

      // 5. Retract after fill so caller's G0 back is clean
      flushDeferred();
      if (CENTER_RETRACT > 1e-6) {
        out.push('G0 Z' + zSafe.toFixed(4));
        prevZ = zSafe;
      }
    }

    // State that the input stage hands over with every event.
    var camFeed = 0;          // current CAM feed (mm/min) when a block is written
    var zKnown = false;       // is the tool's Z known (see gcode-input.js)
    // Z word for an emitted block. While Z is unknown the converter must never
    // invent a Z value — it omits the word so the machine stays where it is.
    function zw(z) { return zKnown ? ' Z' + z.toFixed(4) : ''; }
    var cumC = 0, cInit = false;

    // Polar tracking state — updated after every emitted G1 or G0 rapid
    var prevR = 0, prevC = 0, prevZ = 0;  // polar coords of last emitted point

    // Look-ahead cornering: unit vector of the last emitted segment (Cartesian XY).
    // Reset after G0 rapids so the first G1 after a rapid is never corner-penalised.

    // Deferred-emit state: when a candidate G1 endpoint is closer than MIN_EMIT_DIST
    // to the last emitted point we store it here instead of emitting immediately.
    var _deferR = null, _deferC = null, _deferZ = null;
    // FIX 2.4.0: every point skipped by the merge since the last written block.
    // A skipped point is only dropped if it lies close to the straight block
    // that replaces it. Points at a corner (between two arc chords, or two CAM
    // lines) do not, and dropping them cut the corner (measured 0.0264 mm on
    // random arcs against 0.025).
    var _deferPts = [];
    function _cart(r, c) { var a = c * Math.PI / 180; return [r * Math.cos(a), r * Math.sin(a)]; }
    function _distSeg(p, a, b) {
      var vx = b[0] - a[0], vy = b[1] - a[1], vv = vx * vx + vy * vy, t = 0;
      if (vv > 1e-18) t = Math.max(0, Math.min(1, ((p[0] - a[0]) * vx + (p[1] - a[1]) * vy) / vv));
      return Math.hypot(p[0] - (a[0] + vx * t), p[1] - (a[1] + vy * t));
    }

    // ─── _doEmitG1 ────────────────────────────────────────────────────────────────────
    // Core emit function — called only by the emitG1 wrapper below after the
    // deferred-merge filter has decided this endpoint should be written to output.
    //
    // G93 inverse time from the real 3D path length (radial + rotary arc +
    // axial) at the CAM feed: T = dist3D / F, F_g93 = 1/T (floor MIN_TIME, far
    // below one servo period). The controller enforces axis limits.
    function _doEmitG1(r, outC, z) {
      _deferPts = [];
      var dR     = r - prevR;
      var dC_deg = outC - prevC;
      var dC_rad = Math.abs(dC_deg) * (Math.PI / 180);
      var dZ     = z - prevZ;

      // Inverse time for this block: the time the tool needs to cover the REAL
      // 3D path at the CAM's feed. The path length includes the arc swept by
      // the rotary axis, so the surface feed is the one the CAM asked for.
      // Nothing else is added: velocity and acceleration limits belong to the
      // controller, which stretches any block its axes cannot follow.
      var feed   = Math.max(camFeed, 1.0);
      var rAvg   = (Math.abs(prevR) + Math.abs(r)) / 2;
      var arcLen = dC_rad * rAvg;                              // tangential arc (mm)
      var dist3D = Math.sqrt(dR * dR + arcLen * arcLen + dZ * dZ);
      var T      = Math.max(dist3D / feed, MIN_TIME);         // [min]
      var F_g93  = Math.min(1.0 / T, MAX_F_G93);              // inverse-time word
      out.push('G1 ' + wx(r) + ' ' + wc(outC) + ' Z' + z.toFixed(4) + ' F' + F_g93.toFixed(4));

      if (r < X_MIN_LIMIT || r > X_MAX_LIMIT) xLimitViolations++;

      prevR = r;  prevC = outC;  prevZ = z;
    }

    // ─── flushDeferred / emitG1 ───────────────────────────────────────────────────────
    // emitG1 is the public entry point called by all motion handlers.
    // It measures the 3D distance from the last emitted point and either:
    //   a) defers the endpoint (too close — store as _deferR/C/Z without emitting), or
    //   b) emits the endpoint via _doEmitG1, which resets the defer buffer.
    // flushDeferred() forces emission of any pending deferred point; it is called
    // before every G0 rapid and at end-of-program to avoid losing trailing moves.
    function flushDeferred() {
      if (_deferR !== null) {
        _doEmitG1(_deferR, _deferC, _deferZ);
        _deferR = null;  _deferC = null;  _deferZ = null;
      }
    }

    // ─── emitG1Forced ────────────────────────────────────────────────────────────
    // Emits a block unconditionally, bypassing the MIN_EMIT_DIST deferral.
    //
    // Needed for pure C-axis rotations at or near the pole. emitG1 measures a
    // 3D distance in which the C contribution is dC_rad * rAvg — at r ~ 0 that
    // term vanishes, so a 180 deg rotation at the centre measures as ~0 mm and
    // gets deferred. The deferred point was then merged into the following
    // radial exit move, turning the intended "feed in / rotate / feed out" pole
    // traversal into a single spiral sweep out of the centre.
    // ─── physicallyAt ───────────────────────────────────────────────────────────
    // True when the last EMITTED joint position (prevR, prevC) is the same
    // physical point as Cartesian (x, y). Uses the rosekins forward transform
    // x = r cos C, y = r sin C, which is also valid for a negative (signed) r.
    function physicallyAt(x, y) {
      var a = prevC * Math.PI / 180;
      return Math.hypot(prevR * Math.cos(a) - x, prevR * Math.sin(a) - y) < 0.01;
    }

    // ─── unwindSigned ───────────────────────────────────────────────────────────
    // FIX (2026-09-12, found by the headless rosekins test): after a Signed-X
    // pass the tool can sit at a NEGATIVE X (e.g. X-50 C0). Converting the next
    // point normally gives the positive representation of the SAME physical
    // spot (X50 C180). LinuxCNC then interpolates X -50 -> +50 and C 0 -> 180
    // together, sweeping the tool through the part in a large arc — measured up
    // to 14.6 mm off-path, with the start of the move still at cutting depth.
    //
    // The switch is only geometrically free at r = 0, so it is done there:
    //   1. feed X to 0 with C held   — retraces the Signed-X line just cut
    //   2. rotate C by 180 at X = 0  — pure spin at the pole, no tool motion
    //   3. feed X back to +|r|       — retraces the same line outward
    // The tool returns to the identical physical point, now in the positive
    // representation. Because every Signed-X line passes through the centre
    // along the frozen C direction, steps 1 and 3 run over material that has
    // just been removed: nothing is gouged.
    function unwindSigned(isRapid) {
      if (!(prevR < -1e-6)) return;
      var rOld  = prevR;
      var cFlip = prevC + (prevC > 0 ? -180 : 180);
      if (isRapid) {
        out.push('G0 ' + wx(0) + ' ' + wc(prevC) + zw(prevZ));
        out.push('G0 ' + wx(0) + ' ' + wc(cFlip) + zw(prevZ));
        out.push('G0 ' + wx(-rOld) + ' ' + wc(cFlip) + zw(prevZ));
        prevR = -rOld;  prevC = cFlip;
      } else {
        flushDeferred();
        var zHold = prevZ, cHold = prevC;
        emitG1Forced(0, cHold, zHold);
        emitG1Forced(0, cFlip, zHold);
        emitG1Forced(-rOld, cFlip, zHold);
      }
      cumC = cFlip;  cInit = true;
    }

    function emitG1Forced(r, outC, z) {
      _deferR = null;  _deferC = null;  _deferZ = null;
      _doEmitG1(r, outC, z);
    }

    function emitG1(r, outC, z) {
      // Measure 3D distance from the last EMITTED point (prevR/prevC/prevZ).
      var dR_t   = r - prevR;
      var dCr_t  = Math.abs(outC - prevC) * (Math.PI / 180);
      var rAv_t  = (Math.abs(prevR) + Math.abs(r)) / 2;
      var dZ_t   = z - prevZ;
      var dist_t = Math.sqrt(dR_t*dR_t + (dCr_t*rAv_t)*(dCr_t*rAv_t) + dZ_t*dZ_t);
      // FIX 2.4.0: merge only when the merged block stays within the chord
      // tolerance: its length must fit the local segment length and it may turn
      // C only a little (a block that turns C a lot passes close to the pole,
      // where the error grows as length^2 / radius). Near the pole every merge
      // was undoing the fine pieces walkLine had made (measured 0.05-0.08 mm on
      // lines passing 0.01-0.2 mm from the centre).
      var mergeOK = Math.abs(outC - prevC) <= 5.0 &&
                    jointChordErr(prevR, prevC, r, outC) <= ERR_BUDGET * 0.5;
      if (_deferR !== null && _deferPts.length) {
        var segA = _cart(prevR, prevC), segB = _cart(r, outC);
        for (var dp = 0; dp < _deferPts.length; dp++) {
          // Only the margin left over may be spent here: the arc chord may already
          // be tol/2 off the arc and the machine path up to 0.4 tol off the chord.
          if (_distSeg(_deferPts[dp], segA, segB) > CHORD_TOL * 0.1) { mergeOK = false; break; }
        }
      }
      if (dist_t < MIN_EMIT_DIST && mergeOK) {
        // Too short — accumulate toward the latest endpoint.
        // The next call that crosses the threshold will emit from prevR directly
        // to that point, naturally consuming all intermediate tiny steps.
        _deferR = r;  _deferC = outC;  _deferZ = z;
        _deferPts.push(_cart(r, outC));
      } else {
        // FIX 2.4.0: if a point is waiting and this block may NOT replace it
        // (it would leave the tolerance - typically near the pole, where C
        // turns fast), write the waiting point first. Discarding it joined the
        // last written point straight to this one (measured 0.0287 mm off on a
        // ramp 0.008 mm from the centre).
        if (_deferR !== null && !mergeOK) {
          var wR = _deferR, wC = _deferC, wZ = _deferZ;
          _deferR = null;  _deferC = null;  _deferZ = null;
          _doEmitG1(wR, wC, wZ);
          emitG1(r, outC, z);
          return;
        }
        // Large enough — emit directly, discard any pending deferred point
        // (it was on the same path and is now superseded by this point).
        _deferR = null;  _deferC = null;  _deferZ = null;
        _doEmitG1(r, outC, z);
      }
    }

    // Header comments describing this layout and its output profile.
    function header() {
      return [
      '( Polar G-code - G93 inverse time | radial X, rotary ' + ROT + ', axial Z )',
      '( Output profile: rotary ' + ROT + (O.invertC ? ' inverted' : '') + ', X ' + (O.xDiameter ? 'diameter' : 'radius')
        + (O.invertX ? ' inverted' : '') + '  |  X travel [' + O.xMin.toFixed(1) + ', ' + O.xMax.toFixed(1) + '] )',
      '( Centre zone ' + THRESHOLD.toFixed(2) + ' mm, crossing: ' + CENTER_CROSS_MODE + ' )'
      ];
    }

    // One motion event from the input stage (see gcode-input.js).
    // Returns 'pureZ' when a rapid only moved Z (the input then keeps X/Y).
    function move(ev) {
      var words = ev.words;
      var curX = ev.from.x, curY = ev.from.y, curZ = ev.from.z;
      var newX = ev.to.x, newY = ev.to.y, newZ = ev.to.z;
      var xyKnown = ev.xyKnown;
      var type = ev.kind;
      zKnown = ev.zKnown;
      camFeed = ev.feed;
      var dx = newX - curX, dy = newY - curY, dz = newZ - curZ;

      if (type === 'G0') {
        // Flush any deferred G1 segment before the rapid — we must not lose trailing
        // motion from the previous G1 pass, and G0 resets polar tracking.
        flushDeferred();

        // ─── G0 SEGMENTATION ───────────────────────────────────────────────────
        // A rapid used to be emitted as ONE block with X, C and Z all changing at
        // once. LinuxCNC interpolates linearly in JOINT space, so in Cartesian
        // space the tool traces a SPIRAL, not the straight line the CAM assumed.
        // Worked example: a rapid from (50,0) to (-50,0) — a straight line through
        // the centre — becomes (r=50,C=0) -> (r=50,C=180), i.e. a half-circle of
        // radius 50. Mid-move the tool is 50 mm away from where CAM thinks it is,
        // at rapid speed. This is exactly why Fanuc (G12.1) and Haas (G112) both
        // FORBID G00 inside polar mode: the control cannot guarantee the rapid's
        // path. Because this converter pre-computes everything, it can do what the
        // controls cannot — walk the straight Cartesian line and emit a short
        // chain of G0 blocks along it.
        //
        // Tolerance is deliberately looser than CHORD_TOL: a rapid is not cutting,
        // so only the TOPOLOGY of the path has to be right, not its accuracy.

        // FIX (2026-09-12) — pure-Z rapid (retract/approach with no XY change).
        // Emit Z ONLY and leave X and C exactly where they are. Previously the
        // point was re-converted, which after a Signed-X pass turned X-50 C0 into
        // X50 C180 (same physical spot) and swept the tool through the part.
        // Also covers a Z-only rapid before any XY is known: the old code sent
        // X to the imaginary origin (X0) on such a line.
        var lineHasXY = ('X' in words) || ('Y' in words);
        // (A first line such as "G0 X0 Y0 Z5" has dXY = 0 only because of the
        //  assumed origin — it must still be executed, hence the lineHasXY test.)
        if (Math.hypot(dx, dy) < 1e-9 &&
            ((xyKnown && physicallyAt(newX, newY)) || (!xyKnown && !lineHasXY))) {
          if (Math.abs(dz) > 1e-9) {
            out.push('G0 Z' + newZ.toFixed(4));
            prevZ = newZ;
          } else if (!zKnown && ('Z' in words)) {
            out.push('G0 Z' + newZ.toFixed(4));   // Z was unknown: state it explicitly
            prevZ = newZ;
          }
          // the input stage updates curZ / xyKnown / zKnown itself (pure-Z path: X and Y stay)
          return 'pureZ';
        }

        // FIX (2026-09-12) — leave the signed (negative-X) representation safely
        // before any XY rapid. See unwindSigned().
        if (xyKnown) unwindSigned(true);

        // FIX (2026-10-01): Z UNKNOWN (program start, after G28/G30/G53 or M6).
        // Never invent a Z value: move X/C at the CURRENT height first, then
        // bring Z to its target — the same order Fusion's own posts use.
        var zTarget = null;
        if (!zKnown) {
          if ('Z' in words) zTarget = newZ;
          dz = 0;  newZ = curZ;
        }

        var rapidDXY = Math.hypot(dx, dy);
        var nRapid   = 1;
        if (rapidDXY > 1e-9) {
          // Sagitta of the spiral bulge scales with how much C sweeps. Use the
          // same adaptive rule as cutting moves but with RAPID_TOL, and also cap
          // the angular step so a large C sweep is never one block.
          var rMinRapid = Math.max(lineClosestApproachR(curX, curY, newX, newY), 0.001);
          var segRapid  = Math.max(2 * Math.sqrt(2 * Math.max(rMinRapid, THRESHOLD) * RAPID_TOL), 0.5);
          nRapid = Math.max(1, Math.ceil(rapidDXY / segRapid));
          var aR0 = Math.atan2(curY, curX) * 180 / Math.PI;
          var aR1 = Math.atan2(newY, newX) * 180 / Math.PI;
          if (Math.hypot(curX, curY) >= THRESHOLD && Math.hypot(newX, newY) >= THRESHOLD) {
            nRapid = Math.max(nRapid, Math.ceil(Math.abs(angdiff(aR0, aR1)) / MAX_DEG_PER_SEG));
          }
          nRapid = Math.min(nRapid, 400);   // hard cap: a rapid is never worth more
        }
        // FIX 1 (2026-09-12): the start of the first positioning move is UNKNOWN
        // (the converter only assumes 0,0,0). Walking a path from an imaginary
        // origin is worse than useless, so emit a single block straight to the
        // target — exactly what any CAM program's first rapid expects.
        if (!xyKnown) nRapid = 1;
        // Defensive: a non-finite block count must never silently drop a rapid.
        if (!isFinite(nRapid) || nRapid < 1) nRapid = 1;

        for (var iG0 = 1; iG0 <= nRapid; iG0++) {
          var tG0  = iG0 / nRapid;
          var gx   = curX + dx * tG0, gy = curY + dy * tG0, gz = curZ + dz * tG0;
          var rg0raw = Math.hypot(gx, gy);
          var rg0, outCg0;
          if (rg0raw < THRESHOLD) {
            // Centre zone: C frozen; signed projection so X can go negative.
            var frRad0 = cumC * Math.PI / 180;
            rg0    = gx * Math.cos(frRad0) + gy * Math.sin(frRad0);
            // FIX (2026-10-04): respect X Min here too. With X Min = 0 (one side
            // only) a rapid crossing the centre dipped to about -THRESHOLD (e.g.
            // X-1.4). Now it stops at the limit (the centre), C turns there and
            // the rapid leaves on the same side.
            if (rg0 < X_MIN_LIMIT) rg0 = X_MIN_LIMIT;
            outCg0 = cumC;
          } else {
            // FIX (2026-09-12): if the walk crossed the zone in the signed
            // (negative-X) representation, return to the positive one at the pole
            // BEFORE stepping outside — otherwise X -2 -> +3 with C 0 -> 180 in one
            // block flips through a small spiral (measured 1.4-1.6 mm at safe Z).
            if (xyKnown && prevR < -1e-6) unwindSigned(true);
            rg0    = rg0raw;
            var rawAg0 = Math.atan2(gy, gx) * 180 / Math.PI;
            outCg0 = updateC(rg0, rawAg0);
          }
          // FIX (2026-09-12): if the walk has landed exactly ON the pole and the
          // next point needs a different C, turn C first while X is still 0 — a
          // pure spin that moves the tool nowhere — and only then move out.
          // Doing both in one block traced a half-turn spiral (1.6 mm at safe Z).
          // FIX (2026-10-01): only when the position is KNOWN. At program start
          // prevR is 0 by initialisation, so this fired on the first rapid and
          // emitted "G0 X0 C.. Z0" — tool to the chuck centre at work Z0.
          if (xyKnown && Math.abs(prevR) < 1e-3 && Math.abs(outCg0 - prevC) > 1e-6) {
            out.push('G0 ' + wx(prevR) + ' ' + wc(outCg0) + zw(prevZ));
            prevC = outCg0;
          }
          out.push('G0 ' + wx(rg0) + ' ' + wc(outCg0) + zw(gz));
          if (rg0 < X_MIN_LIMIT || rg0 > X_MAX_LIMIT) xLimitViolations++;
          // Update polar tracking so the next G1 delta starts from the rapid endpoint
          prevR = rg0;  prevC = outCg0;  prevZ = gz;
        }
        if (zTarget !== null) {
          out.push('G0 Z' + zTarget.toFixed(4));
          prevZ = zTarget;  newZ = zTarget;  zKnown = true;
        }
      }
      else if (type === 'G1') {
        var dXY = Math.hypot(dx, dy);
        if (dXY < 1e-9) {
          // Pure Z plunge - no XY motion
          if (Math.abs(dz) > 1e-9 && xyKnown && physicallyAt(curX, curY)) {
            // FIX (2026-09-12): the tool is already at this XY — move Z only and
            // keep X and C exactly as emitted. Re-converting the point here is
            // what flipped X-50 C0 into X50 C180 after a Signed-X pass.
            emitG1(prevR, prevC, newZ);
          } else if (Math.abs(dz) > 1e-9) {
            var rawRz = Math.hypot(curX, curY);
            var rz, outCz;
            if (rawRz < THRESHOLD) {
              var frRadZ = cumC * Math.PI / 180;
              rz    = curX * Math.cos(frRadZ) + curY * Math.sin(frRadZ);
              outCz = cumC;
            } else {
              rz    = rawRz;
              var rawAz = Math.atan2(curY, curX) * 180 / Math.PI;
              outCz = updateC(rz, rawAz);
            }
            emitG1(rz, outCz, newZ);
          }
        } else {
          // XY move: does this line's path come within THRESHOLD of the centre?
          var rMinLine = lineClosestApproachR(curX, curY, newX, newY);

          // ── Decide Signed-X vs Index-at-Pole vs Pocket Fill for this line ─────
          var useSignedX = false;
          var useIndex   = false;   // FIX 6: Siemens POLE_SIDE_FIX style

          // Genuine-crossing test, computed ONCE and shared by Signed-X, Index at
          // Pole and the Auto fallback. A line qualifies when it starts and ends
          // outside the centre zone, both boundary intersections exist, and the
          // angular sweep across the zone is at least AUTO_ANGLE_THRESH (i.e. it
          // really goes THROUGH the pole rather than glancing past it). Glancing
          // lines are excluded because an in-rotate-out or frozen-C path would
          // not follow their programmed contour.
          var idxOK = false, idxTEntry, idxTExit, idxAngEntry, idxAngExit;
          if (rMinLine < THRESHOLD) {
            var xc = analyzeCenterCrossing(curX, curY, newX, newY, THRESHOLD);
            if (!xc.insideStart && !xc.insideEnd && xc.tEntry !== null && xc.tExit !== null) {
              var iEx = curX + dx * xc.tEntry, iEy = curY + dy * xc.tEntry;
              var iXx = curX + dx * xc.tExit,  iXy = curY + dy * xc.tExit;
              var iAngEntry = Math.atan2(iEy, iEx) * 180 / Math.PI;
              var iAngExit  = Math.atan2(iXy, iXx) * 180 / Math.PI;
              if (Math.abs(angdiff(iAngEntry, iAngExit)) >= AUTO_ANGLE_THRESH) {
                idxOK = true;
                idxTEntry = xc.tEntry;  idxTExit = xc.tExit;
                idxAngEntry = iAngEntry; idxAngExit = iAngExit;
              }
            }

            // FIX (2026-09-12): Signed-X EXACTNESS. Signed-X freezes C and moves
            // only X, so it reproduces a line EXACTLY only when the whole line lies
            // on the axis through the pole at the frozen angle. The old code
            // applied it to any line near the centre and claimed the error was
            // bounded by rMinLine — it is not: for a line misaligned with the
            // frozen angle the error GROWS along the line. Worst case found by
            // the rosekins test: a line leaving the pole at 90 deg to the frozen
            // C was emitted as X=0 for its entire length (the tool never moved),
            // then the next rapid swept 14.6 mm off-path.
            // Rule now: Signed-X only if both endpoints are within SIGNED_EXACT_R
            // of that axis. If the tool is physically AT the pole, C may first be
            // spun to the line's own direction — a pure spin at r = 0 moves the
            // tool nowhere — which makes any line leaving the pole exact.
            var SIGNED_EXACT_R = Math.max(CHORD_TOL, 1e-3);
            var perpToAxis = function (x, y, refDeg) {
              var a = refDeg * Math.PI / 180;
              return Math.abs(-x * Math.sin(a) + y * Math.cos(a));
            };
            var refS = cInit ? cumC : (Math.atan2(curY, curX) * 180 / Math.PI);
            var signedExact = perpToAxis(curX, curY, refS) <= SIGNED_EXACT_R &&
                              perpToAxis(newX, newY, refS) <= SIGNED_EXACT_R;
            var poleSpinTo = null;
            if (!signedExact && xyKnown && Math.abs(prevR) < SIGNED_EXACT_R && physicallyAt(curX, curY)) {
              var dirDeg = Math.atan2(dy, dx) * 180 / Math.PI;
              var spinC  = nearestEquivalentAngle(dirDeg, cumC);
              if (perpToAxis(newX, newY, spinC) <= SIGNED_EXACT_R) { signedExact = true; poleSpinTo = spinC; }
            }

            if (CENTER_CROSS_MODE === 'index') {
              useIndex = idxOK;
              // FIX (2026-09-12): a line that ends AT the pole or leaves FROM it,
              // lying exactly on the pole axis, is a pure radial move with X >= 0
              // (after a free spin at r = 0 if needed). That respects Index mode's
              // "X never negative" rule and is exact — previously it fell through to
              // Pocket Fill (measured 2.0 mm off-path at a corner on the pole).
              if (!idxOK && signedExact) {
                var refIx = (poleSpinTo !== null) ? poleSpinTo : refS;
                var aIx = refIx * Math.PI / 180;
                var rIxA = curX * Math.cos(aIx) + curY * Math.sin(aIx);
                var rIxB = newX * Math.cos(aIx) + newY * Math.sin(aIx);
                if (Math.min(rIxA, rIxB) >= -SIGNED_EXACT_R) useSignedX = true;
              }
            } else if (CENTER_CROSS_MODE === 'signed') {
              useSignedX = signedExact;
              if (!signedExact) {
                useIndex = idxOK;
                out.push('( Signed-X not exact for this line, not on the pole axis \u2014 using '
                         + (idxOK ? 'Index at Pole' : 'Pocket Fill') + ' )');
              }
            } else if (CENTER_CROSS_MODE === 'auto') {
              useSignedX = signedExact;
              if (!signedExact) useIndex = idxOK;
            }
            // CENTER_CROSS_MODE === 'fill' -> both stay false.

            // X travel-limit safety check: if Signed-X would ask for an X value
            // outside the machine's configured physical travel, fall back
            // (rSigned is linear in t, so its extremes occur at the endpoints).
            if (useSignedX) {
              var refAngleChk = (poleSpinTo !== null) ? poleSpinTo
                              : (cInit ? cumC : (Math.atan2(curY, curX) * 180 / Math.PI));
              var refRadChk   = refAngleChk * Math.PI / 180;
              var rChkA = curX * Math.cos(refRadChk) + curY * Math.sin(refRadChk);
              var rChkB = newX * Math.cos(refRadChk) + newY * Math.sin(refRadChk);
              if (Math.min(rChkA, rChkB) < X_MIN_LIMIT || Math.max(rChkA, rChkB) > X_MAX_LIMIT) {
                useSignedX = false;
                // FIX 4 (2026-09-12): in Auto, a genuine crossing that cannot use
                // Signed-X now falls back to Index at Pole — measured exact
                // (0.0000 mm) on a through-centre facing pass — instead of Pocket
                // Fill, which clears the whole centre disk and was measured 9-14
                // mm off the programmed path. Pocket Fill remains only for lines
                // that dead-end inside the zone or merely glance past it.
                if ((CENTER_CROSS_MODE === 'auto' || CENTER_CROSS_MODE === 'signed') && idxOK) {
                  useIndex = true;
                  out.push('( Signed-X would exceed X travel [' + X_MIN_LIMIT.toFixed(1)
                           + ', ' + X_MAX_LIMIT.toFixed(1) + '] \u2014 using Index at Pole for this line )');
                } else {
                  out.push('( Signed-X skipped: would exceed X travel [' + X_MIN_LIMIT.toFixed(1)
                           + ', ' + X_MAX_LIMIT.toFixed(1) + '] \u2014 using Pocket Fill for this line )');
                }
              }
            }
          }

          // FIX (2026-09-12): if the tool is still in the signed (negative-X)
          // representation from a previous Signed-X line, return to the positive
          // one at the pole before any line that does not continue it.
          if (!useSignedX) unwindSigned(false);

          if (useIndex) {
            // ── FIX 6: Index at Pole (Siemens TRANSMIT POLE_SIDE_FIX 1/2) ──────
            // Three phases, exactly as the Siemens control does it:
            //   1. The radial axis feeds INTO the pole along the approach tangent.
            //   2. The rotary axis turns to the exit angle while every other axis
            //      involved in the transformation stays stationary.
            //   3. The radial axis feeds back OUT along the departure tangent.
            // X never goes negative, so this works on a machine with no travel
            // past the chuck centreline. The rotation happens at the line's true
            // closest-approach radius, so for a genuine through-centre cut
            // (rMinLine ~ 0) the path error is ~0 and the rotation is a pure spin.
            var idxR = Math.max(rMinLine, Math.max(X_MIN_LIMIT, 0));

            // Phase 0: normal polar segments up to the threshold boundary.
            walkLine(curX, curY, dx, dy, 0, idxTEntry, function (tA) {
              var axA = curX + dx * tA, ayA = curY + dy * tA;
              var arA = Math.hypot(axA, ayA);
              emitG1(arA, updateC(arA, Math.atan2(ayA, axA) * 180 / Math.PI), curZ + dz * tA);
            });
            var zAtEntry = curZ + dz * idxTEntry;
            var zAtExit  = curZ + dz * idxTExit;

            // Phase 1: feed radially IN to the pole, C held at the entry angle.
            // Forced: flush anything pending so the entry move is its own block.
            flushDeferred();
            var cIn = updateC(THRESHOLD, idxAngEntry);
            // FIX (2026-09-12): on a RAMPING line the depth at the pole is the
            // line's Z at its closest approach, not its Z at the zone entry. The
            // old code fed in at zAtEntry and then ramped Z during the rotation,
            // measured 0.059 mm off in Z on a through-centre ramp. Feed in to the
            // correct depth and hold it while C turns.
            var dxy2 = dx * dx + dy * dy;
            var tPole = dxy2 > 1e-12 ? Math.max(0, Math.min(1, -(curX * dx + curY * dy) / dxy2)) : 0;
            var zPole = curZ + dz * tPole;
            emitG1Forced(idxR, cIn, zPole);

            // Phase 2: rotate C to the exit angle with X and Z effectively still.
            // Subdivided by MAX_DEG_PER_SEG (45 deg). The C speed is limited by
            // the controller ([AXIS_C] MAX_VELOCITY), not by the converter.
            // Forced emission: at r ~ 0 these blocks measure ~0 mm of travel and
            // would otherwise all be deferred and merged into the exit move.
            var idxSweep = angdiff(idxAngEntry, idxAngExit);
            var nRot     = Math.max(1, Math.ceil(Math.abs(idxSweep) / 45.0));
            for (var iR = 1; iR <= nRot; iR++) {
              emitG1Forced(idxR, cIn + idxSweep * (iR / nRot), zPole);
            }
            cumC = cIn + idxSweep; cInit = true;

            // Phase 3: feed radially OUT and continue to the end of the line.
            var emitOut = function (tB) {
              var bxA = curX + dx * tB, byA = curY + dy * tB;
              var brA = Math.hypot(bxA, byA);
              emitG1(brA, updateC(brA, Math.atan2(byA, bxA) * 180 / Math.PI), curZ + dz * tB);
            };
            emitOut(idxTExit);
            walkLine(curX, curY, dx, dy, idxTExit, 1, emitOut);
          }
          else if (useSignedX) {
            if (poleSpinTo !== null) {
              // Tool is at the pole: turn C to the line's direction first. Pure
              // spin at r = 0 — the tool does not move relative to the part.
              flushDeferred();
              emitG1Forced(prevR, poleSpinTo, prevZ);
              cumC = poleSpinTo;  cInit = true;
            }
            // ── Signed-X centre crossing ──────────────────────────────────────
            // C is frozen for the ENTIRE line (not just the portion inside the
            // freeze radius) so the rotary table never has to snap through an
            // abrupt ~180° turn as the tool sweeps past the machine centre.
            // X is allowed to go negative: X<0 at a fixed C is geometrically
            // identical to +|X| at C+180°, so a straight cut that continues past
            // the centre reproduces as one continuous radial sweep (+X → 0 → -X)
            // instead of a stop-rotate-restart move. Best suited to near-radial
            // cuts (e.g. facing/slot passes through or near centre); lines that
            // only glance the zone at a shallow angle keep C fixed for their
            // whole length, trading a small geometric offset (bounded by
            // rMinLine < THRESHOLD) for a perfectly smooth C profile.
            var refAngle = cInit ? cumC : (Math.atan2(curY, curX) * 180 / Math.PI);
            if (!cInit) { cumC = refAngle; cInit = true; }
            var refRad = refAngle * Math.PI / 180;

            // CHANGED 2.4.0: C is frozen and the line lies on the pole axis (within
            // SIGNED_EXACT_R), so X alone traces it - a piece of any length is
            // exact. With the tiny automatic centre zone, sizing by the closest
            // approach would cut a facing pass into thousands of blocks.
            var nS = Math.max(1, Math.ceil(dXY / MAX_SEG_G));
            for (var iS = 1; iS <= nS; iS++) {
              var tS  = iS / nS;
              var ixS = curX + dx * tS;
              var iyS = curY + dy * tS;
              var izS = curZ + dz * tS;
              var rSigned = ixS * Math.cos(refRad) + iyS * Math.sin(refRad);
              emitG1(rSigned, refAngle, izS);
            }
            cumC = refAngle;   // C is unchanged by this move — no rotation cost
          } else {
          // XY move: dual-constraint adaptive segmentation
          //   1. Chordal deviation constraint (geometric accuracy)
          //   2. Angular constraint: no single G1 block may rotate C more than
          //      MAX_DEG_PER_SEG degrees — prevents large angular demands on the
          //      rotary table and avoids sudden high-speed C motion near center.
          // MAX_DEG_PER_SEG (45 deg) is declared once at the top of the converter.

          // CHANGED 2.4.0: pieces are sized LOCALLY by walkLine (chordal error and
          // the MAX_DEG_PER_SEG limit per piece) instead of uniformly by the whole
          // line's closest approach to the pole.

          walkLine(curX, curY, dx, dy, 0, 1, function (t) {
            var ix    = curX + dx * t;
            var iy    = curY + dy * t;
            var iz    = curZ + dz * t;
            var rawR1 = Math.hypot(ix, iy);
            if (rawR1 < THRESHOLD) {
              // Centre zone: trigger fill on first entry per Z level, then skip.
              // FIX 1: fill only when going DEEPER than anything already cleared.
              // CHANGED 2.4.0: Pocket Fill only when it is asked for (centerMode
              // 'fill') or the centre zone was set larger than the chord
              // tolerance (old profiles: 2 mm). With the automatic zone (half the
              // chord tolerance) the skipped points are within 0.0125 mm of the
              // pole, so the line stays within tolerance without a fill - the
              // fill used to clear a whole disk around the centre (measured up to
              // 3.8 mm off the programmed path for lines passing 0.8-1.8 mm away).
              if ((CENTER_CROSS_MODE === 'fill' || THRESHOLD > CHORD_TOL) &&
                  (centerFilledZ === null || iz < centerFilledZ - 1e-6)) {
                flushDeferred();
                var cfSavedR = prevR, cfSavedC = prevC, cfSavedZ = prevZ;
                var cfSavedCumC = cumC, cfSavedCInit = cInit;
                insertCenterFill(iz);
                flushDeferred();
                // FIX 2: do NOT command the saved absolute C here.
                // insertCenterFill adds +360 per concentric circle, so prevC is now
                // physically cfSavedC + nCircles*360. Commanding cfSavedC directly
                // made this G0 unwind every accumulated revolution (~3600 deg, about
                // 40 s at 90 deg/s) after every centre fill. Return instead to the
                // rotationally EQUIVALENT angle nearest the current position — same
                // orientation on the part, no unwinding.
                var cfRetC = nearestEquivalentAngle(cfSavedC, prevC);
                out.push('G0 ' + wx(cfSavedR) + ' ' + wc(cfRetC) + ' Z' + cfSavedZ.toFixed(4));
                prevR = cfSavedR; prevC = cfRetC; prevZ = cfSavedZ;
                // Keep cumC consistent with the equivalent angle we actually moved to.
                cumC = cfSavedCumC + (cfRetC - cfSavedC); cInit = cfSavedCInit;
                centerFilledZ = iz;
              }
              // Centre already machined — skip sub-point; loop continues to the
              // exit side and emits a direct G1 from the last outer position.
            } else {
              var r1 = rawR1;
              var rawA1 = Math.atan2(iy, ix) * 180 / Math.PI;
              emitG1(r1, updateC(r1, rawA1), iz);
            }
          });
          }
        }
      }
      else {
        var nI = ev.arc.I, nJ = ev.arc.J, nR = ev.arc.R;
        unwindSigned(false);   // FIX (2026-09-12): leave negative-X representation first
        // FIX (2026-09-12): an arc is approximated TWICE — first into chords here,
        // then each chord is split again for the polar transform. Both used the
        // full CHORD_TOL, so the errors stacked (measured 0.041 mm on an
        // off-centre r=10 circle against a 0.025 target). The arc now gets half
        // the budget, as Autodesk's own posts do for polar mode
        // (activatePolarMode(getTolerance() / 2, ...)).
        var arcPts = linearizeArc(curX, curY, curZ, newX, newY, newZ, nI, nJ, nR, type === 'G2', CHORD_TOL * 0.5);
        // FIX 2.4.0: an arc that LEAVES the pole. At r = 0 the angle is free, so
        // C may still point anywhere; going to the first arc point then turned
        // C while X grew - a spiral, measured 0.50 mm off the arc. Lines leaving
        // the pole already turned C first; arcs now do the same: a pure spin at
        // r = 0 (the tool does not move on the part), then the arc.
        if (arcPts.length && xyKnown && Math.hypot(curX, curY) < Math.max(THRESHOLD, 1e-3)) {
          flushDeferred();
          if (physicallyAt(curX, curY) && Math.abs(prevR) < Math.max(THRESHOLD, 1e-3)) {
            var fp = arcPts[0];
            if (Math.hypot(fp.x, fp.y) >= Math.max(THRESHOLD, 1e-3)) {
              var spinA = nearestEquivalentAngle(Math.atan2(fp.y, fp.x) * 180 / Math.PI, cInit ? cumC : 0);
              if (!cInit || Math.abs(spinA - cumC) > 1e-6) {
                emitG1Forced(prevR, spinA, prevZ);
                cumC = spinA; cInit = true;
              }
            }
          }
        }
        // FIX 2.4.0: each chord of the arc is now split for the polar transform
        // too (the comment above always said so, but every chord went out as ONE
        // block; away from the pole the machine bows it, and that error added
        // to the chord's own - measured 0.034 mm on off-centre R20 arcs against
        // 0.025). The arc chord uses half the tolerance, the polar split gets
        // 0.40 of it, so together they stay within the tolerance with margin.
        var arcEmit = function (ax, ay, az) {
          var rr = Math.hypot(ax, ay);
          if (rr < Math.min(THRESHOLD, CHORD_TOL)) return;   // at the pole: angle undefined, C held
          var aa = Math.atan2(ay, ax) * 180 / Math.PI;
          if (!cInit) { cumC = aa; cInit = true; }
          else {
            var m0 = ((cumC % 360) + 360) % 360, m1 = ((aa % 360) + 360) % 360;
            cumC += angdiff(m0, m1);
          }
          emitG1(rr, cumC, az);
        };
        var chX = curX, chY = curY, chZ = curZ;
        for (var ap = 0; ap < arcPts.length; ap++) {
          var pt = arcPts[ap];
          (function (x0, y0, z0, x1, y1, z1) {
            walkLine(x0, y0, x1 - x0, y1 - y0, 0, 1, function (tt) {
              arcEmit(x0 + (x1 - x0) * tt, y0 + (y1 - y0) * tt, z0 + (z1 - z0) * tt);
            }, CHORD_TOL * 0.40);
          })(chX, chY, chZ, pt.x, pt.y, pt.z);
          chX = pt.x; chY = pt.y; chZ = pt.z;
        }
      }
    }

    // End of program: write what is still waiting, then this layout's warnings.
    function finish() {
      flushDeferred();
    if (xLimitViolations > 0) {
      out.push('( WARNING: ' + xLimitViolations + ' moves exceed configured X travel ['
               + X_MIN_LIMIT.toFixed(1) + ', ' + X_MAX_LIMIT.toFixed(1) + '] mm \u2014 check machine limits! )');
    }
    }

    return {
      header: header,
      move: move,
      flush: function (feed) { camFeed = feed; flushDeferred(); },
      setTool: function (dia) { TOOL_DIA = dia; },
      finish: finish
    };
  }
  return { create: create };
});
