/*
 * Polar CNC — test suite
 *
 * Copyright (c) 2026 Marioskiv
 * https://github.com/Marioskiv/polar-cnc-converter
 * SPDX-License-Identifier: MIT
 */
'use strict';
// G-code validity of the OUTPUT, line by line, against rules the LinuxCNC
// interpreter enforces. Added after a real program failed with
// "Nested comment found": the converter had copied "G21 (mm)" into its own
// comment. Runs over every golden program AND real-world inputs with comments.
const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { convert } = require('../src/core/converter.js');

function lintLine(line) {
  const errs = [];
  let depth = 0, code = '';
  for (const ch of line) {
    if (ch === '(') { depth++; if (depth > 1) errs.push('nested comment'); continue; }
    if (ch === ')') { if (depth === 0) errs.push('unmatched )'); depth = Math.max(0, depth - 1); continue; }
    if (depth === 0) code += ch;
  }
  if (depth > 0) errs.push('unclosed comment');
  code = code.replace(/;.*$/, '').trim().toUpperCase();
  if (!code || code === '%') return errs;
  const words = code.match(/[A-Z]\s*[-+]?[\d.]+/g) || [];
  const rest = code.replace(/[A-Z]\s*[-+]?[\d.]+/g, '').trim();
  if (rest) errs.push('text outside a comment: "' + rest + '"');
  const seen = {}; let motion = 0;
  for (const w of words) {
    const L = w[0], v = parseFloat(w.slice(1));
    if (L === 'G') { if ([0, 1, 2, 3].includes(v)) motion++; continue; }
    if (L === 'M') continue;
    if (seen[L]) errs.push('two ' + L + ' words');
    seen[L] = true;
  }
  if (motion > 1) errs.push('two motion G-codes on one line');
  return errs;
}

function lintProgram(out) {
  const problems = [];
  let g93 = false;
  out.split('\n').forEach((line, i) => {
    lintLine(line).forEach(e => problems.push(`line ${i + 1}: ${e}: ${line}`));
    const code = line.replace(/\(.*?\)/g, '').toUpperCase();
    if (/\bG93\b/.test(code)) g93 = true;
    if (/\bG94\b/.test(code)) g93 = false;
    if (g93 && /\bG0*[123]\b/.test(code) && !/\bF[-\d.]/.test(code))
      problems.push(`line ${i + 1}: G93 move without F: ${line}`);
  });
  return problems;
}

let n = 0, programs = 0;
const ok = (c, m) => { n++; assert.ok(c, m); };

// 1. Every golden program, with every option set it is tested under.
const G = JSON.parse(fs.readFileSync(path.join(__dirname, 'fixtures', 'golden.json'), 'utf8'));
for (const key of Object.keys(G.outputs)) {
  const [on, mode, pn] = key.split('|');
  const p = lintProgram(convert(G.programs[pn], Object.assign({ centerMode: mode }, G.options[on])));
  programs++;
  ok(p.length === 0, `${key}: ${p.slice(0, 3).join(' | ')}`);
}

// 2. Real-world inputs with comments everywhere (the program that failed on the machine).
const real = {
  'benchmark-comments.ngc': fs.readFileSync(path.join(__dirname, 'fixtures', 'benchmark-comments.ngc'), 'utf8'),
  'tool change without a diameter': 'G21 G90\nT5 M6 (no D here)\nG0 X20 Y0 Z2\nG1 Z-1 F100\nG1 X30 F300\nM30',
  'comments on every kind of line':
    '%\n(header)\nG90 G94 G17 (setup)\nG21 (mm)\nG53 G0 Z0 (retract)\nT1 M6 (tool)\nS18000 M3 (spindle)\nG54 (wcs)\n' +
    'G0 X40 Y0 (start)\nG43 Z15 H1 (length)\nG0 Z5\nG1 Z-1 F300 (plunge)\nG1 X50 F500 (cut) ; note\n' +
    'G98 G81 X30 Y10 Z-5 R2 F100 (drill)\nG80 (cancel)\nG0 Z15\nG28 G91 Z0 (home z)\nG90\nM5 (stop)\nM30 (end)\n%',
};
for (const [name, g] of Object.entries(real)) {
  const p = lintProgram(convert(g, { xMin: 0, xMax: 113, retractZMachine: 590 }));
  programs++;
  ok(p.length === 0, `${name}: ${p.join(' | ')}`);
}

// 3. The linter itself catches what it must (so a pass means something).
ok(lintLine('( absorbed modal from: G21 (mm) )').includes('nested comment'), 'linter detects nesting');
ok(lintLine('G1 X1 X2 F10').includes('two X words'), 'linter detects duplicate words');
ok(lintProgram('G93\nG1 X1 C2').length === 1, 'linter detects a G93 move without F');

console.log(`lint: ${programs} converted programs, every output line valid (${n} checks)`);
