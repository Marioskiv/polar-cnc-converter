# Work log — newest first

One entry per working session: what was asked, what was done, what is left, what Marios decided.
Short and factual. Current state lives in `STATUS.md`, permanent decisions in `DECISIONS.md`.

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
