/*
 * Polar CNC — test suite
 *
 * Copyright (c) 2026 Marioskiv
 * https://github.com/Marioskiv/polar-cnc-converter
 * SPDX-License-Identifier: MIT
 */
'use strict';
// Benchmark: 100 mm zigzag facing at two depths, all centre modes.
const { convert } = require('../src/core/converter.js');
const { analyse } = require('./lib/replay.js');
function facing(R, step, depths) {
  const L = ['G21 G90 G17', 'G0 Z10', 'M3 S18000'];
  for (const zd of depths) {
    let dir = 1, first = true;
    for (let y = -R + 1; y <= R - 1; y += step) {
      const x = Math.sqrt(R * R - y * y), xa = -dir * x, xb = dir * x;
      if (first) { L.push(`G0 X${xa.toFixed(3)} Y${y.toFixed(3)}`, `G0 Z2`, `G1 Z${zd} F200`); first = false; }
      else L.push(`G1 X${xa.toFixed(3)} Y${y.toFixed(3)} F800`);
      L.push(`G1 X${xb.toFixed(3)} Y${y.toFixed(3)} F800`); dir = -dir;
    }
    L.push('G0 Z10');
  }
  L.push('M5', 'M30'); return L.join('\n');
}
const prog = facing(50, 3, [-0.5, -1.0]);
console.log('input lines:', prog.split('\n').length);
for (const mode of ['auto', 'index', 'signed', 'fill']) {
  const t0 = Date.now(); let out;
  try { out = convert(prog, { centerMode: mode, xMin: -10, xMax: 125 }); } catch (e) { console.log(mode, 'EXCEPTION', e.message); continue; }
  const ms = Date.now() - t0;
  const r = analyse(`Facing D100 zigzag, 2 depths — mode ${mode}`, prog, out, { g1Tol: 0.03, g0Tol: 0.6 });
  const lines = out.split('\n');
  console.log(`  output lines=${lines.length}  convert time=${ms} ms  M30 count=${lines.filter(l=>/^M30/.test(l.trim())).length}`);
  lines.filter(l => /clamped|Worst radius|Feed reduction|never triggered/.test(l)).forEach(l => console.log('   ' + l.trim()));
}
