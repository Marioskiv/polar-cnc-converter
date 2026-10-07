/*
 * Polar CNC — shared UI/simulator state and DOM element references.
 * Classic script: these top-level vars are intentionally shared with
 * sim/simulator.js and ui/app.js. Loaded after the DOM (end of <body>).
 *
 * Copyright (c) 2026 Marioskiv
 * https://github.com/Marioskiv/polar-cnc-converter
 * SPDX-License-Identifier: MIT
 */
'use strict';

// ============================================================
// COORDINATE MAPPING - Polar Face-Mill
//
//   Input Cartesian:  X, Y, Z  (mm, from CAM)
//   Polar conversion: R = hypot(X,Y),  C = atan2(Y,X) deg,  Z = depth
//
//   Three.js mapping (spindle axis = Z, front face at Z=0):
//     x3 = R * cos(C_rad)   radial in face XY plane
//     y3 = R * sin(C_rad)   radial in face XY plane
//     z3 = Z                depth into front face (negative = cutting)
//
//   ROTARY MILL MODE  workpieceGroup.rotation.z = -C_rad
//     Tool cross-slide: position.set(R, 0, Z) -- Y world LOCKED TO 0
//   STATIC 3D MODE    workpieceGroup.rotation = (0,0,0)
//     Tool at (x3, y3, z3) -- full face-milled Cartesian shape
// ============================================================

// --- Global Simulation State ---
var toolpath   = [];
var g1Counts   = null;
var g0Counts   = null;
var segTimeCum = null;   // Float64Array - cumulative segment durations (seconds)
var simTime    = 0.0;    // current simulation clock (seconds)
var currentIdx = 0;
var currentFrac = 0;     // 0..1 progress from toolpath[currentIdx] toward toolpath[currentIdx+1]
var isPlaying  = false;
var viewMode   = 'rotary'; // 'static' | 'rotary'
var lastTs     = 0;

// --- DOM Refs ---
var elCartInput   = document.getElementById('cartInput');
var elPolarOut    = document.getElementById('polarOutput');
var elInfo        = document.getElementById('parseInfo');
var btnConvert    = document.getElementById('btnConvert');
var btnExport   = document.getElementById('btnExport');
var btnPP       = document.getElementById('btnPlayPause');
var btnReset    = document.getElementById('btnReset');
var btnView     = document.getElementById('btnViewMode');
var elSpeed     = document.getElementById('speedSlider');
var lblSpeed    = document.getElementById('lblSpeed');
var elOverride  = document.getElementById('feedrateSlider');
var elOvrVal    = document.getElementById('overrideVal');
var elTL        = document.getElementById('tlSlider');
var lblProg     = document.getElementById('lblProg');
var tLine       = document.getElementById('tLine');
var tMode       = document.getElementById('tMode');
var tView       = document.getElementById('tView');
var tX          = document.getElementById('tX');
var tC          = document.getElementById('tC');
var tZ          = document.getElementById('tZ');
var tF          = document.getElementById('tF');
var tTilt       = document.getElementById('tTilt');
var tTiltRow    = document.getElementById('tTiltRow');

// --- Three.js Handles ---
var scene, camera, renderer, controls;
var workpieceGroup = null;
var toolGroup      = null;
var g1LineObj      = null;
var g0LineObj      = null;
var sceneObjects   = [];
var sceneMaxR      = 60;   // updated by buildScene; used for camera snap
// Material removal (depth map) — see src/core/material.js
var simToolDia     = 6;      // set from the converter settings before buildScene
var matSim         = null;   // progressive depth map driven by the animation
var matPos         = null;   // Float32Array: mesh vertex positions we own
var matCol         = null;   // Float32Array: mesh vertex colours we own
var matGeo         = null;
var materialStats  = null;   // full-program result (rapid cuts etc.)
var matDirty       = false;  // depth map changed since last redraw
var matLastRefresh = 0;      // ms timestamp of last redraw

