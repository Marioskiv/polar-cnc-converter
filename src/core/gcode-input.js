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
  //   sink.move(event)       a G0/G1/G2/G3 (see the call below for the fields)
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
      TOOL_DIA = (activeTool in toolDiaRaw) ? toolDiaMM(activeTool) : O.toolDia;
      sink.tool(TOOL_DIA, activeTool);
      emit('( polar-cnc tool: T' + activeTool + ' D=' + TOOL_DIA.toFixed(4)
               + ((activeTool in toolDiaRaw) ? toolNote(activeTool) : ' - from settings, no diameter in the program') + ' )');
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
      if (pendingPost) { sink.flush(camFeed); emitPassThrough(pendingPost); pendingPost = null; }
      var ln = rawLine.replace(/\(.*?\)/g, '').replace(/;.*$/, '').trim().toUpperCase();
      // Comment-only lines are kept (they used to be replaced by blank lines,
      // which dropped the CAM's tool list, operation names and notes).
      if (!ln) { emit(rawLine.trim()); continue; }
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
        if (distIncremental) inputError(li, rawLine, 'canned cycles in incremental mode (G91) are not converted. Post the cycles in G90.');
        if (!xyKnown || !zKnown) inputError(li, rawLine, 'canned cycle before the tool position is known. The CAM must position with G0 first.');
        var sc = unitScale;
        if (cyc !== null && (!activeCycle || activeCycle.code !== cyc)) {
          activeCycle = { code: cyc, initialZ: curZ / sc,
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
      //   G53 G0 Z<retractZMachine>
      // with a value the user has entered for THEIR machine. With no value set
      // the conversion stops. X/Y "park" moves are skipped (nothing moves), and
      // G28/G30 with no axis words are rejected.
      var RETRACT_HELP = ' On a lathe conversion, machine Z0 can be at the CHUCK end, so the CAM\'s' +
        ' machine-coordinate retract cannot be passed through. Either set the post\'s safe-retract' +
        ' method to "clearance height", or enter "Safe retract Z (machine)" in the settings' +
        ' (a machine Z near your Z home, far from the chuck) and convert again.';
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
          if (O.retractZMachine === null)
            inputError(li, rawLine, 'machine-coordinate retract (' + refName + ').' + RETRACT_HELP);
          emit('G53 G0 Z' + O.retractZMachine.toFixed(4) + '  ( safe retract, replaces: ' + commentSafe(rawLine) + ' )');
          zKnown = false;
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
          xyKnown: xyKnown, zKnown: zKnown
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
