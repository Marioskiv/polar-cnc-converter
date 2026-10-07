/*
 * Polar CNC — test suite
 *
 * Copyright (c) 2026 Marioskiv
 * https://github.com/Marioskiv/polar-cnc-converter
 * SPDX-License-Identifier: MIT
 */
'use strict';
// Validates converter output geometry against rosekins forward kinematics.
const assert = require('assert');
const { convert } = require('../src/core/converter.js');
const { analyse } = require('./lib/replay.js');

const CASES = {
  'square off-centre':            'G21 G90\nG0 X20 Y20 Z2\nG1 Z-1 F300\nG1 X40 Y20 F500\nG1 X40 Y40\nG1 X20 Y40\nG1 X20 Y20\nG0 Z5\nM30',
  'facing through the pole':      'G21 G90\nG0 X50 Y0 Z2\nG1 Z-1 F300\nG1 X-50 Y0 F500\nG0 Z5\nM30',
  'signed-X then rapid out':      'G21 G90\nG0 X50 Y0 Z2\nG1 Z-1 F300\nG1 X-8 Y0 F500\nG0 Z5\nG0 X50 Y2\nM30',
  'signed-X then zigzag':         'G21 G90\nG0 X50 Y0 Z2\nG1 Z-1 F300\nG1 X-8 Y0 F500\nG1 X-8 Y3\nG1 X50 Y3\nG0 Z5\nM30',
  'line 5 mm from pole':          'G21 G90\nG0 X50 Y5 Z2\nG1 Z-1 F300\nG1 X-50 Y5 F500\nG0 Z5\nM30',
  'line 3 mm from pole':          'G21 G90\nG0 X50 Y3 Z2\nG1 Z-1 F300\nG1 X-50 Y3 F500\nG0 Z5\nM30',
  'circle round the pole':        'G21 G90\nG0 X30 Y0 Z2\nG1 Z-1 F300\nG2 X30 Y0 I-30 J0 F500\nG0 Z5\nM30',
  'off-centre circle':            'G21 G90\nG0 X35 Y0 Z2\nG1 Z-1 F300\nG3 X35 Y0 I-10 J0 F500\nG0 Z5\nM30',
  'ramp through the pole':        'G21 G90\nG0 X50 Y0 Z2\nG1 Z0 F300\nG1 X-50 Y0 Z-3 F500\nG0 Z5\nM30',
  'rapid across the pole':        'G21 G90\nG0 X50 Y0 Z5\nG0 X-50 Y0 Z5\nG1 Z-1 F300\nG1 X-40 Y0 F500\nG0 Z5\nM30',
  'corner on the pole':           'G21 G90\nG0 X40 Y0 Z2\nG1 Z-1 F300\nG1 X0 Y0 F500\nG1 X0 Y40\nG0 Z5\nM30',
  // 2.4.0 - lines passing NEAR (not through) the pole: were 0.17-3.8 mm off
  // with the old 2 mm zone (Index at Pole / Pocket Fill).
  'line 0.01 mm from pole':       'G21 G90\nG0 X40 Y0.01 Z2\nG1 Z-1 F300\nG1 X-40 Y0.01 F500\nG0 Z5\nM30',
  'line 0.2 mm from pole':        'G21 G90\nG0 X40 Y0.2 Z2\nG1 Z-1 F300\nG1 X-40 Y0.2 F500\nG0 Z5\nM30',
  'line 1.2 mm from pole':        'G21 G90\nG0 X40 Y1.2 Z2\nG1 Z-1 F300\nG1 X-40 Y1.2 F500\nG0 Z5\nM30',
  'ramp 0.008 mm from pole':      'G21 G90\nG0 X40 Y0.008 Z2\nG1 Z-0.5 F300\nG1 X-40 Y0.008 Z-2 F500\nG0 Z5\nM30',
  'diagonal 0.5 mm from pole':    'G21 G90\nG0 X28.637 Y27.917 Z2\nG1 Z-1 F300\nG1 X-28.637 Y-27.917 F500\nG0 Z5\nM30',
  // 2.4.0 - arcs at the pole (an arc LEAVING it was a 0.50 mm spiral) and R arcs.
  'arc leaving the pole':         'G21 G90\nG0 X0 Y0 Z2\nG1 Z-1 F300\nG2 X40 Y0 I20 J0 F500\nG0 Z5\nM30',
  'arc leaving the pole, R form': 'G21 G90\nG0 X0 Y0 Z2\nG1 Z-1 F300\nG2 X40 Y0 R20 F500\nG0 Z5\nM30',
  'line to pole, arc out':        'G21 G90\nG0 X30 Y5 Z2\nG1 Z-1 F300\nG1 X0 Y0 F500\nG3 X-20 Y20 I-20 J0\nG0 Z5\nM30',
  'R arcs, short and long':       'G21 G90\nG0 X10 Y10 Z2\nG1 Z-1 F300\nG2 X30 Y30 R20 F500\nG3 X10 Y10 R-20\nG0 Z5\nM30',
};
const G1_TOL = 0.025 + 1e-3, G0_TOL = 0.5;
let failures = 0, n = 0;
for (const [mode, xMin] of [['auto', -10], ['index', -10], ['signed', -10], ['auto', 0]]) {
  for (const [name, prog] of Object.entries(CASES)) {
    n++;
    const out = convert(prog, { centerMode: mode, xMin: xMin, xMax: 125 });
    const r = analyse(name, prog, out, { g1Tol: G1_TOL, g0Tol: G0_TOL }, true);
    const ok = r.maxDevG1 <= G1_TOL && r.maxDevG0 <= G0_TOL && r.nan === 0 && r.missingF === 0 && r.badF === 0;
    if (!ok) { failures++; console.log(`  FAIL [${mode}, X Min ${xMin}] ${name}: G1 ${r.maxDevG1.toFixed(4)} G0 ${r.maxDevG0.toFixed(4)} NaN ${r.nan} missingF ${r.missingF}`); }
  }
}
console.log(`geometry: ${n - failures}/${n} passed (G1 <= ${G1_TOL.toFixed(3)} mm, G0 <= ${G0_TOL} mm)`);
assert.strictEqual(failures, 0);
