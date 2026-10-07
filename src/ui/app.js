/*
 * Polar CNC — UI event handlers and boot.
 *
 * Copyright (c) 2026 Marioskiv
 * https://github.com/Marioskiv/polar-cnc-converter
 * SPDX-License-Identifier: MIT
 */
'use strict';

// ============================================================
// SECTION 7 - EVENT HANDLERS
// ============================================================
function updateProgress() {
  lblProg.textContent = (currentIdx + 1) + ' / ' + toolpath.length;
}

function doReset() {
  isPlaying = false;
  btnPP.textContent = '\u25B6\u2009Play';
  currentIdx  = 0;
  currentFrac = 0;
  simTime    = 0;
  elTL.value = 0;
  updateProgress();
}

// --- Convert & Simulate ---
// Flow: Cartesian text -> convertCartesianToPolar -> polar textarea
//       -> parsePolarGCode -> buildScene -> animation ready
btnConvert.addEventListener('click', function() {
  var raw = elCartInput.value.trim();
  if (!raw) {
    elInfo.textContent = 'Paste Cartesian G-code into Step 1 first.';
    elInfo.className   = 'err';
    return;
  }
  elInfo.textContent  = 'Converting & building scene...';
  elInfo.className    = '';
  btnConvert.disabled = true;

  setTimeout(function() {
    try {
      // Step A.0 — scan Cartesian G-code for XY/Z extents to size the workpiece cylinder.
      (function() {
        var xMax = 0, yMax = 0, zMin = 0, zG1Max = -Infinity;
        var isG1 = false;
        var wRe = /([XYZ])\s*([-+]?(?:\d+\.?\d*|\.\d+)(?:[Ee][+-]?\d+)?)/gi;
        var rawLines = raw.split(/\r?\n/);
        for (var li = 0; li < rawLines.length; li++) {
          var ln = rawLines[li].replace(/\(.*?\)/g,'').replace(/;.*$/,'');
          // Track G0/G1 modal state so we can separate cutting Z from rapid Z
          if (/\bG\s*0\b/i.test(ln)) isG1 = false;
          if (/\bG\s*1\b/i.test(ln)) isG1 = true;
          var m;
          wRe.lastIndex = 0;
          while ((m = wRe.exec(ln)) !== null) {
            var letter = m[1].toUpperCase();
            var val    = parseFloat(m[2]);
            if (letter === 'X' && isFinite(val)) xMax = Math.max(xMax, Math.abs(val));
            if (letter === 'Y' && isFinite(val)) yMax = Math.max(yMax, Math.abs(val));
            if (letter === 'Z' && isFinite(val)) {
              if (val < zMin) zMin = val;
              if (isG1 && val > zG1Max) zG1Max = val;  // highest cutting Z = workpiece surface
            }
          }
        }
        window._gcodeStockR = Math.ceil(Math.max(Math.max(xMax, yMax), 1));
        // Stock height:
        //   FreeCAD convention (Z positive, Z=0 = table): zG1Max = surface Z = full stock height
        //   Standard CNC (Z=0 = surface, negative = depth): |zMin| = depth of cuts
        //   Use max of both to handle either convention correctly.
        var stockH = Math.max(isFinite(zG1Max) ? zG1Max : 0, Math.abs(zMin), 1);
        window._gcodeStockH = Math.ceil(stockH);
      })();

      // Step A - convert Cartesian XY to Polar XZC (G93 inverse-time)
      var polarText = PolarCNC.converter.convert(raw, readConverterOptions());
      elPolarOut.value   = polarText;
      btnExport.disabled = false;

      // Step B - parse the polar G-code for simulation
      // The simulator reads the file the way the user's machine will: same axis
      // letter, direction and radius/diameter convention as the output profile.
      var simProfile = PolarCNC.converter.normalizeOptions(readConverterOptions());
      toolpath = PolarCNC.parser.parsePolarGCode(polarText, simProfile);
      saveConverterSettings();
      if (toolpath.length < 2) {
        elInfo.textContent = 'Warning: fewer than 2 valid moves found. Check input G-code.';
        elInfo.className   = 'err';
        btnConvert.disabled = false;
        return;
      }

      // Step C - build 3D scene from toolpath bounds
      simToolDia = simProfile.toolDia;
      buildScene(toolpath);
      doReset();
      elTL.min      = 0;
      elTL.max      = toolpath.length - 1;
      elTL.value    = 0;
      elTL.disabled = false;
      btnPP.disabled    = false;
      btnReset.disabled = false;
      updateProgress();

      // Default simulation speed starts low (3x) so playback is easy to follow;
      // the user can ramp it up with the +/- buttons or slider as needed.
      if (segTimeCum && segTimeCum.length > 1) {
        elSpeed.value = 3;
        lblSpeed.textContent = '3\u00D7';
      }
      var g1n      = toolpath.filter(function(p) { return p.type === 'G1'; }).length;
      var g0n      = toolpath.filter(function(p) { return p.type === 'G0'; }).length;
      var totalMin = segTimeCum ? (segTimeCum[segTimeCum.length - 1] / 60).toFixed(1) : '?';

      // --- Diagnostics: X travel, in the machine's own X units (as written) ---
      // Velocity checks are deliberately absent: the controller enforces its
      // own axis limits. Retract/park points are symbolic and skipped.
      var diagMaxX = -Infinity, diagMinX = Infinity, diagMaxR = 0;
      var diagMaxRpm = 0, diagRpmR = 0;
      for (var di = 0; di < toolpath.length; di++) {
        if (toolpath[di].machineRef) continue;
        if (toolpath[di].xm > diagMaxX) diagMaxX = toolpath[di].xm;
        if (toolpath[di].xm < diagMinX) diagMinX = toolpath[di].xm;
        if (Math.abs(toolpath[di].r) > diagMaxR) diagMaxR = Math.abs(toolpath[di].r);
        // Chuck speed the PROGRAM asks for (commanded time, no machine limits).
        // Near the centre this can exceed what a machine can do; the controller
        // will then slow the move down, and the cut runs below the CAM feed.
        if (di > 0 && toolpath[di].type === 'G1' && toolpath[di].durCmdSec > 0) {
          var rpmAsk = Math.abs(toolpath[di].theta - toolpath[di - 1].theta) / 360 / (toolpath[di].durCmdSec / 60);
          if (rpmAsk > diagMaxRpm) { diagMaxRpm = rpmAsk; diagRpmR = Math.abs(toolpath[di].r); }
        }
      }
      if (!isFinite(diagMaxX)) { diagMaxX = 0; diagMinX = 0; }
      var xLimitExceeded = diagMinX < simProfile.xMin - 1e-6 || diagMaxX > simProfile.xMax + 1e-6;
      document.getElementById('tMaxR').textContent = diagMaxR.toFixed(2);

      elInfo.textContent = '\u2713 ' + toolpath.length + ' pts  |  G1: ' + g1n
        + '  G0: ' + g0n + '  |  ~' + totalMin + ' min  |  max radius ' + diagMaxR.toFixed(2) + ' mm'
        + (diagMaxRpm > 0 ? '  |  peak chuck speed asked ' + diagMaxRpm.toFixed(1) + ' rpm at r=' + diagRpmR.toFixed(1) + ' mm' : '')
        + (xLimitExceeded ? '  \u26A0 X range [' + diagMinX.toFixed(1) + ', ' + diagMaxX.toFixed(1)
                            + '] exceeds travel [' + simProfile.xMin.toFixed(1) + ', ' + simProfile.xMax.toFixed(1) + ']!' : '');
      // Material removal result: a rapid that cuts material is a collision.
      var rapidCut = materialStats && materialStats.rapidCutCells > 0;
      if (materialStats) {
        elInfo.textContent += '  |  depth ' + materialStats.minZ.toFixed(2) + ' mm'
          + (rapidCut ? '  \u26A0 RAPID CUTS MATERIAL at output line(s) '
                        + materialStats.rapidLines.slice(0, 8).join(', ') + ' \u2014 shown red' : '');
      }
      elInfo.className = (xLimitExceeded || rapidCut) ? 'warn' : 'ok';
    } catch (e) {
      // FIX (2026-10-01): never leave the PREVIOUS program on screen after a
      // failed conversion — it could be exported by mistake.
      elPolarOut.value   = '';
      btnExport.disabled = true;
      elInfo.textContent = 'Error: ' + e.message;
      elInfo.className   = 'err';
      console.error(e);
    } finally {
      btnConvert.disabled = false;
    }
  }, 15);
});

// --- Export Polar G-code ---
btnExport.addEventListener('click', function() {
  var txt = elPolarOut.value;
  if (!txt) return;
  var blob = new Blob([txt], { type: 'text/plain' });
  var a    = document.createElement('a');
  a.href     = URL.createObjectURL(blob);
  a.download = 'polar_xzc_output.ngc';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(a.href);
});

// --- Play / Pause ---
btnPP.addEventListener('click', function() {
  if (!toolpath.length) return;
  if (isPlaying) {
    isPlaying = false;
    btnPP.textContent = '\u25B6\u2009Play';
  } else {
    if (currentIdx >= toolpath.length - 1) { currentIdx = 0; currentFrac = 0; simTime = 0; }
    isPlaying = true;
    btnPP.textContent = '\u23F8\u2009Pause';
  }
});

// --- Reset ---
btnReset.addEventListener('click', doReset);

// --- View Mode Toggle ---
btnView.addEventListener('click', function() {
  viewMode = viewMode === 'static' ? 'rotary' : 'static';
  if (viewMode === 'rotary') {
    btnView.textContent = '\uD83D\uDC41\u2009Mode: Rotary Mill';
    tView.textContent   = 'Rotary Mill';
    // Snap camera straight onto Z-axis looking at the front face.
    // Tool strict horizontal motion on X-axis becomes obvious.
    var snapDist = sceneMaxR * 3.2;
    camera.position.set(0, 0, snapDist);
    camera.up.set(0, 1, 0);
    controls.target.set(0, 0, 0);
    controls.update();
  } else {
    btnView.textContent = '\uD83D\uDC41\u2009Mode: Static 3D';
    tView.textContent   = 'Static 3D';
  }
});

// --- Speed slider & fine-tune buttons ---
elSpeed.addEventListener('input', function() {
  lblSpeed.textContent = elSpeed.value + '\u00D7';
});
document.getElementById('btnSpdUp').addEventListener('click', function() {
  var v = Math.min(parseInt(elSpeed.value, 10) + 1, parseInt(elSpeed.max, 10));
  elSpeed.value = v;
  lblSpeed.textContent = v + '\u00D7';
});
document.getElementById('btnSpdDn').addEventListener('click', function() {
  var v = Math.max(parseInt(elSpeed.value, 10) - 1, parseInt(elSpeed.min, 10));
  elSpeed.value = v;
  lblSpeed.textContent = v + '\u00D7';
});

// --- Feedrate Override slider ---
elOverride.addEventListener('input', function() {
  elOvrVal.textContent = elOverride.value;
});

// --- Timeline scrubber ---
elTL.addEventListener('input', function() {
  currentIdx  = parseInt(elTL.value, 10);
  currentFrac = 0;
  simTime     = segTimeCum ? segTimeCum[currentIdx] : 0;
  isPlaying   = false;
  btnPP.textContent = '\u25B6\u2009Play';
  updateProgress();
});

// --- Drag-and-drop: accept G-code files dropped anywhere on the window ---
// Handles .nc, .ngc, .gcode, .tap and any text file.
document.addEventListener('dragover', function(e) {
  e.preventDefault();
  e.dataTransfer.dropEffect = 'copy';
});
document.addEventListener('drop', function(e) {
  e.preventDefault();
  var file = e.dataTransfer.files[0];
  if (!file) return;
  var reader = new FileReader();
  reader.onload = function(ev) { elCartInput.value = ev.target.result; };
  reader.readAsText(file);
});

// --- Ctrl+Enter shortcut triggers Convert & Simulate ---
document.addEventListener('keydown', function(e) {
  if (e.ctrlKey && e.key === 'Enter') btnConvert.click();
});

// ============================================================
// BOOT
// ============================================================
initThree();
