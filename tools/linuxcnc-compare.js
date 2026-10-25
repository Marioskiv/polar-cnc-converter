/*
 * Polar CNC — independent check against the real LinuxCNC interpreter
 *
 * Copyright (c) 2026 Marioskiv
 * https://github.com/Marioskiv/polar-cnc-converter
 * SPDX-License-Identifier: MIT
 */
'use strict';
// Runs the CAM program (XYZ mill) and the converter output (XZC, the machine .ini) through
// LinuxCNC's own stand-alone interpreter `rs274`, then compares what LinuxCNC would do:
//   - every output cutting point lies on the CAM cutting path, and every CAM cutting point is cut
//     (within the chord tolerance + 0.001 mm);
//   - every output rapid stays within 0.5 mm of some CAM move;
//   - cutting time (G93 F as LinuxCNC applies it) within 1 % of the CAM time, block speed within 5 %;
//   - dwell time equal, X inside the cutting side.
// This is a second opinion: tests/lib/replay.js shares the converter's own conventions, rs274 does not.
// Optional, never part of `npm test`.
//
// rs274 is not on npm: build it once from the LinuxCNC source of the machine's version (2.9.10):
//   git clone -b v2.9.10 --depth 1 https://github.com/LinuxCNC/linuxcnc && cd linuxcnc/src
//   ./autogen.sh && ./configure --with-realtime=uspace --disable-check-runtime-deps \
//       --enable-non-distributable=yes --disable-userspace-pci && make ../bin/rs274
// or use /usr/bin/rs274 from an installed linuxcnc-uspace.
//
// Usage: node tools/linuxcnc-compare.js --rs274 <path> [--ini <machine .ini>] [--xmin 0] [--xmax 108.961]
//            [--tol 0.025] [--air-z 0] program.ngc [more.ngc ...]
//   --ini    your machine's .ini (default: the example XZC sim config in examples/linuxcnc-vismach-xzc-lathe)
//   --air-z  only moves at or below this Z count as cutting (leaves out feed moves in the air)
const fs = require('fs'), os = require('os'), path = require('path'), cp = require('child_process');
const { convert } = require('../src/core/converter.js');

function rs274(bin, ini, text, dir) {
  const tag = Math.random().toString(36).slice(2);
  const fin = path.join(dir, tag + '.ngc'), fout = path.join(dir, tag + '.canon');
  fs.writeFileSync(fin, text);
  const r = cp.spawnSync(bin, ['-i', ini, '-g', fin, fout], { encoding: 'utf8', input: '', cwd: dir });
  const canon = fs.existsSync(fout) ? fs.readFileSync(fout, 'utf8') : '';
  for (const f of [fin, fout]) { try { fs.unlinkSync(f); } catch (e) { /* not written */ } }
  const msg = ((r.stdout || '') + (r.stderr || '')).split('\n').filter(l => l && !/^executing$/.test(l)).join(' | ');
  return { canon, err: r.status !== 0 || /error|unknown|invalid|cannot/i.test(msg) ? (msg || 'exit ' + r.status) : null };
}

// Canonical calls -> moves {kind, from, to [x,y,z,a,b,c] in mm/deg, feed, arc?}
function parseCanon(canon) {
  const moves = []; let pos = [0, 0, 0, 0, 0, 0], feed = 0, dwell = 0, k = 1, m;
  for (const l of canon.split('\n')) {
    if (/USE_LENGTH_UNITS\(CANON_UNITS_INCHES\)/.test(l)) k = 25.4;
    else if (/USE_LENGTH_UNITS\(CANON_UNITS_MM\)/.test(l)) k = 1;
    if ((m = l.match(/SET_FEED_RATE\(([-\d.]+)\)/))) feed = +m[1] * k;
    else if ((m = l.match(/DWELL\(([-\d.]+)\)/))) dwell += +m[1];
    else if ((m = l.match(/(STRAIGHT_TRAVERSE|STRAIGHT_FEED)\(([^)]*)\)/))) {
      const a = m[2].split(',').map(Number).map((v, i) => i < 3 ? v * k : v);
      moves.push({ kind: m[1] === 'STRAIGHT_FEED' ? 'feed' : 'rapid', from: pos.slice(), to: a.slice(), feed });
      pos = a;
    } else if ((m = l.match(/ARC_FEED\(([^)]*)\)/))) {   // XY plane: end1, end2, c1, c2, turn, end z, a, b, c
      const a = m[1].split(',').map(Number), to = [a[0] * k, a[1] * k, a[5] * k, a[6], a[7], a[8]];
      moves.push({ kind: 'feed', arc: { e1: a[0] * k, e2: a[1] * k, c1: a[2] * k, c2: a[3] * k, rot: a[4] }, from: pos.slice(), to, feed });
      pos = to;
    }
  }
  return { moves, dwell };
}

// A move as Cartesian points about ds apart. Polar output: X = radius, C in degrees, both linear
// in joint space (trivkins), which is what the machine really does.
function sample(mv, polar, ds) {
  const P = [], f = mv.from, t = mv.to;
  if (mv.arc) {
    const { e1, e2, c1, c2, rot } = mv.arc;
    const r0 = Math.hypot(f[0] - c1, f[1] - c2), r1 = Math.hypot(e1 - c1, e2 - c2);
    const a0 = Math.atan2(f[1] - c2, f[0] - c1); let sw = Math.atan2(e2 - c2, e1 - c1) - a0;
    if (rot > 0) { while (sw <= 1e-12) sw += 2 * Math.PI; sw += (rot - 1) * 2 * Math.PI; }
    else { while (sw >= -1e-12) sw -= 2 * Math.PI; sw -= (-rot - 1) * 2 * Math.PI; }
    const n = Math.max(2, Math.ceil(Math.abs(sw) * Math.max(r0, r1) / ds));
    for (let i = 0; i <= n; i++) { const u = i / n, a = a0 + sw * u, r = r0 + (r1 - r0) * u;
      P.push([c1 + r * Math.cos(a), c2 + r * Math.sin(a), f[2] + (t[2] - f[2]) * u]); }
    return P;
  }
  if (!polar) {
    const n = Math.max(1, Math.ceil(Math.hypot(t[0] - f[0], t[1] - f[1], t[2] - f[2]) / ds));
    for (let i = 0; i <= n; i++) { const u = i / n; P.push([0, 1, 2].map(d => f[d] + (t[d] - f[d]) * u)); }
    return P;
  }
  const L = Math.hypot(t[0] - f[0], t[2] - f[2]) + Math.abs(t[5] - f[5]) * Math.PI / 180 * Math.max(Math.abs(f[0]), Math.abs(t[0]));
  const n = Math.max(1, Math.ceil(L / ds));
  for (let i = 0; i <= n; i++) { const u = i / n, X = f[0] + (t[0] - f[0]) * u, C = (f[5] + (t[5] - f[5]) * u) * Math.PI / 180;
    P.push([X * Math.cos(C), X * Math.sin(C), f[2] + (t[2] - f[2]) * u]); }
  return P;
}

function segDist(p, a, b) {
  const ab = [b[0] - a[0], b[1] - a[1], b[2] - a[2]], ap = [p[0] - a[0], p[1] - a[1], p[2] - a[2]];
  const L2 = ab[0] ** 2 + ab[1] ** 2 + ab[2] ** 2;
  const t = L2 > 0 ? Math.max(0, Math.min(1, (ap[0] * ab[0] + ap[1] * ab[1] + ap[2] * ab[2]) / L2)) : 0;
  return Math.hypot(ap[0] - ab[0] * t, ap[1] - ab[1] * t, ap[2] - ab[2] * t);
}
function segments(moves, polar, kinds, ds) {
  const S = [];
  for (const mv of moves) { if (!kinds.includes(mv.kind)) continue;
    const P = sample(mv, polar, ds); for (let i = 1; i < P.length; i++) S.push([P[i - 1], P[i], mv]); }
  return S;
}
// Nearest-segment search on a 2 mm grid: dist(p) -> { d, feeds of the segments within 0.1 mm }
function grid(segs) {
  const C = 2, g = new Map(), key = c => c.join(',');
  segs.forEach(s => {
    const lo = [0, 1, 2].map(d => Math.floor(Math.min(s[0][d], s[1][d]) / C)), hi = [0, 1, 2].map(d => Math.floor(Math.max(s[0][d], s[1][d]) / C));
    for (let i = lo[0]; i <= hi[0]; i++) for (let j = lo[1]; j <= hi[1]; j++) for (let k = lo[2]; k <= hi[2]; k++) {
      const K = key([i, j, k]); if (!g.has(K)) g.set(K, []); g.get(K).push(s); }
  });
  return function (p) {
    let d = Infinity; const feeds = new Set(), c = p.map(v => Math.floor(v / C));
    for (let i = -1; i <= 1; i++) for (let j = -1; j <= 1; j++) for (let k = -1; k <= 1; k++) {
      for (const s of g.get(key([c[0] + i, c[1] + j, c[2] + k])) || []) {
        const e = segDist(p, s[0], s[1]); if (e < 0.1) feeds.add(s[2].feed); if (e < d) d = e; } }
    return { d, feeds: [...feeds] };
  };
}
// LinuxCNC's block time: the XYZ length if it is not zero, else the rotary length, over F.
function blockTime(mv) {
  const f = mv.from, t = mv.to;
  const lx = Math.hypot(t[0] - f[0], t[1] - f[1], t[2] - f[2]), la = Math.hypot(t[3] - f[3], t[4] - f[4], t[5] - f[5]);
  return mv.feed > 0 ? (lx > 1e-9 ? lx : la) / mv.feed : 0;
}
function cartLen(mv, polar) {
  const P = sample(mv, polar, 0.02); let s = 0;
  for (let i = 1; i < P.length; i++) s += Math.hypot(P[i][0] - P[i - 1][0], P[i][1] - P[i - 1][1], P[i][2] - P[i - 1][2]);
  return s;
}

function compare(input, opts, env) {
  const res = { issues: [] }, airZ = env.airZ;
  const cutting = mv => mv.kind === 'feed' && (airZ === undefined || Math.min(mv.from[2], mv.to[2]) <= airZ);
  const inR = rs274(env.rs274, env.millIni, input, env.dir);
  if (inR.err) { res.skip = 'the CAM program is not accepted by LinuxCNC: ' + inR.err.slice(0, 200); return res; }
  let out;
  try { out = convert(input, opts); } catch (e) { res.refused = e.message.slice(0, 200); return res; }
  const outR = rs274(env.rs274, env.ini, out, env.dir);
  if (outR.err) { res.issues.push('OUTPUT REJECTED by LinuxCNC: ' + outR.err.slice(0, 200)); return res; }
  const I = parseCanon(inR.canon), O = parseCanon(outR.canon);
  const keep = s => airZ === undefined || Math.min(s[0][2], s[1][2]) <= airZ;
  const inCut = segments(I.moves, false, ['feed'], 0.05).filter(keep), outCut = segments(O.moves, true, ['feed'], 0.05).filter(keep);
  const TOL = (opts.chordTol || 0.025) + 0.001, near = grid(inCut), cover = grid(outCut);
  const worst = (segs, f) => { let w = 0, at = null; for (const s of segs) for (const p of [s[0], s[1]]) { const d = f(p).d; if (d > w) { w = d; at = p; } } return [w, at]; };
  const fmt = (d, p) => (d === Infinity ? '> 2' : d.toFixed(4)) + ' mm at ' + p.map(v => v.toFixed(3)).join(', ');
  const [w1, p1] = worst(outCut, near), [w2, p2] = worst(inCut, cover);
  res.outToCam = w1;  res.camToOut = w2;
  if (w1 > TOL) res.issues.push('cut off the CAM path by ' + fmt(w1, p1));
  if (w2 > TOL) res.issues.push('CAM path not cut by ' + fmt(w2, p2));
  const all = grid(segments(I.moves, false, ['feed', 'rapid'], 0.05));
  let wr = 0, pr = null, first = true;
  for (const mv of O.moves) { if (mv.kind !== 'rapid') { first = false; continue; } if (first) continue;   // the first rapid starts from an unknown point
    for (const p of sample(mv, true, 0.1)) { const d = all(p).d; if (d > wr) { wr = d; pr = p; } } }
  res.rapid = wr;
  if (wr > 0.5) res.issues.push('rapid off the CAM moves by ' + fmt(wr, pr));
  let tIn = 0, tOut = 0, ws = 0, wsAt = '';
  for (const mv of I.moves) if (cutting(mv) && mv.feed > 0) tIn += cartLen(mv, false) / mv.feed;
  for (const mv of O.moves) if (cutting(mv)) {
    const L = cartLen(mv, true), T = blockTime(mv); tOut += T;
    if (T > 0 && L > 0.05) {
      const S = sample(mv, true, 1), mid = S[1] || S[0], n = near(mid);
      if (n.d < 0.1) { const devs = n.feeds.filter(F => F > 0).map(F => Math.abs(L / T / F - 1));
        const dev = devs.length ? Math.min(...devs) : 0; if (dev > ws) { ws = dev; wsAt = mid.map(v => v.toFixed(2)).join(', '); } }
    }
  }
  res.time = [tIn * 60, tOut * 60];  res.speed = ws;
  if (Math.abs(tOut - tIn) > 0.01 * tIn + 1e-4) res.issues.push('cutting time ' + (tOut * 60).toFixed(2) + ' s, CAM ' + (tIn * 60).toFixed(2) + ' s');
  if (ws > 0.05) res.issues.push('block speed ' + (ws * 100).toFixed(1) + ' % off the CAM feed at ' + wsAt);
  if (Math.abs(O.dwell - I.dwell) > 1e-6) res.issues.push('dwell ' + O.dwell + ' s, CAM ' + I.dwell + ' s');
  let xmin = Infinity, xmax = -Infinity;
  for (const mv of O.moves) { xmin = Math.min(xmin, mv.to[0]); xmax = Math.max(xmax, mv.to[0]); }
  res.x = [xmin, xmax];
  if (xmin < opts.xMin - 1e-6 || xmax > opts.xMax + 1e-6) res.issues.push('X outside the cutting side: ' + xmin.toFixed(3) + ' .. ' + xmax.toFixed(3));
  return res;
}

function main(argv) {
  const a = { xmin: 0, xmax: 108.961, tol: 0.025, ini: path.join(__dirname, '..', 'examples', 'linuxcnc-vismach-xzc-lathe', 'polarlathe-sim.ini') };
  const files = [];
  for (let i = 0; i < argv.length; i++) {
    const m = argv[i].match(/^--(rs274|ini|xmin|xmax|tol|air-z)$/);
    if (m) a[m[1]] = argv[++i]; else files.push(argv[i]);
  }
  if (!a.rs274 || !files.length) { console.log('usage: node tools/linuxcnc-compare.js --rs274 <path> [--ini <machine .ini>] [--xmin 0] [--xmax 108.961] [--tol 0.025] [--air-z Z] program.ngc ...'); return 2; }
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'polar-lc-'));
  const millIni = path.join(dir, 'mill.ini');
  fs.writeFileSync(millIni, '[RS274NGC]\nPARAMETER_FILE = mill.var\n[TRAJ]\nCOORDINATES = XYZ\nLINEAR_UNITS = mm\n[KINS]\nKINEMATICS = trivkins coordinates=XYZ\nJOINTS = 3\n');
  const env = { rs274: path.resolve(a.rs274), ini: path.resolve(a.ini), millIni, dir, airZ: a['air-z'] === undefined ? undefined : +a['air-z'] };
  const opts = { xMin: +a.xmin, xMax: +a.xmax, chordTol: +a.tol };
  let bad = 0;
  for (const f of files) {
    const r = compare(fs.readFileSync(f, 'utf8'), opts, env);
    if (r.skip || r.refused) { console.log(f + ': ' + (r.skip || 'converter refused: ' + r.refused)); continue; }
    if (r.issues.length) bad++;
    // 2.26.1: an output LinuxCNC rejects has no measurements; print the reason (it crashed here)
    if (r.camToOut === undefined) { console.log(f + ':\n  ' + r.issues.join('\n  ')); continue; }
    console.log(f + ': CAM->out ' + r.camToOut.toFixed(4) + ' mm, out->CAM ' + r.outToCam.toFixed(4) + ' mm, rapids ' + r.rapid.toFixed(3)
      + ' mm, time ' + r.time.map(t => t.toFixed(1)).join(' / ') + ' s, speed ' + (r.speed * 100).toFixed(2) + ' %, X ' + r.x.map(v => v.toFixed(2)).join(' .. ')
      + (r.issues.length ? '\n  ' + r.issues.join('\n  ') : '  OK'));
  }
  fs.rmSync(dir, { recursive: true, force: true });
  return bad ? 1 : 0;
}

if (require.main === module) process.exitCode = main(process.argv.slice(2));
module.exports = { compare, parseCanon };
