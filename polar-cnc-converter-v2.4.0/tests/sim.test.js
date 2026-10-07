/*
 * Polar CNC — test suite
 *
 * Copyright (c) 2026 Marioskiv
 * https://github.com/Marioskiv/polar-cnc-converter
 * SPDX-License-Identifier: MIT
 */
'use strict';
// Simulator parser: what is DISPLAYED must match what the machine does.
const assert = require('assert');
const { convert } = require('../src/core/converter.js');
const { parsePolarGCode } = require('../src/core/polar-parser.js');
let n = 0; const ok = (c, m) => { n++; assert.ok(c, m); };
const O = { xMin: -10, xMax: 125, retractZMachine: 590 };

// Fusion "LinuxCNC" and "grbl" style programs through the real converter.
const fusion = '%\nG90 G94 G17\nG21\nG53 G0 Z0\nT1 M6\nG54\nG0 X40 Y0\nG0 Z15\nG0 Z5\nG1 Z-1 F300\nG1 X50 F500\nG0 Z15\nG53 G0 Z0\nM30\n%';
const grbl = 'G90 G94\nG21\nG28 G91 Z0\nG90\nG0 X40 Y0\nG0 Z15\nG1 Z-1 F300\nG1 X50 F500\nG0 Z15\nG28 G91 Z0\nG28 G91 X0 Y0\nG90\nM30';
for (const [name, prog] of [['fusion', fusion], ['grbl', grbl]]) {
  const t = parsePolarGCode(convert(prog, O));
  const refs = t.filter(p => p.machineRef);
  ok(refs.length >= 2, `${name}: retracts recognised as machine-reference moves`);
  ok(refs.every(p => p.z >= 15), `${name}: G53/G28 retracts shown going UP, never down to work Z0`);
  ok(!t.some(p => p.type === 'G1' && p.machineRef), `${name}: a retract is never shown as a cut`);
  const firstXY = t.find(p => Math.abs(p.r - 40) < 1e-9);
  ok(firstXY && firstXY.z >= 15, `${name}: first XY rapid shown at a safe height, not at the stock surface`);
}
// Start position shown at the outer edge, not the centre.
ok(parsePolarGCode(convert(fusion, O))[0].r === 50, 'unknown start drawn at the park radius');

// Timing: every block takes at least as long as its slowest joint needs.
const spin = parsePolarGCode('G93\nG0 X0 C0 Z5\nG0 X0 C180 Z5');
const spinT = spin.slice(1).reduce((a, p) => a + p.segDurNom, 0);
ok(spinT > 0.5, 'a rotary-only rapid takes visible time (was 0.001 s)');
const cut93 = parsePolarGCode('G93\nG1 X30 C0 Z0 F100\nG1 X30 C90 Z0 F30');
ok(Math.abs(cut93.slice(1).reduce((a, p) => a + p.segDurNom, 0) - 2.0) < 1e-6, 'a G93 block takes exactly the commanded 60/F seconds');

// Drawing: large C turns follow the real joint-space curve, not a chord.
const arc = parsePolarGCode('G93\nG0 X30 C0 Z5\nG0 X30 C90 Z5');
ok(arc.length > 3, '90 deg rapid is subdivided');
ok(arc.every(p => Math.abs(Math.hypot(p.x3, p.y3) - 30) < 1e-9), 'every drawn point lies on the r = 30 arc');

// Fine converter output is not inflated: typical cut blocks stay single points.
const cut = convert('G21 G90\nG0 X20 Y20 Z2\nG1 Z-1 F300\nG1 X40 Y20 F500\nG1 X40 Y40\nM30', O);
const motionLines = cut.split('\n').filter(l => /^G[01] /.test(l)).length;
ok(parsePolarGCode(cut).length <= motionLines * 2, 'no excessive subdivision of fine output');

console.log(`sim: ${n} checks passed`);
