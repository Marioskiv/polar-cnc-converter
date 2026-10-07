/*
 * Polar CNC — test suite
 *
 * Copyright (c) 2026 Marioskiv
 * https://github.com/Marioskiv/polar-cnc-converter
 * SPDX-License-Identifier: MIT
 */
'use strict';
// Layout "XZC + B" (router tilting in the X-Z plane, 2.7.0). The output is
// replayed the way LinuxCNC runs it under trivkins: X, Z, B and C linear in
// joint space within each block. From every sampled joint position the BALL
// CENTRE is recovered (r = X - K sin B, z = Z - K (cos B - 1)) and its distance
// to the CAM path is measured - it must stay within the chord tolerance.
const assert = require('assert');
const { convert } = require('../src/core/converter.js');
const { intendedPath, distPtSeg } = require('./lib/replay.js');
let n = 0; const ok = (c, m) => { n++; assert.ok(c, m); };

const TOOLS = 'T1 P1 Z40 D6 ;6 mm ball\nT2 P2 Z35 D6 ;6 mm flat';
const BASE = { layout: 'xzcb', xMin: 0, xMax: 113, retractZMachine: 0, tiltPivot: 60, tiltMin: -30, tiltMax: 60,
               tiltLean: 20, toolTable: TOOLS };

// Nearest-segment search through a grid of 2 mm cells (the path has thousands
// of segments; checking all of them for every sample is too slow). Each segment
// is filed only in the cells it passes through.
function index(segs) {
  const C = 2, cells = new Map(), key = (i, j) => i * 100003 + j;
  for (const s of segs) {
    const len = Math.hypot(s.b[0] - s.a[0], s.b[1] - s.a[1]), steps = Math.max(1, Math.ceil(len / (C / 2)));
    const seen = new Set();
    for (let q = 0; q <= steps; q++) {
      const k = key(Math.floor((s.a[0] + (s.b[0] - s.a[0]) * q / steps) / C), Math.floor((s.a[1] + (s.b[1] - s.a[1]) * q / steps) / C));
      if (seen.has(k)) continue; seen.add(k);
      if (!cells.has(k)) cells.set(k, []); cells.get(k).push(s);
    }
  }
  return p => {
    const i0 = Math.floor(p[0] / C), j0 = Math.floor(p[1] / C); let d = Infinity;
    for (let i = i0 - 1; i <= i0 + 1; i++) for (let j = j0 - 1; j <= j0 + 1; j++) {
      for (const s of cells.get(key(i, j)) || []) { const e = distPtSeg(p, s); if (e < d) d = e; }
    }
    if (d > C) for (const s of segs) d = Math.min(d, distPtSeg(p, s));   // nothing near: check all (exact)
    return d;
  };
}

// Replay: returns worst G1 / G0 deviation of the recovered tip, the B range used,
// the machine X range, and lint-like facts.
function replay(prog, out, letters) {
  const L = letters || { rot: 'C', tilt: 'B' };
  const g1 = index(intendedPath(prog).filter(s => s.type === 'G1')), all = index(intendedPath(prog));
  let K = 0, st = { X: null, C: null, Z: null, B: 0 }, mode = null;
  const res = { g1: 0, worstG1: 0, worstG0: 0, bMin: 0, bMax: 0, xMin: Infinity, xMax: -Infinity, missingF: 0 };
  for (const raw of out.split('\n')) {
    const k = raw.match(/polar-cnc tilt: T\d+ K=([\d.]+)/); if (k) K = parseFloat(k[1]);
    if (/polar-cnc tilt: T\d+ is not a ball-end/.test(raw)) K = 0;
    const l = raw.replace(/\(.*?\)/g, '').trim(); if (!l || /^G53/.test(l)) { if (/^G53/.test(l)) st.Z = null; continue; }
    const g = l.match(/^G0*([01])\b/); if (!g) continue; mode = g[1] === '0' ? 'G0' : 'G1';
    const w = c => { const m = l.match(new RegExp('\\b' + c + '(-?[0-9.]+)')); return m ? parseFloat(m[1]) : null; };
    const nx = w('X') ?? st.X, nc = w(L.rot) ?? st.C, nz = w('Z') ?? st.Z, nb = w(L.tilt) ?? st.B;
    if (mode === 'G1') { res.g1++; if (w('F') === null) res.missingF++; }
    if (nx !== null) { res.xMin = Math.min(res.xMin, nx); res.xMax = Math.max(res.xMax, nx); }
    res.bMin = Math.min(res.bMin, nb); res.bMax = Math.max(res.bMax, nb);
    if (st.X !== null && st.C !== null && st.Z !== null && nz !== null) {
      const target = mode === 'G1' ? g1 : all;
      for (let i = 1; i <= 16; i++) {
        const t = i / 16, X = st.X + (nx - st.X) * t, C = (st.C + (nc - st.C) * t) * Math.PI / 180,
              Z = st.Z + (nz - st.Z) * t, B = (st.B + (nb - st.B) * t) * Math.PI / 180;
        const r = X - K * Math.sin(B), z = Z - K * (Math.cos(B) - 1);
        const p = [r * Math.cos(C), r * Math.sin(C), z];
        const d = target(p);
        if (mode === 'G1') res.worstG1 = Math.max(res.worstG1, d); else res.worstG0 = Math.max(res.worstG0, d);
      }
    }
    st = { X: nx, C: nc, Z: nz, B: nb };
  }
  return res;
}

// 1. lean 0: the tilt layout gives the XZC motion, no B words
const P1 = '(T1 D=6. CR=3.)\nG21 G90\nT1 M6\nG0 X40 Y0 Z5\nG1 Z-1 F600\nG1 X10 Y20\nG2 X-15.6205 Y8 I-10 J-12\nG0 Z5\nM30';
const xzc = convert(P1, { xMin: 0, xMax: 113, retractZMachine: 0 }).split('\n').filter(l => /^G[01] /.test(l));
const b0 = convert(P1, Object.assign({}, BASE, { tiltLean: 0 })).split('\n').filter(l => /^G[01] /.test(l));
ok(JSON.stringify(xzc) === JSON.stringify(b0), 'lean 0 = the XZC motion, line for line');
ok(!b0.some(l => / B/.test(l)), 'lean 0 writes no B');

// 2. ball-end lean: the ball centre stays on the CAM path (lines, arcs, pole, ramps)
const progs = [
  P1,
  '(T1 D=6.)\nG21 G90\nT1 M6\nG0 X80 Y0 Z5\nG1 Z-2 F800\nG1 X-0.5 Y0\nG1 X-0.5 Y30\nG3 X0 Y-30 I0.5 J-30\nG1 X60 Y-60 Z-3\nG0 Z10\nM30',
  '(T1 D=6.)\nG21 G90\nT1 M6\nG0 X20 Y20 Z5\nG1 Z-1 F500\nG1 X-20 Y20\nG1 X-20 Y-20\nG1 X20 Y-20\nG1 X20 Y20\nG0 Z5\nG0 X95 Y10\nG1 Z-1 F300\nG2 X95 Y10 I-5 J0\nG0 Z5\nM30',
];
let seed = 99; const rnd = () => { seed = (seed * 1103515245 + 12345) % 2147483648; return seed / 2147483648; };
for (let p = 0; p < 40; p++) {
  const L = ['(T1 D=6.)', 'G21 G90', 'T1 M6']; let x = (rnd() - 0.5) * 120, y = (rnd() - 0.5) * 120;
  L.push(`G0 X${x.toFixed(3)} Y${y.toFixed(3)} Z5`, 'G1 Z-1 F700');
  for (let k = 0; k < 12; k++) {
    if (rnd() < 0.6) { x = (rnd() - 0.5) * 140; y = (rnd() - 0.5) * 140; if (rnd() < 0.2) { x *= 0.01; y *= 0.01; }
      L.push(`G1 X${x.toFixed(3)} Y${y.toFixed(3)} Z${(-rnd() * 4).toFixed(3)}`); }
    else { const R = 2 + rnd() * 25, a = rnd() * 6.28, cx = x - R * Math.cos(a), cy = y - R * Math.sin(a), b = a + (rnd() - 0.5) * 4;
      const ex = cx + R * Math.cos(b), ey = cy + R * Math.sin(b);
      L.push(`${rnd() < 0.5 ? 'G2' : 'G3'} X${ex.toFixed(4)} Y${ey.toFixed(4)} I${(cx - x).toFixed(4)} J${(cy - y).toFixed(4)}`); x = ex; y = ey; }
  }
  L.push('G0 Z10', 'M30'); progs.push(L.join('\n'));
}
let worst = 0, worstR = 0, bMax = 0, xMax = -Infinity, xMin = Infinity;
for (const p of progs) for (const lean of [20, -20, 45]) {
  const out = convert(p, Object.assign({}, BASE, { tiltLean: lean }));
  const r = replay(p, out);
  worst = Math.max(worst, r.worstG1); worstR = Math.max(worstR, r.worstG0);
  bMax = Math.max(bMax, Math.abs(r.bMax), Math.abs(r.bMin)); xMax = Math.max(xMax, r.xMax); xMin = Math.min(xMin, r.xMin);
  ok(r.missingF === 0, 'F on every G1');
}
ok(worst <= 0.026, `ball centre on the CAM path while tilting: worst ${worst.toFixed(4)} mm`);
ok(worstR <= 0.6, `rapids while tilting stay near their line: worst ${worstR.toFixed(4)} mm`);
ok(bMax > 19, 'the tool really leans');
// 3. limits: B inside its travel, machine X inside its travel (when upright fits)
ok(xMax <= 113 + 1e-4 && xMin >= -1e-4, `machine X stays in [0, 113]: ${xMin.toFixed(3)} .. ${xMax.toFixed(3)}`);
const lim = replay(progs[1], convert(progs[1], Object.assign({}, BASE, { tiltLean: 50 })));
ok(lim.bMax <= 50 + 1e-4, 'B never past the wanted lean');
const narrow = convert(progs[1], Object.assign({}, BASE, { tiltLean: 50, tiltMax: 10 }));
ok(replay(progs[1], narrow).bMax <= 10 + 1e-4, 'B never past its travel');
// near the X limit the lean is reduced, not the travel exceeded
const edge = '(T1 D=6.)\nG21 G90\nT1 M6\nG0 X100 Y0 Z5\nG1 Z-1 F500\nG1 X110 Y0\nG0 Z5\nM30';
const er = replay(edge, convert(edge, Object.assign({}, BASE, { tiltLean: 40 })));
ok(er.xMax <= 113 + 1e-4 && er.worstG1 <= 0.026, `lean reduced near the X limit (X max ${er.xMax.toFixed(3)})`);

// 4. a flat tool does not lean
const flat = convert(P1.replace(/T1/g, 'T2').replace('CR=3.', 'CR=0.'), BASE);
ok(/T2 is not a ball-end tool/.test(flat) && !flat.split('\n').some(l => /^G[01] .* B/.test(l)), 'flat end mill stays at B 0');

// 5. upright at a machine retract, before a tool change and at the end
const tc = '(T1 D=6.)\nG21 G90\nT1 M6\nG0 X50 Y0 Z5\nG1 Z-1 F500\nG1 X20 Y10\nG0 Z5\nT2 M6\nG0 X30 Y0 Z5\nG1 Z-1 F500\nG1 X40 Y0\nG0 Z5\nT1 M6\nG0 X50 Y0 Z5\nG1 Z-1 F500\nG1 X10 Y5\nG0 Z5\nG53 G0 Z0\nG0 X60 Y0\nG0 Z5\nG1 Z-1 F500\nG1 X30 Y3\nG0 Z10\nM30';
const tco = convert(tc, BASE).split('\n');
const bAt = i => { let b = 0; for (let k = 0; k <= i; k++) { const m = tco[k].match(/^G[01] .*\bB(-?[\d.]+)/) || tco[k].match(/^G0 B(-?[\d.]+)/); if (m) b = parseFloat(m[1]); } return b; };
tco.forEach((l, i) => { if (/^T\d+ M6/.test(l)) ok(Math.abs(bAt(i)) < 1e-4, 'B is 0 at the tool change line ' + (i + 1)); });
ok(tco.some(l => /^G0 B0\.0000 +\( upright after the retract \)/.test(l)), 'upright after the machine retract');
const endIdx = tco.findIndex(l => /^G94 /.test(l));
ok(Math.abs(bAt(endIdx)) < 1e-4, 'B is 0 at the program end');
ok(replay(tc, tco.join('\n')).worstG1 <= 0.026, 'tool changes: ball centre still on the path');

// 6. letters and direction
const inv = convert(progs[1], Object.assign({}, BASE, { invertTilt: true, tiltMin: -60, tiltMax: 30, tiltAxis: 'A' }));
const ri = replay(progs[1], inv.replace(/\bA(-?[\d.]+)/g, (m, v) => 'B' + (-parseFloat(v)).toFixed(4)));
ok(ri.worstG1 <= 0.026 && /\bA-/.test(inv), 'tilt letter A and inverted direction');

// 7. missing machine data is refused, never assumed
for (const [what, o] of [['pivot', { tiltPivot: '' }], ['travel', { tiltMax: '' }],
                         ['tool length', { toolTable: 'T1 P1 D6 ;ball no length' }]]) {
  let msg = null; try { convert(P1, Object.assign({}, BASE, o)); } catch (e) { msg = e.message; }
  ok(msg && /Tilt layout/.test(msg), 'missing ' + what + ' is refused: ' + msg);
}
let same = null; try { convert(P1, Object.assign({}, BASE, { rotaryAxis: 'B' })); } catch (e) { same = e.message; }
ok(same && /same letter/.test(same), 'rotary and tilt letter must differ');

console.log(`tilt: ${n} checks passed (ball centre worst ${worst.toFixed(4)} mm, rapids ${worstR.toFixed(3)} mm, |B| up to ${bMax.toFixed(1)} deg)`);
