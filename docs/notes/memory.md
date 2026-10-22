# Memory — durable facts for the next session

Update this file when a decision changes. Open work lives in `pending.md`.

## Marios and how we work
- **RULE (Marios, 2026-10-20): NO change without asking him first.** Code, tests, settings, versions: propose,
  explain, wait for a clear "ναι". Research and checks are fine; only these notes may be updated without asking
  (he asked for that). A conditional "if it's fine, do it" is NOT a yes.
- Answer in Greek script. He is a machinist, not a programmer: explain *why*, in plain words.
- Never claim without checking (2026-10-19: I wrongly said FreeCAD's Face has no Spiral; it has. He said he
  will cancel the subscription if such mistakes continue). Research first, test in a real FreeCAD.
- Standing permission: branch → PR → merge into `main` after the tests pass. Never push to `main` directly.
- Do NOT change the web converter unless he asks (2026-10-19: "only addon changes, not the web converter").

## His machine
- Holzmann lathe converted to XZC face milling, LinuxCNC 2.9.10, trivkins XZC. Its real `.ini` is in his private
  repo `cnc-manuals`; calibration notes in `linuxcnc-calibrations` (do not copy either here).
- `examples/linuxcnc-vismach-xzc-lathe/polarlathe-sim.ini` is only a simulation copy of its motion settings
  (X synced 2026-10-19: HOME_OFFSET -24.039, limits -22.039 … 108.961).
- Homed like a mill since 2026-10-04: Z switch at the tailstock end, machine Z0 = the park there (Home All leaves Z
  at 0); machine X0 = the chuck centre. Comments saying "machine Z0 at the chuck end" were outdated and are fixed.
- Cutters changed by hand; all tool lengths in the LinuxCNC tool table; router switched by hand (LinuxCNC later).

## Decisions (newest first)
- 2026-10-20 (2.24.0, Marios: "fix them all, serious work, keep notes, find more check tools"): full review
  (two independent read-throughs, every test, sweeps, LinuxCNC 2.9.10 `rs274` with his machine .ini, ruff,
  eslint). Fixed: no-diameter cutter refused with a chuck; Split Output refuses all files if one is refused (one
  card), simulator plays the files one after another; setup note "touch off Z on the stock TOP with the value
  Z …"; editor edits re-checked (park lines G53 left out of the check, as on first write); Y check in the post;
  drill cycles in Cartesian checks; obstacle cache key; Wrap layout C = -Y/R0 (was mirrored; `program.unroll`
  writes Y = -angle·R0 so Polar Wrap output is unchanged); first rapid and after M6 split in Wrap; Polar Wrap
  points ≤ 1 map cell apart (flat cutter gouged 0.78 mm at a key edge); own `polarwrap_gui.create` (was close
  to FreeCAD's LGPL Create). XZC output unchanged (golden 144/144). Made in parallel with 2.22.0/2.23.0 of
  another chat, merged on top of them.
- 2026-10-20 workflow: Marios said (2026-10-16, in another chat) "no more PRs, the chat's PR button is stuck".
  This repo's CLAUDE.md says branch → PR → merge after tests. Both kept: Claude opens the PR AND merges it
  itself once every test (npm + FreeCAD) passes, so Marios has no button to press.
- 2026-10-16: his machine's X centre was MEASURED (router tip on the chuck axis at X 4.039 with the old
  HOME_OFFSET -20): real .ini HOME_OFFSET -24.039, X limits -22.039 / 108.961 (same physical places), X Axis
  Max on the page 108.9.
- 2026-10-20 (2.23.0) **repositories reorganised** (Marios: "everything polar in one repo, WikiTips separate"):
  this repo = web converter + simulator + Polar CNC (polar, Polar Wrap) + **Knurling & Wrap** (`cad/`, Part
  Design only, separate part, no WikiTips inside, MIT — his yes). WikiTips = only help + error explanations.
  He also wants: this repo renamed (his words "XCZ converter polar, warp"; exact GitHub name to confirm; only
  he can rename it in GitHub Settings), a SEPARATE repo for the cutter libraries, and from now on the chat in
  which this was decided is for WikiTips only.
- 2026-10-22 (2.26.0, Marios: separate repo, name `freecad-addons`): Knurling & Wrap (with the new Hole on any
  surface, 2.25.0) moved to `Marioskiv/Knurling-Wrap` 1.0.0 (created as `freecad-addons`, renamed by Marios the same day) (folder `KnurlWrap/`, its tests and notes
  `docs/notes/knurlwrap.md` there). Removed from here: `cad/`, its 4 tests, the WikiTips fixture, the second
  `<workbench>` in `package.xml`.
- 2026-10-20 (2.22.0, his yes to A/B/C/D): park before every M6 (polar `G53 G0 Z0` then `G53 G0 X0`; Wrap
  `G0 X<X max>` then `G53 G0 Z0`; C stays; Job property *Polar Tool Change Park*, on by default); Post Process
  refuses a Tool Controller without spindle speed; M5 added before the end when left on; outdated comments fixed
  ("no comments that do not match the repo"), sim .ini X synced.
- 2026-10-20 research (no change made): **FreeCAD 26.3 Rotary Surface cannot replace Polar Wrap** for his XZC
  machine. Checked in its source (`Mod/CAM/Path/Op/RotarySurface.py`, `Base/Generator/rotary_*.py`):
  the rotary axis must lie along world X or Y ("Rotary axis along world Z is not supported in v1"), it writes
  X(along the part) Y0 Z(radius) + A, the FreeCAD posts have no X<->Z swap, and it writes G94 feeds: LinuxCNC
  then applies F to the small XYZ part of a move only (docs machining-center.adoc "Feed Rate"), so C would
  spin far too fast. Polar Wrap writes G93 through the converter and checks the chuck. Possible later (ask him
  first): a post that remaps Rotary Surface output (X->Z, Z->X, A->C, G93).
- 2026-10-20 research (no change made): **tool change.** The converter keeps `M5 / M6 Tn / G43 Hn / M3 S`
  in order and adds no move. LinuxCNC M6 (interp_convert.cc `convert_tool_change`) stops the spindle, moves
  nothing unless `[EMCIO] TOOL_CHANGE_QUILL_UP` (G53 Z0) or `TOOL_CHANGE_AT_G30` (G30 point, which also
  moves C: would unwind) is set, waits for the manual tool-change dialog, then the program goes on by itself.
  G43 applies the tool table offsets of all axes (parameters 5081-5089), so with each tool's length in the
  table (Face: Z column; Wrap: X column) no re-zeroing at a tool change. In the Wrap test program the M6 comes
  with the router only SafeDistance (5 mm) above the bar: no retract to a change position (open item).
- 2026-10-20: **C wind-up → Marios raises the C soft limit** in his LinuxCNC .ini to a very large number, the
  same in `[AXIS_C]` and `[JOINT_2]` (e.g. ±9999999; per the LinuxCNC 2.9 ini docs, leaving MIN/MAX_LIMIT out
  of a rotary axis gives ±1e99). **No code change for it** (a draft that turned Wrap helices back was discarded
  at his request). Checked: positions are doubles; Mesa hm2 stepgen keeps 64-bit subcounts (only the
  `stepgen.N.counts` pin is s32). Advice given: Home C (homes in place) before the next program, or it unwinds
  all the turns; never use WRAPPED_ROTARY (our C is cumulative). Lesson: "kane to" on a conditional idea is
  NOT permission to start; wait for an explicit yes.
- 2026-10-20: this folder (`docs/notes/`) is the memory of the repo; `CLAUDE.md` at the root points here.
- 2026-10-20 (2.21.0): Polar Wrap can follow another Wrap operation (After operation) and reports which
  ball end reaches every hollow. Cross-checked against OpenCAMLib (FreeCAD's own rotary drop-cutter).
- 2026-10-19 (2.20.0): Polar Face (automatic operation) REMOVED. In a polar Job he uses FreeCAD's own
  operations (Face, Pocket, Profile, Drilling…). Nothing is greyed out. Each operation is checked when it is
  made: warnings only (e.g. zigzag not recommended, slower by %, leaves material), and a crash (chuck, Y in the
  output, not convertible) opens a "ΘΑ ΤΡΑΚΑΡΕΙ" card and Post Process refuses the program.
  Warnings appear only in polar Jobs, never in ordinary XYZ Jobs. Keep the GIFs and the help.
- Language switch Greek/English: the "?" button at the end of the PolarCNC toolbar.
- Two addons: PolarCNC (this repo, `freecad/`) and WikiTips (repo `freecad-wikitips`).
- 2026-09-11: the converter keeps C cumulative (UNWOUND). No MODULO, no G92 resets
  (see the comment in `src/core/layout-xzc.js`).

## How to test
- Converter: `npm install` once, then `npm test`.
- Also used 2026-10-20: `node tools/sweeps.js` (about a minute); `tools/linuxcnc-compare.js --rs274 <rs274>` with
  LinuxCNC 2.9.10's interpreter built from source (`git clone -b v2.9.10 --depth 1` LinuxCNC; configure needs
  python3.12 first in PATH for tkinter); `ruff check --select F,E9,B` on `freecad/`; `eslint` (no-undef,
  no-redeclare, no-unreachable…) on `src/core`. A FreeCAD 26.3 build was found at `/tmp/claude-0/fcbin/env/bin/freecad`
  in this container (GitHub release downloads are blocked here).
- Addon in a real FreeCAD 26.3 (AppImage extracted, run under xvfb):
  `FREECAD=<path>/bin/freecad OUT=<dir> sh tests/freecad/run.sh` — every test must say PASS; look at the PNGs.
- Pitfalls: with several tool controllers FreeCAD opens a dialog (tests monkeypatch
  `PathUtils.findToolController`); open logs with `encoding="utf-8"`; never `pkill -f` a pattern that is in
  your own command line.
