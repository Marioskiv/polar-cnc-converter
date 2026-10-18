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
// the two FreeCAD runs differ only in the post's "(Output Time:...)" comment
const strip = t => t.split('\n').filter(l => !l.includes('Output Time')).join('\n');
process.exit(strip(out) === strip(read('polar.ngc')) ? 0 : 1);
