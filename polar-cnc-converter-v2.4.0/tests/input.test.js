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
  'G53 with X/Y':             'G21 G90\nG53 G0 X0 Y0',
  'G28 with XY waypoint':     'G21 G90\nG0 X20 Y0 Z2\nG28 X10 Y10',
  'G91 before position known':'G21 G91\nG0 X10 Y0',
  'cut before Z known':       'G21 G90\nG0 X20 Y0\nG1 X30 F300',
  'G31 probe':                'G21 G90\nG0 X20 Y0 Z2\nG31 Z-5 F50',
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

console.log(`input: ${n} checks passed`);
