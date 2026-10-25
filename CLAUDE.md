# CLAUDE.md

Instructions for AI coding assistants working on this repository.

- The owner's working notes, rules and open items are kept privately (repository `Marioskiv/cnc-manuals`,
  folder `polar-cnc-converter/docs/repo-notes/`). Read them first when you have access; otherwise ask the owner.
- Ask the owner before changing code, tests, settings or versions.
- Work on a branch and open a pull request; merge only after `npm test`, `node tools/sweeps.js` and, for the
  FreeCAD addon, `tests/freecad/run.sh` in a real FreeCAD pass.
- Every source file carries `Copyright (c) 2026 Marioskiv`, the repository URL and `SPDX-License-Identifier: MIT`.
  Never copy code from GPL projects.
- The FreeCAD addon must never break FreeCAD and has no pip dependencies.
- Keep notes in the private repository, not here.
