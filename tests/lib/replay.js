/*
 * Polar CNC — test suite
 *
 * Copyright (c) 2026 Marioskiv
 * https://github.com/Marioskiv/polar-cnc-converter
 * SPDX-License-Identifier: MIT
 */
// Replays converter output the way LinuxCNC executes it under trivkins
// (X, C, Z interpolated linearly in joint space, per block), maps every point
// back to Cartesian with LinuxCNC rosekins forward kinematics
// (x = r cos C, y = r sin C) and measures the distance to the path the CAM
// asked for. Pure Node, no browser.
'use strict';
// ---------- intended Cartesian path from input program ----------
function intendedPath(gcode) {
  const segs = []; let x = 0, y = 0, z = 0, mode = 'G0';
  for (let raw of gcode.split('\n')) {
    const l = raw.replace(/\(.*?\)/g, '').toUpperCase().trim(); if (!l) continue;
    const g = l.match(/G0*([0-3])(?![0-9.])/); if (g) mode = 'G' + g[1];
    const num = k => { const m = l.match(new RegExp(k + '(-?[0-9.]+)')); return m ? parseFloat(m[1]) : null; };
    const nx = num('X') ?? x, ny = num('Y') ?? y, nz = num('Z') ?? z;
    const hasIJ = num('I') !== null || num('J') !== null, R = num('R');
    const isArc = (mode === 'G2' || mode === 'G3') && (hasIJ || R !== null);
    if (!isArc && nx === x && ny === y && nz === z) continue;
    if (isArc) {
      // Centre from I/J, or (2.4.0) from R: the centre lies on the perpendicular
      // bisector of the chord; RS274: R > 0 = the shorter arc (<= 180 deg),
      // R < 0 = the longer one. Before, R arcs were checked as straight lines,
      // so their conversion was never really validated.
      let cx, cy;
      if (hasIJ) { cx = x + (num('I') ?? 0); cy = y + (num('J') ?? 0); }
      else {
        const mx = (x + nx) / 2, my = (y + ny) / 2, hx = nx - x, hy = ny - y, c = Math.hypot(hx, hy);
        const h = Math.sqrt(Math.max(R * R - (c / 2) * (c / 2), 0));
        const cw = mode === 'G2', small = R > 0;
        const side = (cw === small) ? 1 : -1;           // which side of the chord the centre is on
        cx = mx + side * h * (hy / c); cy = my - side * h * (hx / c);
      }
      const r = Math.hypot(x - cx, y - cy);
      let a0 = Math.atan2(y - cy, x - cx), a1 = Math.atan2(ny - cy, nx - cx);
      if (mode === 'G2') { while (a1 >= a0 - 1e-12) a1 -= 2 * Math.PI; } else { while (a1 <= a0 + 1e-12) a1 += 2 * Math.PI; }
      const n = 400; let px = x, py = y, pz = z;
      for (let i = 1; i <= n; i++) {
        const t = i / n, a = a0 + (a1 - a0) * t;
        const qx = cx + r * Math.cos(a), qy = cy + r * Math.sin(a), qz = z + (nz - z) * t;
        segs.push({ type: 'G1', a: [px, py, pz], b: [qx, qy, qz] }); px = qx; py = qy; pz = qz;
      }
    } else segs.push({ type: mode === 'G0' ? 'G0' : 'G1', a: [x, y, z], b: [nx, ny, nz] });
    x = nx; y = ny; z = nz;
  }
  return segs;
}
function distPtSeg(p, s) {
  const [ax, ay, az] = s.a, [bx, by, bz] = s.b;
  const dx = bx - ax, dy = by - ay, dz = bz - az, L2 = dx * dx + dy * dy + dz * dz;
  let t = L2 > 0 ? ((p[0] - ax) * dx + (p[1] - ay) * dy + (p[2] - az) * dz) / L2 : 0;
  t = Math.max(0, Math.min(1, t));
  return Math.hypot(p[0] - (ax + t * dx), p[1] - (ay + t * dy), p[2] - (az + t * dz));
}

// ---------- analyse converter output ----------
function analyse(name, gcode, out, opts = {}, quiet = false) {
  const intended = intendedPath(gcode);
  const g1Int = intended.filter(s => s.type === 'G1');
  const allInt = intended;
  let r = null, c = null, z = null, mode = null;
  const res = { blocks: 0, g0: 0, g1: 0, maxDevG1: 0, maxDevG0: 0, worstG1: null, worstG0: null,
                missingF: 0, badF: 0, nan: 0, maxCstep: 0, warnings: 0, fill: 0 };
  let inFill = false;
  for (const raw of out.split('\n')) {
    const lraw = raw.trim();
    if (/\(.*center.*fill|pocket/i.test(lraw)) res.fill++;
    if (/WARNING/.test(lraw)) res.warnings++;
    const l = lraw.replace(/\(.*?\)/g, '').trim(); if (!l) continue;
    const g = l.match(/^G0*([01])\b/); if (g) mode = g[1] === '0' ? 'G0' : 'G1';
    const num = k => { const m = l.match(new RegExp('\\b' + k + '(-?[0-9.]+)')); return m ? parseFloat(m[1]) : null; };
    const nr = num('X'), nc = num('C'), nz = num('Z'), f = num('F');
    if (nr === null && nc === null && nz === null) continue;
    if ([nr, nc, nz, f].some(v => v !== null && !isFinite(v))) res.nan++;
    const R1 = nr ?? r, C1 = nc ?? c, Z1 = nz ?? z;
    if (r !== null && c !== null && z !== null) {
      res.blocks++;
      if (mode === 'G1') { res.g1++; if (f === null) res.missingF++; else if (f <= 0) res.badF++; } else res.g0++;
      res.maxCstep = Math.max(res.maxCstep, Math.abs(C1 - c));
      // sample block in JOINT space, map with rosekins forward kinematics
      const N = 24; let worst = 0, worstPt = null;
      const target = mode === 'G1' ? g1Int : allInt;
      for (let i = 1; i < N; i++) {
        const t = i / N, rr = r + (R1 - r) * t, cc = (c + (C1 - c) * t) * Math.PI / 180, zz = z + (Z1 - z) * t;
        const p = [rr * Math.cos(cc), rr * Math.sin(cc), zz];
        let d = Infinity; for (const s of target) { const e = distPtSeg(p, s); if (e < d) d = e; if (d < 1e-6) break; }
        if (d > worst) { worst = d; worstPt = p.map(v => +v.toFixed(3)); }
      }
      if (mode === 'G1') { if (worst > res.maxDevG1) { res.maxDevG1 = worst; res.worstG1 = { line: l, at: worstPt }; } }
      else if (worst > res.maxDevG0) { res.maxDevG0 = worst; res.worstG0 = { line: l, at: worstPt }; }
    }
    r = R1; c = C1; z = Z1;
  }
  if (!quiet) console.log(`\n### ${name}`);
  if (!quiet) console.log(`  blocks=${res.blocks} (G1 ${res.g1}, G0 ${res.g0})  NaN=${res.nan}  G1-missing-F=${res.missingF}  F<=0=${res.badF}  WARN lines=${res.warnings}`);
  if (!quiet) console.log(`  max path deviation  G1: ${res.maxDevG1.toFixed(4)} mm   G0: ${res.maxDevG0.toFixed(4)} mm   max |dC| per block: ${res.maxCstep.toFixed(2)} deg`);
  if (!quiet && res.maxDevG1 > (opts.g1Tol ?? 0.06)) console.log(`  !! worst G1: ${JSON.stringify(res.worstG1)}`);
  if (!quiet && res.maxDevG0 > (opts.g0Tol ?? 0.6)) console.log(`  !! worst G0: ${JSON.stringify(res.worstG0)}`);
  return res;
}

module.exports = { intendedPath, analyse };
