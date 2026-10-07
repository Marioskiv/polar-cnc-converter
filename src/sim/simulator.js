/*
 * Polar CNC — Three.js 3D simulator: scene setup, scene builder,
 * per-frame updater and the feedrate-based animation loop.
 * Uses the shared state declared in ui/state.js.
 *
 * Copyright (c) 2026 Marioskiv
 * https://github.com/Marioskiv/polar-cnc-converter
 * SPDX-License-Identifier: MIT
 */
'use strict';

// ============================================================
// SECTION 3 - THREE.JS INIT
// ============================================================
function initThree() {
  var canvas = document.getElementById('c3d');
  renderer = new THREE.WebGLRenderer({ canvas: canvas, antialias: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  scene = new THREE.Scene();
  scene.background = new THREE.Color(0x0d0d0d);
  var w = canvas.clientWidth, h = canvas.clientHeight || 1;
  camera = new THREE.PerspectiveCamera(50, w / h, 0.01, 100000);
  camera.position.set(60, 60, 200);
  camera.lookAt(0, 0, 0);
  controls = new THREE.OrbitControls(camera, renderer.domElement);
  controls.enableDamping      = true;
  controls.dampingFactor      = 0.08;
  controls.screenSpacePanning = true;
  controls.minDistance        = 1;
  controls.maxDistance        = 50000;
  scene.add(new THREE.AmbientLight(0xffffff, 0.45));
  var dl1 = new THREE.DirectionalLight(0xffffff, 0.85);
  dl1.position.set(100, 150, 200); scene.add(dl1);
  var dl2 = new THREE.DirectionalLight(0x4477cc, 0.25);
  dl2.position.set(-150, -120, -200); scene.add(dl2);
  window.addEventListener('resize', onResize);
  onResize();
  requestAnimationFrame(animLoop);
}

function onResize() {
  var c = renderer.domElement;
  var w = c.clientWidth, h = c.clientHeight || 1;
  if (c.width !== w || c.height !== h) {
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
  }
}

// ============================================================
// SECTION 4 - SCENE BUILDER (called once per Convert)
// ============================================================
function clearScene() {
  sceneObjects.forEach(function(obj) {
    scene.remove(obj);
    obj.traverse(function(child) {
      if (child.geometry) child.geometry.dispose();
      if (child.material) {
        var mats = Array.isArray(child.material) ? child.material : [child.material];
        mats.forEach(function(m) { m.dispose(); });
      }
    });
  });
  sceneObjects   = [];
  workpieceGroup = null;
  toolGroup      = null;
  g1LineObj      = null;
  g0LineObj      = null;
  segTimeCum     = null;
}

function reg(obj) { scene.add(obj); sceneObjects.push(obj); return obj; }

var simHasTilt = false;   // the program uses the tilt axis (shows the Tilt telemetry row)
function buildScene(pts) {
  clearScene();
  simHasTilt = pts.some(function (p) { return Math.abs(p.tilt || 0) > 1e-6; });

  // Bounds from toolpath
  var maxR = 1, zMin = Infinity, zMax = -Infinity;
  var g1ZMax = -Infinity;  // highest Z of G1 cutting moves = workpiece top surface
  pts.forEach(function(p) {
    if (Math.abs(p.r) > maxR) maxR = Math.abs(p.r);   // Signed-X can make r negative
    if (p.z < zMin) zMin = p.z;
    if (p.z > zMax) zMax = p.z;
    if (p.type === 'G1' && p.z > g1ZMax) g1ZMax = p.z;
  });
  sceneMaxR = maxR;
  if (!isFinite(zMin))   zMin   = 0;
  if (!isFinite(zMax))   zMax   = 0;
  if (!isFinite(g1ZMax)) g1ZMax = zMin;

  // Stock sized from Cartesian G-code scan; fall back to toolpath bounds if not set
  var cylR       = (window._gcodeStockR > 0) ? window._gcodeStockR : Math.max(maxR, 1);
  var stockDepth = (window._gcodeStockH > 0) ? window._gcodeStockH : Math.max(Math.abs(g1ZMax), Math.abs(zMin), 1);

  // surfaceZ: Z of the workpiece TOP FACE (where the tool first touches the material).
  //   = max Z of G1 cutting moves (not G0 rapids which are above the surface).
  //   FreeCAD convention (Z=30 surface, Z=35 retract): g1ZMax=30 → surfaceZ=30.
  //   Standard CNC (Z=0 surface, Z=-5 depth): g1ZMax=0 → surfaceZ=0.
  var surfaceZ = Math.max(g1ZMax, 0);

  // Workpiece group - rotation.z drives spindle in Rotary Mill Mode
  workpieceGroup = reg(new THREE.Group());

  // Cylinder body — semi-transparent so the toolpath inside is visible
  var cylMesh = new THREE.Mesh(
    new THREE.CylinderGeometry(cylR, cylR, stockDepth, 64, 1, false),
    new THREE.MeshPhongMaterial({
      color: 0x3a7ab8, transparent: true, opacity: 0.45,
      side: THREE.DoubleSide, depthWrite: false
    })
  );
  cylMesh.rotation.x = Math.PI / 2;
  cylMesh.position.z = surfaceZ - stockDepth / 2;
  workpieceGroup.add(cylMesh);

  // Top face disc at the cutting surface (surfaceZ)
  var faceMesh = new THREE.Mesh(
    new THREE.CircleGeometry(cylR, 64),
    new THREE.MeshPhongMaterial({
      color: 0x2a5a8a, transparent: true, opacity: 0.40,
      side: THREE.DoubleSide, depthWrite: false
    })
  );
  faceMesh.position.z = surfaceZ;
  workpieceGroup.add(faceMesh);

  // ── Material removal depth map (2026-10-01) ─────────────────────────────
  // A height grid fixed to the part (inside workpieceGroup, so it turns with
  // the chuck). It replaces the plain top face. One full run gives the
  // program-wide result (e.g. rapids that cut material); a second instance is
  // advanced in step with the animation.
  matSim = null; materialStats = null;
  if (window.PolarCNC && PolarCNC.material) {
    var matCfg = { stockR: cylR, surfaceZ: surfaceZ, toolDia: simToolDia };
    var fullRun = PolarCNC.material.createMaterial(matCfg);
    fullRun.advanceTo(pts, pts.length - 1);
    materialStats = fullRun.stats();
    matSim = PolarCNC.material.createMaterial(matCfg);
    buildMaterialMesh(matSim);
    faceMesh.visible = false;
  }

  // Bottom face disc
  var botMesh = new THREE.Mesh(
    new THREE.CircleGeometry(cylR, 64),
    new THREE.MeshPhongMaterial({
      color: 0x1a3a5a, transparent: true, opacity: 0.35,
      side: THREE.DoubleSide, depthWrite: false
    })
  );
  botMesh.position.z = surfaceZ - stockDepth;
  workpieceGroup.add(botMesh);

  // Outline rings at top face and bottom face
  var ringMat = new THREE.LineBasicMaterial({ color: 0x60aaee, transparent: true, opacity: 0.90 });
  [surfaceZ, surfaceZ - stockDepth].forEach(function(fz) {
    var verts = [], NS = 64;
    for (var i = 0; i <= NS; i++) {
      var a = (i / NS) * Math.PI * 2;
      verts.push(cylR * Math.cos(a), cylR * Math.sin(a), fz);
    }
    var g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.BufferAttribute(new Float32Array(verts), 3));
    workpieceGroup.add(new THREE.Line(g, ringMat));
  });

  // Vertical edge lines connecting top ring to bottom ring
  var edgeMat = new THREE.LineBasicMaterial({ color: 0x60aaee, transparent: true, opacity: 0.70 });
  var NE = 16;
  for (var i = 0; i < NE; i++) {
    var a = (i / NE) * Math.PI * 2;
    var ex = cylR * Math.cos(a), ey = cylR * Math.sin(a);
    var ev = new Float32Array([ex, ey, surfaceZ, ex, ey, surfaceZ - stockDepth]);
    var eg = new THREE.BufferGeometry();
    eg.setAttribute('position', new THREE.BufferAttribute(ev, 3));
    workpieceGroup.add(new THREE.Line(eg, edgeMat));
  }

  // 12 radial spokes on cutting face (top) - rotate visibly in Rotary Mode
  var spokeMat = new THREE.LineBasicMaterial({ color: 0x4488cc, transparent: true, opacity: 0.85 });
  var sv = [], NR = 12;
  for (var i = 0; i < NR; i++) {
    var a = (i / NR) * Math.PI * 2;
    sv.push(0, 0, surfaceZ, cylR * Math.cos(a), cylR * Math.sin(a), surfaceZ);
  }
  var spokeGeo = new THREE.BufferGeometry();
  spokeGeo.setAttribute('position', new THREE.BufferAttribute(new Float32Array(sv), 3));
  workpieceGroup.add(new THREE.LineSegments(spokeGeo, spokeMat));

  // Toolpath lines - inside workpieceGroup so they rotate with it in Rotary Mode
  var g1v = [], g0v = [], g1map = [], g0map = [];
  for (var i = 1; i < pts.length; i++) {
    var a = pts[i - 1], b = pts[i];
    if (b.type === 'G1') {
      g1v.push(a.x3, a.y3, a.z3, b.x3, b.y3, b.z3); g1map.push(i);
    } else {
      g0v.push(a.x3, a.y3, a.z3, b.x3, b.y3, b.z3); g0map.push(i);
    }
  }

  // Pre-compute cumulative draw-counts for O(1) per-frame drawRange updates
  g1Counts = new Int32Array(pts.length);
  g0Counts = new Int32Array(pts.length);
  var c1 = 0, c0 = 0, i1 = 0, i0 = 0;
  for (var i = 0; i < pts.length; i++) {
    while (i1 < g1map.length && g1map[i1] <= i) { c1++; i1++; }
    while (i0 < g0map.length && g0map[i0] <= i) { c0++; i0++; }
    g1Counts[i] = c1; g0Counts[i] = c0;
  }

  if (g1v.length > 0) {
    var geo1 = new THREE.BufferGeometry();
    geo1.setAttribute('position', new THREE.BufferAttribute(new Float32Array(g1v), 3));
    geo1.setDrawRange(0, 0);
    g1LineObj = new THREE.LineSegments(geo1, new THREE.LineBasicMaterial({ color: 0x00c8d4 }));
    workpieceGroup.add(g1LineObj);
  }
  if (g0v.length > 0) {
    var geo0 = new THREE.BufferGeometry();
    geo0.setAttribute('position', new THREE.BufferAttribute(new Float32Array(g0v), 3));
    geo0.setDrawRange(0, 0);
    g0LineObj = new THREE.LineSegments(geo0,
      new THREE.LineBasicMaterial({ color: 0xff6b35, transparent: true, opacity: 0.72 }));
    workpieceGroup.add(g0LineObj);
  }

  // Pre-compute cumulative segment durations for O(log n) binary-search seek
  segTimeCum = new Float64Array(pts.length);
  segTimeCum[0] = 0;
  for (var i = 1; i < pts.length; i++) {
    segTimeCum[i] = segTimeCum[i - 1] + pts[i].segDurNom;
  }

  // Fixed scene elements (not in workpieceGroup - do not rotate)
  var axv = new Float32Array([0, 0, stockDepth * 0.55,  0, 0, -stockDepth * 1.55]);
  var axGeo = new THREE.BufferGeometry();
  axGeo.setAttribute('position', new THREE.BufferAttribute(axv, 3));
  reg(new THREE.LineSegments(axGeo,
    new THREE.LineBasicMaterial({ color: 0x3a3a3a, transparent: true, opacity: 0.55 })));

  reg(new THREE.AxesHelper(maxR * 0.22));

  // End-Mill tool mesh
  // Tip at local origin (Z=0). Body extends in +Z toward camera.
  // CylinderGeometry default axis = local Y; rotation.x=PI/2 maps to world Z.
  toolGroup = reg(new THREE.Group());
  var ts       = Math.max(maxR * 0.050, 0.7);
  var toolRad  = ts * 0.40;
  var toolLen  = ts * 6.5;
  var fluteLen = ts * 1.8;

  var shank = new THREE.Mesh(
    new THREE.CylinderGeometry(toolRad, toolRad, toolLen, 16),
    new THREE.MeshPhongMaterial({ color: 0xaaaaaa, shininess: 70 })
  );
  shank.rotation.x = Math.PI / 2;
  shank.position.z = toolLen / 2;
  toolGroup.add(shank);

  var flutes = new THREE.Mesh(
    new THREE.CylinderGeometry(toolRad * 1.08, toolRad * 0.68, fluteLen, 6),
    new THREE.MeshPhongMaterial({ color: 0xffd700, emissive: 0x221100, shininess: 160 })
  );
  flutes.rotation.x = Math.PI / 2;
  flutes.position.z = fluteLen / 2;
  toolGroup.add(flutes);

  toolGroup.add(new THREE.PointLight(0xffcc44, 0.55, maxR * 0.9));

  // Camera: position depends on active view mode.
  // Both position and target account for surfaceZ so the camera always
  // looks at the actual workpiece face, not at world origin.
  var camDist   = Math.max(cylR * 3.0, 80);
  var centerZ   = surfaceZ - stockDepth / 2;   // centre of the workpiece cylinder
  if (viewMode === 'rotary') {
    // Rotary Mill mode: look straight down the Z-axis at the cutting face
    camera.position.set(0, 0, surfaceZ + camDist);
    camera.up.set(0, 1, 0);
    controls.target.set(0, 0, surfaceZ);
  } else {
    // Static 3D mode: slightly off-axis perspective centred on the workpiece
    camera.position.set(camDist * 0.22, camDist * 0.22, surfaceZ + camDist);
    controls.target.set(0, 0, centerZ);
  }
  camera.near = camDist * 0.001;
  camera.far  = camDist * 45;
  camera.updateProjectionMatrix();
  controls.update();
}

// ============================================================
// SECTION 5 - SCENE UPDATER (O(1) per frame)
// ============================================================
function updateScene() {
  if (!toolpath.length || !toolGroup) return;

  var idx  = Math.min(currentIdx, toolpath.length - 1);
  var pt   = toolpath[idx];

  // Interpolate continuously between toolpath[idx] and toolpath[idx+1] using
  // currentFrac (0..1, set by animLoop from elapsed time within this segment).
  // Without this the tool would sit still at pt for the whole segment duration
  // and then jump instantly to the next vertex — this reproduces smooth,
  // real feedrate-based motion instead of discrete point-to-point teleports.
  var pt2 = (currentFrac > 0 && idx + 1 < toolpath.length) ? toolpath[idx + 1] : null;
  var r, theta, z, x3, y3, z3, dispPt, tilt;
  if (pt2) {
    var fr = currentFrac;
    tilt  = (pt.tilt || 0) + ((pt2.tilt || 0) - (pt.tilt || 0)) * fr;
    r     = pt.r     + (pt2.r     - pt.r)     * fr;
    theta = pt.theta + (pt2.theta - pt.theta) * fr;
    z     = pt.z     + (pt2.z     - pt.z)     * fr;
    var rad = theta * Math.PI / 180;
    x3 = r * Math.cos(rad);
    y3 = r * Math.sin(rad);
    z3 = z;
    dispPt = pt2;   // telemetry (F/type/line#) reflects the move currently in progress
  } else {
    r = pt.r; theta = pt.theta; z = pt.z; tilt = pt.tilt || 0;
    x3 = pt.x3; y3 = pt.y3; z3 = pt.z3;
    dispPt = pt;
  }
  var cRad = theta * Math.PI / 180;
  // Advance the material depth map with the animation (redraw only on change;
  // seeking backwards restarts it).
  // Throttled to ~10 redraws/s while playing: a full-size grid is ~90k
  // vertices, too many to rebuild on every animation frame.
  if (matSim) {
    if (matSim.advanceTo(toolpath, idx)) matDirty = true;
    var nowMs = (typeof performance !== 'undefined') ? performance.now() : Date.now();
    if (matDirty && (!isPlaying || nowMs - matLastRefresh > 100)) {
      refreshMaterialMesh(matSim);
      matDirty = false;  matLastRefresh = nowMs;
    }
  }
  if (g1LineObj) g1LineObj.geometry.setDrawRange(0, g1Counts[idx] * 2);
  if (g0LineObj) g0LineObj.geometry.setDrawRange(0, g0Counts[idx] * 2);

  // Extend whichever trail (G1 cut / G0 rapid) is currently in progress so its
  // last drawn vertex tracks the interpolated tool position — the trail line
  // grows smoothly in sync with the tool instead of jumping in whole segments.
  if (pt2) {
    if (pt2.type === 'G1' && g1LineObj) {
      var segIdx1 = g1Counts[idx];
      var arr1 = g1LineObj.geometry.attributes.position.array;
      var base1 = segIdx1 * 6;
      arr1[base1 + 3] = x3; arr1[base1 + 4] = y3; arr1[base1 + 5] = z3;
      g1LineObj.geometry.attributes.position.needsUpdate = true;
      g1LineObj.geometry.setDrawRange(0, (segIdx1 + 1) * 2);
    } else if (pt2.type === 'G0' && g0LineObj) {
      var segIdx0 = g0Counts[idx];
      var arr0 = g0LineObj.geometry.attributes.position.array;
      var base0 = segIdx0 * 6;
      arr0[base0 + 3] = x3; arr0[base0 + 4] = y3; arr0[base0 + 5] = z3;
      g0LineObj.geometry.attributes.position.needsUpdate = true;
      g0LineObj.geometry.setDrawRange(0, (segIdx0 + 1) * 2);
    }
  }

  if (viewMode === 'rotary') {
    // ROTARY MILL MODE
    // Workpiece rotates around Z (spindle axis).
    // Tool cross-slide moves along X only - Y STRICTLY LOCKED TO 0.
    workpieceGroup.rotation.set(0, 0, -cRad);
    toolGroup.position.set(r, 0, z);
    toolGroup.position.y = 0;           // hard guard - Y must always be 0
    // 2.7.0: tilting router (XZC + B): the tool leans in the X-Z plane about
    // its tip; + = tip toward the chuck axis (the top of the tool outward).
    toolGroup.rotation.set(0, tilt * Math.PI / 180, 0);
  } else {
    // STATIC 3D MODE - workpiece fixed, tool traces Cartesian shape
    workpieceGroup.rotation.set(0, 0, 0);
    toolGroup.position.set(x3, y3, z3);
    // lean in the radial plane first, then turn to the point's angle
    toolGroup.rotation.set(0, tilt * Math.PI / 180, Math.atan2(y3, x3), 'ZYX');
  }

  // Telemetry overlay
  tLine.textContent = dispPt.lineNum;
  tMode.textContent = dispPt.type;
  tMode.style.color = dispPt.type === 'G0' ? '#ff6b35' : '#00c8d4';
  tX.textContent    = r.toFixed(4);
  tC.textContent    = theta.toFixed(2);
  tZ.textContent    = z.toFixed(4);
  if (tTilt) { tTilt.textContent = tilt.toFixed(1); tTiltRow.style.display = simHasTilt ? '' : 'none'; }
  var fMode = dispPt.feedMode || 'G93';
  tF.textContent    = dispPt.f > 0
    ? (fMode === 'G93'
        ? dispPt.f.toFixed(4) + '\u2009inv/min\u2009(\u2009' + (60 / dispPt.f).toFixed(2) + 's\u2009)'
        : dispPt.f.toFixed(3) + '\u2009mm/min')
    : '\u2014';
}

// ============================================================
// SECTION 6 - ANIMATION LOOP (feedrate-based real-time kinematics)
//
// simTime advances at: dt * overrideMultiplier * speedMultiplier
//
// overrideMultiplier = feedrateSlider / 100  (0.1 - 3.0)
//   100% => machine runs at nominal G94 feed timing (1:1 real time)
//   200% => twice as fast as G-code specifies
//
// speedMultiplier = speedSlider (1 - 200)
//   Additional fast-forward on top of override
//
// Current index found via O(log n) binary search on segTimeCum[].
// ============================================================
function animLoop(ts) {
  requestAnimationFrame(animLoop);
  var dt = lastTs > 0 ? Math.min((ts - lastTs) / 1000, 0.15) : 0;
  lastTs = ts;

  if (isPlaying && toolpath.length > 0 && segTimeCum) {
    var overrideMult = parseFloat(elOverride.value) / 100;
    var speedMult    = parseFloat(elSpeed.value);
    simTime += dt * overrideMult * speedMult;

    var totalTime = segTimeCum[segTimeCum.length - 1];
    if (simTime >= totalTime) {
      currentIdx  = toolpath.length - 1;
      currentFrac = 0;
      simTime     = totalTime;
      isPlaying   = false;
      btnPP.textContent = '\u25B6\u2009Play';
    } else {
      // Binary search: find lo such that segTimeCum[lo] <= simTime < segTimeCum[lo+1]
      var lo = 0, hi = toolpath.length - 1;
      while (hi - lo > 1) {
        var mid = (lo + hi) >> 1;
        if (segTimeCum[mid] <= simTime) lo = mid; else hi = mid;
      }
      currentIdx = lo;
      // Fraction of progress through the CURRENT segment (lo -> lo+1), used by
      // updateScene() to interpolate a smooth in-between position/telemetry.
      var segSpan = segTimeCum[lo + 1] - segTimeCum[lo];
      currentFrac = segSpan > 1e-9 ? (simTime - segTimeCum[lo]) / segSpan : 0;
    }
    elTL.value = currentIdx;
    updateProgress();
  }

  updateScene();
  controls.update();
  renderer.render(scene, camera);
}

// ─── Material removal mesh (2026-10-01) ─────────────────────────────────────
// One vertex per depth-map cell. Triangles are only built where all corners
// are inside the stock disc. Colour encodes depth; cells cut by a RAPID are red.
function buildMaterialMesh(m) {
  var n = m.n, cnt = n * n;
  matPos = new Float32Array(cnt * 3);
  matCol = new Float32Array(cnt * 3);
  var idx = [];
  for (var j = 0; j < n; j++) {
    for (var i = 0; i < n; i++) {
      var k = j * n + i;
      matPos[k * 3]     = m.x0 + i * m.cell;
      matPos[k * 3 + 1] = m.x0 + j * m.cell;
      if (i < n - 1 && j < n - 1) {
        var a = k, b = k + 1, c = k + n, d = k + n + 1;
        if (m.inside[a] && m.inside[b] && m.inside[c] && m.inside[d]) idx.push(a, b, d, a, d, c);
      }
    }
  }
  matGeo = new THREE.BufferGeometry();
  matGeo.setAttribute('position', new THREE.BufferAttribute(matPos, 3));
  matGeo.setAttribute('color', new THREE.BufferAttribute(matCol, 3));
  matGeo.setIndex(idx);
  var mesh = new THREE.Mesh(matGeo, new THREE.MeshPhongMaterial({
    vertexColors: true, side: THREE.DoubleSide, shininess: 20
  }));
  workpieceGroup.add(mesh);
  refreshMaterialMesh(m);
}

function refreshMaterialMesh(m) {
  if (!matPos || !matGeo) return;
  var n = m.n, cnt = n * n, top = m.surfaceZ;
  var span = Math.max(top - m.stats().minZ, 0.5);
  for (var k = 0; k < cnt; k++) {
    var zc = m.z[k];
    matPos[k * 3 + 2] = zc;
    var r, g, b;
    if (m.rapidHit[k]) { r = 1.0; g = 0.18; b = 0.18; }              // rapid cut: red
    else if (zc >= top - 0.005) { r = 0.16; g = 0.35; b = 0.54; }    // untouched stock
    else {                                                           // machined: light -> dark
      var t = Math.min((top - zc) / span, 1);
      r = 0.62 - 0.52 * t; g = 0.86 - 0.60 * t; b = 1.0 - 0.62 * t;
    }
    matCol[k * 3] = r; matCol[k * 3 + 1] = g; matCol[k * 3 + 2] = b;
  }
  matGeo.attributes.position.needsUpdate = true;
  matGeo.attributes.color.needsUpdate = true;
  if (matGeo.computeVertexNormals) matGeo.computeVertexNormals();
}
