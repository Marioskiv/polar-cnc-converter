/*
 * Polar CNC — test suite
 *
 * Copyright (c) 2026 Marioskiv
 * https://github.com/Marioskiv/polar-cnc-converter
 * SPDX-License-Identifier: MIT
 */
'use strict';
// Material removal depth map: cuts where the tool goes, nowhere else, and
// flags rapids that remove material (collisions).
const assert = require('assert');
const { convert } = require('../src/core/converter.js');
const { parsePolarGCode } = require('../src/core/polar-parser.js');
const { createMaterial } = require('../src/core/material.js');
const O = { xMin: -10, xMax: 125, retractZMachine: 590, toolDia: 6 };
let n = 0; const ok = (c, m) => { n++; assert.ok(c, m); };
function run(g, stockR) {
  const pts = parsePolarGCode(convert(g, O));
  const m = createMaterial({ stockR, surfaceZ: 0, toolDia: 6 });
  m.advanceTo(pts, pts.length - 1);
  m.at = (x, y) => m.z[Math.round((y - m.x0) / m.cell) * m.n + Math.round((x - m.x0) / m.cell)];
  return { m, pts };
}

const sq = run('G21 G90\nG0 X20 Y20 Z2\nG1 Z-1 F300\nG1 X40 Y20 F500\nG1 X40 Y40\nG1 X20 Y40\nG1 X20 Y20\nG0 Z5\nM30', 50);
ok(Math.abs(sq.m.at(30, 20) + 1) < 1e-6, 'on the path the depth is the cut depth');
ok(sq.m.at(30, 30) === 0, 'inside the square (not on the path) is untouched');
ok(sq.m.at(30, 15) === 0, 'beyond the cutter edge is untouched');
ok(sq.m.stats().rapidCutCells === 0, 'a correct program has no rapid cuts');

const bad = run('G21 G90\nG0 X20 Y0 Z5\nG0 Z-1\nG0 X35 Y10\nG0 Z5\nM30', 50);
ok(bad.m.stats().rapidCutCells > 0 && bad.m.stats().rapidLines.length > 0, 'a rapid below the surface is reported with its line');

// Progressive stamping (as the animation advances) ends in the same state,
// and seeking backwards restarts cleanly.
const p = sq.pts, prog = createMaterial({ stockR: 50, surfaceZ: 0, toolDia: 6 });
for (let i = 0; i < p.length; i++) prog.advanceTo(p, i);
ok(prog.z.every((v, k) => v === sq.m.z[k]), 'step-by-step stamping equals one full run');
prog.advanceTo(p, 1);
ok(prog.z.every(v => v === 0), 'seeking back to the start restores uncut stock');

// Full facing: the whole face is machined, in reasonable time.
const L = ['G21 G90', 'G0 Z10']; let d = 1, f = true;
for (let y = -49; y <= 49; y += 3) { const x = Math.sqrt(2500 - y * y), a = -d * x, b = d * x;
  if (f) { L.push('G0 X' + a.toFixed(3) + ' Y' + y, 'G0 Z2', 'G1 Z-0.5 F200'); f = false; } else L.push('G1 X' + a.toFixed(3) + ' Y' + y + ' F800');
  L.push('G1 X' + b.toFixed(3) + ' Y' + y + ' F800'); d = -d; }
L.push('G0 Z10', 'M30');
const t0 = Date.now(); const face = run(L.join('\n'), 50); const ms = Date.now() - t0;
let inside = 0, cut = 0; for (let k = 0; k < face.m.z.length; k++) if (face.m.inside[k]) { inside++; if (face.m.z[k] < -0.4) cut++; }
ok(cut / inside > 0.97, `facing machines the whole face (${(100 * cut / inside).toFixed(1)}%)`);
ok(ms < 2000, `full facing simulated quickly (${ms} ms)`);
console.log(`material: ${n} checks passed`);
