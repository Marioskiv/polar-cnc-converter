/*
 * Polar CNC — test suite: layout "Wrap" (router radial, the outside of a cylinder).
 *
 * Copyright (c) 2026 Marioskiv
 * https://github.com/Marioskiv/polar-cnc-converter
 * SPDX-License-Identifier: MIT
 */
'use strict';
// Every written block is replayed the way LinuxCNC runs it (X, Z and C linear in joint space)
// and mapped back onto the unrolled surface (u = Z, v = -C * R0, w = X - R0; 2.22.0: C = -Y / R0). The replayed tool
// tip must stay on the CAM path (lines exactly, arcs within the chord tolerance), and the time
// of every cutting block (1 / F under G93) must be the true tip path length over the CAM feed.
const assert = require('assert');
const { convert } = require('../src/core/converter.js');

let checks = 0;
function ok(cond, msg) { checks++; assert.ok(cond, msg); }

// the CAM path as a dense list of points (lines and arcs in the XY plane, as the CAM meant it)
function camPath(prog) {
  const pts = [];
  let p = { x: 0, y: 0, z: 0 }, feed = null;
  for (const raw of prog.split('\n')) {
    const w = {};
    raw.replace(/\(.*?\)/g, '').toUpperCase().replace(/([A-Z])\s*(-?[\d.]+)/g, (m, k, v) => { w[k] = +v; });
    if (w.F) feed = w.F;
    const g = 'G' in w ? w.G : null;
    if (g === null || g > 3) { if (!('G' in w) && ('X' in w || 'Y' in w || 'Z' in w)) {} else continue; }
    const q = { x: 'X' in w ? w.X : p.x, y: 'Y' in w ? w.Y : p.y, z: 'Z' in w ? w.Z : p.z };
    if (g === 2 || g === 3) {
      const cx = p.x + w.I, cy = p.y + w.J, r = Math.hypot(p.x - cx, p.y - cy);
      let a0 = Math.atan2(p.y - cy, p.x - cx), a1 = Math.atan2(q.y - cy, q.x - cx);
      let sw = a1 - a0;
      if (g === 2) { while (sw >= 0) sw -= 2 * Math.PI; } else { while (sw <= 0) sw += 2 * Math.PI; }
      for (let i = 0; i <= 400; i++) {
        const t = i / 400;
        pts.push({ x: cx + r * Math.cos(a0 + sw * t), y: cy + r * Math.sin(a0 + sw * t), z: p.z + (q.z - p.z) * t, cut: true });
      }
    } else if (g === 1) {
      for (let i = 0; i <= 200; i++) {
        const t = i / 200;
        pts.push({ x: p.x + (q.x - p.x) * t, y: p.y + (q.y - p.y) * t, z: p.z + (q.z - p.z) * t, cut: true });
      }
    }
    p = q;
  }
  return pts;
}

// replay the wrapped output in joint space; return [{u,v,w}] samples of the G1 blocks and the
// worst feed error (true tip length / F_g93 time against the CAM feed)
function replay(out, R0, feeds, opts) {
  const sx = opts.xDiameter ? 2 : 1, sc = opts.invertC ? 1 : -1;   // v = -C R0 (2.22.0)
  let X = null, Z = null, C = null, k = 0, worstFeed = 0;
  const samples = [];
  for (const line of out.split('\n')) {
    const m = line.match(/^(G[01])\s/);
    if (!m) continue;
    const w = {};
    line.replace(/([XZCF])(-?[\d.]+)/g, (mm, a, v) => { w[a] = +v; });
    const nX = 'X' in w ? w.X / sx : X, nZ = 'Z' in w ? w.Z : Z, nC = 'C' in w ? w.C * sc : C;
    if (m[1] === 'G1') {
      let L = 0, prev = null;
      for (let i = 0; i <= 50; i++) {
        const t = i / 50;
        const r = X + (nX - X) * t, z = Z + (nZ - Z) * t, c = (C + (nC - C) * t) * Math.PI / 180;
        const pt = { u: z, v: c * R0, w: r - R0, r: r, c: c };
        if (prev) L += Math.hypot(pt.u - prev.u, pt.w - prev.w, ((pt.r + prev.r) / 2) * (pt.c - prev.c));
        prev = pt;
        samples.push(pt);
      }
      const T = 1 / w.F, feed = feeds[k++];
      if (L > 1e-6) worstFeed = Math.max(worstFeed, Math.abs(L / T - feed) / feed);
    }
    X = nX; Z = nZ; C = nC;
  }
  return { samples, worstFeed };
}

// distance to the CAM path as a polyline (its points are dense: 400 per arc, 200 per line)
function distToPath(p, path) {
  let best = Infinity;
  for (let i = 1; i < path.length; i++) {
    const a = path[i - 1], b = path[i];
    const dx = b.x - a.x, dy = b.y - a.y, dz = b.z - a.z, L2 = dx * dx + dy * dy + dz * dz;
    let t = L2 > 0 ? ((p.u - a.x) * dx + (p.v - a.y) * dy + (p.w - a.z) * dz) / L2 : 0;
    t = Math.max(0, Math.min(1, t));
    best = Math.min(best, Math.hypot(p.u - a.x - t * dx, p.v - a.y - t * dy, p.w - a.z - t * dz));
  }
  return best;
}

const CASES = {
  'groove round the part':  'G21 G90\nG0 Z2\nG0 X10 Y0\nG1 Z-1 F300\nG1 Y125.6637 F600\nG0 Z5\nM30',
  'slot along the part':    'G21 G90\nG0 Z2\nG0 X0 Y10\nG1 Z-1.5 F300\nG1 X40 F600\nG0 Z5\nM30',
  'helix (diagonal line)':  'G21 G90\nG0 Z2\nG0 X0 Y0\nG1 Z-1 F300\nG1 X60 Y188.4956 F600\nG0 Z5\nM30',
  'ramp in depth':          'G21 G90\nG0 Z2\nG0 X0 Y0\nG1 Z0 F300\nG1 X30 Y20 Z-2 F500\nG0 Z5\nM30',
  'letter O (arcs)':        'G21 G90\nG0 Z2\nG0 X15 Y20\nG1 Z-0.5 F200\nG2 X15 Y20 I5 J0 F400\nG3 X25 Y20 I5 J0\nG0 Z5\nM30',
  'R arc, CW and CCW':      'G21 G90\nG0 Z2\nG0 X5 Y5\nG1 Z-0.8 F200\nG2 X25 Y25 I10 J10 F400\nG3 X45 Y5 I20 J0\nG0 Z5\nM30',
};

for (const R0 of [10, 30]) {
  for (const opts of [{}, { invertC: true }, { xDiameter: true }]) {
    for (const [name, prog] of Object.entries(CASES)) {
      const out = convert(prog, Object.assign({ layout: 'wrap', wrapRadius: R0, xMax: 200 }, opts));
      ok(/^\( Wrap G-code - G93/.test(out), name + ': wrap header');
      ok(out.indexOf('G93') > 0 && /G94\s+\( restore/.test(out), name + ': G93 ... G94');
      const cam = camPath(prog).filter(p => p.cut);
      // feeds of the written G1 blocks, in order: the CAM feed modal at each G1/G2/G3
      const feeds = [];
      let f = null;
      const lines = prog.split('\n');
      for (const ln of lines) {
        const mf = ln.match(/F([\d.]+)/); if (mf) f = +mf[1];
        if (/^G1\b/.test(ln)) feeds.push(f);
        if (/^G[23]\b/.test(ln)) {
          // one feed per written piece: count them from the output later
          feeds.push({ arc: f });
        }
      }
      // expand arc feeds to the number of pieces written for them
      const g1Count = out.split('\n').filter(l => /^G1\s/.test(l)).length;
      const flat = [];
      const nArcs = feeds.filter(x => typeof x === 'object').length;
      const nLines = feeds.length - nArcs;
      let perArc = nArcs ? Math.round((g1Count - nLines) / nArcs) : 0;
      for (const x of feeds) { if (typeof x === 'object') for (let i = 0; i < perArc; i++) flat.push(x.arc); else flat.push(x); }
      const r = replay(out, R0, flat, opts);
      let worst = 0;
      for (const s of r.samples) worst = Math.max(worst, distToPath(s, cam));
      const tol = /arc|O \(/.test(name) ? 0.025 * Math.max(1, (R0 + 1) / R0) + 0.01 : 0.01;
      ok(worst <= tol, `R0 ${R0} ${JSON.stringify(opts)} ${name}: tip ${worst.toFixed(4)} mm from the CAM path (max ${tol.toFixed(3)})`);
      if (nArcs <= 1 && (nArcs === 0 || (g1Count - nLines) % nArcs === 0))
        ok(r.worstFeed < 0.01, `R0 ${R0} ${name}: feed on the real surface within 1 % (${(100 * r.worstFeed).toFixed(2)} %)`);
    }
  }
}

// one straight line is one block, however long (the map is linear)
{
  const out = convert(CASES['helix (diagonal line)'], { layout: 'wrap', wrapRadius: 30, xMax: 200 });
  ok(out.split('\n').filter(l => /^G1\s/.test(l)).length === 2, 'a long helix line is one block (plus the plunge)');
  const cs = out.split('\n').filter(l => /^G1\s/.test(l)).map(l => +l.match(/C(-?[\d.]+)/)[1]);
  ok(Math.abs(cs[cs.length - 1] + 360) < 0.001, 'Y = 2 pi R0 is one full turn, C -360 (C ' + cs[cs.length - 1] + ')');
}
// a groove round the part: C goes 0 -> 240 deg at R0 30 (125.66 mm of arc), X = R0 - 1
{
  const out = convert(CASES['groove round the part'], { layout: 'wrap', wrapRadius: 30, xMax: 200 });
  ok(/G1 X29\.0000 Z10\.0000 C-240\.0000 F/.test(out), 'groove: X 29, Z 10, C -240');
  ok(/G0 X32\.0000/.test(out) && /G0 X35\.0000/.test(out), 'rapids above the surface: X = R0 + Z');
  const f = +out.match(/C-240\.0000 F([\d.]+)/)[1];
  const L = 29 * (240 * Math.PI / 180);
  ok(Math.abs(1 / f - L / 600) < 1e-6, 'groove: block time = true arc length at r 29 / feed');
}
// a rapid that changes the radius and moves round/along the part is split: out first, in last
{
  const out = convert('G21 G90\nG0 X0 Y0 Z5\nG1 Z-1 F300\nG1 X10 F500\nG0 X40 Y20 Z5\nG0 X50 Y30 Z-0.5\nM30',
                      { layout: 'wrap', wrapRadius: 20, xMax: 200 });
  const g0 = out.split('\n').filter(l => /^G0\s/.test(l));
  const iOut = g0.findIndex((l, i) => /^G0 X25\.0000$/.test(l) && /^G0 Z40/.test(g0[i + 1] || ''));   // 2.22.0: the first rapid splits too
  ok(iOut >= 0 && /^G0 Z40\.0000 C/.test(g0[iOut + 1]), 'going out: X first, then Z/C: ' + g0.join(' | '));
  const iIn = g0.findIndex(l => /^G0 Z50\.0000 C/.test(l));
  ok(iIn >= 0 && /^G0 X19\.5000$/.test(g0[iIn + 1]), 'going in: Z/C first, then X');
}
// 2.22.0: the unrolled drawing is NOT mirrored on the part. Seen from outside the bar, CAM X
// (along) x CAM Y (round) must point out of the part, as X x Y points up in the CAM. Positions
// from the written blocks, mapped with the converter's own convention x = r cos C, y = r sin C
// (the one the F test proved on the machine), along the part = +Z.
{
  const at = (prog) => {
    const out = convert('G21 G90\nG0 X0 Y0 Z5\n' + prog + '\nM30', { layout: 'wrap', wrapRadius: 20, xMax: 200 });
    let X = null, Z = null, C = null;
    for (const l of out.split('\n')) {
      if (!/^G[01]\s/.test(l)) continue;
      const w = {}; l.replace(/([XZC])(-?[\d.]+)/g, (m, a, v) => { w[a] = +v; });
      if ('X' in w) X = w.X; if ('Z' in w) Z = w.Z; if ('C' in w) C = w.C;
    }
    const c = C * Math.PI / 180;
    return [X * Math.cos(c), X * Math.sin(c), Z];
  };
  const p0 = at('G1 Z0 F100'), pX = at('G1 Z0 F100\nG1 X10'), pY = at('G1 Z0 F100\nG1 Y10');
  const a = pX.map((v, i) => v - p0[i]), b = pY.map((v, i) => v - p0[i]);
  const n = [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
  const outward = [p0[0], p0[1], 0];
  ok(n[0] * outward[0] + n[1] * outward[1] > 0, 'unrolled drawing reads the right way round (not mirrored): ' + n.map(v => v.toFixed(2)));
}
// 2.22.0: the first rapid of a program (radius unknown) is split too: out first, then along/round
{
  const out = convert('G21 G90\nG0 X10 Y30 Z5\nG1 Z-1 F100\nM30', { layout: 'wrap', wrapRadius: 20, xMax: 200 });
  const g0 = out.split('\n').filter(l => /^G0\s/.test(l));
  ok(/^G0 X25\.0000$/.test(g0[0]) && /^G0 Z10\.0000 C-85\.9437$/.test(g0[1]), 'first rapid: X first, then Z/C: ' + g0.join(' | '));
}
// 2.22.0: after a tool change the position is unknown again: the next rapid is split as well
{
  const out = convert('G21 G90\nG0 X0 Y0 Z5\nG1 Z-1 F100\nG1 X10\nG0 Z5\nM6 T2\nG0 X50 Y50 Z5\nG1 Z-1 F100\nM30',
                      { layout: 'wrap', wrapRadius: 20, xMax: 200 });
  const g0 = out.split('\n').filter(l => /^G0\s/.test(l));
  const i = g0.findIndex(l => /^G0 Z50\.0000 C/.test(l));
  ok(i > 0 && /^G0 X25\.0000$/.test(g0[i - 1]), 'after M6: X first, then Z/C: ' + g0.join(' | '));
}
// refusals: no wrap radius; Z below the chuck axis
assert.throws(() => convert(CASES['slot along the part'], { layout: 'wrap', xMax: 200 }), /Wrap radius is not set/);
checks++;
assert.throws(() => convert('G21 G90\nG0 Z2\nG0 X0 Y0\nG1 Z-12 F300\nM30', { layout: 'wrap', wrapRadius: 10, xMax: 200 }),
              /past the chuck axis/);
checks++;
// no cutting side needed for wrap; X max still reported
assert.throws(() => convert('G21 G90\nG0 Z2\nG0 X0 Y0\nG1 Z-1 F300\nG1 X10 F500\nM30',
                            { layout: 'wrap', wrapRadius: 150, xMax: 100 }), /goes past X Axis Max/);
checks++;
console.log(`wrap: ${checks} checks passed`);
