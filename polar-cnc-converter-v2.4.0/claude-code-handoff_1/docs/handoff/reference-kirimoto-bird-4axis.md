# Reference — Kiri:Moto CAM internals and Joshua Bird's 4-axis code

*Αρχείο αναφοράς για το Project Knowledge. Γράφτηκε 2026-10-07 από ανάγνωση του ίδιου του κώδικα (όχι περιλήψεις).
Σκοπός: να σχεδιαστεί ο άξονας κλίσης του ρούτερ στον converter και η συνεργασία με το Kiri:Moto, χωρίς να ξαναδιαβαστεί ο κώδικας.*

Read from source on 2026-10-07. Nothing below is copied into the converter: Kiri:Moto is MIT but each file
header also says "All Rights Reserved"; Bird's code is GPL-3 (two repos with a no-sell clause). We learn the
method and write our own code.

---

## 1. Kiri:Moto (GridSpace/grid-apps)

**Source read:** `github.com/GridSpace/grid-apps`, commit `d138275` (2026-07-26).
**Licence:** `license.md` = MIT, "Copyright 2014-2018 Stewart Allen <sa@grid.space>". Every source file header,
however, says `/** Copyright Stewart Allen <sa@grid.space> -- All Rights Reserved */`. The repo licence is MIT;
the headers are worth raising politely if code is ever contributed.

### 1.1 Where CAM lives
- `src/kiri/mode/cam/app/` — UI (ops menus, tools, animation).
- `src/kiri/mode/cam/core/` — `op.js` (CamOp base class), `ops.js`, `tool.js`.
- `src/kiri/mode/cam/work/` — worker side: slicing, toolpaths, export. About 430 KB of code.
- Machine definitions: `src/kiri/dev/cam/*.json` (e.g. `Any.Generic.LinuxCNC.json`).
- Docs: `docs/kiri-moto/CAM/` — `processOpts.mdx` says indexed stock is supported **"(barely)"**.

### 1.2 The toolpath point — the integration "door"
- `src/geo/point.js`: points carry **x, y, z and an optional `a`** (`setA(a)` stores `this.a`; `clone()` keeps it).
- There is **no tool-orientation vector** anywhere. Every Kiri toolpath assumes the tool is along the machine Z.
- All toolpath output goes through **`camOut(point, emit = 1, opts)`** in `work/prepare.js`.
  - `opts`: `{ center, factor, feed, shortCut, moveOnly }`.
  - Converts to work coordinates (`toWorkCoords`).
  - On an operation change: move to safe Z keeping the old A, move over the new point, then set the new A.
  - **Rotary interpolation:** when A changes, it inserts points every ~1 mm of arc length
    (`arcLen = |ΔA|/360 · 2π · maxZ`, `steps = ceil(arcLen)`), interpolating Z and A linearly. The comment says
    this is "for rendering and animation"; the points are emitted too.

### 1.3 The two 4th-axis features
- **Indexed** — `work/op-index.js` (`OpIndex`): needs `state.isIndexed`; rotates the mesh with
  `setAxisIndex(degrees, absolute)`, recomputes topo and shadows; in `prepare()` goes to `zSafe`, then outputs one
  move with `setA(degrees)`. Ordinary 3-axis ops then run on that face.
- **Lathe (continuous)** — `work/op-lathe.js` (`OpLathe`) + `work/topo4.js` (`Topo`, 644 lines).
  - Cylindrical "drop cutter" around the **X** axis: XZ are swapped, the part is rastered by angle, and for each
    angle the tool height (= radius) is found from the slice lines plus the tool profile (`lathePath()`).
  - Runs on workers / WebGPU (`slice`, `sliceGPU`, `sliceWorker`, `sliceMinions`, `lathe`, `latheGPU`).
  - The tool is always **radial** (perpendicular to the A axis). **No tilt.**
  - `prepare()`: starts at `newPoint(0, 0, zSafe).setA(0)`, emits every point of every `slice.camLines`, and ends
    with `G0 Z<safe>` plus `device.gcodeResetA` or the default **`G92.4 A0 R0`**.
- Neither is face-polar (XZC with the rotary axis along the spindle). That would be a new mode.

### 1.4 G-code export — `work/export.js`
- Axis letters fixed in a map `{ X, Y, Z, A, F, R, I, J }`.
- **Feed:** `feed = min(speed, maxf)`, `maxf = camFastFeedZ` when plunging, else `camFastFeed`;
  `dist = sqrt(dx² + dy² + dz²)` — **A is not part of the distance. No G93 anywhere.** With A moving, the
  controller's feed is not the real cutting feed (LinuxCNC uses the XYZ length only). This is a real gap our
  converter fills (G93 inverse time).
- `A` is written whenever it changes. Duplicate points (all deltas 0) are dropped.
- `gcodePre` directives: `;; SCALE {"X":..,"Y":..,"Z":..,"A":..,"DEC":..}`, `;; REWRITE-COMMENTS-PARENS`,
  `;; DECIMALS`. Options `outputInvertX/Y`, `camOriginTop`.

### 1.5 LinuxCNC machine definition — `src/kiri/dev/cam/Any.Generic.LinuxCNC.json`
- `pre`: `G21`, `G90`, `M03 S20000`; `post`: `M05`, `M30`; `tool-change`: `M6 T{tool}`.
- `dwell`: `G4 P{time} ; dwell for {time}ms` — **in LinuxCNC `P` is seconds.** If `{time}` really is in ms this is
  a bug in Kiri's LinuxCNC profile (not verified which unit `{time}` is). Same trap as `G04 P2000`.
- `strip-comments: true`.

### 1.6 What this means for us
1. A polar-face (XZC) mode can reuse Kiri's existing 3-axis ops: their XY toolpaths go through our converter
   core (segmentation, pole handling, G93) as the output stage. Hook points: the `camOut` stream in `prepare.js`,
   or the move records at export.
2. A router **tilt** axis needs a new concept in Kiri: a tool direction per point (or a tilt angle), and ops that
   produce it. That is a bigger contribution than the polar mode — do the polar mode first.
3. G93 for any rotary move (including Kiri's own A-axis lathe/indexed output) is a concrete improvement to offer.

---

## 2. Joshua Bird — Core R-Theta 4-axis printer and slicers

### 2.1 Repositories and licences (verified in the files)
| Repo | Commit | Licence |
|---|---|---|
| `jyjblrd/S4_Slicer` | `bc4b8d9` (2025-04-27) | GPL-3.0 |
| `jyjblrd/Radial_Non_Planar_Slicer` | `6a01738` (2025-06-08) | GPL-3.0 **+ no-sell exception** |
| `jyjblrd/Core-R-Theta-4-Axis-Printer` | `107e2c1` (2025-06-08) | GPL-3.0 (hardware) **+ no-sell exception** |

All copyleft → **no code may go into the MIT converter.** Method only.

### 2.2 Machine
C = rotating bed, X = radial arm, Z = lead screw, **B = nozzle tilt about the tangential axis** (the nozzle leans
toward/away from the centre, in the plane through the bed axis). X and B share one belt (CoreXY-like mixing).

### 2.3 Radial slicer (`main.ipynb`, 272 lines of code)
- **Tilt is a rule of the radius:** `ROTATION = lambda r: deg2rad(15 + 30·r/r_max)` (propeller/tree); alternatives
  in comments: fixed `-40°`, or `-40 + 30·(1 - r/r_max)²` (bridge).
- **Segmentation:** every G1 cut into fixed **1 mm** pieces *before* the transform.
- **Feed:** G93 inverse time, `F = 1 / (seg_length / feed)` per piece.
- **Transform per point:** `r = |xy|`, `θ = atan2(y, x)`, shortest-delta unwrap (±π) accumulated into C.
- **Nozzle-offset compensation** (L = pivot-to-tip): `r += sin(tilt)·L`, `z += (cos(tilt) − 1)·L`;
  output `B = −tilt`.
- Rapids: written in **G94 with F50000**, then back to G93. Points with z < 0 or NaN are skipped.
- **No pole handling.**

### 2.4 S4 slicer (`main.ipynb`, 1316 lines of code)
- Tetrahedral mesh; a **rotation field** per cell (about the tangential vector `cross(Z, cell_center_xy)` → always
  radial-plane tilt), initial value from the overhang angle, then optimised (neighbour smoothness + target,
  scipy). The mesh is deformed, sliced with Cura, and every G-code point is mapped back by barycentric
  interpolation, giving position **and tilt** per point.
- **Tilt smoothing:** exponential moving average, α = 0.2.
- **Max tilt change per point: 1°** (`ROTATION_MAX_DELTA`). Larger jumps get interpolated points (inverse-time F
  multiplied by the number of pieces) "to prevent the nozzle hitting the part as it rotates".
- `NOZZLE_OFFSET = 42` (comment: "actually 41.5").
- Travel moves: **1 mm hop along the tool axis**: `r += −sin(tilt)·(L + hop)`,
  `z += (cos(tilt) − 1)·(L + hop) + hop`; output `B = +tilt` (sign convention opposite to the radial slicer).
- Same θ unwrap. **No pole handling.**

### 2.5 Firmware (RepRapFirmware, `reprap firmware config/`)
- **Two modes:** `topolar.g` uses RRF's **built-in polar kinematics** (`M669 K7`) for normal printing;
  `to4axis.g` switches to `M669 K0` (linear motor-mixing matrix) with `M584 … S0` = "treat all as linear axes in
  feedrate calculations (have to use inverse time feed rate in gcode)".
- 4-axis limits: **C ±20,000,000** (practically unlimited turns), B −180 … (90 − offset).
- Max speeds (units/min): C 21600, X 20000, Z 8000, B 21600; accel: C 2000, X 5000, Z 1500, B 2000.
- Mixing: `M669 K0 C0:0:0:0:1 X-1:0:0:1:0 Z0:0:1:0:0 B0.22222222:0:0:0.222222222:0`.

### 2.6 What we take (as method)
- Tilt in the **radial plane** (about the tangential axis): C stays the polar angle, the pole logic still works.
- Pivot-to-tip compensation, **per tool** for a router (L changes with every tool and stick-out).
- Tilt smoothing and a **max tilt change per block** with interpolated points.
- Hop along the tool axis for travel moves.
- G93 for every move, and practically unlimited C limits in the controller.
- What Bird does **not** have and we already do: pole handling, error-controlled segmentation, verification.

---

## 3. Converter state at the time of writing (v2.4.0, 2026-10-07)
- Automatic centre zone = half the chord tolerance; only lines practically through the pole get Signed-X /
  Index at Pole; Pocket Fill only if asked for (or an explicit large zone).
- Local segmentation, each piece accepted by its measured joint-interpolation error.
- Arcs split for the polar transform (chord tol/2 + polar 0.4 tol).
- Merge of tiny moves checks the merged block's real error and never drops a point that is off the new block.
- Validator understands R arcs.
- Sweeps: 1,424 near-pole lines, 3,000 random arcs, 800 random polylines — worst 0.0225 mm (tol 0.025).

## 4. Agreed plan for the tilt axis (Marios, 2026-10-07)
Future machine: chuck = C, router on X and Z, plus a rotary axis that **tilts the router continuously** during a
program (he calls it A; in the X-Z plane the conventional letter would be B — the letter is a setting).
Goal: make the converter attractive for the Kiri:Moto author to accept.
1. Study Kiri:Moto's 4-axis code — **done** (section 1).
2. Restructure the converter into input → machine layout → output with **zero output change** (golden 144/144).
3. Add the tilt layout: tool-direction input (Kiri API / 5-axis G-code), pivot-to-tip per tool, tilt smoothing,
   max tilt per block, tip + orientation error checks, simulator with a tilted tool.
