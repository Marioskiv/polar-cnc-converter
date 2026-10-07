/*
 * Polar CNC — test suite
 *
 * Copyright (c) 2026 Marioskiv
 * https://github.com/Marioskiv/polar-cnc-converter
 * SPDX-License-Identifier: MIT
 */
'use strict';
// Option parsing, including the "0 is a real value" regression.
const assert = require('assert');
const { normalizeOptions, DEFAULT_OPTIONS } = require('../src/core/converter.js');
const n = normalizeOptions;
// The centre zone default is AUTOMATIC (2.4.0): half the chord tolerance.
assert.deepStrictEqual(n({}), Object.assign({}, DEFAULT_OPTIONS, { threshold: DEFAULT_OPTIONS.chordTol / 2 }), 'empty -> defaults');
assert.strictEqual(n({ chordTol: 0.05 }).threshold, 0.025, 'automatic zone follows the chord tolerance');
assert.strictEqual(n({ threshold: 2 }).threshold, 2, 'an explicit zone is respected');
assert.strictEqual(n({ threshold: '' }).threshold, DEFAULT_OPTIONS.chordTol / 2, 'an empty zone field means automatic');
assert.strictEqual(n({ xMin: '0' }).xMin, 0, 'X Min 0 must stay 0 (was silently -1000)');
assert.strictEqual(n({ centerStep: '0' }).centerStep, 0, 'Center Fill Step 0 must disable fill');
assert.strictEqual(n({ centerRetract: '0' }).centerRetract, 0, 'Center Retract 0 must mean no retract');
assert.strictEqual(n({ xMin: '5' }).xMin, 0, 'X Min clamped to <= 0');
assert.strictEqual(n({ chordTol: '' }).chordTol, DEFAULT_OPTIONS.chordTol, 'blank -> default');
assert.strictEqual(n({ chordTol: '0' }).chordTol, DEFAULT_OPTIONS.chordTol, 'invalid 0 tolerance -> default');
assert.ok(!('maxAngVel' in n({})) && !('cAccel' in n({})) && !('cornerMult' in n({})), 'machine dynamics are not converter settings');
assert.strictEqual(n({ rotaryAxis: 'a' }).rotaryAxis, 'A', 'rotary axis letter normalised');
assert.strictEqual(n({ rotaryAxis: 'Q' }).rotaryAxis, 'C', 'unknown rotary letter -> C');
assert.strictEqual(n({ invertC: true, invertX: 1, xDiameter: 'yes' }).invertX, true, 'profile flags are booleans');
assert.strictEqual(n({ centerMode: 'bogus' }).centerMode, 'auto', 'unknown mode -> auto');
assert.strictEqual(n({ autoStepover: false }).autoStepover, false);
console.log('options: all checks passed');
