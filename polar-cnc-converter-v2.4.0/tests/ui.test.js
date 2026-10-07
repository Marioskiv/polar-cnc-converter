/*
 * Polar CNC — test suite
 *
 * Copyright (c) 2026 Marioskiv
 * https://github.com/Marioskiv/polar-cnc-converter
 * SPDX-License-Identifier: MIT
 */
'use strict';
// Loads index.html with all its scripts in jsdom (Three.js stubbed: no WebGL
// here), clicks Convert like a user, and checks the page wiring end to end.
// Also guards that the form's default values match DEFAULT_OPTIONS.
const assert = require('assert');
const path = require('path');
const { JSDOM, ResourceLoader, VirtualConsole } = require('jsdom');
const { convert, DEFAULT_OPTIONS } = require('../src/core/converter.js');
const THREE_STUB = "window.THREE=(function(){function m(){var f=function(){};return new Proxy(f,{get:function(t,p){if(p==='domElement')return document.createElement('canvas');if(p===Symbol.toPrimitive)return function(){return 0};if(p==='then')return undefined;if(!(p in t))t[p]=m();return t[p]},set:function(t,p,v){t[p]=v;return true},apply:function(){return m()},construct:function(){return m()}})}return m()})();";
class Loader extends ResourceLoader {
  fetch(url, o) { if (/cdn\.jsdelivr\.net/.test(url)) return Promise.resolve(Buffer.from(/three\.min/.test(url) ? THREE_STUB : '')); return super.fetch(url, o); }
}
const PAGE = path.join(__dirname, '..', 'index.html');
const PROG = 'G21 G90\nG0 X50 Y0 Z2\nG1 Z-1 F300\nG1 X-50 Y0 F500\nG1 X-50 Y3\nG1 X50 Y3 F500\nG0 Z5\nM30';
async function run(setup) {
  const errors = [];
  const vc = new VirtualConsole(); vc.on('jsdomError', e => errors.push(e.message));
  const dom = await JSDOM.fromFile(PAGE, { runScripts: 'dangerously', resources: new Loader(), pretendToBeVisual: true, virtualConsole: vc });
  await new Promise(r => dom.window.addEventListener('load', r));
  const d = dom.window.document;
  const v = id => d.getElementById(id).value, c = id => d.getElementById(id).checked;
  const defaults = {
    chordTol: v('inpChordTol'), threshold: v('inpThreshold'), xMin: v('inpXMin'), xMax: v('inpXMax'),
    toolDia: v('inpToolDia'), retractZMachine: v('inpRetractZ'),
    rotaryAxis: v('selRotaryAxis'), xDiameter: v('selXMode') === 'diameter', invertC: c('chkInvertC'), invertX: c('chkInvertX'),
  };
  // Removed from the page: machine dynamics (2.2.0) and, 2026-10-04, the inert G93 button,
  // centre-crossing buttons and pocket-fill details (automatic / defaults now).
  const removed = ['inpMaxAngVel', 'inpMaxCRpm', 'inpCAccel', 'inpCornerMult', 'btnModeG93',
    'btnCenterSignedX', 'btnCenterAuto', 'btnCenterPocket', 'btnCenterIndex',
    'inpCenterStep', 'inpCenterRetract', 'chkAutoStep'].filter(id => d.getElementById(id));
  d.getElementById('cartInput').value = PROG;
  if (setup) setup(d);
  d.getElementById('btnConvert').click();
  await new Promise(r => setTimeout(r, 300));
  const res = { out: d.getElementById('polarOutput').value, info: d.getElementById('parseInfo').textContent, errors, defaults, removed };
  dom.window.close();
  return res;
}
(async () => {
  const a = await run();
  assert.deepStrictEqual(a.errors, [], 'page raised script errors');
  for (const [k, val] of Object.entries(a.defaults)) {
    const got = (typeof val === 'boolean' || k === 'rotaryAxis') ? val : (val === '' ? null : parseFloat(val));
    assert.strictEqual(got, DEFAULT_OPTIONS[k], `form default for ${k} differs from DEFAULT_OPTIONS`);
  }
  assert.deepStrictEqual(a.removed, [], 'removed controls must be gone from the page');
  assert.ok(!/C-vel/.test(a.info), 'no velocity check on the page');
  assert.strictEqual(a.out, convert(PROG, {}), 'Convert button output != converter output');
  assert.ok(/pts/.test(a.info), 'simulator did not parse the toolpath');
  const b = await run(d => { d.getElementById('inpXMin').value = '0'; });
  assert.strictEqual(b.out, convert(PROG, { xMin: 0 }), 'X Min (machining side) not wired through');
  // A profile that sets options with NO control on the page must still be honoured.
  const hidden = { centerMode: 'fill', centerStep: 0, centerRetract: 0, autoStepover: false, xMin: -10 };
  const hp = await run(d => d.defaultView.applyProfile({ format: 'polar-cnc-profile', version: 1, name: 't', options: hidden }));
  assert.strictEqual(hp.out, convert(PROG, hidden), 'profile options without a control on the page were lost');
  const pr = await run(d => { d.getElementById('selRotaryAxis').value = 'A'; d.getElementById('chkInvertC').checked = true; });
  assert.strictEqual(pr.out, convert(PROG, { rotaryAxis: 'A', invertC: true }), 'profile settings not wired through the page');
  // Machine profiles: every shipped profile loads into the form through applyProfile.
  const fs = require('fs');
  const profDir = path.join(__dirname, '..', 'profiles');
  for (const f of fs.readdirSync(profDir)) {
    const prof = JSON.parse(fs.readFileSync(path.join(profDir, f), 'utf8'));
    const p = await run(d => {
      d.defaultView.applyProfile(prof);
      d.getElementById('cartInput').value = 'G21 G90\nG0 X20 Y0 Z2\nG1 Z-1 F300\nG1 X30 F500\nG0 Z5\nM30';
    });
    assert.deepStrictEqual(p.errors, [], `profile ${f}: page errors`);
    assert.strictEqual(p.out, convert('G21 G90\nG0 X20 Y0 Z2\nG1 Z-1 F300\nG1 X30 F500\nG0 Z5\nM30', prof.options),
                       `profile ${f}: the form did not reproduce the profile's options`);
  }
  const c = await run(d => { d.getElementById('cartInput').value = 'G21 G90\nG0 X20 Y0 Z5\nG0 Z-1\nG0 X35 Y10\nG0 Z5\nM30'; });
  assert.deepStrictEqual(c.errors, [], 'page raised script errors with the material map');
  assert.ok(/RAPID CUTS MATERIAL/.test(c.info), 'rapid-cut collision warning must be shown on the page');
  assert.ok(/depth -1\.00 mm/.test(c.info), 'machined depth shown on the page');
  console.log('ui: page loads cleanly, form defaults match, buttons wired, material warnings shown, every profile loads');
})().catch(e => { console.error(e.message); process.exit(1); });
