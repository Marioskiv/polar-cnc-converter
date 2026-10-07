# Polar CNC converter — instructions for Claude Code

Owner: Marios (GitHub: Marioskiv). Browser tool + Node tests that convert Cartesian XYZ G-code (from any CAM) to
polar XZC G-code for a lathe converted into a face-milling machine, running LinuxCNC 2.9 (trivkins, G93).
Read `docs/handoff/STATUS.md` first (what is installed on the real machine and what is still open), then
`docs/handoff/DECISIONS.md` (what was decided and what must NOT be re-proposed).

@docs/handoff/STATUS.md
@docs/handoff/DECISIONS.md

## Rules from Marios — non-negotiable
1. **Never change a file without his explicit permission.** Propose first, show the diff, wait for a clear yes.
2. **Order of work:** first the machine config (`.ini`, `.hal`), only when that is finished the converter.
3. **Base every `.ini`/`.hal` change on the real files on the machine** (`~/linuxcnc/configs/holzmann_cnc_mesa_7i92`
   on the LinuxCNC computer; copies of the last delivered versions are in `docs/handoff/machine-config/`, and they
   may be behind or ahead of the real ones). Give the full updated block, with a comment for every change.
4. **Do not assume pinouts or hardware parameters.** If something critical is missing, ask.
5. Check pin names, scaling (steps/mm, steps/deg) and G93 inverse-time / feed-rate settings on every change.
6. **Never write a comment after a value on the same line in an `.ini`** (LinuxCNC makes it part of the value).
7. **Never start LinuxCNC or run anything that could move the machine.** Edit and check files only.
8. **Answer Marios in proper Greek script** (he types Greeklish; reply in Greek, not Greeklish). Be direct and honest;
   do not tell him what he wants to hear. He prefers ready-made / configuration solutions over writing code from scratch.
9. Keep it **easy but correct**: the converter must stay universal (any machine / controller), with few settings.
10. **Keep notes (asked by Marios 2026-10-07).** At the start read the latest entry of `docs/handoff/LOG.md`.
    During/at the end of every session add an entry at the top of `LOG.md` (asked / done / not done /
    decided) and keep `STATUS.md` (current state) and `DECISIONS.md` (decisions, rejected ideas) up to date.
    Other people's code that was studied: `docs/handoff/references/README.md` (one notes file per project, with
    URL + commit, licence, method in our own words). Never copy their code into this repo.

## Safety facts that cost real mistakes before
- G-code `G53 G0 Z0` goes to machine Z0. Which end of the lathe that is depends on the INSTALLED `.ini`
  (see STATUS.md). The converter replaces G53/G28 retracts with "Safe retract Z" and rejects them if it is empty.
- In LinuxCNC `G4 P` is **seconds** (a benchmark with `G04 P2000` would wait 33 minutes).
- A mirrored part passes every software check (the validator uses the same convention as the converter). Only a
  physical asymmetric test cut ("F") proves C direction and X sign.
- LinuxCNC makes `G0` follow a straight line in JOINT space, which is a spiral in polar. The converter therefore
  segments rapids too. Never emit a long G0 with X and C both changing.

## Code layout
- `src/core/converter.js` — `convert(text, options)`, a pure function (no DOM). Since 2.6.0 three stages:
  `gcode-input.js` (reads/checks the CAM program, emits events in order) → `layout-xzc.js` (machine layout: polar
  transform, G93) → output in `converter.js`. New machine layouts go next to `layout-xzc.js`. `geometry.js`, `material.js`,
  `polar-parser.js` next to it. `src/sim/simulator.js`, `src/ui/*` (page), `index.html`, `css/`.
- `profiles/` — machine output profiles (JSON). `examples/linuxcnc-vismach-xzc-lathe/` — LinuxCNC simulation config.
- `tests/` — `npm test` (= `node tests/run-all.js`; needs `npm install` once for jsdom). `tests/lib/replay.js` replays
  the output in joint space and measures deviation from the intended path (understands I/J and R arcs).
- `tools/sweeps.js` — heavy randomized validation (about a minute). Run it after ANY change to the converter.

## Definition of done for a converter change
1. `npm test` passes. A changed `golden` baseline must be explained line by line (comment-only? within tolerance?
   explicit user option?) before `node tests/golden.test.js --update`.
2. `node tools/sweeps.js` — worst G1 deviation stays <= 0.026 mm.
3. Every output line passes `tests/lint.test.js` (no nested comments, one motion code per line, F on every G93 move).
4. README + CHANGELOG + `package.json` version updated; every new source file carries the header
   `Copyright (c) 2026 Marioskiv`, the repo URL and `SPDX-License-Identifier: MIT`.
5. Test the extracted release zip, not only the working copy.

## Licences
- This repo is MIT. Do **not** copy code from GPL projects (Joshua Bird's slicers/printer: GPL-3 plus a no-sell
  clause). Learn the method, write our own. Kiri:Moto is MIT but its file headers say "All Rights Reserved".
