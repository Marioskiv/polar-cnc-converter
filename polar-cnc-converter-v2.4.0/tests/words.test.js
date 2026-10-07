/*
 * Polar CNC — test suite
 *
 * Copyright (c) 2026 Marioskiv
 * https://github.com/Marioskiv/polar-cnc-converter
 * SPDX-License-Identifier: MIT
 */
'use strict';
// Universality: everything a program carries besides motion reaches the
// machine in the right order; tools are tracked; drilling cycles expand;
// the output follows each machine's own axis profile.
const assert = require('assert');
const { convert } = require('../src/core/converter.js');
const { parsePolarGCode } = require('../src/core/polar-parser.js');
let n = 0; const ok = (c, m) => { n++; assert.ok(c, m); };
const O = { xMin: -10, xMax: 125, retractZMachine: 590 };
const L = (g, o) => convert(g, Object.assign({}, O, o || {})).split('\n').map(l => l.trim()).filter(Boolean);
const idx = (arr, re) => arr.findIndex(l => re.test(l));

// --- non-motion words ---------------------------------------------------------
const tc = '%\n(T1 D=6. CR=0. - flat end mill)\n(T2 D=3. CR=0. - flat end mill)\nG90 G94 G17\nG21\nT1 M6\nS18000 M3\nG54\nG0 X40 Y0\nG43 Z15 H1\nG0 Z5\nG1 Z-1 F300\nG1 X50 F500\nG0 Z15\nM5\nT2 M6\nG0 X30 Y10 S20000 M3 M8\nG43 Z15 H2\nG1 Z-2 F200\nG1 X35 F400 (finish pass)\nG0 Z15 M9\nM30\n%';
const t = L(tc);
ok(t.includes('(T1 D=6. CR=0. - flat end mill)'), 'CAM comment-only lines are kept');
ok(idx(t, /^G43 H1$/) >= 0 && idx(t, /^G43 H1$/) < idx(t, /^G0 Z15\.0000$/), 'G43 H1 kept and placed before its Z move');
ok(t.includes('G43 H2'), 'G43 H2 kept for the second tool');
const sp = idx(t, /^S20000 M3 M8$/), mv = idx(t, /^G0 X31\.6228/);
ok(sp >= 0 && sp < mv, 'spindle start + coolant on a motion line come BEFORE that motion');
ok(t.includes('(finish pass)'), 'comment on a motion line is kept');
ok(idx(t, /^M9$/) > idx(t, /^G1 .*X36\.4005/), 'M9 on a rapid line is kept');
ok(t.filter(l => /^M30$/.test(l)).length === 1 && t[t.length - 2] === 'M30', 'one M30, at the end');
const g1 = L('G21 G90\nG0 X20 Y0 Z2\nG1 Z-1 F100\nG1 X30 M0\nG1 X40\nM30');
ok(idx(g1, /^M0$/) > idx(g1, /^G1 X30\.0000/) && idx(g1, /^M0$/) < idx(g1, /^G1 X32/), 'M0 on a motion line runs AFTER that motion');

// --- tools ---------------------------------------------------------------------
ok(t.includes('( polar-cnc tool: T1 D=6.0000 )') && t.includes('( polar-cnc tool: T2 D=3.0000 )'), 'tool diameters read from the CAM comments');
const noDia = L('G21 G90\nT5 M6\nG0 X20 Y0 Z2\nM30', { toolDia: 4 });
ok(noDia.some(l => /polar-cnc tool: T5 D=4\.0000 - from settings/.test(l)), 'missing diameter falls back to the setting, and says so');
const pts = parsePolarGCode(convert(tc, O), O);
ok(pts.some(p => p.toolD === 6) && pts.some(p => p.toolD === 3), 'the simulator follows the active tool');
// pocket fill uses the active cutter: first fill circle at r = D/2 (or the threshold)
const fill = (d) => L('(T1 D=' + d + ')\nG21 G90\nT1 M6\nG0 X20 Y0 Z2\nG1 Z-1 F100\nG1 X0 Y0 F300\nG0 Z5\nM30', { centerMode: 'fill', threshold: 5 });
const firstFillX = (lines) => lines.find(l => /^G0 X\d.* Z/.test(l) && /Z(2|3)\./.test(l)) || '';
ok(/X1\.5000/.test(fill(3).join('\n')) && /X3\.0000/.test(fill(6).join('\n')), 'pocket fill starts at the active tool radius');

// --- drilling cycles ------------------------------------------------------------
const dr = L('G21 G90\nG0 X20 Y0 Z10\nG98 G81 X20 Y0 Z-3 R2 F100\nX0 Y20\nX-20 Y0\nG80\nG0 Z10\nM30');
ok(dr.filter(l => /^G1 .*Z-3\.0000/.test(l)).length === 3, 'G81 drills every modal hole');
ok(dr.some(l => /^G1 X20\.0000 C90\.0000 Z-3/.test(l)) && dr.some(l => /^G1 X20\.0000 C180\.0000 Z-3/.test(l)), 'holes land at the right radius and angle');
const after81 = dr.slice(idx(dr, /^G1 X20\.0000 C0\.0000 Z-3/) + 1);
ok(/^G0 Z10\.0000$/.test(after81[0]), 'G98 retracts to the initial level');
const pk = L('G21 G90\nG0 X20 Y0 Z10\nG99 G83 X20 Y0 Z-6 R2 Q2.5 F80\nG80\nG0 Z10\nM30');
ok(pk.filter(l => /^G1 /.test(l)).length === 4, 'G83 pecks: 2 -> -0.5 -> -3 -> -5.5 -> -6');
ok(pk.filter(l => /^G0 Z2\.0000$/.test(l)).length >= 4, 'G83 clears to R between pecks; G99 ends at R');
const dw = L('G21 G90\nG0 X20 Y0 Z10\nG82 X20 Y0 Z-2 R2 P0.5 F80\nG80\nM30');
ok(dw.includes('G4 P0.5000'), 'G82 dwells at the bottom');
let e1 = null; try { convert('G21 G90\nG0 X20 Y0 Z10\nG81 X20 Y0 Z-3 R2 F100\nG1 X30\nM30', O); } catch (e) { e1 = e.message; }
ok(e1 === null, 'an explicit G1 ends the cycle cleanly');
let e2 = null; try { convert('G21 G90\nG0 X20 Y0 Z10\nG83 X20 Y0 Z-3 R2 F100\nM30', O); } catch (e) { e2 = e.message; }
ok(e2 && /Line 3 /.test(e2), 'G83 without Q is rejected, naming the user line');

// --- machine output profile ----------------------------------------------------------
const base = 'G21 G90\nG0 X20 Y10 Z2\nG1 Z-1 F100\nG1 X30 Y20 F300\nG0 Z5\nM30';
const mot = (o) => convert(base, Object.assign({}, O, o)).split('\n').filter(l => /^G[01] /.test(l));
const ref = mot({});
const asA = mot({ rotaryAxis: 'A' });
ok(asA.every((l, i) => l === ref[i].replace(/ C(-?\d)/, ' A$1')) && !asA.join(' ').includes(' C'), 'rotary letter A replaces C everywhere');
const invC = mot({ invertC: true });
ok(invC.every((l, i) => { const a = (l.match(/C(-?[\d.]+)/) || [])[1], b = (ref[i].match(/C(-?[\d.]+)/) || [])[1];
  return a === undefined ? b === undefined : Math.abs(+a + +b) < 1e-9; }), 'invert rotary negates every angle');
const dia = mot({ xDiameter: true, xMin: -20, xMax: 250 });
ok(dia.every((l, i) => { const a = (l.match(/X(-?[\d.]+)/) || [])[1], b = (ref[i].match(/X(-?[\d.]+)/) || [])[1];
  return a === undefined ? b === undefined : Math.abs(+a - 2 * +b) < 1e-3; }), 'diameter mode doubles X');
const invX = mot({ invertX: true, xMin: -125, xMax: 10 });
ok(invX.every((l, i) => { const a = (l.match(/X(-?[\d.]+)/) || [])[1], b = (ref[i].match(/X(-?[\d.]+)/) || [])[1];
  return a === undefined ? b === undefined : Math.abs(+a + +b) < 1e-9; }), 'invert X negates X (limits stay in machine terms)');
// the simulator reads each profile back to the same physical path
for (const o of [{}, { rotaryAxis: 'A' }, { invertC: true }, { xDiameter: true, xMin: -20, xMax: 250 }, { invertX: true, xMin: -125, xMax: 10 }]) {
  const opts = Object.assign({}, O, o), p = parsePolarGCode(convert(base, opts), opts), q = parsePolarGCode(convert(base, O), O);
  ok(p.length === q.length && p.every((pt, i) => Math.abs(pt.x3 - q[i].x3) < 1e-3 && Math.abs(pt.y3 - q[i].y3) < 1e-3),
     'simulator shows the same physical path for profile ' + JSON.stringify(o));
}
// travel limits in machine terms: with X inverted, Signed-X still respects them
const sx = 'G21 G90\nG0 X50 Y0 Z2\nG1 Z-1 F100\nG1 X-8 Y0 F300\nG0 Z5\nM30';
ok(convert(sx, Object.assign({}, O, { invertX: true, xMin: -125, xMax: 10 })).split('\n').some(l => /^G1 X8\.0000 /.test(l)),
   'Signed-X into the other side is written as +8 when X is inverted');
console.log(`words: ${n} checks passed`);
