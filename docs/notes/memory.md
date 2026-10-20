# Memory — durable facts for the next session

Update this file when a decision changes. Open work lives in `pending.md`.

## Marios and how we work
- Answer in Greek script. He is a machinist, not a programmer: explain *why*, in plain words.
- Never claim without checking (2026-10-19: I wrongly said FreeCAD's Face has no Spiral; it has. He said he
  will cancel the subscription if such mistakes continue). Research first, test in a real FreeCAD.
- Standing permission: branch → PR → merge into `main` after the tests pass. Never push to `main` directly.
- Do NOT change the web converter unless he asks (2026-10-19: "only addon changes, not the web converter").

## His machine
- Holzmann lathe converted to XZC face milling, LinuxCNC 2.9.10, trivkins XZC. Its real configuration and
  calibration notes are in the separate repo `linuxcnc-calibrations` (do not copy them here).
- `examples/linuxcnc-vismach-xzc-lathe/polarlathe-sim.ini` is a simulation copy of its motion settings.

## Decisions (newest first)
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
- Addon in a real FreeCAD 26.3 (AppImage extracted, run under xvfb):
  `FREECAD=<path>/bin/freecad OUT=<dir> sh tests/freecad/run.sh` — every test must say PASS; look at the PNGs.
- Pitfalls: with several tool controllers FreeCAD opens a dialog (tests monkeypatch
  `PathUtils.findToolController`); open logs with `encoding="utf-8"`; never `pkill -f` a pattern that is in
  your own command line.
