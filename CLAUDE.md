# CLAUDE.md — read this first

Owner: Marios (GitHub: Marioskiv). He writes in Greeklish; **always answer in proper Greek script**, simple,
honest and direct. Never claim something you have not checked (he has caught wrong claims before).

## Before doing anything
1. Read `docs/notes/memory.md` — rules, decisions, workflow, how to test.
2. Read `docs/notes/pending.md` — open items and questions waiting for Marios.
3. For the FreeCAD addon read `docs/FREECAD.md`; for the converter `docs/TECHNICAL.md`.

## Rules for this repo
- Scope: ONLY the polar converter (web) and its FreeCAD addon (`freecad/`). His other projects
  (`freecad-wikitips`, `linuxcnc-calibrations`) have their own repos: never mix files or notes.
- Do not touch the web converter (`src/`, `lib/`, `css/`, `index.html` logic) unless he asks for it.
- Work on a branch, open a PR, merge into `main` only after the tests pass. Never push to `main` directly.
- No pip dependencies in the addon; the addon must never break FreeCAD.
- At the end of every session update `docs/notes/memory.md` (decisions) and `docs/notes/pending.md` (open items).
