/*
 * Polar CNC — test suite
 *
 * Copyright (c) 2026 Marioskiv
 * https://github.com/Marioskiv/polar-cnc-converter
 * SPDX-License-Identifier: MIT
 */
'use strict';
// Runs every test file; exits non-zero if any fails. Used by `npm test` and CI.
const { spawnSync } = require('child_process');
const path = require('path');
const files = ['options.test.js', 'input.test.js', 'lint.test.js', 'words.test.js', 'sim.test.js', 'material.test.js', 'golden.test.js', 'geometry.test.js', 'ui.test.js'];
let failed = 0;
for (const f of files) {
  const r = spawnSync(process.execPath, [path.join(__dirname, f)], { stdio: 'inherit' });
  if (r.status !== 0) { failed++; console.log(`FAILED: ${f}`); }
}
console.log(failed ? `\n${failed} test file(s) failed` : '\nall tests passed');
process.exit(failed ? 1 : 0);
