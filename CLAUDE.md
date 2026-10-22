# CLAUDE.md — read this first

Owner: Marios (GitHub: Marioskiv). He writes in Greeklish; **always answer in proper Greek script**, simple,
honest and direct. Never claim something you have not checked (he has caught wrong claims before).
**No change without asking him first** (code, tests, settings, versions): propose, wait for a clear "ναι".

## Before doing anything
1. Read `docs/notes/memory.md` — rules, decisions, workflow, how to test.
2. Read `docs/notes/pending.md` — open items and questions waiting for Marios.
3. For the FreeCAD addon read `docs/FREECAD.md`; for the converter `docs/TECHNICAL.md`.

## What lives where (decided by Marios, 2026-10-20)
| Repository | What it holds |
|---|---|
| **this repo** (`polar-cnc-converter`, to be renamed) | everything for the XZC machine: the web converter + simulator (`src/`, `lib/`, `css/`, `index.html`), the FreeCAD addon Polar CNC (`freecad/`: polar, Polar Wrap, chuck, simulator, post) |
| `freecad-addons` (since 2026-10-22) | the Part Design tools **Knurling & Wrap** (Knurl, Wrap on a cylinder, Hole on any surface); were `cad/` here until 2.25.0 |
| `freecad-wikitips` | ONLY WikiTips: hover help for FreeCAD's commands and the Greek error explanations. No tools. |
| `linuxcnc-calibrations` (private) | calibration tools and notes of the machine |
| `cnc-manuals` (private) | the machine's real `.ini` / `.hal` and manuals |
| (to make) a tool-library repo | the cutter libraries (YG-1, IZAR, Amana, Stepcraft) — Marios asked for it 2026-10-20 |

Never mix files or notes between them. `examples/linuxcnc-vismach-xzc-lathe` here is only the simulation copy.

## Rules for this repo
- Do not touch the web converter (`src/`, `lib/`, `css/`, `index.html` logic) unless he asks for it.
- Work on a branch, open a PR, merge into `main` only after the tests pass (`npm test` and
  `tests/freecad/run.sh` in a real FreeCAD). Never push to `main` directly.
- No pip dependencies in the addon; the addon must never break FreeCAD.
- At the end of every session update `docs/notes/memory.md` (decisions) and `docs/notes/pending.md` (open items).
