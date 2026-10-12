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
const O = { xMin: -10, xMax: 125 };
const lines = g => convert(g, O).split('\n').map(l => l.trim()).filter(Boolean);
const motion = g => lines(g).filter(l => /^G[01] /.test(l));
let n = 0; const ok = (c, m) => { n++; assert.ok(c, m); };

// 1. Fusion "LinuxCNC" post: G53 G0 Z0 at start and end, % delimiters, G54 kept.
const fusion = '%\nN10 G90 G94 G17\nN15 G21\nN20 G53 G0 Z0\nN25 T1 M6\nN30 S18000 M3\nN35 G54\nN40 G0 X40 Y0\nN45 G0 Z15\nN50 G0 Z5\nN55 G1 Z-1 F300\nN60 G1 X50 F500\nN65 G0 Z15\nN70 G53 G0 Z0\nN75 M5\nN80 M30\n%';
const fl = lines(fusion);
ok(fl[0] === '%' && fl[fl.length - 1] === '%', '% must be the first and last line');
ok(fl.filter(l => l === '%').length === 2, 'no % in the middle of the file');
// 2.11.0: a machine retract goes to the program's own highest Z (here 15), never to a machine coordinate
ok(fl.filter(l => /safe retract to the program's highest Z/.test(l)).length === 2, 'both G53 retracts are replaced');
ok(fl[fl.findIndex(l => /replaces: N20 G53/.test(l)) + 1] === 'G0 Z15.0000', 'the first retract rises to the program\'s highest Z');
ok(!fl.some(l => /^G53/.test(l)), 'no machine-coordinate move reaches the machine');
ok(fl.includes('N35 G54'), 'work offset G54 preserved');
const fm = motion(fusion);
ok(fm[0] === 'G0 Z15.0000' && fm[1] === 'G0 X40.0000 C0.0000', 'Z rises first (safe retract), then the XY rapid at that height');
ok(!fl.some(l => /^G[01] .*Z0\.0000/.test(l) && !/^G53/.test(l)), 'never a work-coordinate move to Z0');

// 2. Fusion "grbl" post: G28 G91 Z0 / G28 G91 X0 Y0.
const grbl = 'G90 G94\nG17\nG21\nG28 G91 Z0\nG90\nG0 X40 Y0\nG0 Z15\nG1 Z-1 F300\nG1 X50 F500\nG0 Z15\nG28 G91 Z0\nG28 G91 X0 Y0\nG90\nM30';
const gl = lines(grbl);
ok(gl.filter(l => /safe retract to the program's highest Z/.test(l)).length === 2, 'G28 G91 Z0 becomes the safe retract');
ok(gl.includes('G0 Z15.0000'), 'G28 G91 Z0 rises to the program\'s highest Z (absolute, despite its G91)');
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

// 6b. (2.11.0) A retract with no Z of the program's own to go to, or G28 with no axis, is rejected.
for (const g of ['G21 G90\nG53 G0 Z0', 'G21 G90\nG0 X20 Y0 Z5\nG28']) {
  let msg = null; try { convert(g, { xMin: -10, xMax: 125 }); } catch (e) { msg = e.message; }
  ok(msg && /no Z height of its own|stored position/.test(msg), 'retract must be rejected: ' + g.split('\n').pop());
}

// 7. Harmless header codes produce no warnings.
ok(!lines('G90 G17\nG21\nG0 X20 Y0 Z2\nM30').some(l => /WARNING/.test(l)), 'G17 must not raise a warning');

// 8. After a home retract, unwinding a Signed-X state must not invent a Z.
const sx = 'G21 G90\nG0 X50 Y0 Z2\nG1 Z-1 F300\nG1 X-8 Y0 F500\nG28 G91 Z0\nG90\nG0 X50 Y2\nM30';
const after = lines(sx); const k = after.findIndex(l => /safe retract done/.test(l));
ok(after.slice(k + 1).filter(l => /^G0 /.test(l)).every(l => !/ Z/.test(l) || / Z2\.0000/.test(l)), 'no invented Z after G28 retract (stays at the retract height)');

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
// 2.12.0: an arc centred on the chuck axis is now a few exact C-only blocks, so "an arc" is
// checked by its path (a straight line would be 10 mm off), not by a block count.
ok(require('./lib/replay.js').analyse('semi', semi, convert(semi, { xMin: 0, xMax: 113 }), {}, true).maxDevG1 <= 0.026,
   'rounded R half circle converted as an arc');
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
ok(park.filter(l => /safe retract to the program's highest Z/.test(l)).length === 1, 'the G53 Z retract still becomes the safe retract');
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

// 17. (2.8.0) Cutter diameter from the tool comments of other CAMs.
const prog = (head, unit) => lines((unit || 'G21') + ' G90\n' + head + '\nG0 X20 Y0 Z5\nG1 Z-1 F300\nM30');
const dia = (out) => { const m = out.map(l => l.match(/polar-cnc tool: .*?D=([\d.]+)/)).find(Boolean); return m ? +m[1] : null; };
ok(dia(prog('( T1 | 1/4 FLAT ENDMILL | H1 | D1 | WEAR COMP | TOOL DIA. - .25 )\nT1 M6', 'G20')) === 6.35, 'Mastercam TOOL DIA read, the D1 register ignored');
ok(dia(prog('(TC: 5mm Endmill)\nM5\nM6 T1\nG43 H1\n(Compensated Tool Path. Diameter: 5.0)')) === 5, 'FreeCAD tool controller + Diameter comment');
const fcName = prog('(TC: 6mm Ball End)\nM6 T1');
ok(dia(fcName) === 6 && fcName.some(l => /from the tool name "TC: 6mm Ball End"/.test(l)), 'FreeCAD size from the tool name, marked as such');
ok(dia(prog('(TC: 3mm Endmill)\nM6 T1\nG0 X5 Y0 Z5\n(Compensated Tool Path. Diameter: 3.2)')) === 3.2, 'a stated diameter beats the name');
ok(dia(prog('( T1 : 6.0 )\nM6 T1')) === 6, 'CamBam-style "T1 : 6.0"');
ok(dia(prog('(Tool: 102)\n(TOOL/MILL,3.175, 0.00, 0.00, 0.00)\nM6 T102')) === 3.175, 'APT TOOL/MILL (Carbide Create)');
ok(dia(prog('(Tools: 1 = End Mill (1/8"))\nT1 M6')) === 3.175, 'Vectric-style name with inch size and nested parentheses');
ok(dia(prog('(Tool: End Mill 6 mm)')) === 6, 'program with no tool number: the stated tool is used');
ok(dia(prog('(Stock 100mm x 50mm)\n(Part diameter: 80)\n(Feed 600mm/min)\nM6 T1')) === null, 'stock / part / feed comments are not tool diameters');
// 18. (2.9.0) No Tool Diameter setting: Pocket Fill with auto stepover needs the program's diameter.
const fillO = Object.assign({ centerMode: 'fill' }, O);
const fillProg = 'G21 G90\nM6 T1\nG0 X-20 Y0 Z5\nG1 Z-1 F300\nG1 X20 Y0 F500\nM30';
assert.throws(() => convert(fillProg, fillO), /Pocket Fill with Auto Stepover needs the cutter diameter/); n++;
ok(/polar-cnc tool: T1 D=6/.test(convert('(T1 D=6)\n' + fillProg, fillO)), 'with the diameter in the program the fill runs');
ok(convert(fillProg, Object.assign({ autoStepover: false, centerStep: 1 }, fillO)).length > 0, 'fixed fill step works without a diameter');
const two = convert('(T1 D=6)\n(T1 D=8)\nG21 G90\nM6 T1\nG0 X20 Y0 Z5\nG1 Z-1 F300\nM30', O);
ok(/two diameters for T1/.test(two), 'two different diameters for one tool are reported');

// 19. (2.11.2) The merge of short moves (found by the 2026-10-11 research).
const { analyse } = require('./lib/replay.js');
const g1s = p => convert('G21 G90 G17\n' + p + '\nM30', { xMin: 0, xMax: 113 }).split('\n').filter(l => /^G1 /.test(l));
const plunge = g1s('G0 X20 Y0 Z5\nG1 Z0 F200\nG1 Z-0.1 F100\nG1 X30 Y0 F1000');
ok(plunge.includes('G1 X20.0000 C0.0000 Z-0.1000 F1000.0000'), 'a 0.1 mm plunge is kept as a plunge, at its own feed (F100 -> 1/0.001 min)');
const stepUp = 'G21 G90\nG0 X20 Y0 Z5\nG1 Z-1 F200\nG1 X10 Y0 F1000\nG1 Z-0.9 F1000\nG1 X5 Y0\nM30';
ok(analyse('s', stepUp, convert(stepUp, { xMin: 0, xMax: 113 }), {}, true).maxDevG1 <= 0.026, 'a 0.1 mm step up is not merged into a ramp (was a 0.1 mm gouge)');
ok(g1s('G0 X20 Y0 Z1\nG1 Z0 F100\nG1 X20.1 Y0 F50\nG1 X30 Y0 F3000').includes('G1 X20.1000 C0.0000 Z0.0000 F500.0000'),
   'a short move keeps its own slow feed (F50 over 0.1 mm), not the next line\'s');
const sx2 = 'G21 G90 G17\nG0 Z5\nG0 X-1 Y0\nG1 Z-1 F200\nG1 X0 Y0.01 F600\nG1 X0.1 Y0.02\nG1 X1 Y0.5\nG0 Z5\nM30';
ok(analyse('x', sx2, convert(sx2, { xMin: -18, xMax: 113 }), {}, true).maxDevG1 <= 0.026, 'both sides: a short Signed-X move is unwound at the pole (was 0.12 mm off)');
ok(/converted point by point, no fill/.test(convert('G21 G90\nG0 X-5 Y0.002 Z1\nG1 Z-1 F300\nG1 X0.002 Y0.002 F600\nM30', { xMin: 0, xMax: 113 })),
   'the comment no longer claims a Pocket Fill that is not done');
// 20. (2.11.3) Signed-X only for lines really on the pole axis (0.0268 mm found near the pole).
const sx3 = 'G21 G90 G17\nG0 Z5\nG0 X-0.8993 Y-0.1462\nG1 Z-1 F200\nG1 X-0.0088 Y-0.0107 F600\nG1 X0.0142 Y-0.0144\nG1 X1.0000 Y-0.0224\nG0 Z5\nM30';
for (const xm of [0, -18])
  ok(analyse('x', sx3, convert(sx3, { xMin: xm, xMax: 113 }), {}, true).maxDevG1 <= 0.026,
     'a line 0.02 mm off the pole axis is not treated as on it (was 0.0268 mm), xMin ' + xm);

// 21. (2.11.4) Polar INPUT is refused, never read as Cartesian (G16 X20 Y45 became r 49.24).
const P = (body) => 'G21 G90 G17\nG0 Z5\nG0 X10 Y0\n' + body + '\nM30';
// 2.12.1: G16 is converted (G90, XY plane): G16 X20 Y45 = radius 20 at 45 deg, not the point X20 Y45.
ok(/G0 X20\.0000 C45\.0000/.test(convert(P('G16\nG0 X20 Y45'), { xMin: 0, xMax: 113 })), 'G16 X20 Y45 goes to radius 20 at 45 deg');
assert.throws(() => convert(P('G12.1\nG1 X10 Y0 F100'), { xMin: 0, xMax: 113 }), /polar interpolation/); n++;
assert.throws(() => convert(P('G112\nG1 X10 F100'), { xMin: 0, xMax: 113 }), /polar interpolation/); n++;
assert.throws(() => convert(P('G0 @20 ^45'), { xMin: 0, xMax: 113 }), /polar words/); n++;
const g15 = convert('G90 G17 G21 G40 G49 G80 G15\nG0 Z5\nG0 X10 Y0\nG1 Z-1 F100\nM30', { xMin: 0, xMax: 113 });
ok(!g15.split('\n').some(l => /\bG15\b/.test(l.replace(/\([^)]*\)/g, ''))) && /G40 G49 G80/.test(g15),
   'G15 in a safety line is removed (LinuxCNC does not know it), the rest of the line stays');
ok(/C0\.0000 Z-1\.0000/.test(convert(P('(a @ and ^ inside a comment)\nG1 Z-1 F100'), { xMin: 0, xMax: 113 })),
   '@ and ^ inside a comment are fine');

// 22. (2.12.0) An arc centred on the chuck axis is cut exactly: X constant, only C turns,
// at most 45 deg of C per block, the CAM feed along the real arc (Zhang/Chen/Du 2013, "G20").
{
  const { analyse } = require('./lib/replay.js');
  const circ = 'G21 G90 G17\nG0 Z5\nG0 X10 Y0\nG1 Z-1 F300\nG2 X10 Y0 I-10 J0 F600\nG0 Z5\nM30';
  const o = convert(circ, { xMin: 0, xMax: 113 });
  const arc = o.split('\n').filter(l => /^G1 X10\.0000 C-/.test(l));
  ok(arc.length === 8 && arc.every(l => / F76\.394/.test(l)), 'R10 circle about the axis = 8 blocks of 45 deg, X10, F = 600 mm/min along the arc');
  ok(analyse('c', circ, o, {}, true).maxDevG1 <= 0.001, 'R10 circle about the axis is exact');
  const helix = 'G21 G90 G17\nG0 Z5\nG0 X15 Y0\nG1 Z0 F300\nG3 X15 Y0 Z-2 I-15 J0 F600\nG0 Z5\nM30';
  ok(/G1 X15\.0000 C360\.0000 Z-2\.0000/.test(convert(helix, { xMin: 0, xMax: 113 })), 'helix about the axis: C turns 360, Z goes down linearly');
  const off = 'G21 G90 G17\nG0 Z5\nG0 X30 Y0\nG1 Z-1 F300\nG3 X30 Y0 I-10 J0 F600\nG0 Z5\nM30';
  ok(convert(off, { xMin: 0, xMax: 113 }).split('\n').filter(l => /^G1 /.test(l)).length > 20, 'an arc NOT centred on the axis still takes the general path');
}

// 23. (2.12.1) G16 converted: a bolt circle gives the same motion as the same holes written in X/Y;
// uncertain forms stop with the line number; G15/G16 never reach the output.
{
  const holes = [0, 60, 120, 180, 240, 300];
  const pol = 'G90 G21 G17\nG0 X0 Y0 Z50\nG16\nG81 Z-15 R2 F150\n' + holes.map(a => 'X100 Y' + a).join('\n') + '\nG80\nG15\nM30';
  const car = 'G90 G21 G17\nG0 X0 Y0 Z50\nG81 Z-15 R2 F150\n' + holes.map(a => 'X' + (100 * Math.cos(a * Math.PI / 180)).toFixed(6) + ' Y' + (100 * Math.sin(a * Math.PI / 180)).toFixed(6)).join('\n') + '\nG80\nM30';
  const mv = g => convert(g, { xMin: 0, xMax: 113 }).split('\n').filter(l => /^G[01] /.test(l)).join('\n');
  ok(mv(pol) === mv(car), 'G16 bolt circle = the same holes in X/Y');
  ok(!convert(pol, { xMin: 0, xMax: 113 }).split('\n').some(l => /\bG1[56]\b/.test(l.replace(/\([^)]*\)/g, ''))), 'G15/G16 removed from the output');
  const Q = b => 'G21 G90 G17\nG0 X10 Y0 Z5\n' + b + '\nM30';
  assert.throws(() => convert(Q('G16\nG91 G0 X10 Y30'), { xMin: 0, xMax: 113 }), /incremental G91 in polar/); n++;
  assert.throws(() => convert(Q('G16\nG0 X20'), { xMin: 0, xMax: 113 }), /both the radius \(X\) and the angle \(Y\)/); n++;
  assert.throws(() => convert(Q('G16 X6 Y6\nG0 X5 Y30'), { xMin: 0, xMax: 113 }), /G16 line itself/); n++;
  assert.throws(() => convert(Q('G1 Z-1 F100\nG16\nG3 X20 Y90 R20'), { xMin: 0, xMax: 113 }), /arcs in polar coordinate mode/); n++;
  ok(/G0 X20\.0000 C90\.0000/.test(convert(Q('G16\nG0 X20 Y90 ; side comment'), { xMin: 0, xMax: 113 })), 'G16 line with a ; comment');
}
// 24. (2.12.1) An arc with both R and I/J is refused, as LinuxCNC does ("mixed radius-ijk").
assert.throws(() => convert('G21 G90 G17\nG0 X10 Y0 Z1\nG1 Z-1 F100\nG3 X0 Y10 I-10 J0 R10\nM30', { xMin: 0, xMax: 113 }), /both R and I\/J/); n++;
// 25. (2.12.1) A radial rapid (C constant) is one block, not 0.5 mm pieces.
{
  const g0 = g => convert(g, { xMin: 0, xMax: 113 }).split('\n').filter(l => /^G0 X/.test(l));
  ok(g0('G21 G90\nG0 X0 Y0 Z5\nG0 X30 Y40\nG1 Z-1 F100\nM30').length === 3, 'rapid from the centre outward = spin C at the centre + one block');
  ok(g0('G21 G90\nG0 X50 Y50 Z5\nG0 X10 Y10\nG1 Z-1 F100\nM30').length === 2, 'rapid inward on the same ray = one block');
  ok(g0('G21 G90\nG0 X50 Y0 Z5\nG0 X0 Y50\nG1 Z-1 F100\nM30').length > 3, 'a rapid that turns C is still segmented');
}

console.log(`input: ${n} checks passed`);
