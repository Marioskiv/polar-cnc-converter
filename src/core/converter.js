/*
 * Polar CNC — Cartesian XYZ -> polar XZC converter (G93 inverse-time output).
 * Pure: no DOM, no globals. convert(text, options) -> polar G-code string.
 * Browser: PolarCNC.converter.convert(...)   Node: require('./converter.js').convert(...)
 *
 * Copyright (c) 2026 Marioskiv
 * https://github.com/Marioskiv/polar-cnc-converter
 * SPDX-License-Identifier: MIT
 */
(function (root, factory) {
  'use strict';
  var isNode = typeof module === 'object' && module.exports;
  var api = isNode ? factory(require('./gcode-input.js'), require('./layout-xzc.js'), require('./layout-xzcb.js'))
                   : factory(root.PolarCNC.gcodeInput, root.PolarCNC.layoutXZC, root.PolarCNC.layoutXZCB);
  if (isNode) module.exports = api;
  else { root.PolarCNC = root.PolarCNC || {}; root.PolarCNC.converter = api; }
})(typeof self !== 'undefined' ? self : this, function (gcodeInput, layoutXZC, layoutXZCB) {
  'use strict';

  // ---------------------------------------------------------------------------
  // DEFAULT_OPTIONS — the single source of truth for converter settings.
  // tests/ui-defaults.test.js fails if index.html ever shows different defaults.
  // ---------------------------------------------------------------------------
  var DEFAULT_OPTIONS = Object.freeze({
    chordTol:      0.025,   // mm   chordal deviation per segment
    threshold:     null,    // mm   centre zone radius; null = automatic (half the chord tolerance)
    centerMode:    'auto',  //      'auto' | 'signed' | 'index' | 'fill'
    xMin:          -1000,   // mm   X travel limit in MACHINE units (as output), <= 0
    xMax:          1000,    // mm   X travel limit in MACHINE units (as output), >= 0
    toolDia:       6.0,     // mm   fallback cutter diameter when the program does not state one
    autoStepover:  true,    //      pocket fill stepover = 50% of toolDia
    centerStep:    1.0,     // mm   pocket fill stepover (0 = disable fill)
    centerRetract: 2.0,     // mm   pocket fill Z retract (0 = no retract)
    retractZMachine: null,  // mm   machine-coordinate Z used for G53/G28 retracts (null = reject them)
    // ---- machine output profile: how the user's machine names and orients its axes ----
    rotaryAxis:    'C',     //      letter of the rotary axis: 'C' | 'A' | 'B'
    invertC:       false,   //      rotary turns the other way (else parts come out mirrored)
    invertX:       false,   //      radial axis counts the other way / tool on the -X side
    xDiameter:     false,   //      controller expects X as a DIAMETER (lathe diameter mode)
    // ---- machine layout (2.6.0). 'xzc' = today's machine; 'xzcb' = XZC plus a router
    // that tilts in the X-Z plane (the radial plane through the chuck axis). ----
    layout:        'xzc',   //      'xzc' | 'xzcb'
    tiltAxis:      'B',     //      letter of the tilt axis (B by ISO 841 / LinuxCNC; A only as a rename)
    invertTilt:    false,   //      tilt axis turns the other way
    tiltPivot:     null,    // mm   pivot axis -> tool holder face (machine constant; no default on purpose)
    tiltMin:       null,    // deg  tilt travel, in machine terms (no default on purpose)
    tiltMax:       null,    // deg
    tiltLean:      0,       // deg  lean wanted for BALL-END tools (+ = tool tip toward the chuck axis)
    toolTable:     '',      //      LinuxCNC tool.tbl text (T.. Z<length> D<dia> ;comment "ball")
    ballTools:     ''       //      ball-end tool numbers, e.g. "1, 3" (also: "ball" in the tool table comment)
  });
  // CLEANUP (2026-10-02): the C velocity limit, C motor rpm, C acceleration
  // and corner-feed settings were removed. Every controller this targets
  // (LinuxCNC, Mach3/Mach4, grblHAL) enforces its own per-axis velocity and
  // acceleration limits on every move — in LinuxCNC this is
  // getStraightVelocity() in emccanon.cc — so a block the axis cannot follow
  // is simply executed more slowly. Re-implementing that in the converter only
  // duplicated machine-specific values that every user would have to copy.
  var ROTARY_AXES = ['C', 'A', 'B'];
  var CENTER_MODES = ['auto', 'signed', 'index', 'fill'];
  var LAYOUT_NAMES = ['xzc', 'xzcb'];

  // normalizeOptions: accepts partial options (numbers or numeric strings, as
  // read from form fields) and returns a complete, clamped options object.
  //
  // BUG FIX (2026-09-29): the old code parsed every field as
  //   parseFloat(value) || default
  // and `||` treats 0 as "missing". Three fields where 0 is a MEANINGFUL value
  // were therefore silently overridden:
  //   X Min 0            -> became -1000 (allowed Signed-X into negative X the
  //                         machine does not have)
  //   Center Fill Step 0 -> became 1.0   ("0 = disable fill" never worked)
  //   Center Retract 0   -> became 2.0   ("0 = no retract" never worked)
  // Those fields now use `num` (any finite value is kept). Fields where 0 is
  // invalid use `pos` (must be > 0, else default) and keep their old clamps.
  function num(v, d) { var p = parseFloat(v); return isFinite(p) ? p : d; }
  function pos(v, d) { var p = parseFloat(v); return (isFinite(p) && p > 0) ? p : d; }
  function normalizeOptions(o) {
    o = o || {};
    var D = DEFAULT_OPTIONS;
    return {
      chordTol:      Math.max(pos(o.chordTol,   D.chordTol),   0.001),
      // CHANGED 2.4.0: the centre zone is automatic by default - half the chord
      // tolerance - so only lines that pass practically THROUGH the pole get
      // special handling and every other line is converted exactly. A value
      // given explicitly is still respected (old profiles used 2 mm).
      threshold:     (function (v, tol) {
                       var p = parseFloat(v);
                       return (isFinite(p) && p > 0) ? Math.max(p, 0.001) : tol * 0.5;
                     })(o.threshold, Math.max(pos(o.chordTol, D.chordTol), 0.001)),
      centerMode:    CENTER_MODES.indexOf(o.centerMode) >= 0 ? o.centerMode : D.centerMode,
      xMin:          Math.min(num(o.xMin, D.xMin), 0),
      xMax:          Math.max(num(o.xMax, D.xMax), 0),
      toolDia:       Math.max(pos(o.toolDia,    D.toolDia),    0.1),
      autoStepover:  (o.autoStepover === undefined) ? D.autoStepover : !!o.autoStepover,
      centerStep:    Math.max(num(o.centerStep,    D.centerStep),    0),
      centerRetract: Math.max(num(o.centerRetract, D.centerRetract), 0),
      // No default on purpose: a safe machine Z is machine-specific (see the
      // G53/G28 handling in the converter loop).
      retractZMachine: (function (v) { var p = parseFloat(v); return isFinite(p) ? p : null; })(o.retractZMachine),
      rotaryAxis:    ROTARY_AXES.indexOf(String(o.rotaryAxis || '').toUpperCase()) >= 0
                       ? String(o.rotaryAxis).toUpperCase() : D.rotaryAxis,
      invertC:       !!o.invertC,
      invertX:       !!o.invertX,
      xDiameter:     !!o.xDiameter,
      layout:        LAYOUT_NAMES.indexOf(o.layout) >= 0 ? o.layout : D.layout,
      tiltAxis:      ROTARY_AXES.indexOf(String(o.tiltAxis || '').toUpperCase()) >= 0
                       ? String(o.tiltAxis).toUpperCase() : D.tiltAxis,
      invertTilt:    !!o.invertTilt,
      tiltPivot:     (function (v) { var p = parseFloat(v); return (isFinite(p) && p >= 0) ? p : null; })(o.tiltPivot),
      tiltMin:       (function (v) { var p = parseFloat(v); return isFinite(p) ? p : null; })(o.tiltMin),
      tiltMax:       (function (v) { var p = parseFloat(v); return isFinite(p) ? p : null; })(o.tiltMax),
      tiltLean:      num(o.tiltLean, D.tiltLean),
      toolTable:     typeof o.toolTable === 'string' ? o.toolTable : D.toolTable,
      ballTools:     typeof o.ballTools === 'string' ? o.ballTools : (o.ballTools == null ? D.ballTools : String(o.ballTools))
    };
  }

  // ============================================================
  // convertCartesianToPolar(text)
  //
  // Converts Cartesian XYZ G-code to Polar XZC with G93 inverse-time feed.
  // Returns the polar G-code string, which is then passed to parsePolarGCode().
  //
  // Parameters come from the `options` object (see DEFAULT_OPTIONS / normalizeOptions):
  //   CHORD_TOL   = inpChordTol    mm      chordal deviation tolerance (adaptive segmentation)
  //   THRESHOLD   = inpThreshold   mm      C-axis freeze radius near center (avoids singularity)
  // Hardcoded bounds:
  //   MIN_SEG     = 0.02 mm   absolute minimum sub-segment length floor
  //   MAX_SEG_G   = 5.0  mm   segment length cap (large-radius efficiency)
  //
  // Math:
  //   R     = hypot(X, Y)
  //   angle = atan2(Y, X) * 180 / PI
  //   C     = continuous multi-turn unwrap across 360-degree boundaries
  //   Output: G93 inverse-time throughout; G94 restored only at M30.
  //   Each G1 block's inverse time T = (3D path length incl. the C arc) / CAM feed,
  //   so the surface feed is the CAM's; the controller slows any block its axes
  //   cannot follow (it enforces its own velocity and acceleration limits).
  //   G0 rapids: emitted as G0 (G93 mode stays active, G0 ignores F word)
  //
  // Adaptive segment length for a line (x0,y0)->(x1,y1):
  //   r_min = min distance from origin to the segment
  //   r_used = max(r_min, THRESHOLD)
  //   L_max  = clamp(2*sqrt(2*r_used*CHORD_TOL), MIN_SEG, MAX_SEG_G)
  // ============================================================
  // RESTRUCTURED 2.6.0: the converter is now three stages, so other machine
  // layouts (e.g. a tilting router, XZC + B) can be added without touching the
  // input reading, and the same pieces can be used inside another CAM:
  //   gcode-input.js  - reads and checks the Cartesian program, in order
  //   layout-xzc.js   - the machine layout (polar transform, G93 blocks)
  //   layout-xzcb.js  - XZC + a router tilting in the X-Z plane (B), built on XZC
  //   this file       - options, the common header/footer, output clean-up
  // The output is byte-for-byte the same as before (tests/golden.test.js).
  var LAYOUTS = { xzc: layoutXZC, xzcb: layoutXZCB };

  function convertCartesianToPolar(text, options) {
    var O = normalizeOptions(options);
    var out = [];
    var layout = LAYOUTS[O.layout].create(O, out);
    Array.prototype.push.apply(out, layout.header());
    out.push('', 'G21', 'G90', 'G93');

    var res = gcodeInput.read(text, O, {
      // A layout may need to act before a passed-through line (the tilting
      // layout turns the router back to B0 before a tool change).
      text: function (line) { if (layout.text) layout.text(line); else out.push(line); },
      flush: function (feed) { layout.flush(feed); },
      move: function (ev) { return layout.move(ev); },
      tool: function (dia, number) { layout.setTool(dia, number); },
      programEnd: function (feed) {
        layout.flush(feed);
        if (layout.beforeEnd) layout.beforeEnd();
        out.push('G94  ( restore units/min mode before end )');
      }
    });
    var usedPercent = res.usedPercent, programEnded = res.programEnded;

    layout.finish();
    Array.prototype.push.apply(out, res.warnings);

    // G93 must NOT be left active when the program ends — LinuxCNC will carry it
    // into the next program, making all subsequent F values wrong.
    out.push('');
    if (!programEnded) {
      out.push('G94  ( restore units/min mode before end )');
      out.push('M30');
    }

    // Re-wrap with % delimiters if the input used them: LinuxCNC requires the
    // % to be the very first line, and stops reading at the second one.
    if (usedPercent) { out.unshift('%'); out.push('%'); }
    // FIX (2026-10-04): LinuxCNC rejects a comment inside a comment ("Nested
    // comment found"). Whatever produced it - a message of the converter or
    // a bad comment in the input - remove the inner parentheses (their text
    // is kept). tests/lint.test.js checks every output line for this.
    out = out.map(function (line) {
      if (line.indexOf('(') < 0) return line;
      var res = '', depth = 0;
      for (var k = 0; k < line.length; k++) {
        var ch = line[k];
        if (ch === '(') { depth++; if (depth > 1) continue; }
        else if (ch === ')') { if (depth > 1) { depth--; continue; } if (depth > 0) depth--; }
        res += ch;
      }
      return res;
    });
    return out.join('\n');
  }
  return { DEFAULT_OPTIONS: DEFAULT_OPTIONS, normalizeOptions: normalizeOptions, convert: convertCartesianToPolar };
});
