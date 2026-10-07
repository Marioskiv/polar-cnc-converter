# Work log — newest first

One entry per working session: what was asked, what was done, what is left, what Marios decided.
Short and factual. Current state lives in `STATUS.md`, permanent decisions in `DECISIONS.md`.

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
