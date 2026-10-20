/*
 * Polar CNC — used by tests/freecad/run.sh: converts FreeCAD's own LinuxCNC output with the Node
 * converter and compares it with what the FreeCAD post wrote. Exit 0 when they are the same.
 *
 * Copyright (c) 2026 Marioskiv
 * https://github.com/Marioskiv/polar-cnc-converter
 * SPDX-License-Identifier: MIT
 */
'use strict';
const fs = require('fs');
const path = require('path');
const { convert } = require('../../src/core/converter.js');
const dir = process.argv[2];
const read = f => fs.readFileSync(path.join(dir, f), 'utf8');
const out = convert(read('cartesian.ngc'), JSON.parse(read('options.json')));
// the two FreeCAD runs differ only in the post's "(Output Time:...)" comment; the FreeCAD post
// also adds the operator's setup lines from the Job, the park before each tool change (a comment
// and two moves) and an M5 before the program end (not the converter's)
const strip = t => {
  const ls = t.split('\n').filter(l => !l.includes('Output Time') && !/^\( (Setup|Note|Chuck): /.test(l));
  const out = [];
  for (let i = 0; i < ls.length; i++) {
    if (/^\( tool change: /.test(ls[i])) { i += 2; continue; }
    if (ls[i] === 'M5' && /^M(0*2|30)\b/.test(ls[i + 1] || '')) continue;
    out.push(ls[i]);
  }
  return out.join('\n');
};
process.exit(strip(out) === strip(read('polar.ngc')) ? 0 : 1);
