/*
 * Polar CNC — reads the Converter Settings panel into an options object for
 * PolarCNC.converter.convert(), and remembers the settings in this browser so
 * each user keeps their own machine profile between visits.
 * The converter itself never touches the DOM.
 *
 * Copyright (c) 2026 Marioskiv
 * https://github.com/Marioskiv/polar-cnc-converter
 * SPDX-License-Identifier: MIT
 */
'use strict';

var SETTINGS_FIELDS = {
  chordTol:        'inpChordTol',
  threshold:       'inpThreshold',
  xMin:            'inpXMin',
  xMax:            'inpXMax',
  toolDia:         'inpToolDia',
  centerStep:      'inpCenterStep',
  centerRetract:   'inpCenterRetract',
  retractZMachine: 'inpRetractZ',
  // 2.7.0: tilting router (layout XZC + B)
  tiltPivot:       'inpTiltPivot',
  tiltMin:         'inpTiltMin',
  tiltMax:         'inpTiltMax',
  tiltLean:        'inpTiltLean',
  ballTools:       'inpBallTools',
  toolTable:       'inpToolTable'
};
var SETTINGS_CHECKS = { autoStepover: 'chkAutoStep', invertC: 'chkInvertC', invertX: 'chkInvertX', invertTilt: 'chkInvertTilt' };
// Plain <select> settings: option key -> element id (value = option value).
var SETTINGS_SELECTS = { rotaryAxis: 'selRotaryAxis', layout: 'selLayout', tiltAxis: 'selTiltAxis' };
var CENTER_MODE_BUTTONS = {
  signed: 'btnCenterSignedX',
  index:  'btnCenterIndex',
  fill:   'btnCenterPocket',
  auto:   'btnCenterAuto'
};
var SETTINGS_STORAGE_KEY = 'polar-cnc-settings-v2';

// Options that have NO control on the page (2026-10-04: the page was simplified
// - centre-crossing buttons and pocket-fill details were removed). A loaded
// profile or the browser's saved settings may still set them; they are kept
// here and passed to the converter, so nothing in a profile is ever lost.
var profileExtras = {};

function hasControl(key) {
  if (SETTINGS_FIELDS[key]) return !!document.getElementById(SETTINGS_FIELDS[key]);
  if (SETTINGS_CHECKS[key]) return !!document.getElementById(SETTINGS_CHECKS[key]);
  if (SETTINGS_SELECTS[key]) return !!document.getElementById(SETTINGS_SELECTS[key]);
  if (key === 'xDiameter') return !!document.getElementById('selXMode');
  if (key === 'centerMode') return !!document.getElementById(CENTER_MODE_BUTTONS.auto);
  return false;
}

function readConverterOptions() {
  var o = {};
  Object.keys(profileExtras).forEach(function (k) { o[k] = profileExtras[k]; });
  Object.keys(SETTINGS_FIELDS).forEach(function (key) {
    var el = document.getElementById(SETTINGS_FIELDS[key]);
    if (el) o[key] = el.value;             // normalizeOptions parses & clamps
  });
  Object.keys(SETTINGS_CHECKS).forEach(function (key) {
    var el = document.getElementById(SETTINGS_CHECKS[key]);
    if (el) o[key] = el.checked;
  });
  Object.keys(SETTINGS_SELECTS).forEach(function (key) {
    var el = document.getElementById(SETTINGS_SELECTS[key]);
    if (el) o[key] = el.value;
  });
  var xm = document.getElementById('selXMode');
  if (xm) o.xDiameter = (xm.value === 'diameter');
  if (hasControl('centerMode')) {
    o.centerMode = 'auto';
    ['signed', 'index', 'fill'].forEach(function (mode) {
      var b = document.getElementById(CENTER_MODE_BUTTONS[mode]);
      if (b && b.classList.contains('active')) o.centerMode = mode;
    });
  }
  return o;
}

function applyConverterOptions(o) {
  // MIGRATION 2.4.0: a centre zone of exactly 2 mm was the old DEFAULT, kept
  // by the browser and written into profiles without anyone choosing it. It
  // makes lines passing near the centre cut up to ~4 mm off their path, so it
  // is upgraded to the new automatic zone. Any other value is respected.
  if (o && Number(o.threshold) === 2) { o = Object.assign({}, o); delete o.threshold; }
  profileExtras = {};
  Object.keys(o).forEach(function (k) { if (!hasControl(k)) profileExtras[k] = o[k]; });
  Object.keys(SETTINGS_FIELDS).forEach(function (key) {
    var el = document.getElementById(SETTINGS_FIELDS[key]);
    if (!el) return;
    if (key in o && o[key] !== null && o[key] !== undefined) el.value = o[key];
    else if (key === 'threshold') el.value = '';   // automatic zone
    else if (key in o && o[key] === null) el.value = '';   // e.g. a tilt value not set
  });
  Object.keys(SETTINGS_CHECKS).forEach(function (key) {
    var el = document.getElementById(SETTINGS_CHECKS[key]);
    if (el && key in o) el.checked = !!o[key];
  });
  Object.keys(SETTINGS_SELECTS).forEach(function (key) {
    var el = document.getElementById(SETTINGS_SELECTS[key]);
    if (el && o[key]) el.value = o[key];
  });
  showTiltFields();
  var xm = document.getElementById('selXMode');
  if (xm && 'xDiameter' in o) xm.value = o.xDiameter ? 'diameter' : 'radius';
  if (o.centerMode && CENTER_MODE_BUTTONS[o.centerMode]) {
    Object.keys(CENTER_MODE_BUTTONS).forEach(function (m) {
      var b = document.getElementById(CENTER_MODE_BUTTONS[m]);
      if (b) b.classList.toggle('active', m === o.centerMode);
    });
  }
}

// Browser storage is best-effort: it can be unavailable (privacy mode, files
// opened from disk in some browsers) and then the page simply starts from the
// defaults every time.
function saveConverterSettings() {
  try { window.localStorage.setItem(SETTINGS_STORAGE_KEY, JSON.stringify(readConverterOptions())); } catch (e) { /* ignore */ }
}
function restoreConverterSettings() {
  try {
    var raw = window.localStorage.getItem(SETTINGS_STORAGE_KEY);
    if (raw) applyConverterOptions(JSON.parse(raw));
  } catch (e) { /* ignore */ }
}

// The tilt fields are shown only for the layout "XZC + tilt".
function showTiltFields() {
  var sel = document.getElementById('selLayout'), box = document.getElementById('tiltFields');
  if (sel && box) box.style.display = sel.value === 'xzcb' ? '' : 'none';
}

(function wireSettingsPersistence() {
  restoreConverterSettings();
  showTiltFields();
  var lay = document.getElementById('selLayout');
  if (lay) lay.addEventListener('change', showTiltFields);
  // Load the machine's own LinuxCNC tool table (tool lengths for the tilt).
  var bTbl = document.getElementById('btnLoadToolTable'), fTbl = document.getElementById('fileToolTable');
  if (bTbl && fTbl) {
    bTbl.addEventListener('click', function () { fTbl.click(); });
    fTbl.addEventListener('change', function () {
      var f = fTbl.files && fTbl.files[0];
      if (!f) return;
      var rd = new FileReader();
      rd.onload = function () {
        var ta = document.getElementById('inpToolTable');
        if (ta) { ta.value = String(rd.result); saveConverterSettings(); }
        fTbl.value = '';
      };
      rd.readAsText(f);
    });
  }
  var ids = Object.keys(SETTINGS_FIELDS).map(function (k) { return SETTINGS_FIELDS[k]; })
    .concat(Object.keys(SETTINGS_CHECKS).map(function (k) { return SETTINGS_CHECKS[k]; }))
    .concat(Object.keys(SETTINGS_SELECTS).map(function (k) { return SETTINGS_SELECTS[k]; }))
    .concat(['selXMode']);
  ids.forEach(function (id) {
    var el = document.getElementById(id);
    if (el) el.addEventListener('change', saveConverterSettings);
  });
  Object.keys(CENTER_MODE_BUTTONS).forEach(function (m) {
    var b = document.getElementById(CENTER_MODE_BUTTONS[m]);
    if (b) b.addEventListener('click', function () { setTimeout(saveConverterSettings, 0); });
  });
})();

// ─── Machine profiles as files (2026-10-02) ─────────────────────────────────
// A profile is simply every converter option as JSON, plus a name. Loading
// one passes it through normalizeOptions, so unknown or out-of-range values
// fall back to safe defaults instead of reaching the converter.
var PROFILE_FORMAT = 'polar-cnc-profile';

function profileFromSettings(name) {
  var o = PolarCNC.converter.normalizeOptions(readConverterOptions());
  return { format: PROFILE_FORMAT, version: 1, name: name || 'my machine', options: o };
}

function applyProfile(profile) {
  if (!profile || profile.format !== PROFILE_FORMAT || !profile.options)
    throw new Error('not a polar-cnc machine profile');
  var o = PolarCNC.converter.normalizeOptions(profile.options);
  applyConverterOptions(o);
  saveConverterSettings();
  return o;
}

(function wireProfileButtons() {
  var bSave = document.getElementById('btnSaveProfile');
  var bLoad = document.getElementById('btnLoadProfile');
  var file  = document.getElementById('fileProfile');
  if (bSave) bSave.addEventListener('click', function () {
    var name = (window.prompt && window.prompt('Profile name (your machine):', 'my machine')) || 'my machine';
    var blob = new Blob([JSON.stringify(profileFromSettings(name), null, 2) + '\n'], { type: 'application/json' });
    var a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = name.replace(/[^\w.-]+/g, '-').toLowerCase() + '.polar-profile.json';
    document.body.appendChild(a); a.click(); a.remove();
  });
  if (bLoad && file) {
    bLoad.addEventListener('click', function () { file.click(); });
    file.addEventListener('change', function () {
      var f = file.files && file.files[0];
      if (!f) return;
      var rd = new FileReader();
      rd.onload = function () {
        try {
          var p = JSON.parse(rd.result);
          applyProfile(p);
          if (typeof elInfo !== 'undefined' && elInfo) {
            elInfo.textContent = 'Profile loaded: ' + (p.name || f.name) + ' \u2014 convert again to apply it.';
            elInfo.className = 'ok';
          }
        } catch (e) {
          if (typeof elInfo !== 'undefined' && elInfo) { elInfo.textContent = 'Profile not loaded: ' + e.message; elInfo.className = 'err'; }
        }
        file.value = '';
      };
      rd.readAsText(f);
    });
  }
})();
