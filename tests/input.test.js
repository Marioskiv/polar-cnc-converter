/*
 * Polar CNC — test suite
 *
 * Copyright (c) 2026 Marioskiv
 * https://github.com/Marioskiv/polar-cnc-converter
 * SPDX-License-Identifier: MIT
 */
'use strict';
// Input handling: real CAM post output (Fusion "LinuxCNC" and "grbl" styles),
// machine-reference moves, G91, G20, % delimiters, unknown position at start,
// and everything that must be REJECTED rather than converted wrongly.
const assert = require('assert');
const { convert } = require('../src/core/converter.js');
const O = { xMin: -10, xMax: 125, retractZMachine: 590 };   // 590 = this machine's Z home park
const lines = g => convert(g, O).split('\n').map(l => l.trim()).filter(Boolean);
const motion = g => lines(g).filter(l => /^G[01] /.test(l));
let n = 0; const ok = (c, m) => { n++; assert.ok(c, m); };

// 1. Fusion "LinuxCNC" post: G53 G0 Z0 at start and end, % delimiters, G54 kept.
const fusion = '%\nN10 G90 G94 G17\nN15 G21\nN20 G53 G0 Z0\nN25 T1 M6\nN30 S18000 M3\nN35 G54\nN40 G0 X40 Y0\nN45 G0 Z15\nN50 G0 Z5\nN55 G1 Z-1 F300\nN60 G1 X50 F500\nN65 G0 Z15\nN70 G53 G0 Z0\nN75 M5\nN80 M30\n%';
const fl = lines(fusion);
ok(fl[0] === '%' && fl[fl.length - 1] === '%', '% must be the first and last line');
ok(fl.filter(l => l === '%').length === 2, 'no % in the middle of the file');
ok(fl.filter(l => /^G53 G0 Z590\.0000/.test(l)).length === 2, 'both G53 retracts go to the configured safe machine Z');
ok(!fl.some(l => /^G53 G0 Z0\.0000/.test(l)), 'the CAM\'s G53 Z0 (chuck end on this machine) never reaches the machine');
ok(fl.includes('N35 G54'), 'work offset G54 preserved');
const fm = motion(fusion);
ok(fm[0] === 'G0 X40.0000 C0.0000', 'first XY rapid must carry NO Z while Z is unknown');
ok(!fl.some(l => /^G[01] .*Z0\.0000/.test(l) && !/^G53/.test(l)), 'never a work-coordinate move to Z0');

// 2. Fusion "grbl" post: G28 G91 Z0 / G28 G91 X0 Y0.
const grbl = 'G90 G94\nG17\nG21\nG28 G91 Z0\nG90\nG0 X40 Y0\nG0 Z15\nG1 Z-1 F300\nG1 X50 F500\nG0 Z15\nG28 G91 Z0\nG28 G91 X0 Y0\nG90\nM30';
const gl = lines(grbl);
ok(gl.filter(l => /^G53 G0 Z590\.0000/.test(l)).length === 2, 'G28 G91 Z0 becomes the configured safe retract');
ok(!gl.some(l => /^G28\b/.test(l)), 'no G28 reaches the machine (its stored position defaults to machine 0,0,0)');
ok(gl.some(l => /park skipped/.test(l)), 'G28 G91 X0 Y0 park is skipped, not executed');
ok(!gl.some(l => /^G91\b/.test(l)), 'a bare G91 must never reach the machine');

// 3. First rapid from an unknown position: straight to the target, never via X0.
const sq = 'G21 G90\nG0 X20 Y20 Z2\nG1 Z-1 F300\nG1 X40 Y20 F500\nM30';
const sm = motion(sq);
ok(sm[0] === 'G0 X28.2843 C45.0000', 'first block goes to the first programmed XY (was "G0 X0 C45 Z0")');
ok(sm[1] === 'G0 Z2.0000', 'then Z to its programmed height');

// 4. G91 input gives the same motion as the equivalent G90 program.
const abs = 'G21 G90\nG0 X30 Y0 Z5\nG1 Z-1 F300\nG1 X40 Y10 F500\nG1 X20 Y20\nG0 Z5\nM30';
const inc = 'G21 G90\nG0 X30 Y0 Z5\nG91\nG1 Z-6 F300\nG1 X10 Y10 F500\nG1 X-20 Y10\nG0 Z6\nG90\nM30';
ok(JSON.stringify(motion(abs)) === JSON.stringify(motion(inc)), 'G91 program must match its G90 equivalent');

// 5. G20 input gives the same motion as the mm program (within rounding).
const mm = 'G21 G90\nG0 X25.4 Y12.7 Z5.08\nG1 Z-2.54 F254\nG1 X50.8 Y25.4 F508\nG0 Z5.08\nM30';
const inch = 'G20 G90\nG0 X1 Y0.5 Z0.2\nG1 Z-0.1 F10\nG1 X2 Y1 F20\nG0 Z0.2\nM30';
const a = motion(mm), b = motion(inch);
ok(a.length === b.length, 'inch and mm programs give the same number of blocks');
const nums = l => (l.match(/-?\d+\.\d+/g) || []).map(Number);
ok(a.every((l, i) => nums(l).every((v, j) => Math.abs(v - nums(b[i])[j]) < 1e-3)), 'inch program converted to mm');

// 6. Must be rejected with a clear message, never converted wrongly.
const rejects = {
  'G41 cutter comp':          'G21 G90\nG0 X20 Y0 Z2\nG41 D1 G1 X30 F300',
  'G84 tapping cycle':        'G21 G90\nG0 X20 Y0 Z2\nG84 X20 Y0 Z-3 R2 F100',
  'rotary word in the input': 'G21 G90\nG0 X20 Y0 Z2\nG1 X30 A10 F100',
  'multi-turn arc (P2)':      'G21 G90\nG0 X20 Y0 Z2\nG1 Z-1 F100\nG2 X20 Y0 I-20 J0 P2',
  'G92 Cartesian offset':     'G21 G90\nG92 X0 Y0',
  'G18 plane arc':            'G21 G90\nG0 X20 Y0 Z2\nG1 Z0 F100\nG18\nG2 X30 Z-5 I5 K0',
  'G90.1 absolute centres':   'G21 G90.1\nG0 X20 Y0 Z2',
  'G93 input feed':           'G21 G90 G93\nG0 X20 Y0 Z2',
  'G53 G1 with X/Y':          'G21 G90\nG53 G1 X0 Y0',
  'exponent number':          'G21 G90\nG0 X20 Y0 Z2\nG1 Z-1 F1E3',
  'G28 with XY waypoint':     'G21 G90\nG0 X20 Y0 Z2\nG28 X10 Y10',
  'G91 before position known':'G21 G91\nG0 X10 Y0',
  'cut before Z known':       'G21 G90\nG0 X20 Y0\nG1 X30 F300',
  'G31 probe':                'G21 G90\nG0 X20 Y0 Z2\nG31 Z-5 F50',
  // 2.4.1: refused like LinuxCNC refuses them (interp_arc.cc), never converted into something else
  'G1 with no feed rate':     'G21 G90\nG0 X20 Y0 Z2\nG1 Z-1\nG1 X30',
  'arc with no I/J/R':        'G21 G90\nG0 X20 Y0 Z2\nG1 Z-1 F100\nG2 X0 Y20',
  'R too small for the arc':  'G21 G90\nG0 X10 Y0 Z2\nG1 Z-1 F100\nG3 X0 Y30 R5',
  'R full circle':            'G21 G90\nG0 X10 Y0 Z2\nG1 Z-1 F100\nG3 X10 Y0 R5',
  'end radius far off':       'G21 G90\nG0 X10 Y0 Z2\nG1 Z-1 F100\nG3 X0 Y12 I-10 J0',
};
for (const [name, g] of Object.entries(rejects)) {
  let msg = null; try { convert(g, O); } catch (e) { msg = e.message; }
  ok(msg && /^Line \d+ /.test(msg), `${name} must be rejected with a line number (got: ${msg})`);
}

// 6b. Without a configured safe machine Z, machine-coordinate retracts are rejected.
for (const g of ['G21 G90\nG53 G0 Z0', 'G21 G90\nG0 X20 Y0 Z5\nG28 G91 Z0', 'G21 G90\nG0 X20 Y0 Z5\nG28']) {
  let msg = null; try { convert(g, { xMin: -10, xMax: 125 }); } catch (e) { msg = e.message; }
  ok(msg && /CHUCK|stored position/.test(msg), 'retract without a safe machine Z must be rejected: ' + g.split('\n').pop());
}

// 7. Harmless header codes produce no warnings.
ok(!lines('G90 G17\nG21\nG0 X20 Y0 Z2\nM30').some(l => /WARNING/.test(l)), 'G17 must not raise a warning');

// 8. After a home retract, unwinding a Signed-X state must not invent a Z.
const sx = 'G21 G90\nG0 X50 Y0 Z2\nG1 Z-1 F300\nG1 X-8 Y0 F500\nG28 G91 Z0\nG90\nG0 X50 Y2\nM30';
const after = lines(sx); const k = after.findIndex(l => /^G53 G0 Z590/.test(l)) - 1;
ok(after.slice(k + 2).filter(l => /^G0 /.test(l)).every(l => !/ Z/.test(l)), 'no invented Z after G28 retract');

// 9. X Min = 0 means ONE side: no output X may be negative, rapids included.
for (const g of ['G21 G90\nG0 X100 Y0 Z5\nG0 X-100 Y0 Z5\nG1 Z-1 F300\nG1 X-90 Y0 F500\nG0 Z5\nM30',
                 'G21 G90\nG0 X50 Y1 Z5\nG0 X-50 Y1 Z5\nM30',
                 'G21 G90\nG0 X50 Y0 Z2\nG1 Z-1 F300\nG1 X-50 Y0 F500\nG0 Z5\nM30']) {
  const xs = convert(g, { xMin: 0, xMax: 113 }).split('\n').filter(l => /^G[01] X/.test(l)).map(l => +l.match(/X(-?[\d.]+)/)[1]);
  ok(Math.min(...xs) >= 0, 'X Min 0 must keep every block on one side (got ' + Math.min(...xs) + ')');
}

// 10. (2.4.1) A half circle in R format whose end points were rounded a hair
// more than 2R apart is still a half circle (was converted as a straight line).
const { linearizeArc } = require('../src/core/geometry.js');
for (const extra of [0, 0.0001, 0.001]) {
  const pts = linearizeArc(10, 0, 0, -10 - extra, 0, 0, null, null, 10, false, 0.0125);
  ok(Math.max(...pts.map(p => Math.abs(p.y))) > 9.99, 'R half circle ' + extra + ' mm too long must stay a half circle');
}
const semi = 'G21 G90\nG0 X10 Y0 Z2\nG1 Z-1 F100\nG3 X-10.001 Y0 R10\nG0 Z5\nM30';
ok(motion(semi).length > 10, 'rounded R half circle converted as an arc');
// 11. (2.4.1) An I/J arc whose end radius differs within LinuxCNC's tolerance
// is a spiral that ends exactly on the programmed end point.
const sp = linearizeArc(10, 0, 0, 0, 10.02, 0, -10, 0, null, false, 0.0125);
const last = sp[sp.length - 1];
ok(Math.hypot(last.x - 0, last.y - 10.02) < 1e-9, 'I/J arc ends exactly on its end point');
// 12. (2.4.1) A dwell of a minute or more is flagged (G4 P is seconds in LinuxCNC).
ok(lines('G21 G90\nG0 X20 Y0 Z5\nG04 P2000\nM30').some(l => /dwell of 2000 SECONDS/.test(l)), 'G04 P2000 must be flagged');
ok(!lines('G21 G90\nG0 X20 Y0 Z5\nG4 P0.5\nM30').some(l => /dwell of/.test(l)), 'a short dwell is not flagged');

// 13. (2.5.0) Fusion's optional end park "G53 G0 X0 Y0" is skipped like the G28 park.
const park = lines('G21 G90\nG0 X20 Y0 Z5\nG1 Z-1 F300\nG1 X30 F500\nG53 G0 Z0\nG53 G0 X0 Y0\nM30');
ok(park.some(l => /G53 X\/Y park skipped/.test(l)) && !park.some(l => /^G53 G0 X/.test(l)), 'G53 G0 X0 Y0 park is skipped');
ok(park.filter(l => /^G53 G0 Z590/.test(l)).length === 1, 'the G53 Z retract still becomes the safe retract');
// 14. (2.5.0) Cutter diameter from Kiri:Moto's tool list ("; tool#=N flute=D ... unit=...").
const kiri = (body) => lines('; --- tools ---\n; tool#=2 flute=3.175 len=20 unit=metric\n; tool#=5 flute=0.25 len=1 unit=imperial\nG21 G90\n' + body + '\nG0 X20 Y0 Z5\nG1 Z-1 F300\nM30');
ok(kiri('M6 T2').some(l => /polar-cnc tool: T2 D=3\.1750 \)/.test(l)), 'Kiri metric tool diameter read');
ok(kiri('M6 T5').some(l => /polar-cnc tool: T5 D=6\.3500 \)/.test(l)), 'Kiri imperial tool diameter converted to mm');
// 15. (2.5.0) One listed tool and no tool change: that tool's diameter is used from the start.
const one = lines('; tool#=1 flute=4 len=20 unit=metric\nG21 G90\nG0 X20 Y0 Z5\nG1 Z-1 F300\nM30');
ok(one.some(l => /polar-cnc tool: T1 D=4\.0000 - the only tool listed/.test(l)), 'single listed tool used without M6');
const fus = lines('(T3 D=0.125 CR=0.)\nG20 G90\nG0 X1 Y0 Z0.2\nG1 Z-0.04 F10\nM30');
ok(fus.some(l => /polar-cnc tool: T3 D=3\.1750/.test(l)), 'single Fusion tool in an inch program converted to mm');
// 16. (2.5.0) A radial line (C constant) is not cut into small pieces.
ok(motion('G21 G90\nG0 X10 Y0 Z5\nG1 Z-1 F300\nG1 X100 Y0\nM30').filter(l => /^G1 /.test(l)).length <= 20, 'radial line in 5 mm pieces');

console.log(`input: ${n} checks passed`);
