# Polar CNC — Cartesian → Polar (XCZ) G-code Converter &amp; Simulator

A browser-based tool that converts ordinary 3-axis XYZ G-code (from Fusion 360 or any CAM package) into
**polar G-code for face machining** on a machine with one radial axis, one rotary axis and one depth axis —
typically a lathe conversion where the chuck turns the part and a spindle on the carriage machines its face.

It is **machine-independent**: the rotary axis can be C, A or B, X can be output as radius or diameter, either
axis can be inverted, and all of it is saved as a **machine profile** (a small JSON file you can share). Output
uses only widely supported codes (`G0/G1`, `G93/G94`, `G53`, comments) and has been checked against the
LinuxCNC interpreter source and the Mach3 G-code list; other controllers that support G93 inverse time should
work — check yours before the first cut.

Live demo (once GitHub Pages is enabled for this repo): https://marioskiv.github.io/polar-cnc-converter/

Open [`index.html`](./index.html) directly in any modern browser — no build step, no server required.

> [!WARNING]
> **Project Status & Disclaimer:** This software is currently in the **experimental/development** phase. The conversion algorithms and mathematical models have been validated via the built-in 3D simulator and dry-run code analysis, but **the generated G-code has not yet been physically tested on a live CNC machine**. 
> 
> If you decide to test this on your hardware, always perform a **dry run** (air cut) first with no stock or tooling installed, and keep your hand close to the E-stop! Use at your own risk.

## Why this exists

Converting a Cartesian XY toolpath to Polar (radius + angle) is conceptually simple — but naively doing it
introduces two hard problems on a real machine:

1. **Feed-rate correctness.** A polar machine's tangential tool-tip speed depends on the radius
   (`v = r · ω`). A feed rate that's correct for a Cartesian machine is wrong on a polar one — too slow near
   the edge, or physically impossible near the center. Just re-emitting the original F value (as most simple
   postprocessors do) produces an inefficient or physically incorrect program.
2. **The center singularity.** At small radius, a tiny Cartesian move can demand a huge, sudden rotation of
   the C axis (in the limit, infinite angular velocity at r = 0). Something has to give: freeze the axis,
   detour around it, or reformulate the move.

This project solves both:

- **G93 inverse-time feed** — every emitted `G1` block carries its own computed `F` (`F = 1/T`, with T the
  time the CAM's feed needs along the real 3-D path), rather than letting the controller reinterpret a
  Cartesian-style F on non-Cartesian motion.
- **Geometry here, dynamics in the controller.** The converter changes coordinates, never the machine's
  dynamics. It writes the CAM's feed; the controller applies its own axis velocity and acceleration limits to
  every move — LinuxCNC does this in `getStraightVelocity()`, and g2core/TinyG document the same rule: if one
  axis cannot keep up, the move is slowed to the limiting axis. So there are no speed, acceleration, gear-ratio
  or cornering settings to get wrong.
- **Center-zone handling.** Only lines that pass practically **through** the pole get special treatment: the
  centre zone is automatic, **half the chord tolerance** (0.0125 mm by default). Every other line — even one
  passing 0.05 mm from the centre — is converted **exactly**; near the centre the chuck must turn fast, so the
  controller slows the move — the same way Fanuc and Siemens controls behave. (Until 2.3 the zone was 2 mm, and
  lines passing 0.05–2 mm from the centre were cut up to 3.8 mm off their path.) The strategy is chosen
  automatically (Auto); **X Axis Min** decides whether the tool may cross to the other side of the centre.
  A profile can still fix one strategy (`centerMode`). The four strategies:
  - **Signed X** — freeze C and let X sweep through zero into negative values (X<0 at a fixed C is the same
    point as +|X| at C+180°), so a cut through the centre needs **no C rotation at all**. Used only when it is
    *exact*: the whole line must lie on the axis through the pole at the frozen angle, and must fit the X travel
    limits. If the tool is already at the pole, C is first spun to the line's direction (a pure spin at r = 0),
    which makes any line leaving the pole exact. Siemens TRANSMIT default (`POLE_SIDE_FIX = 0`, "pole crossing").
  - **Auto** *(default)* — tries, in order: **Signed X** (if exact and within travel) → **Index at Pole** (for a
    genuine through-the-pole crossing). With the automatic zone, a line that only glances it is converted
    directly (its error stays within about one zone radius); Pocket Fill is not used.
  - **Index at Pole** — feed X in to the line's closest-approach radius at the correct depth, rotate C with X and
    Z held still, feed back out. X never goes negative, so it works with no travel past the chuck centreline.
    Radial lines ending at or leaving from the pole are handled exactly. Siemens TRANSMIT `POLE_SIDE_FIX = 1/2`.
  - **Pocket Fill** — mills the centre disk with concentric circles the first time it is entered at a given Z
    depth. It deliberately clears the *whole* disk, removing material the CAM did not ask for, so it is used only
    when a profile asks for it (`centerMode: fill`) or sets a centre zone larger than the chord tolerance.
- **Leaving the negative-X representation safely.** After a Signed-X pass the tool can sit at, e.g., `X-50 C0`.
  Converting the next point naively gives `X50 C180` — the same physical spot — and LinuxCNC would interpolate
  X and C together, sweeping the tool through the part (measured 14.6 mm off-path). The converter instead
  retraces the line it has just cut to the pole, spins C by 180° there, and retraces back out. Nothing is gouged.
  Pure-Z moves (retracts, plunges) never touch X or C at all.
- **Adaptive chordal segmentation** — subdivides lines/arcs based on distance-to-centre and a chord-tolerance
  setting, denser near the centre where curvature (in polar space) is highest.
- **Segmented rapids.** Because the output is *polar*, LinuxCNC interpolates X and C linearly in joint space,
  which traces a **spiral** in Cartesian space, not the straight line the CAM assumed. A single-block rapid
  from (50,0) to (−50,0) would sweep a half-circle of radius 50 — 50 mm off-path at rapid speed. `G0` moves
  are therefore walked along the true Cartesian line and emitted as a short chain of blocks, with a looser
  `RAPID_TOL` since a rapid removes no material. This is exactly why Fanuc (G12.1) and Haas (G112) *forbid*
  `G00` inside polar mode — a real-time control cannot do this, but a pre-processor can.
- **Everything else in the program is kept.** Tool changes (`T`/`M6`), tool length (`G43 H`), spindle and
  coolant words, work offsets, dwells, comments — including when they share a line with a move. They are
  emitted before the move (stop codes `M0/M1/M2/M30` after it), the same order a controller executes a line.
- **Tools.** The active tool's diameter is read from the CAM's tool comments (e.g. Fusion's `(T2 D=3. ...)`),
  or taken from the **Tool Diameter** setting, and used for the centre pocket fill and the material map.
- **Drilling cycles expanded.** `G81, G82, G83, G73, G85, G89` with `G98/G99`, `R`, `Q`, `P` become plain
  moves — in polar, a hole is just a position (X, C) followed by Z moves.
- **Rejected with the line number** (never converted wrongly): cutter compensation `G41/G42`, tapping and
  threading cycles, offsets set with coordinates, probing, `G68`, `G90.1`, `G93` input, `G18/G19` arcs,
  multi-turn arcs, rotary-axis words in the input, and cuts before the tool position is known.
- **3D toolpath simulator** (Three.js) with continuous, feedrate-accurate playback (not just point-to-point
  jumps), Rotary-Mill and Static-3D view modes, live telemetry, a material-removal depth map with rapid-collision
  detection, and the peak chuck speed the program asks for.

## Why a pre-processor and not custom kinematics

LinuxCNC *can* do this conversion in real time — `rosekins` ships with it, and builders have written custom
`caxis.comp` modules using `switchkins` (see `millturn.comp` for the official template). That route makes
straight lines and constant feed free, because the trajectory planner works in Cartesian space and only
converts on the final servo tick.

It was rejected here for three reasons:

1. `kinematicsInverse()` runs once per servo tick and sees only the current pose — no lookahead. The
   centre-crossing strategies and adaptive segmentation in this converter are whole-program
   decisions that cannot be relocated into a point-wise real-time function.
2. Every documented success required high-resolution closed-loop feedback (one builder needed a 10,000-line
   encoder with Mesa input filtering disabled, and still reported feature misalignment). Open-loop steppers
   are the wrong hardware tier.
3. Under `trivkins` the C axis *is* joint 2, so LinuxCNC enforces `[JOINT_2]` velocity and acceleration
   limits on every commanded move — a genuine safety backstop that is weakened under non-trivial kinematics.

The trade-off is that straightness and feed correctness must be bought with segmentation and per-block G93,
which is what most of this converter's machinery exists to do. Notably, this is also the approach a LinuxCNC
developer recommends for exactly this machine class: *work out the feed rates at the G-code level or earlier,
and use inverse-time feed mode to tell the motion controller how long each move should take.*

## Verification

```bash
npm install     # one time — installs jsdom, used only by the UI test
npm test        # all tests below
node tools/sweeps.js   # heavy random validation (several minutes) - run after any converter change
```

The suite runs automatically on every push via GitHub Actions (`.github/workflows/test.yml`).

| Test | What it guards |
|---|---|
| `options.test.js` | option parsing, including "0 is a real value" (X Min, fill step, retract) |
| `input.test.js` | real CAM post output (Fusion LinuxCNC / grbl), G91, G20, `%`, retracts, and everything that must be rejected with its line number |
| `lint.test.js` | every output line of 147 programs is valid LinuxCNC: no nested comments, one motion code per line, F on every G93 move |
| `words.test.js` | non-motion words (T, M6, S, M3, G43 H, coolant…) and expanded drilling cycles keep their order |
| `golden.test.js` | byte-for-byte output of 144 program/mode/settings combinations — any unintended change fails |
| `geometry.test.js` | 80 cases (lines and ramps near the pole, arcs, R arcs, with X Min 0) replayed with rosekins kinematics against the CAM path |
| `sim.test.js` | the simulator shows retracts going up, realistic block times, joint-space curves |
| `material.test.js` | material is removed only under the cutter path; rapids into material are reported |
| `ui.test.js` | the page loads without errors, form defaults equal `DEFAULT_OPTIONS`, buttons are wired, warnings shown |

If you change converter behaviour **on purpose**, review the diff and refresh the baseline with
`npm run test:golden:update`.


The converter is a pure module (`src/core/converter.js`) and is tested directly in Node — no browser needed.
Every output block is replayed the way LinuxCNC executes it under
`trivkins` — linear interpolation of X, C and Z in joint space — then mapped back to Cartesian with the
**forward kinematics of LinuxCNC's own `rosekins`** (`x = r·cos C`, `y = r·sin C`). The distance from each
replayed point to the path the CAM asked for is measured.

With an X travel of −10 … +125 mm, in Auto, Index and Signed modes:

| Case | Cutting (G1) | Rapids (G0) |
|---|---|---|
| Square off-centre | 0.024 mm | 0 |
| Facing pass through the pole | 0.000 mm | 0 |
| Signed-X then zigzag stepover | 0.025 mm | 0 |
| Lines 5 mm / 3 mm from the pole | 0.025 mm | 0 |
| Circle round the pole / off-centre circle | 0.001 / 0.021 mm | 0 |
| Ramp through the pole | 0.000 mm | 0 |
| Rapid across the pole | 0.000 mm | 0 |
| Corner exactly on the pole | 0.000 mm | 0 |

Targets are `CHORD_TOL` (0.025 mm) for cutting and `RAPID_TOL` (0.5 mm) for rapids. A realistic 100 mm zigzag
facing program at two depths converts to ~3,500 blocks in ~20 ms with no invalid values.

**What this does NOT prove:** the harness models joint-space interpolation only. It does not model LinuxCNC's
`G64` blending (which rounds corners by up to its `P` value), acceleration, or anything about the physical
machine. Air-cut every new program first.

## Project structure

```
index.html              page markup only
css/styles.css          styles
src/core/geometry.js    angle helpers, arc linearisation           (pure)
src/core/converter.js   Cartesian -> polar XZC, DEFAULT_OPTIONS    (pure)
src/core/polar-parser.js polar G-code -> toolpath for the simulator (pure)
src/ui/state.js         shared UI/simulator state, DOM references
src/ui/settings.js      reads the settings panel into an options object
src/core/material.js    material removal depth map, rapid-collision check (pure)
src/sim/simulator.js    Three.js scene, per-frame update, animation loop
src/ui/app.js           event handlers and boot
tests/                  Node test suite (see Verification)
profiles/               machine profiles (generic examples + the author's machine)
examples/               LinuxCNC vismach simulation of an example lathe conversion
```

The three `src/core` files have no DOM access and no globals. They load in the browser as
`PolarCNC.converter`, `PolarCNC.geometry`, `PolarCNC.parser`, and in Node with `require()`:

```js
const { convert } = require('./src/core/converter.js');
const polar = convert(cartesianGcode, { centerMode: 'auto', xMin: -10, xMax: 125 });
```

The converter no longer reads the page. All settings come in as one `options` object, and
`DEFAULT_OPTIONS` in `converter.js` is the single source of truth for defaults.

Plain `<script>` files are used rather than ES modules on purpose: the tool keeps working when
`index.html` is opened straight from disk, where browsers block ES modules.

## Quick start

1. Open `index.html` in a browser (or use the GitHub Pages link). Keep the folder structure intact —
   the page loads its scripts from `src/` and `css/`.
2. Paste Cartesian G-code (X/Y/Z, G0/G1/G2/G3) into **Step 1**.
3. Click **Convert &amp; Simulate**.
4. Set up your machine once under **Converter Settings → Machine Output Profile** (rotary axis letter, X as
   radius or diameter, directions, X travel, safe retract Z) — or **Load profile** from `profiles/`. Settings
   are remembered by the browser; **Save profile** writes them to a file.
5. Export the Polar G-code (`.nc`) from **Step 2**, or watch it run in the 3D simulator below.

## CAM post-processor settings (what the converter accepts)

The converter reads ordinary 3-axis milling G-code. Use a LinuxCNC (or grbl) post and set it up like this:

| Input | Handling |
|---|---|
| mm (`G21`) or inch (`G20`) | Inch is converted to mm; output is always `G21` |
| Absolute `G90` or incremental `G91` | `G91` is converted to absolute; output is always `G90` |
| Feed `G94` (units/min) | Required — the converter computes `G93` itself. `G93` input is rejected |
| Arcs in the XY plane (`G17`, incremental I/J) | Converted. Arcs in `G18`/`G19` planes are rejected — set the post to output them as lines |
| `G53 G0 Z…`, `G28 G91 Z0`, `G30 G91 Z0` retracts | Replaced by `G53 G0 Z<Safe retract Z>` — see below. Rejected if that setting is empty |
| `G28 G91 X0 Y0` (park) | Skipped — the tool stays where it is |
| `%` delimiters | Kept as the first and last line, as LinuxCNC requires |
| `G54`–`G59` | Passed through. **Your work offset must have X = 0 at the chuck centre** |

**Rejected with a message naming the line** (so nothing is ever converted wrongly):
cutter compensation `G41/G42` (use compensation *in computer*), tapping, threading and boring cycles
`G74/G76/G84/G86–G88` (enable *expand cycles*; drilling cycles are expanded by the converter itself),
offsets set with coordinates `G92/G52/G10`, probing `G31/G38.x`, rotation `G68`, absolute arc centres
`G90.1`, `G53` or `G28` with an X/Y point, a cut before the tool position is known, a cut without a
feed rate, and arcs LinuxCNC itself would refuse (no I/J/R, R too small, R full circle, end radius
too far from the start radius — same tolerances as LinuxCNC 2.9).

A dwell `G4 P` of 60 or more is kept but flagged with a warning: in LinuxCNC P is **seconds**, while
Fanuc-style posts write milliseconds.

**Machine-coordinate retracts are machine-specific.** A mill's post emits `G53 G0 Z0` because on a
mill machine Z0 is the top of Z. On many lathe conversions the Z home switch is at the tailstock end
and machine Z0 is at the **chuck** end (the author's machine too, until its mill-style Z numbering is
installed) — passing `G53 G0 Z0` through would rapid the carriage toward
the chuck. `G28` is no safer: its stored position is machine 0,0,0 unless set with `G28.1`. So the
converter never passes these through. Either set the post's safe-retract method to **clearance
height** (then no machine-coordinate moves appear at all), or enter **Safe retract Z (machine)** —
a machine Z far from the chuck, such as the Z home park position — and every such retract becomes
`G53 G0 Z<that value>`. With the setting empty, such programs are rejected.

After a retract or a tool change the converter treats Z (and, after a park, X/C) as
unknown: the next rapid moves X/C at the current height first, then lowers Z — never inventing a
Z value. **Home the C axis before each program**, since part orientation follows the C position.

## The simulator

The 3D view in **rotary mode** shows what the machine does: the chuck turns, the tool only moves radially
(X, both sides of centre) and in depth (Z). Each block is interpolated in joint space, as a controller does
with plain axes, so the tool follows the real curve, not an idealised one. The machine profile is applied in
reverse, so the view is right whatever axis letters and directions you use. Retracts (`G53`, `G28`) are shown
at a symbolic safe height, because machine coordinates are not known to the simulator.

**Timing is the program's own** (G93 times; rapids at a nominal display speed). Near the centre a real
machine may be slower, because its controller limits the chuck speed. The info line shows the **peak chuck
speed the program asks for** — compare it with what your machine can do. For exact timing, run the program
through your controller's own simulation (see `examples/` for LinuxCNC).

**Material removal.** The stock face is a depth map fixed to the part, so it turns with the chuck and
shows what has been cut so far — lighter to darker with depth. Any cell removed by a **rapid** (`G0`)
is painted red, and the info line warns *RAPID CUTS MATERIAL* with the output line numbers: that is
a collision. Each tool is modelled as a flat end mill of its own diameter.

The depth map is 2.5D (one height per point of the face), which is exact for face machining.

**Before the first real part**, cut something asymmetric (a letter "F", for example). If the C axis
direction or X sign on the machine is the opposite of what the converter assumes, the part comes out
mirrored — and no simulator can show that. If it is, tick **Invert rotary direction** in the profile.
For a full check of the machine's own behaviour, LinuxCNC can simulate the machine itself with a `vismach`
model — `examples/linuxcnc-vismach-xzc-lathe` is a ready example.

## Settings reference

The page shows only what you must set for your machine. Everything else has a safe default.

**Machine**

| Setting | Meaning |
|---|---|
| X Axis Min | Smallest X the machine may go to. **Also the machining side: `0` = one side of the centre only**; a negative value lets the tool cross the centre by up to that many mm, only on cuts that pass exactly through it |
| X Axis Max | Largest X (radius) the machine can reach — its soft limit |
| Safe retract Z | Machine-coordinate Z for `G53`/`G28` retracts; empty = such programs are rejected |
| Tool Diameter | Fallback cutter diameter, used when the program does not state one in its tool comments |

**Machine output profile** — rotary axis letter (C/A/B), X as radius or diameter, invert rotary, invert X,
and **Save / Load profile**.

**Advanced** (closed by default — change only if needed)

| Setting | Meaning |
|---|---|
| Chord Tolerance | Max deviation (mm) of the converted path from the CAM path — smaller = more accurate, bigger files. Default 0.025 |
| Center Zone | Radius (mm) of the zone around the centre that gets special handling. **Empty = automatic** (half the chord tolerance, recommended). A larger value brings back Pocket Fill. A stored value of exactly 2 (the old default) is upgraded to automatic |

**Profile-only options** (no control on the page; set in a profile file, kept when a profile is loaded):
`centerMode` (`auto` / `signed` / `index` / `fill`), `centerStep`, `centerRetract`, `autoStepover`.

## Credit / prior art

This project was inspired by **kadirilkimen**'s PolarBear CNC ecosystem, which first explored Cartesian-to-
Polar G-code postprocessing for this class of machine:

- [Polar-Bear-Cnc-Machine](https://github.com/kadirilkimen/Polar-Bear-Cnc-Machine) — the physical machine concept
- [polarToolsJS](https://github.com/kadirilkimen/polarToolsJS) — web UI g-code converter
- [gCodePolarizerJS](https://github.com/kadirilkimen/gCodePolarizerJS) — core Cartesian→Polar JS library

No code from those repositories is reused verbatim here; this is an independent implementation targeting
LinuxCNC specifically, with its own feed-physics model, center-singularity strategies, and simulator. Full
credit to the original author for pioneering the underlying concept.

### Implementations read in source during validation

Every one of these was read directly, not cited second-hand. None is reused verbatim.

| Project | File | What it validated / contributed |
|---|---|---|
| **LinuxCNC** | `src/emc/kinematics/rosekins.c` | The only stock polar kinematics in LinuxCNC (radius/Z/cumulative-theta). Confirms the core transform; has no centre handling, no C velocity limit, and is `KINS_NOT_SWITCHABLE` |
| **LinuxCNC** | `interp_find.cc`, `interp_inverse.cc`, `tc.c`, `emccanon.cc` | Established that G94 ignores rotary distance, that G93 carries time directly, and that `getStraightVelocity()` reduces linear velocity until the C axis can keep up (NIST IR6556 §2.1.2.5(A)) |
| **Klipper** | `klippy/kinematics/polar.py` | `check_move()` limits speed near the pole using the **perpendicular distance from the origin to the segment**, not the endpoint radius — the same quantity Fanuc calls `L` |
| **Marlin** | `src/module/polar.cpp` | Same >180° delta unwrap. `POLAR_CENTER_OFFSET` avoids the singularity *mechanically* by mounting the tool off-centre |
| **RepRapFirmware** | `src/Movement/Kinematics/PolarKinematics.cpp` | `LimitSpeedAndAcceleration()` is the same guarantee that LinuxCNC's own axis limits give this converter's output (the converter's former `T_crot` was removed in favour of the controller's limits). Also has `minRadius`/`maxRadius` and a continuous-rotation shortcut |
| **grblHAL** | `kinematics/polar.c` | Identical unwrap; feed corrected by the ratio of polar to Cartesian distance, clamped at 0.5× |
| **Grbl_Esp32** | `Custom/polar_coaster.cpp` | The original that grblHAL's version was lifted from — nothing additional |
| **FreeCAD CAM** | `Path/Base/Generator/rotary_spiral.py`, `rotary_wrap.py` | `_FeedClamp` inspired the original feed-clamp diagnostics (since replaced by the simulator's peak chuck speed). `apply_wrap_strategy()` supplied the UNWOUND / MODULO / REZERO vocabulary for the C-unwind problem |
| **dune-weaver** | `modules/core/pattern_manager.py` | Polar sand table. Its cross-coupling compensation is specific to tables where the radial carriage rides the rotating arm — not applicable to a lathe |

### Vendor documentation consulted

Fanuc **G12.1/G112** (the `F < L × R × π/180` formula, where `L` is the radius at closest approach, plus the
PS214 illegal-code list and the `G00` prohibition), Haas **G112**, Siemens SINUMERIK **TRANSMIT** (the three
`POLE_SIDE_FIX` strategies), Heidenhain **FUNCTION POLARKIN**, and SprutCAM's polar transformation mode.

The search for further prior art was carried out in English, Chinese, Russian and Japanese, across GitHub,
Gitee, vendor documentation and the LinuxCNC source, docs and forums. It is considered exhausted.

## License

Copyright (c) 2026 **Marioskiv** — <https://github.com/Marioskiv/polar-cnc-converter>

Released under the MIT License — see [`LICENSE`](./LICENSE). You are free to use, modify and redistribute
this code, including in other CAM software. The license requires that the copyright notice above and the
license text are kept in all copies or substantial portions. Every source file carries this notice in its
header; please leave it in place, and a link back to this repository is appreciated.