# Work log — newest first

One entry per working session: what was asked, what was done, what is left, what Marios decided.
Short and factual. Current state lives in `STATUS.md`, permanent decisions in `DECISIONS.md`.

---

## 2026-10-07 (late night, 6) — 2.7.0: layout XZC + tilt (ball-end lean)

**Marios said:** the router may not reach 90° (X travel) and big parts cannot be machined on the periphery — then chose
option 2: tilt that changes while cutting, ball-end, automatic, as far as it fits.

**Done (2.7.0):** layout selector XZC / XZC + tilt (page, profiles, `normalizeOptions`). `layout-xzcb.js` on top of the
XZC layout: K = pivot→ball centre per tool (pivot setting + `tool.tbl` length − ball radius); X = r + K sin B,
Z = z + K (cos B − 1), C unchanged; lean auto-limited by X and B travel; blocks split so the tilt error ≤ 0.08·tol;
upright at tool change / after machine retract / end; flat tools upright; missing pivot/travel/length refused.
**Found while building: G43 stays valid** (research note §3 corrected). Simulator: B read, tool tip recovered, tilted
tool drawn, Tilt telemetry. Tests: `tilt.test.js` 150 checks (ball centre worst 0.0229 mm), lint on tilted outputs,
golden 144/144 unchanged, sweeps, Chromium check with screenshots.

**Open:** B direction on the real machine needs a test cut; tilt following the shape needs CAM orientation (Kiri);
fixed B for non-ball tools; periphery input. Machine not built: nothing for the `.ini`/`.hal`.

---

## 2026-10-07 (late night, 5) — which CAM: not Fusion; FreeCAD checked

**Marios said:** most likely **not Fusion** for the tilted work (no subscription) — maybe Kiri:Moto or FreeCAD;
Fusion perhaps for plain XYZ. If merged into Kiri one day, it should feel like a **professional program**.

**Done:** FreeCAD CAM source read (`e326ee2`, dev 2026-10-07) → `references/freecad-cam.md`: indexed tilt per
operation and a machine kinematic model, continuous 4th-axis RotarySurface (tool radial), **no simultaneous
tilt**. Neither Kiri nor FreeCAD gives a tool orientation that changes while cutting.

**Proposed:** XZC + B layout in stages — B fixed per program for face work; periphery at B 90 from 4th-axis
programs (FreeCAD RotarySurface, Kiri lathe); simultaneous tilt for ball-end tools computed by the converter;
full tilt operations later inside Kiri. Waiting for his go-ahead.

---

## 2026-10-07 (late night, 4) — step 2 done: converter in three stages (2.6.0)

**Asked:** go-ahead ("NAI") for step 2, the restructure.

**Done:** `src/core/converter.js` (one 1,600-line function) split into `gcode-input.js` (reads/checks the CAM
program, emits events in order: text / flush / move / tool / programEnd), `layout-xzc.js` (the polar transform,
unchanged code) and `converter.js` (options, header, end, clean-up). Done by a script that cut the old code line
by line with anchor checks — moved, not rewritten. Verified: npm test (golden 144/144), sweeps 0.0225 mm,
Chromium offline, release zip, and 13,671 old-vs-new comparisons (all golden programs + 1,500 random programs ×
9 option sets): 0 differences, identical errors. `index.html` loads the two new files.

**Next (needs Marios):** the selector "XZC / XZC + B" (a `layout-xzcb.js` next to `layout-xzc.js`), which CAM
gives the tool orientation; or first the Kiri:Moto `gcodeProc` proof.

---

## 2026-10-07 (late night, 3) — goal: converter merged into Kiri:Moto

**Marios said:** later the converter must be adapted to Kiri:Moto; if its author allows, merge them into a CAM
for polar (and multi-axis) machining where everything is computed inside the CAM, like a professional CAM:
choose the machine layout, set all parameters in the CAM, do all operations there.

**Claude's answer:** agreed, it is the right direction (already in `references/kirimoto.md` §6/§10). Kiri is public
and MIT (headers say "All Rights Reserved" → ask Stewart); merging into his main code needs his agreement, a
fork is legal but costly to maintain. Phases: gcodeProc proof → converter as a clean machine-layout library
(= step 2, serves both) → Kiri device option "machine layout" + export/preview/animation → tilt ops in Kiri
(needs tool orientation per point there; biggest part). Recommended to start step 2 now; asked for go-ahead.

---

## 2026-10-07 (late night, 2) — tilt direction confirmed: like Bird's printer → B

**Marios said:** "it will rotate the way Bird's 3D printer rotates, something like that." → radial plane, **B**
(DECISIONS.md). Proposed next steps and asked for go-ahead + which CAM will provide tool orientations.

---

## 2026-10-07 (late night) — Marios's answers on the tilt axis

**Marios said:** (1) the tilt must **change while cutting** (simultaneous), not fixed 0/90 positions;
(2) on tool lengths in a settings list + cancelling G43: "I don't know which is more correct — what do you
believe?"; (3) "the router will turn *kata ton axona X*, i.e. while it does face machining, when asked to tilt,
to make **propellers** and difficult spots".

**Open — must be clarified before any code:** "kata ton axona X" is ambiguous: *about* X (tool leans sideways,
tangential = **A**) or *along/toward* X (tool leans toward/away from the centre, radial plane = **B**, as in
Bird's printer and as assumed so far). It matters: B reaches the periphery (B 90 points at the chuck axis) and
keeps the pole logic; A leans into the gaps between propeller blades but leaves an unreachable disk of radius
L·|sin a| around the centre and cannot point radially at the periphery (except at X = 0). Asked him to describe
which way the tool tip moves. Also open: which CAM will produce simultaneous tool orientations (Fusion
multi-axis may need a paid extension — not verified).

**Claude's recommendation given:** the converter must know each tool's length when tilting (trivkins `G43` adds
it to Z only); best source = LinuxCNC's own `tool.tbl` (same numbers the machine uses) + one measured pivot
length; `G43` then not used in tilted output. Not implemented — waiting for his OK.

---

## 2026-10-07 (night) — tilt axis: letter B, research, selector design proposed

**Asked:** the 4th axis is not ready (router fixed for now) → no `.ini`/`.hal` changes, converter only; make sure
which letter LinuxCNC needs (A or B); a selector "XZC or XZC + A/B" must go in; search the web, GitHub and
LinuxCNC for such layouts.

**Done:** LinuxCNC source/docs (master `46a388f`) and web searched; notes in `references/tilt-axis-research.md`.
Result: **B** (A about X, B about Y, C about Z — LinuxCNC docs, ISO 841; LinuxCNC's own tilting-head kins and
industry B-axis mill-turns use B). With trivkins the letter has no geometry (A would run too); direction must be
an invert option + test cut. Big consequence: at B = 90 `G43` adds tool length to the wrong axis → the converter
needs per-tool lengths in the tilted layout. Face = polar interpolation (today); periphery = cylindrical
interpolation (G7.1 style): inputs either a mill 4th-axis XYZA program (Fusion rotary, Kiri lathe op) or an
unrolled 2-D program + radius. Forums of LinuxCNC/Autodesk are blocked in this sandbox (titles only).

**Not done — waiting for Marios** (proposal in the chat): first version indexed only (B fixed per section: 0 face,
90 periphery) or simultaneous; which periphery input first (XYZA program or unrolled 2-D); tool lengths from a
list in the settings + `G49` in periphery sections. No converter code written for the selector yet (rule 1).

---

## 2026-10-07 (evening) — converter 2.5.0, Bird repos in detail

**Asked:** (1) "it should behave like a Fusion 360 CAM for polar / multi-axis machines — a universal CAM for all
machine types"; (2) fix the remaining review findings, especially the cutter diameter not being read; (3) he will
often ask about Kiri:Moto; (4) he plans a 4th axis: the router, on X and Z, will **tilt about 90°** to machine
the periphery of the part, like Bird's printer — read `Core-R-Theta-4-Axis-Printer` and `S4_Slicer` in detail,
because the converter must support it with a **layout selector**; say if they must be downloaded.

**Done — converter 2.5.0** (all tests, sweeps 0.0225 mm, release zip, Chromium offline check):
- G93 floor 0.06 s → 0.6 ms: real feed now = CAM feed on short blocks (F1500: 844 → ~1443 measured).
  Golden 68 changed — only F of blocks at the old F1000 floor (script-checked line by line).
- Kiri:Moto tool list `; tool#=N flute=D … unit=` read (imperial → mm); single listed tool used without M6.
- Radial lines in 5 mm pieces (was ~1.4 mm). Golden 29 changed — fewer blocks, same rapids, same deviation.
- `G53 G0 X Y` park skipped like `G28` park; exponent numbers refused.
- three.js r134 in `lib/three/` (MIT, from the npm package — cdn.jsdelivr.net is blocked in this sandbox).

**Done — Bird repos:** cloned here (Marios does not need to download anything); firmware read completely, S4
notebook read completely. Notes rewritten: `references/bird-4axis.md` (pipeline, kinematics, what carries over to
milling and what not, consequences for his machine). Key points: same layout as his plan (B in the radial plane);
RRF 4-axis mode = offline transform + G93 like ours; S4's optimiser is for printing overhangs, not milling;
**adding the axis moves C to joint 3**; a mill 4th-axis program (Kiri's lathe op, Fusion rotary) maps directly
to "router at 90°".

**Waiting for Marios:** indexed or simultaneous tilt; axis letter, travel, motor/drive/reduction, homing, BOB
output, pivot-to-tip L per tool, pivot offset, router clearance at 90° (rule 4: not assumed).

---

## 2026-10-07 (later) — references folder, full Kiri:Moto CAM read

**Asked:** set up a place to remember other people's code (one notes file per project); check Kiri:Moto in
full, because Marios may one day offer the converter to its author so Kiri becomes a CAM for complex machines
"like mine XZC, XZCYA, ZCZA and the others" (his words; those layouts still need to be defined with him).
Next he will give another project's code to check and say what he wants done with it.

**Done:**
- `docs/handoff/references/` with an index (`README.md`, incl. how to add a project). Old
  `reference-kirimoto-bird-4axis.md` split into `references/kirimoto.md` and `references/bird-4axis.md`.
  CLAUDE.md rule 10 points to the index.
- Kiri:Moto `d138275` (4.7.0, no newer commit) re-read: the whole CAM output path (slice → prepare → export),
  the rotary ops, engine/CLI, export dialog, mods, docs. Notes in `references/kirimoto.md`.
- **Key finding:** Kiri already has a post-processor hook — device JSON `gcodeProc` names a page function that
  receives the whole G-code. Our converter can plug in **without changing Kiri** (UI export only, not the
  headless engine). Other findings: no G93 anywhere; CLI broken (30/59 files missing); a docs/code directive
  name mismatch; a dwell time-estimate bug; our converter does not read Kiri's `; tool#=` comments yet.
- Corrected two wrong points of the first notes (lerp points are not exported; AXISMAP exists).

**Not done / next:** proof of concept (self-hosted Kiri + `gcodeProc` + our converter) only with Marios's
go-ahead; reading Kiri's tool comments is a converter change (his OK first).

---

## 2026-10-07 — full code review, converter 2.4.1

**Asked:** read the whole repo, check the code, list the open items; then "fix what you believe is
wrong" and keep notes from now on.

**Checked:** `npm test` all green; `node tools/sweeps.js` worst G1 0.0225 mm (limit 0.026), 0 over.
Read every file in `src/`, `index.html`, profiles, README, CHANGELOG, `docs/handoff/machine-config/*`.
No open issues or PRs on GitHub. v2.4.0 is already on GitHub (PR #1 merged).

**Fixed (2.4.1), verified against the LinuxCNC 2.9 source (`interp_arc.cc`, `interp_internal.hh`):**
- R-format half circle with rounded end points became a straight line (10 mm off on R10) → half circle.
- I/J arc with slightly different end radius ended beside its end point → spiral to the exact end point.
- Arcs LinuxCNC refuses are refused with the line number (no I/J/R, R too small, R full circle, zero
  radius, end radius too far off). Before, some became straight lines.
- Missing F: was silently 500 mm/min → rejected with the line number (as LinuxCNC).
- `G4 P` >= 60 gets a warning comment (seconds vs milliseconds).
- Docs: README test table, cycles text, chuck-end note, `T_crot`; `index.html` SPDX header and old
  "C velocity limiting" text; `isNode ? factory() : factory()` in geometry/parser.
- Golden 144/144 unchanged. New checks in `tests/input.test.js` (49 checks).

**Not changed — waiting for Marios's decision:**
1. Feed floor: `MIN_TIME = 0.001 min` per G1 block (0.06 s) silently lowers the cutting feed on short
   blocks. Measured on a circle r20: F1000 → ~767, F1500 → ~844, F3000 → ~856 mm/min real. Options:
   lower the floor, or keep it and show a warning with the real feed. (Converter change → his choice.)
2. `G53 G0 X.. Y..` park is rejected while `G28 G91 X0 Y0` park is skipped. Skip it too?
3. Pure radial lines (C constant) are cut into many blocks without need. Optimisation, changes output.
4. Three.js is loaded from a CDN: the simulator does not open without internet. Ship a local copy
   (three.js is MIT)?
5. Exponent numbers (`F1e3`) are accepted by the parser and leave a stray `e3` line. No CAM writes them.

**Machine files — NOT edited** (the copies in `machine-config/` may differ from the real ones; fix on
the real files, rule 3):
- `.ini` header still says "CALIBRATION STILL TO DO: HOME_OFFSET = 135" — stale, it is -20 now.
- `.hal` Z comment says the switch is "coordinate 600" — with the new `.ini` it is 10.
- `axis_user.py` has no copyright/licence header.

**Safety items found (added to STATUS.md):** no hardware E-stop (only the gamepad Options button;
`estop-ext` reads the raw pin, not fail-safe); input P11 (`gpio.014`, Z zeroing sensor) not responding.
