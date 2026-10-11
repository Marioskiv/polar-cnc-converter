/*
 * Polar CNC — test suite
 *
 * Copyright (c) 2026 Marioskiv
 * https://github.com/Marioskiv/polar-cnc-converter
 * SPDX-License-Identifier: MIT
 */
'use strict';
// Byte-for-byte regression: output must not change unless a change is intended.
// If you change converter behaviour ON PURPOSE, regenerate with:
//   node tests/golden.test.js --update
const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { convert } = require('../src/core/converter.js');
const FILE = path.join(__dirname, 'fixtures', 'golden.json');
const G = JSON.parse(fs.readFileSync(FILE, 'utf8'));
const update = process.argv.includes('--update');
let same = 0, changed = [];
// 2.9.0: the Tool Diameter setting was removed (the diameter comes only from the
// program). The diameter each option set used to give through the setting is now
// stated in the program, as a CAM tool comment; the outputs gained exactly the two
// tool comment lines and are otherwise byte-for-byte the same (checked at the change).
const DIA = { real: 6, wide: 6, alt: 10 };
for (const key of Object.keys(G.outputs)) {
  const [on, mode, pn] = key.split('|');
  const got = convert('(T1 D=' + DIA[on] + ')\n' + G.programs[pn], Object.assign({ centerMode: mode }, G.options[on]));
  if (got === G.outputs[key]) same++; else { changed.push(key); if (update) G.outputs[key] = got; }
}
if (update) { fs.writeFileSync(FILE, JSON.stringify(G)); console.log(`golden: updated ${changed.length} outputs`); process.exit(0); }
changed.slice(0, 5).forEach(k => console.log('  CHANGED', k));
console.log(`golden: ${same}/${same + changed.length} outputs identical`);
assert.strictEqual(changed.length, 0, 'converter output changed — run with --update only if intended');
