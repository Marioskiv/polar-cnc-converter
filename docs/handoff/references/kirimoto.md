# Reference — Kiri:Moto (GridSpace/grid-apps)

*Full CAM read 2026-10-07, from the source itself (no summaries). First pass the same day was 4th-axis only;
this replaces it and corrects two points (see §9). Why: Marios may one day offer the converter to Kiri:Moto's
author (Stewart Allen) so that Kiri becomes a CAM for polar / multi-axis machines such as his XZC (he also
named "XZCYA", "ZCZA" and others — to be defined with him).*

- **Repo:** `https://github.com/GridSpace/grid-apps` — commit **`d138275`** (2026-07-26), version **4.7.0**.
  Re-read with `git clone --depth 50 https://github.com/GridSpace/grid-apps` and `git checkout d138275`.
- **Licence:** `license.md` = **MIT** ("Copyright 2014-2018 Stewart Allen"). But every source file starts with
  `/** Copyright Stewart Allen <sa@grid.space> -- All Rights Reserved */`. Raise politely before contributing;
  never copy Kiri code into our repo without his written OK. Our converter is MIT, so he may take ours.
- **Size:** `src/kiri` ≈ 47,600 lines (app 16,500, modes 26,100 of which **CAM 12,400**, FDM 6,600, SLA 5,900).
  The monorepo also holds Mesh:Tool (`src/mesh`) and Void:Form (`src/void`, a CAD in early development).
  Author's own map for AI agents: `docs/agents.md`; his to-do list: `docs/future.md`.
- **What was read in full:** CAM `work/` (slice, prepare, export, op-lathe, op-index, op-loop, topo4 lathe path,
  init-work), `core/op.js`, `core/ops.js`, `run/engine.js`, `run/cli.js`, `app/export.js`, `core/print.js`
  (Output class), device profiles, CAM docs (ops, processOpts, gcode-macros, apis, integrations), `mods/`.
  Skimmed only: the other CAM ops (area, contour, pocket, …), `topo3.js`, the UI files (`mode/cam/app/*`).
  Not read: FDM, SLA, laser, Mesh:Tool, Void:Form (not relevant to CNC output).

---

## 1. Architecture in one page

- Browser app (plus an Electron build). Heavy work runs in **Web Workers** (`run/worker.js`, a pool of
  "minions" in `run/minion.js`); some CAM steps can use **WebGPU**.
- A model is a **widget**. Settings = `device` (machine), `process` (job), `controller` (app), `tools`.
- Each mode (CAM, FDM, …) is a **driver** with the same contract: `slicePre → slice(widget) → prepare(widgets)
  → export(print)`. CAM's driver: `mode/cam/work/init-work.js` exports `CAM = { slice, prepare, export, … }`.
- **Headless:** `run/engine.js` (`newEngine()`): `load/parse STL → setMode('CAM') → setDevice/Process/Tools/
  Stock/Origin → slice() → prepare() → export()` (export resolves to the G-code text). Same calls exist for an
  embedding IFrame (`docs/kiri-moto/apis.md`).
- **`run/cli.js` is stale:** its file list `src/cli/kiri-source.json` names 59 files, **30 do not exist**
  (pre-ES-module layout). Command-line slicing does not work at this commit.

## 2. CAM slice — `work/slice.js` (`cam_slice`)
- `process.ops` = the user's operation list. Each op type maps to a class in `core/ops.js` (area, contour,
  drill, gcode, helical, index, laser on/off, lathe, level, loop, outline, pocket, register, rough, shadow,
  trace, xray). Base class `CamOp { slice(progress), prepare(ops, progress), weight() }`.
- A shared `state` object is handed to every op (widget, stock, tool, workarea Z limits, `setAxisIndex`,
  `addSlices`, slicer factory, shadows, tabs).
- Ops produce **slices** whose `camLines` are polygons of `Point`s (`geo/point.js`: x, y, z and optional `a`).
- **Loop** op: duplicates the next N ops M times (expansion happens here; the op itself is a marker).
- Non-indexed jobs start with a hidden `shadow` op; indexed jobs with an `index` op.

## 3. CAM prepare — `work/prepare.js` (`prepare_one`), the routing layer
- Calls each op's `prepare(ops)`. The `ops` toolbox: `camOut`, `polyEmit`, `pocket`, `emitDrills`,
  `emitTraces`, `setTool`, `setSpindle`, `setContouring`, `setTravelBoundary`, `addGCode`, `newLayer`, …
- **`camOut(point, emit, opts)`** is the single door for every move (emit 0 = G0, 1 = G1, 2/3 = arc):
  - widget → work coordinates (`toWorkCoords`), carries `a` forward;
  - on an op change: up to `zSafe` keeping the old A, over, then the new A;
  - **rotary "lerp":** when A changes it adds points about every 1 mm of arc (`arcLen = |ΔA|/360·2π·maxZ`),
    tagged `type: "lerp"` — **display/animation only, dropped at export** (§9);
  - travel logic: coastline routing, short moves turned into cuts, plunge-through-stock caught (rapid to just
    above stock, then cut), "up and over" for long moves / travel-boundary crossings, lathe moves split Z first;
  - outside contouring, **every downward move becomes a cut at the plunge rate** ("plunge safety catch").
- Arcs: `polyEmit` can fit arcs (`camArcEnabled`, tolerance `camArcTolerance`) → G2/G3 with I/J **relative**.
- Output records: `print.addOutput(layer, point, emit, speed, tool, { type, center })` → `Output` objects
  (`core/print.js`): `{ point, emit, speed (mm/min, or dwell **ms** when point is null), tool, type, center }`.

## 4. CAM export — `work/export.js` (`cam_export`)
- Walks the Output records, writes one line per move. `X Y Z` written when changed, **`A` whenever it changes**,
  `F` only when it changes, `I J` for arcs.
- **Feed:** `feed = min(speed || maxf, maxf)`, `maxf = camFastFeedZ` when going down else `camFastFeed`.
  `dist = √(dx²+dy²+dz²)` — **A is not in the distance and there is no G93 anywhere** in Kiri. On a move where
  A turns, LinuxCNC applies F to the XYZ length only, so the real cutting speed is wrong (pure-A moves read F
  as deg/min). Time estimate uses the same distance (A ignored).
- G0 lines also carry `F` (the rapid feed). Dup points are dropped. First move (and after a tool change) is
  split: XY then Z, or Z then XY with `camFirstZMax`.
- **Header directives** in the device `gcodePre`:
  `;; SCALE {"X":..,"Y":..,"Z":..,"A":..,"DEC":n}`, `;; DECIMALS = n`, `;; COMPACT-OUTPUT`,
  `;; AXISMAP {"A":"C", …}` (rename output axes), `;; REWRITE-COMMENTS-PARENS` (`;` comments → `( )`).
- Macros: `{tool}`, `{tool_name}`, `{speed}/{spindle}/{rpm}`, `{feed}`, `{pos_x/y/z}`; dwell: `{time}` =
  `{time_sec}` = **seconds**, `{time_ms}` = ms.
- Options: `outputInvertX/Y`, `camOriginTop` (Z0 at stock top, default on), `camOriginCenter`,
  `camOriginOffX/Y/Z`, `camToolInit`, `camFirstZMax`.
- Header comments include a tool list in **this format**: `; tool#=1 flute=6 len=20 unit=metric`.

## 5. Rotary support today (A axis = rotation about X, a 4th-axis lathe/indexer)
- Device switch `useIndexed` ("4th axis"); process switch `camStockIndexed`. Only the **Makera Carvera**
  profiles enable it. Reset macro `gcodeResetA` (default `G92.4 A0 R0`, Carvera firmware).
- **Indexed** (`op-index.js`): rotates the mesh (`setAxisIndex`), recomputes topo/shadows, then normal 3-axis
  ops machine that face. prepare: go to `zSafe`, one move with the new A.
- **Lathe** (`op-lathe.js` + `topo4.js`): cylindrical drop-cutter. XZ swapped; for each angle step (default
  1°) the radius at each X is the max over the tool profile of the slice lines (`lathePath`). Output: per X
  ring, points (x, 0, z=radius, A) — A keeps decreasing (`degrees + i·-360`) so it never rolls back; or a
  "linear" zig-zag. Ends with `G0 Z<safe>` + reset A. Tool always radial; **no tilt anywhere**.
- `docs/kiri-moto/CAM/processOpts.mdx`: indexed stock is supported "**(barely)**" — the author's own word.
- None of this is face-polar (rotary axis along the spindle, our XZC).

## 6. Extension points — how our converter could plug in (best first)
1. **`device.gcodeProc` post-processor hook** (`app/export.js` `exportGCodeDialog`): if the device profile
   names a function, `self[gcodeProc](gcode)` receives the whole G-code text and returns the new text. Our
   converter is already a plain browser global (`PolarCNC.converter.convert(text, options)`), so a polar
   device = Kiri's normal 3-axis output + this hook, **with no change to Kiri's code**. Limits: set only in the
   device JSON (no UI field); runs only in the UI export dialog, **not** in `engine.export()`; the function must
   be loaded into the page first (a mod, or a script tag in a self-hosted copy).
2. **Mods** (`mods/*/init.js`, server side): `server.inject("kiri", "file.js")` adds a client script that runs
   `self.kiri.load(api => …)` and can wrap API functions (see `mods/devel`). Only on a **self-hosted** server
   (`npm run dev` / Electron), not on grid.space.
3. Header directives (`AXISMAP` etc.): rename/scale only, no kinematics.
4. A real contribution in Kiri's core: a machine-kinematics option (e.g. "polar face XZC") whose export runs
   the converter, plus a polar animation (rotating chuck). Needs Stewart's agreement — it is his code.

## 7. Facts that matter for an XZC job made in Kiri
- Work XY origin must be the **chuck centre**: use `camOriginCenter` (+ offsets) so X0 Y0 = part centre on the
  rotary axis. Z: `camOriginTop` (Z0 = stock top) matches our usual setup.
- Kiri writes G2/G3 with relative I/J (fine for us), `;` comments (LinuxCNC accepts them; our converter keeps
  comment-only lines), F on G0 lines (LinuxCNC treats it as modal feed — so do we).
- **Our converter does not yet read Kiri's tool comments** (`; tool#=N flute=D …`: semicolon, not parentheses,
  and a different pattern). Today it would fall back to the Tool Diameter setting. Small converter change
  when we get there.
- Kiri's own A-axis output would be **rejected** by our converter (A words in the input) — correct: that is
  a different machine (A about X), not face-polar.

## 8. Problems found in Kiri (verified in the code) — small, concrete things to offer Stewart
1. No G93: feed wrong whenever A moves (see §4). Our converter's G93 method is the fix.
2. `run/cli.js` broken: 30 of 59 files in `src/cli/kiri-source.json` missing.
3. Docs say `;; COMMENT_REWRITE_PARENS` (`gcode-macros.md`) but the code checks `;; REWRITE-COMMENTS-PARENS`.
4. Dwell time estimate: `time += out.speed / 60` with `speed` in **ms** (should be `/ 1000`): a 250 ms
   dwell counts as 4.2 s.
5. `Any.Generic.LinuxCNC.json`: `G4 P{time} ; dwell for {time}ms` — the G-code is right (`{time}` is
   seconds, LinuxCNC P is seconds), only the comment is wrong.
6. `op-lathe.js`: `gcodeResetA.join('\n') ?? "G92.4 A0 R0"` — `join` never returns null, so the fallback never
   applies (an empty list gives an empty line). Harmless for LinuxCNC (which has no G92.4), but not as meant.

## 9. Corrections to the first notes (same day, first pass)
- "Interpolated lerp points are emitted too" — **wrong**: `export.js` skips `type === 'lerp'`; G-code has one
  block per A change.
- "Axis letters fixed" — **wrong**: `;; AXISMAP` renames them.
- The dwell unit question is settled: `{time}` is seconds (see §4, §8.5).

## 10. Plan (agreed principles; each step only with Marios's go-ahead)
1. **Prove it without touching Kiri:** a device profile with `gcodeProc` + a small loader for our converter on
   a self-hosted Kiri; make a real XZC part from a Kiri job; air cut / "F" test / aluminium part.
2. Converter: read Kiri's tool comment format; restructure into input → machine layout → output with zero
   output change (golden 144/144), so other layouts (tilt axis, Marios's "XZCYA", "ZCZA", …) can be added.
3. Only after real cuts and photos (STATUS.md): contact Stewart. Offer the small fixes of §8 first (trust),
   then G93 for his A-axis output, then a polar-face machine kind. Ask about the "All Rights Reserved" headers.
4. Tilting tool (A/B in the X-Z plane): Kiri has no tool orientation per point; that is a much bigger change on
   his side. Method notes from Bird: `bird-4axis.md`.
