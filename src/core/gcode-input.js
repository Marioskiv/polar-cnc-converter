/*
 * Polar CNC — input stage: reads a Cartesian XYZ program (any CAM), checks it the way
 * LinuxCNC would, and hands every line over IN ORDER: motion as events for the
 * machine layout, everything else as text. Pure: no DOM, no globals.
 * Browser: PolarCNC.gcodeInput   Node: require('./gcode-input.js')
 *
 * Copyright (c) 2026 Marioskiv
 * https://github.com/Marioskiv/polar-cnc-converter
 * SPDX-License-Identifier: MIT
 */
(function (root, factory) {
  'use strict';
  var isNode = typeof module === 'object' && module.exports;
  var api = factory();
  if (isNode) module.exports = api;
  else { root.PolarCNC = root.PolarCNC || {}; root.PolarCNC.gcodeInput = api; }
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  // RESTRUCTURED 2.6.0: the input half of the old single converter function,
  // moved here unchanged. The output goes through `sink`:
  //   sink.text(line)        a line to write as it is
  //   sink.flush(feed)       write any motion the layout still holds back
  //   sink.move(event)       a G0/G1/G2/G3 (see the call below for the fields; line = source line, 2.13.0)
  //   sink.tool(dia, number) the active cutter changed (diameter in mm, tool number as text)
  //   sink.programEnd(feed)  the CAM's own M2/M30 follows (flush + G94 restore)
  // Returns { usedPercent, programEnded, warnings[] } for the converter.
  // ADDED 2.8.0: cutter diameters from the tool comments of ANY CAM.
  // Every comment, "( ... )" or "; ...", is checked. Known forms:
  //   Fusion / HSM / Inventor  (T1 D=6. CR=0. - ZMIN=-5. - flat end mill)
  //   Mastercam                ( T1 | 1/4 FLAT ENDMILL | H1 | D1 | TOOL DIA. - .25 )
  //                            ("D1" there is the offset register, NOT a diameter)
  //   FreeCAD                  (TC: 5mm Endmill)  (Compensated Tool Path. Diameter: 5.0)
  //   Kiri:Moto                ; tool#=1 flute=6 len=20 unit=metric
  //   CamBam-style             ( T1 : 6.0 )
  //   APT/CL (Carbide Create)  (TOOL/MILL,3.175, 0.00, 0.00, 0.00)
  //   generic                  (Tool Diameter: 6.35)  (DIA 6)  (Tool: End Mill 6 mm)  (T2 1/4" ball)
  // A comment naming a tool number belongs to that tool. One without a number
  // belongs to the tool change that follows it before any motion (FreeCAD
  // writes "(TC: ...)" just before "M6 T1"), else to the tool selected before it.
  // A stated diameter (D=, DIA, Diameter, TOOL/MILL, flute=) beats a size inside
  // a tool NAME ("5mm Endmill"). Returns { tools: { n: { d, mm, fromName } },
  // conflicts: [text] }; n is the tool number as text, '?' when the program
  // never selects a tool. mm = the comment gave the unit (else the program's unit).
  var NUM = '(\\d+(?:\\.\\d*)?|\\.\\d+)';
  var UNIT = '\\s*(mm|millimet(?:er|re)s?|"|in(?:ch(?:es)?)?\\b|\'\')?';
  var RE_KIRI   = /tool#\s*=\s*(\d+)\s+flute\s*=\s*(\d*\.?\d+)(?:.*?\bunit\s*=\s*(metric|imperial))?/i;
  var RE_APT    = new RegExp('\\bTOOL\\s*\\/\\s*MILL\\s*,\\s*' + NUM, 'i');
  var RE_DIAKW  = new RegExp('(?:\\bDIA(?:M(?:ETER)?)?\\b\\.?|\\u00D8|\\u2300)\\s*(?:[:=]|-(?!\\d)|\\s)*\\s*' + NUM + UNIT, 'i');
  var RE_DEQ    = new RegExp('(?:^|[\\s|,(])D\\s*[=:]\\s*' + NUM + UNIT, 'i');
  var RE_TONLY  = new RegExp('^\\s*T\\s*\\d+\\s*[:=]\\s*' + NUM + UNIT + '\\s*$', 'i');
  var RE_TNUM   = /(?:^|[^A-Z0-9])T\s*0*(\d+)\b(?!\s*[.,]\d)/i;
  var RE_TOOLNO = /\bTOOLS?\s*(?:#|NO\.?|NUMBER)?\s*[:=#]?\s*0*(\d+)\s*(?=$|[:=|,)\-]\s*(?![\d.]*\s*(?:mm|"|in\b)))/i;
  var RE_TOOLISH = /\b(?:TC\s*:|TOOLS?\b|TOOL\s*\/|CUTTER|END\s*-?\s*MILLS?|ENDMILLS?|BALL|BULL|FLAT|BIT|DRILL|MILL|ROUTER|ENGRAV|V-?\s*BIT|SPOT)/i;
  var RE_NOTTOOL = /\b(?:STOCK|PART|BLANK|WORK\s*PIECE|WORKPIECE|HOLE|THREAD|BORE|CIRCLE|BOSS|FEED|SPEED|MIN\b|DEPTH|STEP|PASS)/i;
  // a size inside a tool name: "5mm", "6.35 mm", '1/4"', "0.25in", "1/8 inch"
  var RE_NAMESZ = /(?:^|[^\w.\/])(\d+\s*\/\s*\d+|\d+(?:\.\d*)?|\.\d+)\s*(mm|millimet(?:er|re)s?|"|''|in(?:ch(?:es)?)?)(?![\w\/])/i;

  function toNum(s) {
    var f = String(s).match(/^(\d+)\s*\/\s*(\d+)$/);
    return f ? parseFloat(f[1]) / parseFloat(f[2]) : parseFloat(s);
  }
  function unitMM(u) {            // null = unit not stated
    if (!u) return null;
    return /^m/i.test(u) ? 1 : 25.4;
  }

  // One comment -> { tool: 'n' | null, d, scale (1, 25.4 or null), strong }
  function readToolComment(c) {
    var tool = null, m;
    var k = c.match(RE_KIRI);
    if (k) return { tool: String(parseInt(k[1], 10)), d: parseFloat(k[2]),
                    scale: k[3] && k[3].toLowerCase() === 'imperial' ? 25.4 : 1, strong: true };
    if ((m = c.match(RE_TNUM))) tool = String(parseInt(m[1], 10));
    else if ((m = c.match(RE_TOOLNO))) tool = String(parseInt(m[1], 10));
    var toolish = tool !== null || RE_TOOLISH.test(c);
    if (!toolish) return null;
    if (tool === null && RE_NOTTOOL.test(c) && !/\bTOOL\b/i.test(c)) return null;
    if ((m = c.match(RE_APT)))   return { tool: tool, d: toNum(m[1]), scale: null, strong: true };
    if ((m = c.match(RE_DIAKW))) return { tool: tool, d: toNum(m[1]), scale: unitMM(m[2]), strong: true };
    if ((m = c.match(RE_DEQ)))   return { tool: tool, d: toNum(m[1]), scale: unitMM(m[2]), strong: true };
    if ((m = c.match(RE_TONLY))) return { tool: tool, d: toNum(m[1]), scale: unitMM(m[2]), strong: true };
    if ((m = c.match(RE_NAMESZ))) return { tool: tool, d: toNum(m[1]), scale: unitMM(m[2]), strong: false };
    return null;
  }

  function scanToolDiameters(lines) {
    function code(l) { return l.replace(/\([^)]*\)/g, ' ').replace(/;.*$/, ''); }
    function comments(l) {
      var out = [], body = l;
      // ";" starts a comment unless it sits inside "( ... )"
      var depth = 0, cut = -1;
      for (var i = 0; i < l.length; i++) {
        if (l[i] === '(') depth++;
        else if (l[i] === ')') depth = Math.max(0, depth - 1);
        else if (l[i] === ';' && depth === 0) { cut = i; break; }
      }
      if (cut >= 0) { out.push(l.slice(cut + 1)); body = l.slice(0, cut); }
      // "( ... )" - a nested name like "(Tool: End Mill (6 mm))" stays one comment
      var start = -1; depth = 0;
      for (var j = 0; j < body.length; j++) {
        if (body[j] === '(') { if (depth === 0) start = j + 1; depth++; }
        else if (body[j] === ')' && depth > 0) { depth--; if (depth === 0) out.push(body.slice(start, j)); }
      }
      if (depth > 0) out.push(body.slice(start));
      return out;
    }
    // where each line's untagged comments belong: the next T word if no motion
    // comes first, else the last T word before
    var tAt = [], moveAt = [], anyT = false;
    lines.forEach(function (l, i) {
      var c = code(l).toUpperCase();
      var t = c.match(/\bT\s*(\d+)/) || c.match(/T\s*(\d+)/);
      tAt[i] = t ? String(parseInt(t[1], 10)) : null;
      if (tAt[i] !== null) anyT = true;
      moveAt[i] = /[XYZ]\s*[-+.\d]/.test(c);
    });
    var nextT = [], pending = null;
    for (var b = lines.length - 1; b >= 0; b--) {
      if (tAt[b] !== null) pending = tAt[b];
      else if (moveAt[b]) pending = null;
      nextT[b] = pending;
    }
    var tools = {}, conflicts = [], prevT = null;
    lines.forEach(function (l, i) {
      comments(l).forEach(function (c) {
        var r = readToolComment(c);
        if (!r || !(r.d > 0) || !isFinite(r.d)) return;
        var n = r.tool;
        if (n === null) n = nextT[i] !== null ? nextT[i] : (prevT !== null ? prevT : (anyT ? null : '?'));
        if (n === null) return;
        var e = { d: r.scale ? r.d * r.scale : r.d, mm: r.scale !== null, fromName: !r.strong,
                  text: c.trim() };
        var old = tools[n];
        if (!old || (old.fromName && r.strong)) { tools[n] = e; return; }
        if (r.strong && !old.fromName && old.mm === e.mm && Math.abs(old.d - e.d) > 1e-6)
          conflicts.push('T' + n + ': "' + old.text + '" and "' + e.text + '"');
      });
      if (tAt[i] !== null) prevT = tAt[i];
    });
    return { tools: tools, conflicts: conflicts };
  }

  function read(text, O, sink) {
    function emit(line) { sink.text(line); }
    var passThroughWarnings = 0;   // illegal-in-polar G-codes copied through verbatim
    var dwellWarnings = 0;         // G4 dwells of a minute or more (seconds vs milliseconds)
    var TOOL_DIA = O.toolDia;   // diameter of the ACTIVE tool (mm) - reported to the layout
    var lines        = text.split(/\r?\n/);
    var curX = 0, curY = 0, curZ = 0;
    // FIX (2026-09-12): the converter starts by ASSUMING the tool is at (0,0,0).
    // The machine is really parked somewhere else (at the edge, Z up). Until the
    // program has actually stated an XY position, that assumption must not be
    // used to build a path: the segmented-rapid code was walking the first G0
    // from the imaginary origin, which commanded "G0 X6.25 C0 Z0.25" — driving
    // the tool DOWN to Z0.25 near the centre at rapid speed on the very first
    // block of every program.
    var xyKnown = false;
    var programEnded = false;   // set when the CAM's own M2/M30 is passed through

    // FIX (2026-10-01): INPUT-MODE TRACKING. Researched against the LinuxCNC
    // interpreter itself (convert_home in interp_convert.cc: G28/G30 go to the
    // waypoint, then ONLY the named axes go home; percent handling in
    // rs274ngc_pre.cc: % is a delimiter only as the FIRST line) and against
    // what real CAM posts emit for LinuxCNC (Fusion "LinuxCNC": G53 G0 Z0 at
    // start and end; Fusion "grbl": G28 G91 Z0 and G28 G91 X0 Y0).
    var zKnown = false;           // Z unknown at start and after G28/G30/G53/M6
    var distIncremental = false;  // input is in G91
    var unitScale = 1.0;          // 25.4 while the input is in inches (G20)
    var polarMode = false;        // 2.12.1: inside Fanuc G16 polar coordinate mode
    var polarR = null, polarA = null; // 2.12.2: last radius / angle given in G16 (Fanuc keeps them)
    var plane = 17;               // active arc plane of the input
    var usedPercent = false;      // input used % tape delimiters
    // FIX (2026-10-04): an input line copied INTO one of the converter's own
    // comments must lose its parentheses, or a line like "G21 (mm)" becomes
    // "( absorbed modal from: G21 (mm) )" - a nested comment, which LinuxCNC
    // rejects ("Nested comment found"). The cycle expansion already did this.
    function commentSafe(raw) { return String(raw).trim().replace(/[()]/g, ''); }
    function inputError(lineIdx, raw, msg) {
      var no = (srcNo && srcNo[lineIdx]) ? srcNo[lineIdx] : lineIdx + 1;
      throw new Error('Line ' + no + ' "' + String(raw).trim() + '": ' + msg);
    }
    // ADDED 2.4.1: arcs are checked the way LinuxCNC 2.9 checks them
    // (interp_arc.cc arc_data_r / arc_data_ijk, default INI tolerances), so a
    // program LinuxCNC would refuse is refused here too, with the line number,
    // instead of being converted into something else. Before, an R arc whose
    // radius could not reach the end point became a straight line, an arc with
    // no I/J/R became a straight line, and an I/J arc whose end radius was far
    // off was cut on the start radius and ended somewhere else.
    // All values are in mm here (inch input is already scaled).
    function checkArc(lineIdx, raw, x0, y0, x1, y1, I, J, R) {
      var RADIUS_TOL = 0.00127;                                  // RADIUS_TOLERANCE_MM (= 0.00005 in)
      var SPIRAL_ABS = unitScale === 1 ? 0.02 * Math.SQRT2       // CENTER_ARC_RADIUS_TOLERANCE_MM
                                       : 0.002 * Math.SQRT2 * 25.4;  // ..._INCH, in mm
      var SPIRAL_REL = 0.001;                                    // SPIRAL_RELATIVE_TOLERANCE
      if (R === null && I === null && J === null)
        inputError(lineIdx, raw, 'arc without I/J or R.');
      // ADDED 2.12.1: LinuxCNC refuses an arc with both R and I/J ("mixed radius-ijk format");
      // the converter used to take R silently, whatever the I/J said.
      if (R !== null && (I !== null || J !== null))
        inputError(lineIdx, raw, 'arc with both R and I/J. Give the arc either with R or with I/J, not both (LinuxCNC refuses this too).');
      if (R !== null) {
        if (x0 === x1 && y0 === y1)
          inputError(lineIdx, raw, 'R-format arc whose start and end are the same point (a full circle needs I/J).');
        var half = Math.hypot(x1 - x0, y1 - y0) / 2;
        if (half - Math.abs(R) > RADIUS_TOL)
          inputError(lineIdx, raw, 'arc radius R' + Math.abs(R).toFixed(4) + ' is too small to reach the end point (half the distance is ' + half.toFixed(4) + ' mm).');
        return;
      }
      var cx = x0 + (I || 0), cy = y0 + (J || 0);
      var r1 = Math.hypot(x0 - cx, y0 - cy), r2 = Math.hypot(x1 - cx, y1 - cy);
      if (r1 < RADIUS_TOL || r2 < RADIUS_TOL)
        inputError(lineIdx, raw, 'zero-radius arc (the centre is on the start or end point).');
      var absErr = Math.abs(r1 - r2), relErr = absErr / Math.max(r1, r2);
      if (absErr > SPIRAL_ABS * 100 || (relErr > SPIRAL_REL && absErr > SPIRAL_ABS))
        inputError(lineIdx, raw, 'radius to the end of the arc (' + r2.toFixed(4) + ') differs from the radius to the start (' + r1.toFixed(4) + ').');
    }
    var modalMove    = null;
    // FIX 2.4.1: no invented feed. It used to start at 500 mm/min, so a
    // program without an F word was cut at a speed nobody chose. LinuxCNC
    // refuses a G1 with no feed rate; the converter now does the same.
    var camFeed      = 0;                 // last feedrate seen in CAM input (mm/min, G94 units); 0 = none yet
    function requireFeed(lineIdx, raw) {
      if (!(camFeed > 0))
        inputError(lineIdx, raw, 'cutting move without a feed rate. The CAM must state F (units/min) before or on the first G1/G2/G3.');
    }

    // Source line numbers, kept in step when canned cycles are expanded into
    // several lines, so every error still names the user's original line.
    var srcNo = lines.map(function (_, i) { return i + 1; });
    var isGen = lines.map(function () { return false; });   // line produced by a cycle expansion

    // 2.11.0 (Marios): no "Safe retract Z" setting. A machine-coordinate retract
    // (G53 G0 Z.., G28/G30 Z) goes to the program's OWN highest Z instead - the
    // clearance height the CAM already uses above the part, in work coordinates.
    // It needs nothing about the machine, so it is right on any machine. Found here
    // from every absolute Z (and drilling R plane) outside machine-reference lines; mm.
    var SAFE_Z_MM = (function () {
      var best = null, sc = 1, inc = false;
      lines.forEach(function (l) {
        var c = l.replace(/\([^)]*\)/g, '').replace(/;.*$/, '').toUpperCase();
        if (/G0*20(?![.\d])/.test(c)) sc = 25.4;
        if (/G0*21(?![.\d])/.test(c)) sc = 1;
        if (/G(?:53|0*28|0*30)(?![.\d])/.test(c)) return;
        if (/G0*91(?![.\d])/.test(c)) inc = true;
        if (/G0*90(?![.\d])/.test(c)) inc = false;
        if (inc) return;
        var zm = c.match(/Z\s*([-+]?(?:\d+\.?\d*|\.\d+))/);
        if (zm) { var z = parseFloat(zm[1]) * sc; if (best === null || z > best) best = z; }
        if (/G(?:8[1-9]|73)(?![.\d])/.test(c)) {
          var rm = c.match(/R\s*([-+]?(?:\d+\.?\d*|\.\d+))/);
          if (rm) { var r = parseFloat(rm[1]) * sc; if (best === null || r > best) best = r; }
        }
      });
      return best;
    })();
    var RETRACT_MARK = '( polar-cnc: safe retract done )';

    // ─── NON-MOTION WORDS (2026-10-02) ─────────────────────────────────────────
    // A line can carry far more than a move: S, T, M3/M5/M8, G43 H, G54, G64 P,
    // comments... All of it must reach the machine. The converter rewrites only
    // the motion, so everything else is split off and written as its own line:
    // BEFORE the move (RS274/NGC order of execution: speeds, tools, spindle,
    // coolant, tool length, work offset, path control all act before motion)
    // and the stop codes M0/M1/M2/M30/M60 AFTER it (they act after motion).
    // Previously "G43 Z15 H1" lost its G43 and "G0 X30 Y10 S20000 M3" lost the
    // spindle start — a tool could plunge with the spindle stopped.
    var MOTION_G  = /\bG0*(?:0|1|2|3)(?![.\d])/gi;
    var HANDLED_G = /\bG0*(?:17|18|19|20|21|73|80|81|82|83|85|89|90|91|94|98|99)(?![.\d])/gi;
    function splitNonMotion(raw, keepPQ) {
      var comments = raw.match(/\([^)]*\)/g) || [];
      var t = raw.replace(/\([^)]*\)/g, ' ').replace(/;.*$/, ' ')
                 .replace(MOTION_G, ' ').replace(HANDLED_G, ' ')
                 .replace(/\bN\d+/gi, ' ')
                 .replace(/\b[XYZIJKRF]\s*[-+]?(?:\d+\.?\d*|\.\d+)/gi, ' ');
      if (!keepPQ) t = t.replace(/\b[PQL]\s*[-+]?(?:\d+\.?\d*|\.\d+)/gi, ' ');
      var post = [];
      t = t.replace(/\bM0*(?:0|1|2|30|60)(?![.\d])/gi, function (m) { post.push(m.toUpperCase()); return ' '; });
      t = t.replace(/\s+/g, ' ').trim();
      return { pre: [t].concat(comments).filter(Boolean).join(' '), post: post.join(' ') };
    }
    // Writes a pass-through line; the program end (M2/M30) gets the G94 restore first.
    function emitPassThrough(text) {
      if (!text) return;
      if (/\bM0*(?:2|30)(?![.\d])/i.test(text) && !programEnded) {
        sink.programEnd(camFeed);   // flush + 'G94 restore' (written by the converter)
        programEnded = true;
      }
      emit(text);
    }
    var pendingPost = null;   // stop codes from the previous move line

    // Tool diameters stated by the CAM in comments (any CAM, see scanToolDiameters).
    // toolDiaRaw[n] = { d: diameter, mm: true if the CAM said the unit (else the
    // program's own unit at the tool change applies), fromName }.
    var scanned = scanToolDiameters(lines);
    var toolDiaRaw = scanned.tools;
    function toolDiaMM(t) { var e = toolDiaRaw[t]; return e.mm ? e.d : e.d * unitScale; }
    function toolNote(t) {
      return toolDiaRaw[t].fromName ? ' - from the tool name "' + commentSafe(toolDiaRaw[t].text) + '"' : '';
    }
    var nextTool = null, activeTool = null;
    function noteToolChange() {
      if (nextTool === null) return;
      activeTool = nextTool;
      TOOL_DIA = (activeTool in toolDiaRaw) ? toolDiaMM(activeTool) : null;   // 2.9.0: no setting to fall back on
      sink.tool(TOOL_DIA, activeTool);
      emit('( polar-cnc tool: T' + activeTool + ((activeTool in toolDiaRaw)
               ? ' D=' + TOOL_DIA.toFixed(4) + toolNote(activeTool)
               : ' - no diameter in the program') + ' )');
    }
    // ADDED 2.5.0: a program with ONE tool in its list and no tool change at all
    // (e.g. Kiri:Moto with "initial tool change" off) used that tool's
    // diameter nowhere - the setting was used instead. Use the listed tool.
    var listedTools = Object.keys(toolDiaRaw);
    if (listedTools.length === 1 && !lines.some(function (l) {
          return /\bM0*6(?![.\d])/i.test(l.replace(/\([^)]*\)/g, '').replace(/;.*$/, ''));
        })) {
      nextTool = listedTools[0];
      // the program's unit is not read yet here: look for G20 in it
      var inchProg = lines.some(function (l) { return /\bG0*20(?![.\d])/i.test(l.replace(/\([^)]*\)/g, '').replace(/;.*$/, '')); });
      TOOL_DIA = toolDiaRaw[nextTool].mm ? toolDiaRaw[nextTool].d : toolDiaRaw[nextTool].d * (inchProg ? 25.4 : 1);
      sink.tool(TOOL_DIA, nextTool === '?' ? null : nextTool);
      emit('( polar-cnc tool: ' + (nextTool === '?' ? '' : 'T' + nextTool + ' ') + 'D=' + TOOL_DIA.toFixed(4)
           + (nextTool === '?' ? ' - from the program, no tool number' : ' - the only tool listed, no tool change')
           + toolNote(nextTool) + ' )');
      if (nextTool === '?') nextTool = null;
    }

    // ─── CANNED DRILLING CYCLES (2026-10-02) ───────────────────────────────────
    // A drilled hole is a point: in polar coordinates it is simply X (radius)
    // and C (angle), then Z moves. So G81/G82/G83/G73/G85/G89 are expanded into
    // plain G0/G1/G4 lines (in the program's own units and G90) and fed back
    // through the normal conversion — rapids, pole handling and feeds included.
    // Behaviour follows the LinuxCNC/RS274NGC cycle descriptions: preliminary
    // Z up to R if below it, rapid to XY, rapid to R, cycle motion, then retract
    // to R (G99) or to the initial level (G98, never below R). Z/R/Q/P are sticky.
    var activeCycle = null, retractInitial = true;
    function f4(v) { return (Math.abs(v) < 5e-5 ? 0 : v).toFixed(4); }
    function expandCycle(c, x, y, fromZ) {
      var L = [], R = c.R, Zb = c.Z, F = c.F;
      var delta = unitScale === 1 ? 0.254 : 0.01;      // peck back-off (LinuxCNC uses 0.010 in)
      var retZ = retractInitial ? Math.max(c.initialZ, R) : R;
      if (fromZ < R) L.push('G0 Z' + f4(R));
      L.push('G0 X' + f4(x) + ' Y' + f4(y));
      L.push('G0 Z' + f4(R));
      if (c.code === 83 || c.code === 73) {
        if (!(c.Q > 0)) return null;
        var depth = R, first = true;
        while (depth > Zb + 1e-9) {
          var nxt = Math.max(depth - c.Q, Zb);
          if (!first && c.code === 83) L.push('G0 Z' + f4(depth + delta));
          L.push('G1 Z' + f4(nxt) + ' F' + f4(F));
          if (nxt > Zb + 1e-9) L.push('G0 Z' + f4(c.code === 83 ? R : nxt + delta));
          depth = nxt; first = false;
        }
        L.push('G0 Z' + f4(retZ));
      } else {
        L.push('G1 Z' + f4(Zb) + ' F' + f4(F));
        if (c.code === 82 || c.code === 89) L.push('G4 P' + f4(c.P || 0));
        if (c.code === 85 || c.code === 89) {
          L.push('G1 Z' + f4(R) + ' F' + f4(F));
          if (retZ > R) L.push('G0 Z' + f4(retZ));
        } else {
          L.push('G0 Z' + f4(retZ));
        }
      }
      return L;
    }

    for (var li = 0; li < lines.length; li++) {
      var rawLine = lines[li];
      // ADDED 2.12.1 (Marios: F): lathe diameter mode G7 in the input is refused - the converter's
      // X is a radius (or a diameter only through the profile), and a G7 passed to a LinuxCNC lathe
      // configuration halved the part. G8 (radius mode) is removed: the header states the mode.
      if (!isGen[li]) {
        // 2.12.2: a Fanuc program number ("O1000", also with moves on the same line, B-63534EN
        // p.248) is not a LinuxCNC command - LinuxCNC reads "O1000" as an o-word without a
        // keyword. It is kept as a comment. O-word subroutines/loops are refused further down.
        var onum = rawLine.match(/^\s*O\s*(\d+)(?!\d)/i);
        if (onum && !/^\s*O\s*\d+\s*(SUB|ENDSUB|CALL|RETURN|IF|ELSEIF|ELSE|ENDIF|WHILE|ENDWHILE|DO|REPEAT|ENDREPEAT|BREAK|CONTINUE)\b/i.test(rawLine)) {
          rawLine = rawLine.slice(onum[0].length).trim();
          rawLine = (rawLine ? rawLine + ' ' : '') + '( program O' + onum[1] + ' )';
          lines[li] = rawLine;
        }
        var g78 = rawLine.replace(/\([^)]*\)/g, ' ').replace(/;.*$/, '');
        if (/\bG0*7(?![.\d])/i.test(g78))
          inputError(li, rawLine, 'lathe diameter mode (G7) is not converted: the converter writes X itself (radius, or diameter through the output profile). Remove G7 from the post.');
        // 2.12.2: Fanuc "G08 P1" is advanced preview control (B-63534EN p.476), not LinuxCNC's
        // G8 radius mode; removing the G8 left a stray "P1" line. Refused with its own reason.
        if (/\bG0*8(?![.\d])/i.test(g78) && /P\s*[-+]?[\d.]/i.test(g78))
          inputError(li, rawLine, 'Fanuc G08 P (advanced preview control) is not a LinuxCNC command. Remove it from the post (LinuxCNC blends with G64).');
        if (/\bG0*8(?![.\d])/i.test(g78) && rawLine.indexOf(';') < 0) {
          rawLine = rawLine.replace(/\bG0*8(?![.\d])/gi, '').replace(/\s{2,}/g, ' ').trim() + ' ( G8 removed: the header sets the X mode )';
          lines[li] = rawLine;
        }
      }
      // ─── POLAR COORDINATE COMMAND G15/G16 (Fanuc) ─────────────────────────
      // 2.11.4 removed G15 (polar off, the default; LinuxCNC does not know it).
      // ADDED 2.12.1 (Marios): G16 is CONVERTED instead of refused, in the plain form used for
      // hand-written bolt circles: XY plane (G17), absolute (G90) - the pole is then the work
      // origin - X = radius, Y = angle in degrees counter-clockwise from +X, both written on
      // every line that moves in X/Y. The line is rewritten to Cartesian X/Y before anything
      // else reads it (canned cycles included) and G15/G16 are removed from the output.
      // Everything whose meaning is less certain stops with the line number: G91 in polar
      // mode (Fanuc then takes the pole at the current position), a missing radius or angle,
      // arcs, other planes, and offset / machine-coordinate commands.
      if (!isGen[li]) {
        var pcmt = [], pcode = rawLine.replace(/\([^)]*\)/g, function (m) { pcmt.push(m.slice(1, -1).trim()); return ' '; });
        var psemi = pcode.indexOf(';');
        if (psemi >= 0) { pcmt.push(pcode.slice(psemi + 1).trim()); pcode = pcode.slice(0, psemi); }
        var hasG15 = /\bG0*15(?![.\d])/i.test(pcode), hasG16 = /\bG0*16(?![.\d])/i.test(pcode);
        if (hasG15 || hasG16 || polarMode) {
          if (hasG15 && hasG16) inputError(li, rawLine, 'G15 and G16 on the same line.');
          var pnote = [];
          if (hasG15) { polarMode = false; pnote.push('G15 removed: polar coordinates off'); }
          if (hasG16) { polarMode = true;  pnote.push('G16 polar coordinates on - X = radius, Y = angle, converted to X/Y'); }
          if (hasG15 || hasG16) { polarR = null; polarA = null; }
          pcode = pcode.replace(/\bG0*1[56](?![.\d])/gi, ' ');
          if (polarMode) {
            var pc = pcode.toUpperCase();
            var px = pc.match(/X\s*([-+]?(?:\d+\.?\d*|\.\d+))/), py = pc.match(/Y\s*([-+]?(?:\d+\.?\d*|\.\d+))/);
            var pInc = /\bG0*91(?![.\d])/.test(pc) ? true : /\bG0*90(?![.\d])/.test(pc) ? false : distIncremental;
            if (/\bG0*1[89](?![.\d])/.test(pc) || (plane !== 17 && !/\bG0*17(?![.\d])/.test(pc)))
              inputError(li, rawLine, 'polar coordinates (G16) are converted only in the XY plane (G17).');
            if (/\bG0*[23](?![.\d])/.test(pc) || ((px || py) && (modalMove === 'G2' || modalMove === 'G3') && !/\bG0*[01](?![.\d])/.test(pc) && !/\bG0*(7[3-9]|8\d)(?![.\d])/.test(pc)))
              inputError(li, rawLine, 'arcs in polar coordinate mode (G16) are not converted. Program the arc in Cartesian X/Y (after G15).');
            if (/\bG0*(10|28|30|52|53|92)(?![.\d])/.test(pc) && (px || py))
              inputError(li, rawLine, 'offset or machine-coordinate commands with X/Y are not converted in polar coordinate mode (G16).');
            // X/Y on the G16 line itself: some sources make them the pole (Machining Doctor:
            // "G16 X5 Y6" puts the pole at X5 Y6), others a first polar point - not certain, refused.
            if (hasG16 && (px || py))
              inputError(li, rawLine, 'X/Y on the G16 line itself is read differently by different controls (pole position or first point). Put G16 alone on its line, with the pole at the work origin.');
            // 2.12.2 (Marios: E, from the Fanuc 16i/18i-MB manual B-63534EN/02 section 8.2, p.138-140):
            // a radius or angle left out keeps its last value in G16 ("N3 Y150.0 ; a distance of
            // 100 mm and an angle of 150 degrees"), and "G91 Y120.0" turns the angle by +120 degrees
            // with the same radius and the pole still at the work origin. G91 WITH a radius moves
            // the pole to the current position (p.138) - still refused. The first polar point after
            // G16 must give both, because nothing is kept from before G16.
            if (px || py) {
              var pr, paDeg;
              if (pInc) {
                if (px) inputError(li, rawLine, 'incremental G91 with a radius in polar coordinate mode (G16) is not converted (Fanuc then takes the pole at the current position). Use G90 with the radius and angle from the work origin; G91 with only an angle (Y) is converted.');
                if (polarR === null || polarA === null || !xyKnown) inputError(li, rawLine, 'incremental angle (G91 Y) in polar coordinate mode (G16) before a radius and angle are known. Give the first point with G90 X(radius) Y(angle).');
                pr = polarR; paDeg = polarA + parseFloat(py[1]);
              } else {
                pr = px ? parseFloat(px[1]) : polarR;
                paDeg = py ? parseFloat(py[1]) : polarA;
                if (pr === null || paDeg === null) inputError(li, rawLine, 'the first point after G16 must give both the radius (X) and the angle (Y); later lines may leave one out (it keeps its last value).');
              }
              polarR = pr; polarA = paDeg;
              var pa = paDeg * Math.PI / 180;
              var cxp = pr * Math.cos(pa), cyp = pr * Math.sin(pa);
              // In G91 the line stays incremental (the G91 code further down adds the current
              // position), so the Cartesian step is written; in G90 the absolute point.
              var oxp = pInc ? cxp - curX : cxp, oyp = pInc ? cyp - curY : cyp;
              pcode = pcode.replace(/X\s*[-+]?(?:\d+\.?\d*|\.\d+)/i, ' ').replace(/Y\s*[-+]?(?:\d+\.?\d*|\.\d+)/i, ' ')
                .replace(/\s+$/, '') + ' X' + oxp.toFixed(6) + ' Y' + oyp.toFixed(6);
              pnote.push('G16 ' + (px ? 'X' + px[1] + ' ' : '') + (py ? (pInc ? 'G91 ' : '') + 'Y' + py[1] : '')
                + ' = radius ' + +pr.toFixed(6) + ' at ' + +paDeg.toFixed(6) + ' deg');
            }
          }
          var ptext = pcmt.concat(pnote).filter(function (t) { return t; }).join(' / ').replace(/[()]/g, '');
          rawLine = pcode.replace(/\s{2,}/g, ' ').trim() + (ptext ? ' ( ' + ptext + ' )' : '');
          lines[li] = rawLine;
        }
      }
      if (pendingPost) { sink.flush(camFeed); emitPassThrough(pendingPost); pendingPost = null; }
      var ln = rawLine.replace(/\(.*?\)/g, '').replace(/;.*$/, '').trim().toUpperCase();
      // Comment-only lines are kept (they used to be replaced by blank lines,
      // which dropped the CAM's tool list, operation names and notes).
      if (!ln) {
        if (rawLine === RETRACT_MARK) sink.flush(camFeed);   // the retract move is out before the marker
        emit(rawLine.trim()); continue;
      }
      // '%' tape delimiters: LinuxCNC only honours % as the FIRST line of the
      // file. The converter writes its own header first, so a passed-through %
      // would land mid-file. Strip it here and re-wrap the output at the end.
      if (ln === '%') { usedPercent = true; continue; }
      // ADDED 2.5.0: numbers like "F1E3" are not G-code (LinuxCNC has no
      // exponent notation). The word reader accepted them and the rest of the
      // line leaked into the output as a stray "e3" line. Refused instead.
      if (/\d\.?E[+-]?\d/.test(ln))
        inputError(li, rawLine, 'number in exponent notation (like 1E3). Write it as a plain number.');

      // Collect all G-codes on this line
      var gSet = {};
      var gm, gRe = /\bG(\d+(?:\.\d*)?)\b/g;
      while ((gm = gRe.exec(ln)) !== null) {
        var gn = Math.round(parseFloat(gm[1]) * 10) / 10;
        gSet[gn] = true;
      }

      // Extract word-value pairs (first occurrence per letter wins)
      var words = {};
      var wm, wRe = /([A-Z])\s*([-+]?(?:\d+\.?\d*|\.\d+)(?:[Ee][+-]?\d+)?)/g;
      while ((wm = wRe.exec(ln)) !== null) {
        if (!(wm[1] in words)) words[wm[1]] = parseFloat(wm[2]);
      }

      if ('T' in words) nextTool = String(Math.round(words['T']));

      // ADDED 2.11.4: polar INPUT is refused, never guessed (G16 is converted since 2.12.1, above). After G16 the X and Y words mean
      // radius and angle (Fanuc polar coordinate command); they were read as Cartesian X/Y
      // (G16 X20 Y45 became a point 49.24 mm from the centre) and G16 went to the output.
      // LinuxCNC polar words (@ radius, ^ angle) and polar interpolation (G12.1/G13.1,
      // Haas G112/G113) passed through unconverted. The converter itself makes the polar
      // output; the input must be plain Cartesian XY.
      // 2.12.1: Mitsubishi G12.2/G13.2 too; cylindrical interpolation (Fanuc G7.1, Haas G107) as well.
      if (gSet[12.1] || gSet[13.1] || gSet[112] || gSet[113] || gSet[12.2] || gSet[13.2])
        inputError(li, rawLine, 'polar interpolation (G12.1/G13.1, G112/G113, G12.2/G13.2) is not supported in the input. Post the job as a 3-axis mill with Cartesian X/Y; the converter makes the polar output itself.');
      if (gSet[7.1] || gSet[107])
        inputError(li, rawLine, 'cylindrical interpolation (G7.1, G107) is not supported. Post the job as a 3-axis mill with Cartesian X/Y.');
      // ADDED 2.12.1 (Marios: D): program flow the converter cannot follow is refused, never passed
      // through. A subprogram body (M98/M99, LinuxCNC o-word sub/call) was converted where it stands
      // in the file - after M30 - from the position of the line before it, not from the call; loops
      // and conditions (o-word if/while/repeat) run lines a different number of times than written;
      // parameters and expressions (#1, [5+5]) are values the converter cannot compute ("G1 X#1" lost
      // its X). The CAM can post all of these as plain moves.
      if (/\bM0*9[89](?![.\d])/.test(ln))
        inputError(li, rawLine, 'subprograms (M98/M99) are not converted. Post the job with the subprograms expanded into plain moves.');
      if (/^O\s*(<[^>]*>|\d+)\s*(SUB|ENDSUB|CALL|RETURN|IF|ELSEIF|ELSE|ENDIF|WHILE|ENDWHILE|DO|REPEAT|ENDREPEAT|BREAK|CONTINUE)\b/.test(ln))
        inputError(li, rawLine, 'o-word subroutines, loops and conditions are not converted. Post the job as plain moves.');
      if (/[#\[\]]/.test(ln))
        inputError(li, rawLine, 'parameters and expressions (#, [ ]) are not converted. Post the job with plain numbers.');
      if (/[@^]/.test(ln))
        inputError(li, rawLine, 'polar words (@ radius, ^ angle) are not supported. Post the job with Cartesian X/Y; the converter makes the polar output itself.');

      // ADDED 2.12.2 (Marios: "if they matter, do them"), after reading the whole Fanuc 16i/18i-MB
      // manual B-63534EN/02 and testing its codes on the converter. Until 2.12.1 only a LIST of
      // known-bad codes was refused and everything else passed: "G4 X1" (Fanuc dwell 1 s) moved the
      // tool to X1; the X/Y of G51 (scaling centre), G50.1 (mirror axis), G22 (stroke area), G29,
      // G45 and G60 became moves; NURBS (G6.2), involute (G2.2) and 3-D arcs (G2.4) became straight
      // lines; threading G33 became a plain G1; G5/G5.1 (Fanuc high-speed modes, LinuxCNC splines),
      // G43.4/G43.5, G65/G66 (macro calls) passed through. Now only the codes below are read; any
      // other G code stops with the line number. Codes refused with their own reason further down
      // are listed too, so that reason is the one shown.
      var G_READ = [0, 1, 2, 3, 4, 10, 17, 18, 19, 20, 21, 28, 30, 40, 43, 49, 52, 53,
                    54, 55, 56, 57, 58, 59, 59.1, 59.2, 59.3, 61, 61.1, 64, 73, 80, 81, 82, 83, 85, 89,
                    90, 91, 91.1, 92, 92.1, 92.2, 92.3, 94, 97, 98, 99];
      var G_OWN_REASON = [27, 31, 37, 38.2, 38.3, 38.4, 38.5, 41, 42, 41.1, 42.1, 68,
                          74, 76, 84, 86, 87, 88, 90.1, 93];
      for (var gk in gSet) {
        var gv = parseFloat(gk);
        if (G_READ.indexOf(gv) < 0 && G_OWN_REASON.indexOf(gv) < 0)
          inputError(li, rawLine, 'G' + gk + ' is not converted (the converter reads only plain 3-axis milling: G0-G3, G4 P, cycles G73/G81-G83/G85/G89, G17-G21, G28/G30/G53, G40/G43/G49, G54-G59, G61/G64, G80, G90/G91, G94, G98/G99). Post the job for LinuxCNC as a 3-axis mill.');
      }
      // Fanuc writes the dwell as "G4 X1.5" (seconds) as well as "G4 P" (B-63534EN p.114);
      // LinuxCNC only knows G4 P. An axis word on a G4 line was read as a move.
      if (gSet[4] && (('X' in words) || ('Y' in words) || ('Z' in words)))
        inputError(li, rawLine, 'dwell G4 with an axis word (Fanuc "G4 X" = seconds) is not converted. Write the dwell as G4 P<seconds>, on its own line.');
      // Fanuc optional chamfer / corner rounding ",C" ",R" (p.243): the comma word was read as the
      // C axis, and ",R" was ignored, leaving a sharp corner instead of the rounding.
      if (/,\s*[A-Z]/.test(ln))
        inputError(li, rawLine, 'chamfer / corner rounding words (,C ,R) are not converted. Post the job with the chamfers and roundings as plain moves.');
      // Block delete "/": LinuxCNC skips the line when the switch is on, but the converter splits
      // one input line into many output lines, and the "/" ended up on a line of its own - the
      // move then ran ALWAYS. A "/" inside a line (Fanuc: skip the rest) was dropped too.
      if (ln.indexOf('/') >= 0)
        inputError(li, rawLine, 'block delete "/" (optional skip) is not converted. Post the job without block-delete lines.');

      // The input must be plain XYZ milling G-code: a rotary or secondary
      // linear axis word means the program was posted for a different machine.
      ['A', 'B', 'C', 'U', 'V', 'W'].forEach(function (k) {
        if (k in words) inputError(li, rawLine, 'the input contains an ' + k + ' axis word. The converter expects 3-axis XYZ G-code (it produces the rotary axis itself) — post the job for a 3-axis mill.');
      });

      // Canned cycles: unsupported kinds stop here; drilling kinds are expanded.
      if (gSet[74] || gSet[76] || gSet[84] || gSet[86] || gSet[87] || gSet[88])
        inputError(li, rawLine, 'tapping, threading and spindle-stop boring cycles (G74/G76/G84/G86/G87/G88) are not converted. Enable "expand cycles" in the post.');
      if (gSet[98]) retractInitial = true;
      if (gSet[99]) retractInitial = false;
      var cyc = gSet[81] ? 81 : gSet[82] ? 82 : gSet[83] ? 83 : gSet[73] ? 73 : gSet[85] ? 85 : gSet[89] ? 89 : null;
      // An explicit motion G-code or G80 ends the cycle — but not the G0/G1
      // lines the converter itself generated for the previous hole.
      if (!isGen[li] && (gSet[80] || ((gSet[0] || gSet[1] || gSet[2] || gSet[3]) && cyc === null))) activeCycle = null;
      if (!isGen[li] && (cyc !== null || (activeCycle && (('X' in words) || ('Y' in words)) && !gSet[80]))) {
        // FIX 2.12.2: a G91 on the cycle's own line ("G91 G81 X5 Z-3 R-2") was not seen here (the
        // mode is updated later), and the holes were drilled at absolute X5 with the wrong depth.
        if ((distIncremental && !gSet[90]) || gSet[91]) inputError(li, rawLine, 'canned cycles in incremental mode (G91) are not converted. Post the cycles in G90.');
        if (!xyKnown || !zKnown) inputError(li, rawLine, 'canned cycle before the tool position is known. The CAM must position with G0 first.');
        var sc = unitScale;
        if (cyc !== null && (!activeCycle || activeCycle.code !== cyc)) {
          // FIX 2.12.3: a change of cycle code without G80 keeps the first cycle's initial level, as
          // LinuxCNC does (cycle_il, reset only by a non-cycle motion). It was the current Z (= R after
          // a G99 hole), so later G98 holes retracted only to R.
          activeCycle = { code: cyc, initialZ: activeCycle ? activeCycle.initialZ : curZ / sc,
                          R: activeCycle ? activeCycle.R : null, Z: activeCycle ? activeCycle.Z : null,
                          Q: activeCycle ? activeCycle.Q : null, P: activeCycle ? activeCycle.P : 0 };
        }
        if ('R' in words) activeCycle.R = words['R'];
        if ('Z' in words) activeCycle.Z = words['Z'];
        if ('Q' in words) activeCycle.Q = words['Q'];
        if ('P' in words) activeCycle.P = words['P'];
        if ('F' in words) camFeed = words['F'] * sc;
        requireFeed(li, rawLine);
        activeCycle.F = camFeed / sc;
        if (activeCycle.R === null || activeCycle.Z === null)
          inputError(li, rawLine, 'drilling cycle without R and Z.');
        var hx = ('X' in words) ? words['X'] : curX / sc, hy = ('Y' in words) ? words['Y'] : curY / sc;
        var gen = expandCycle(activeCycle, hx, hy, curZ / sc);
        if (!gen) inputError(li, rawLine, 'peck drilling (G83/G73) needs a positive Q.');
        var cp = splitNonMotion(rawLine, false);
        if (cp.pre) gen.unshift(cp.pre);
        if (cp.post) gen.push(cp.post);
        gen.unshift('( G' + activeCycle.code + ' expanded: ' + rawLine.trim().replace(/[()]/g, '') + ' )');
        Array.prototype.splice.apply(lines, [li + 1, 0].concat(gen));
        Array.prototype.splice.apply(srcNo, [li + 1, 0].concat(gen.map(function () { return srcNo[li]; })));
        Array.prototype.splice.apply(isGen, [li + 1, 0].concat(gen.map(function () { return true; })));
        continue;
      }

      // ─── INPUT VALIDATION & MODE TRACKING (FIX 2026-10-01) ────────────────
      // Anything that cannot be converted EXACTLY stops the conversion with a
      // message saying what to change in the post — never silently wrong output.
      if (gSet[41] || gSet[42] || gSet[41.1] || gSet[42.1])
        inputError(li, rawLine, 'cutter radius compensation (G41/G42) cannot be applied in polar coordinates. Post with compensation "in computer" (tool-centre path) instead.');
      var hasAxisWord = ('X' in words) || ('Y' in words) || ('Z' in words);
      if ((gSet[92] || gSet[52] || gSet[10]) && hasAxisWord)
        inputError(li, rawLine, 'coordinate offsets given as Cartesian X/Y values cannot be converted. Set work offsets at the machine (X = 0 at the chuck centre) and remove this line.');
      if (gSet[27] || gSet[31] || gSet[37] || gSet[38.2] || gSet[38.3] || gSet[38.4] || gSet[38.5] || gSet[68])
        inputError(li, rawLine, 'this command uses Cartesian coordinates and is not supported in polar output.');
      if (gSet[90.1])
        inputError(li, rawLine, 'absolute arc centres (G90.1) are not supported — use the default incremental I/J (G91.1).');
      if (gSet[93])
        inputError(li, rawLine, 'the input already uses inverse-time feed (G93). Post with units-per-minute feed (G94); the converter computes G93 itself.');
      if (gSet[17]) plane = 17;
      if (gSet[18]) plane = 18;
      if (gSet[19]) plane = 19;
      if (gSet[20]) unitScale = 25.4;
      if (gSet[21]) unitScale = 1.0;
      if (gSet[90]) distIncremental = false;
      if (gSet[91]) distIncremental = true;
      // Inch input: convert every length (and the feed, in/min -> mm/min) to mm.
      // Output is always G21, and all tolerances are in mm.
      if (unitScale !== 1.0) {
        ['X', 'Y', 'Z', 'I', 'J', 'K', 'R', 'F'].forEach(function (k) {
          if (k in words) words[k] *= unitScale;
        });
      }
      // A tool change may move the machine (TOOL_CHANGE_POSITION): position unknown.
      if (/\bM0*6\b/.test(ln)) { xyKnown = false; zKnown = false; }

      // Update modal move
      if (gSet[0]) modalMove = 'G0';
      if (gSet[1]) modalMove = 'G1';
      if (gSet[2]) modalMove = 'G2';
      if (gSet[3]) modalMove = 'G3';

      // Capture F word BEFORE the absorption check — needed even on lines that carry
      // a modal prefix such as 'G94 F500' or 'G94 G0 Z2.000 F300'.
      if ('F' in words) { camFeed = words['F']; }

      // ─── MACHINE-REFERENCE MOVES: G53, G28, G30 ───────────────────────────
      // CORRECTED 2026-10-01 (same day). The first version passed "G53 G0 Z0"
      // and "G28 G91 Z0" straight to the machine, reasoning that LinuxCNC
      // executes them as retracts. That is only true on a MILL, where machine
      // Z0 is the top of Z. On many lathe conversions (the author's included)
      // the Z home switch is at the TAILSTOCK end (the positive end), so
      // machine Z0 is at the CHUCK end: "G53 G0 Z0" would rapid the carriage
      // toward the chuck. G28 is no better — its stored position (parameters
      // 5161-5169) is machine 0,0,0 unless set with G28.1.
      // Rule now: a machine-coordinate Z retract is replaced by
      //   G0 Z<the program's own highest Z>   (2.11.0; was a machine Z the user entered)
      // with a value the user has entered for THEIR machine. With no value set
      // the conversion stops. X/Y "park" moves are skipped (nothing moves), and
      // G28/G30 with no axis words are rejected.
      var RETRACT_HELP = ' Machine coordinates differ from machine to machine (on a lathe conversion machine Z0 can' +
        ' be at the CHUCK end), so such a retract is never passed through. Set the post\'s safe-retract' +
        ' method to "clearance height" and post again.';
      if (gSet[53] || gSet[28] || gSet[30]) {
        sink.flush(camFeed);
        var refName = gSet[53] ? 'G53' : (gSet[28] ? 'G28' : 'G30');
        var rx = ('X' in words), ry = ('Y' in words), rz = ('Z' in words);
        if (gSet[53] && (gSet[1] || (!gSet[0] && modalMove !== 'G0')))
          inputError(li, rawLine, 'use G53 G0 for machine-coordinate retracts.');
        // CHANGED 2.5.0: "G53 G0 X.. Y.." (Fusion's optional end-of-program park)
        // was rejected while "G28 G91 X0 Y0" was skipped. Machine X/Y of a mill
        // mean nothing on this machine, and NOT moving can hit nothing: skipped
        // the same way, the position stays known. A Z on the line is still the
        // safe retract below.
        if (gSet[53] && (rx || ry))
          emit('( G53 X/Y park skipped: the tool stays where it is )');
        if (!gSet[53] && !rx && !ry && !rz)
          inputError(li, rawLine, refName + ' with no axis words sends EVERY axis to the stored position (machine 0,0,0 unless set with G28.1) — the chuck centre and the chuck end of Z.' + RETRACT_HELP);
        if (!gSet[53] && (rx || ry)) {
          var parkOnly = distIncremental && (!rx || Math.abs(words['X']) < 1e-9)
                                         && (!ry || Math.abs(words['Y']) < 1e-9);
          if (!parkOnly)
            inputError(li, rawLine, refName + ' with an X/Y intermediate point is Cartesian and cannot be converted.');
          // A park is a convenience, not a safety move: skip it, position unchanged.
          emit('( ' + refName + ' X/Y park skipped: the tool stays where it is )');
        }
        if (rz) {
          // 2.11.0: up to the program's own highest Z (work coordinates), as an
          // ordinary rapid that the machine layout handles like any other move.
          if (SAFE_Z_MM === null)
            inputError(li, rawLine, 'machine-coordinate retract (' + refName + '), but the program has no Z height of its own to retract to.' + RETRACT_HELP);
          // an absolute height; an incremental mode in force (e.g. "G28 G91 Z0" sets G91)
          // is switched off for this one move and restored after it
          var gen2 = ['( safe retract to the program\'s highest Z, replaces: ' + commentSafe(rawLine) + ' )',
                      'G0 Z' + (SAFE_Z_MM / unitScale).toFixed(4), RETRACT_MARK];
          if (distIncremental) { distIncremental = false; gen2.push('G91'); }
          Array.prototype.splice.apply(lines, [li + 1, 0].concat(gen2));
          Array.prototype.splice.apply(srcNo, [li + 1, 0].concat(gen2.map(function () { return srcNo[li]; })));
          Array.prototype.splice.apply(isGen, [li + 1, 0].concat(gen2.map(function () { return true; })));
        }
        continue;
      }

      // Absorb G20/G21/G93/G94 mode-switch words — we emit our own modal state.
      // CRITICAL: only skip (continue) if this is a PURE modal line with no motion.
      // Combined lines such as 'G94 G0 Z2.000' carry a real move that must be
      // processed; silently discarding them causes the Z coordinate to go stale and
      // produces collisions (e.g. tool retracts are dropped, Z stays at cut depth).
      if (gSet[17] || gSet[18] || gSet[19] || gSet[20] || gSet[21] || gSet[90] || gSet[91] || gSet[94]) {
        emit('( absorbed modal from: ' + commentSafe(rawLine) + ' )');
        var hasMotionOnAbsorbed = gSet[0] || gSet[1] || gSet[2] || gSet[3]
                                || ('X' in words) || ('Y' in words) || ('Z' in words)
                                || ('I' in words) || ('J' in words) || ('R' in words);
        // FIX (2026-10-01): keep whatever else was on the line. "G90 G54" used
        // to drop the G54 (work offset) together with the absorbed G90.
        var keepRest = rawLine.replace(/\(.*?\)/g, '').replace(/;.*$/, '')
          .replace(/\bG0*(?:17|18|19|20|21|90|91|94)(?![.\d])/gi, '')
          .replace(/\bN\d+/gi, '').trim();
        if (!hasMotionOnAbsorbed) {
          emitPassThrough(keepRest);
          if (/\bM0*6(?![.\d])/i.test(rawLine)) noteToolChange();
          continue;  // modal line — nothing more to do
        }
        // Motion also on this line — fall through to process the move below.
      }

      var hasPos = ('X' in words) || ('Y' in words) || ('Z' in words);
      var hasArc = ('I' in words) || ('J' in words) || ('R' in words);
      var isMove = (gSet[0] || gSet[1] || gSet[2] || gSet[3] || modalMove)
                   && (hasPos || hasArc);

      if (!isMove) {
        // ─── Pass-through guard ────────────────────────────────────────────────
        // Non-move lines are copied through verbatim. That is right for M-codes,
        // comments and spindle words, but Fanuc alarm PS214 lists G-codes that
        // are ILLEGAL inside polar interpolation mode, because their coordinates
        // are not (and cannot be) converted: G27, G28, G30, G31, G37, G52, G53,
        // G92, G17/G18/G19, G68 and the canned cycles G81-G89. If the CAM emitted
        // any of these, their raw Cartesian X/Y would reach the machine
        // unconverted — X read as a radius and Y as an axis that does not exist.
        // Flag them loudly instead of letting them slip by silently.
        var riskyG = null;
        for (var rg in gSet) {
          var rgn = parseInt(rg, 10);
          if (rgn === 27 || rgn === 28 || rgn === 30 || rgn === 31 || rgn === 37 ||
              rgn === 52 || rgn === 53 || rgn === 68 || rgn === 92 ||
              (rgn >= 17 && rgn <= 19) || (rgn >= 81 && rgn <= 89)) { riskyG = rgn; break; }
        }
        if (riskyG !== null) {
          passThroughWarnings++;
          emit('( !! WARNING: G' + riskyG + ' passed through UNCONVERTED \u2014 illegal in polar mode )');
          emit('( !! its X/Y are raw Cartesian and will be misread. Verify before running. )');
        }
        // ADDED 2.4.1: in LinuxCNC (and Mach3) G4 P is in SECONDS, but Fanuc
        // style posts write milliseconds: "G4 P2000" meant 2 s and waits 33
        // minutes. Kept as written (the converter cannot know), but flagged.
        if (gSet[4] && ('P' in words) && words['P'] >= 60) {
          dwellWarnings++;
          emit('( !! WARNING: dwell of ' + words['P'] + ' SECONDS - G4 P is seconds in LinuxCNC. Milliseconds? )');
        }
        // FIX (2026-09-12): the CAM's own M2/M30 used to pass through first, and
        // the converter then appended its "G94 restore" and a second M30 AFTER
        // it — lines that never execute. Restore G94 just before the CAM's end
        // instead, and suppress the duplicate at the bottom.
        emitPassThrough(rawLine.trim());
        if (/\bM0*6(?![.\d])/i.test(ln)) noteToolChange();
        continue;
      }

      // G91 input: convert to absolute here (arc I/J are already relative).
      if (distIncremental) {
        if ((('X' in words) || ('Y' in words)) && !xyKnown)
          inputError(li, rawLine, 'incremental (G91) X/Y move before any absolute XY position is known.');
        if (('Z' in words) && !zKnown)
          inputError(li, rawLine, 'incremental (G91) Z move before the Z position is known.');
        if ('X' in words) words['X'] += curX;
        if ('Y' in words) words['Y'] += curY;
        if ('Z' in words) words['Z'] += curZ;
      }
      var newX = ('X' in words) ? words['X'] : curX;
      var newY = ('Y' in words) ? words['Y'] : curY;
      var newZ = ('Z' in words) ? words['Z'] : curZ;

      var type = gSet[0] ? 'G0' : gSet[1] ? 'G1'
               : gSet[2] ? 'G2' : gSet[3] ? 'G3' : modalMove;

      // LinuxCNC reads P on G2/G3 as the number of TURNS; only one turn is converted.
      if ((type === 'G2' || type === 'G3') && ('P' in words) && Math.abs(words['P'] - 1) > 1e-9)
        inputError(li, rawLine, 'multi-turn arcs (G2/G3 with P) are not converted. Post helices as lines or single turns.');
      var nm = splitNonMotion(rawLine, !(type === 'G2' || type === 'G3'));
      if (nm.pre) {
        sink.flush(camFeed);
        emit(nm.pre);
        if (/\bM0*6(?![.\d])/i.test(ln)) noteToolChange();
      }
      if (nm.post) pendingPost = nm.post;
      // ── Motion: checks that belong to the INPUT, then hand over to the layout ──
      var arcWords = null;
      if (type === 'G1') {
        if (!xyKnown || !zKnown)
          inputError(li, rawLine, 'cutting move before the tool position is known (program start, or after G28/G53/tool change). The CAM must position X/Y and Z with G0 first.');
        requireFeed(li, rawLine);
      }
      else if (type === 'G2' || type === 'G3') {
        if (plane !== 17)
          inputError(li, rawLine, 'arcs in the XZ/YZ plane (G18/G19) are not supported. Set the post to output those as straight lines.');
        if (!xyKnown || !zKnown)
          inputError(li, rawLine, 'arc before the tool position is known. The CAM must position with G0 first.');
        requireFeed(li, rawLine);
        // Arc: linearize first, then polar-convert each sub-point
        var nI = ('I' in words) ? words['I'] : null;
        var nJ = ('J' in words) ? words['J'] : null;
        var nR = ('R' in words) ? words['R'] : null;
        checkArc(li, rawLine, curX, curY, newX, newY, nI, nJ, nR);
        arcWords = { I: nI, J: nJ, R: nR };
      }
      var how = null;
      if (type === 'G0' || type === 'G1' || type === 'G2' || type === 'G3') {
        how = sink.move({
          kind: type, words: words, arc: arcWords, feed: camFeed,
          from: { x: curX, y: curY, z: curZ }, to: { x: newX, y: newY, z: newZ },
          xyKnown: xyKnown, zKnown: zKnown, line: srcNo[li]
        });
      } else {
        emit(rawLine.trim());
      }
      // A rapid that stated Z makes Z known (also when Z was unknown before).
      if (type === 'G0' && ('Z' in words)) zKnown = true;
      if (how === 'pureZ') {
        // pure-Z rapid: X and Y are not updated (as before the restructure)
        curZ = newZ;
        if (('X' in words) || ('Y' in words)) xyKnown = true;
        continue;
      }
      curX = newX; curY = newY; curZ = newZ;
      if (('X' in words) || ('Y' in words)) xyKnown = true;
    }

    if (pendingPost) { sink.flush(camFeed); emitPassThrough(pendingPost); pendingPost = null; }
    // Flush any deferred segment before the end-of-program block.
    sink.flush(camFeed);

    var warnings = [];
    if (passThroughWarnings > 0) {
      warnings.push('( !! ' + passThroughWarnings + ' lines contained G-codes that are illegal inside polar )');
      warnings.push('( !! interpolation, Fanuc PS214 list, and were copied through UNCONVERTED.           )');
      warnings.push('( !! Search this file for "WARNING: G" and check each one before running.           )');
    }

    if (dwellWarnings > 0) {
      warnings.push('( !! ' + dwellWarnings + ' dwells G4 of 60 s or more - search this file for "dwell of" )');
    }

    // 2.8.0: one tool with two different stated diameters - the first was used
    scanned.conflicts.forEach(function (c) {
      warnings.push('( !! two diameters for ' + commentSafe(c) + ' - the first was used, check the tool )');
    });

    return { usedPercent: usedPercent, programEnded: programEnded, warnings: warnings };
  }
  return { read: read, scanToolDiameters: scanToolDiameters };
});
